# Product Requirements Document — cre-deal-agent

See `ROADMAP.md` for per-person build plans. See `AGENTS.md` for branch naming and PR rules.

---

## §1 Mission

Help a CRE data analyst monitor an active deal and surface, in minutes, the signals that change what they do next.

**Success — the 3-minute test:**
- Opens the agent, sees posture and recommendation in seconds
- Reads the signal breakdown with source for each data point
- Reads `next_move` and knows exactly what to do this week
- Trusts it enough to escalate to the deal team — or kills it cleanly

---

## §2 Target user

A data analyst working an active commercial real estate deal. They have deal context in their head — asset type, location, anchor tenant, lender — and need a fast read on whether market conditions have shifted since the last team meeting.

---

## §3 Demo scenario

**Do not change this scenario. All testing and demo prep runs against these inputs.**

| Field | Value |
|---|---|
| Asset type | Industrial, 412k sqft |
| Submarket | Phoenix-Mesa-Chandler |
| Anchor tenant | Amazon · 65% of NOI |
| Pricing | $95M · 5.8% cap rate |
| Lender | Wells Fargo · 1.25 DSCR |
| Event to replay | Real recent rate move + AMZN 8-K |

---

## §4 Core workflow

```
Step 1  main.py starts — prompts user for deal details
Step 2  main.py calls fred.py and census.py — pulls live economic data
Step 3  main.py calls tavily.py — pulls live news and market reports
Step 4  main.py passes all raw signals to analyzer.py
Step 5  analyzer.py plugs data into prompt, sends to Claude, gets back structured brief
Step 6  analyzer.py returns DealBrief dict to main.py
Step 7  main.py prints brief to terminal — asks human checkpoint question
Step 8  If approved, main.py prints final structured output
```

---

## §5 Data sources & APIs

| API | Data pulled | Key required | Owner |
|---|---|---|---|
| FRED | Interest rates, Treasury yields, regional employment | Yes | Manny |
| Census Bureau | Demographics, population shifts, building permits | No | Manny |
| Tavily | Live brokerage reports, news, submarket events | Yes | Michael |
| OpenRouter | AI model — v1.0 | Yes | Joel |
| Anthropic | AI model — v2.0 upgrade | Yes | Joel |

---

## §6 FRED series IDs

| Series ID | Metric | Rationale | Status |
|---|---|---|---|
| `MORTGAGE30US` | 30-yr fixed mortgage rate | Directly impacts acquisition financing cost | Confirmed |
| `FEDFUNDS` | Federal funds rate | Baseline rate environment signal | Confirmed |
| `DGS10` | 10-yr Treasury yield | Cap rate benchmark | Confirmed |
| `AZUR` | Arizona unemployment rate | Tenant health proxy (Phoenix metro proxy — Manny: verify if a tighter Phoenix MSA series exists) | Confirmed |
| `TTLCONS` | Total construction spending | New supply signal | Confirmed |
| `INDPRO` | Industrial production index | Demand-side signal for industrial assets | Confirmed |

---

## §7 Data contracts

**These are the handoff agreements. Both sides must match exactly. No exceptions.**

### 7.1 Signal format — what Manny and Michael return

Every signal from every fetcher must follow this exact shape:

```python
{
    "name":   str,   # human-readable label e.g. "30-yr mortgage rate"
    "value":  str,   # the data point as a string e.g. "6.82%"
    "source": str    # API or publication name e.g. "FRED"
}
```

Each fetcher returns a **list** of these dicts. Joel expects a list. Not a dict of dicts. Not a string. A list.

```python
# What fred.fetch() returns
[
    {"name": "30-yr mortgage rate", "value": "6.82%", "source": "FRED"},
    {"name": "10-yr Treasury yield", "value": "4.31%", "source": "FRED"}
]
```

**Agreed `name` strings — use these exactly. No variations.**

| Owner | File | Signal name | Source value |
|---|---|---|---|
| Manny | fred.py | `"30-yr mortgage rate"` | `"FRED"` |
| Manny | fred.py | `"federal funds rate"` | `"FRED"` |
| Manny | fred.py | `"10-yr Treasury yield"` | `"FRED"` |
| Manny | fred.py | `"Phoenix unemployment rate"` | `"FRED"` |
| Manny | fred.py | `"construction spending"` | `"FRED"` |
| Manny | fred.py | `"industrial production index"` | `"FRED"` |
| Manny | census.py | `"Phoenix population growth"` | `"Census Bureau"` |
| Manny | census.py | `"Phoenix industrial permits"` | `"Census Bureau"` |
| Michael | tavily.py | article headline (full, as returned) | publication name (e.g. `"CoStar"`, `"Bloomberg"`) |

### 7.2 DealBrief format — what Joel returns to Victor

`analyzer.analyze()` must return exactly this dict. No extra keys. No missing keys.

```python
{
    "posture":          str,   # "buyer's market" | "balanced" | "seller's market"
    "recommendation":  str,   # "hold" | "accelerate" | "renegotiate" | "exit"
    "signal_breakdown": list,  # list of signal dicts — same shape as §7.1
    "next_move":        str,   # one sentence — specific action to take this week
    "watch_list":       str    # one metric to monitor over the next 30 days
}
```

**TEAM: `posture` and `recommendation` must be one of the exact strings listed above. No variations.**

---

## §8 Scope

### v1.0 — ships Wednesday week 1

- OpenRouter free model
- Full core loop: input → fetch → analyze → checkpoint → output
- Human checkpoint: agent pauses and asks before finalizing
- Working demo the whole team can run in three minutes

### v2.0 — ships end of week 2

- Upgrade to Anthropic API
- New capability: PDF deal memo upload — analyst drops a memo, agent reads it and skips manual input
- Same core loop, smarter model, one new input path

---

## §9 Open questions — resolve before writing code

- [x] **§6** — Confirm all FRED series IDs (Manny + team)
- [x] **§7.1** — Agree on exact `name` strings for each signal (all fetcher owners + Joel)
- [x] **§7.2** — Confirm `signal_breakdown` in DealBrief is the same list shape as §7.1 (Joel + Victor) — **Confirmed. Same shape: `{"name": str, "value": str, "source": str}`**
- [x] What happens if a FRED series returns no data for the requested date range? — **Skip that signal and continue. Return `{"name": <name>, "value": "unavailable", "source": "FRED (unavailable)"}` for any missing series.**
- [x] What happens if Tavily returns zero results? — **Skip news signals and continue. Return an empty list.**
- [x] Does the human checkpoint accept only `yes` / `no` or any truthy input? — **`yes` / `no` only. Any other input re-prompts.**
