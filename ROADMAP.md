# Roadmap — cre-deal-agent

See `docs/PRD.md` for full requirements and data contracts.

---

## Prerequisites — align before anyone writes code

- [ ] All five members have read `docs/PRD.md`
- [ ] FRED series IDs confirmed (PRD §6) — Manny owns this, others unblock against it
- [ ] Signal `name` strings agreed on (PRD §7.1) — all fetcher owners + Joel
- [ ] DealBrief schema confirmed (PRD §7.2) — Joel + Victor
- [ ] GitHub branch protection configured per `.github/GITHUB_SETUP.md`
- [ ] Each member has a GitHub issue assigned — use the issue number for branch naming (`feat/cre-{id}-{description}`)
- [ ] Everyone has run `cp .env.example .env` and filled in their keys locally

---

## Ibrahima — AI Prompts

**File owned:** `ai/analyzer.py` (prompt section — coordinate with Joel)

**What you write:**
- The system prompt that tells Claude what role it's playing and what output format to return
- The user message template that inserts the deal context and raw signals
- Test the prompt in isolation until the DealBrief comes back clean every time

**Input your prompt receives:**
```python
deal_context = {
    "asset_type": str,
    "submarket":  str,
    "price":      str
}
signals = [{"name": str, "value": str, "source": str}]  # see PRD §7.1
```

**Output your prompt must produce** (Claude must return strict JSON matching this):
```python
{
    "posture":          str,
    "recommendation":  str,
    "signal_breakdown": list,
    "next_move":        str,
    "watch_list":       str
}
```

**Done looks like:** Claude returns valid JSON matching the DealBrief schema 10 out of 10 test runs. No hallucinated keys. No missing keys.

**Riskiest part:** Claude returning free-form text instead of strict JSON. Fix: put the exact JSON schema in the system prompt and add `"Return only valid JSON. No explanation."` at the end.

**Checklist:**
- [ ] Write system prompt — sets Claude's role as a CRE analyst
- [ ] Write user message template — inserts deal context + signals
- [ ] Force strict JSON output — schema in prompt, no prose
- [ ] Test against demo scenario (Phoenix industrial, Amazon, $95M)
- [ ] Test with empty signal list — confirm graceful output
- [ ] Hand prompt to Joel to wire into the API call

---

## Manny — Data Fetching

**Files owned:** `fetchers/fred.py`, `fetchers/census.py`

**What you write:**
- `fred.fetch(submarket: str) -> list[dict]` — pulls FRED series for the given market
- `census.fetch(submarket: str) -> list[dict]` — pulls Census Bureau data for the given market

**Input:**
```python
submarket: str  # e.g. "Phoenix-Mesa-Chandler"
```

**Output** (both functions return the same shape — see PRD §7.1):
```python
[
    {"name": str, "value": str, "source": str},
    ...
]
```

**Done looks like:** Both functions return a clean list of signal dicts for the Phoenix-Mesa-Chandler demo submarket. `source` is always `"FRED"` or `"Census Bureau"`. No raw API response objects leak through.

**Riskiest part:** FRED returning a 400 for a series ID that doesn't exist or isn't available for the requested region. Always check `response.status_code` before parsing.

**Checklist:**
- [ ] Confirm FRED series IDs with team (PRD §6) before writing any fetch logic
- [ ] Write `fred.fetch()` — pulls confirmed series, returns signal list
- [ ] Handle FRED 400/404 — return empty list with a `source: "FRED (unavailable)"` entry
- [ ] Write `census.fetch()` — pulls building permits and demographics
- [ ] Test both functions against Phoenix-Mesa-Chandler
- [ ] Confirm output matches PRD §7.1 signal shape exactly

---

## Manny — Search & News (reassigned from v1)

**File owned:** `fetchers/tavily.py` (reassigned to Manny — v1 complete)

**What you maintain:**
- `tavily.fetch(submarket: str, asset_type: str) -> list[dict]` — pulls live brokerage reports and news

**v1 checklist:**
- [x] Write `tavily.fetch()` with targeted search query
- [x] Parse Tavily response into signal list — name = headline, value = summary, source = publication
- [x] Handle zero results — return empty list, do not crash
- [x] Test against Phoenix-Mesa-Chandler industrial query
- [x] Confirm output matches PRD §7.1 signal shape exactly

---

## Joel — Claude Layer

**File owned:** `ai/analyzer.py` (API call section — coordinate with Ibrahima)

**What you write:**
- `analyze(deal_context: dict, signals: list) -> dict` — combines Ibrahima's prompt with the raw signals, sends to Claude, returns a clean DealBrief dict

**Input:**
```python
deal_context = {"asset_type": str, "submarket": str, "price": str}
signals      = [{"name": str, "value": str, "source": str}]
```

**Output** (see PRD §7.2):
```python
{
    "posture":          str,
    "recommendation":  str,
    "signal_breakdown": list,
    "next_move":        str,
    "watch_list":       str
}
```

**Done looks like:** `analyze()` returns a valid DealBrief dict for the demo scenario. Claude's raw response is fully parsed — Victor never sees a raw string or a JSON parse error.

**Riskiest part:** Claude returning valid JSON that doesn't match the DealBrief schema. Fix: validate the parsed dict against the five required keys before returning. Raise a clear error if any key is missing.

**Checklist:**
- [ ] Wait for Ibrahima's prompt before writing API call
- [ ] Wire OpenRouter API call — model: `openai/gpt-4o-mini` for v1
- [ ] Parse Claude's JSON response into DealBrief dict
- [ ] Validate all five keys present before returning
- [ ] Handle JSON parse error — raise `ValueError` with Claude's raw response in the message
- [ ] Test against demo scenario with real signal data from Manny and Michael
- [ ] Confirm return shape matches PRD §7.2 exactly

---

## Victor — Core Loop

**Files owned:** `main.py`, `.env.example`, `.env` setup for team

**What you write:**
- `get_deal_input() -> dict` — prompts user for deal details, returns deal context dict
- `run_checkpoint(brief: dict) -> bool` — prints brief to terminal, asks approve/kill, returns True if approved
- `print_brief(brief: dict)` — formats and prints the final DealBrief
- The main loop that wires all four modules together

**Input to main loop:** none — gets everything from user input and module returns

**Output:** structured DealBrief printed to terminal

**Done looks like:** `python main.py` runs end-to-end for the demo scenario. User inputs Phoenix deal, signals are fetched, Claude analyzes, checkpoint fires, user approves, brief prints. No crashes. No missing keys.

**Riskiest part:** Integration — everyone's functions work in isolation but break when plugged together. Fix: write stub functions on Day 1 that return correctly-shaped fake data. Run the full loop against stubs before anyone's real code lands.

**Checklist:**
- [ ] Write stub versions of `fred.fetch()`, `census.fetch()`, `tavily.fetch()`, `analyze()` — return correctly-shaped fake data
- [ ] Write `get_deal_input()` — prompt for asset type, submarket, price
- [ ] Write main loop — calls fetchers, passes to analyzer, calls checkpoint
- [ ] Write `run_checkpoint()` — print brief, prompt `yes/no`, return bool
- [ ] Write `print_brief()` — clean terminal output for all five DealBrief fields
- [ ] Confirm full loop runs against stubs before teammates finish their files
- [ ] Swap stubs for real modules on integration day (Tuesday)
- [ ] Run demo scenario end-to-end — Phoenix industrial, Amazon, $95M

---

## Integration & Review — v1

- [x] All branches rebased to latest `main` before opening PRs
- [x] PRs opened in dependency order: Manny (parallel) → Joel → Victor
- [x] Ibrahima's prompt landed and tested before Joel opens his PR
- [x] All CI checks pass: Branch Guard, Quality Checks, Security Checks, Build App
- [x] Demo scenario runs end-to-end without errors
- [x] Human checkpoint fires correctly — approve path and kill path both tested
- [x] `python main.py` works on a clean clone with only `.env` filled in

---

---

# v2 — Offer Finder · Deal Closer · Terminal Dashboard

See `ARCHITECTURE.md` for full system design, data schemas, and prompt map.

---

## Prerequisites — v2

- [ ] All members have read `ARCHITECTURE.md`
- [ ] deal_context v2 schema agreed — Victor migrates `main.py`, Joel migrates `ai/analyzer.py`
- [ ] DealBrief v2 schema agreed — Joel validates new keys in `ai/analyzer.py`
- [ ] `ai/prompts/` directory structure agreed — Ibrahima owns all four `.txt` files
- [ ] Each member has a GitHub issue assigned for their v2 work

---

## Ibrahima — Prompts (v2)

**Files owned:** `ai/prompts/` (all four system prompt files)

**What you own:**

All four system prompts are live in `ai/prompts/`. Joel loads them at runtime — do not rename files without telling Joel.

- `analysis_system.txt` — 12-step financial analysis prompt → wired into `ai/analyzer.py`
- `outreach_email.txt` — first contact to listing broker → wired into `ai/closer.py`
- `loi_email.txt` — LOI cover email → wired into `ai/closer.py`
- `counter_offer_email.txt` — counter offer response → wired into `ai/closer.py`

**v2 checklist:**
- [x] Write `analysis_system.txt` — 12-step math, extended DealBrief schema
- [x] Write `outreach_email.txt` — first contact email
- [x] Write `loi_email.txt` — LOI cover email, 72hr expiry
- [x] Write `counter_offer_email.txt` — accept / counter / walk logic
- [ ] Test `analysis_system.txt` against demo scenario — confirm all 12 new keys return correctly
- [ ] Test each email prompt — confirm JSON output shape matches schema exactly
- [ ] Confirm `signal_breakdown` includes `impact` field in all analysis test runs

---

## Manny — Data Fetching (v2)

**Files owned:** `fetchers/fred.py`, `fetchers/census.py`, `fetchers/tavily.py`

**v2 work — source-level tagging in `fred.py`:**

Update the `source` field for each FRED series to reflect geographic scope.
No new fetch calls, no contract change — strictly a relabeling.

```
MORTGAGE30US  →  "FRED (national)"
DGS10         →  "FRED (national)"
FEDFUNDS      →  "FRED (national)"
TTLCONS       →  "FRED (national)"
INDPRO        →  "FRED (national)"
AZUR          →  "FRED (state-level)"
```

`census.py` and `tavily.py`: no changes needed for v2.

**Branch:** `feat/cre-{id}-fred-source-tags`

**v2 checklist:**
- [ ] Update source tags in `fred.py` — national vs state-level
- [ ] Run `python fetchers/fred.py` — confirm all six signals return with updated labels
- [ ] `ruff check fetchers/fred.py` passes

---

## Joel — Claude Layer + Finder (v2)

**Files owned:** `fetchers/finder.py` (new), `ai/analyzer.py` (API call), `ai/closer.py` (new)

### finder.py

**Branch:** `feat/cre-{id}-finder`

Function to implement:

```python
def find_offers(location: str, asset_type: str, price: float) -> list[dict]
# Returns: [{"name": str, "value": str, "source": str}]
# name   = property headline or listing title
# value  = price, cap rate, and one-sentence summary
# source = brokerage or publication hostname
```

Suggested Tavily query:
`"{location} {asset_type} commercial real estate FOR SALE comparable listing 2025 2026"`

Target 3–5 results. Return empty list on zero results — do not crash.
Lock the function signature on Day 1 — Ibrahima and Victor are unblocked once this is confirmed.

**v2 checklist — finder.py:**
- [ ] Lock function signature — confirm with team before writing implementation
- [ ] Write `find_offers()` using Tavily endpoint
- [ ] Return empty list on zero results — no crash
- [ ] Test against Phoenix-Mesa-Chandler industrial
- [ ] `ruff check fetchers/finder.py` passes

### ai/analyzer.py — v2 updates

**Branch:** `feat/cre-{id}-analyzer-v2`

- Load system prompt from `ai/prompts/analysis_system.txt` at runtime (do not hardcode)
- Update function signature to accept v2 deal_context schema
- Update response validator — DealBrief now has 10 keys, not 5
- Required keys to validate: `posture`, `recommendation`, `signal_breakdown`, `next_move`, `watch_list`, `bid_floor_usd`, `bid_ceiling_usd`, `negotiation_posture`, `loi_urgency`, `key_negotiation_levers`

**v2 checklist — analyzer.py:**
- [ ] Load prompt from file — `Path("ai/prompts/analysis_system.txt").read_text()`
- [ ] Update deal_context passthrough — new field names from v2 schema
- [ ] Update `REQUIRED_KEYS` validator — 10 keys
- [ ] Test against demo scenario — confirm all 10 keys return
- [ ] `ruff check ai/analyzer.py` passes

### ai/closer.py — new file

**Branch:** `feat/cre-{id}-closer`

Three functions, each loading its own prompt file:

```python
def draft_outreach_email(deal_context: dict) -> dict
def draft_loi_email(deal_context: dict, brief: dict, loi_terms: dict) -> dict
def draft_counter_email(deal_context: dict, counter_terms: dict, decision: dict) -> dict
```

All return a dict matching the email output schema in `ARCHITECTURE.md`.
Same OpenRouter/LiteLLM pattern as `analyzer.py`. Temperature: 0.4. Max tokens: 1024.
Raise `RuntimeError` on failure — Victor catches in `main.py`.

**v2 checklist — closer.py:**
- [ ] Write `draft_outreach_email()` — load `outreach_email.txt`, call API, return dict
- [ ] Write `draft_loi_email()` — load `loi_email.txt`, call API, return dict with `loi_expiry_hours: 72`
- [ ] Write `draft_counter_email()` — load `counter_offer_email.txt`, call API, return dict
- [ ] Validate output shape for each function before returning
- [ ] Test each function with mock inputs
- [ ] `ruff check ai/closer.py` passes

---

## Victor — Core Loop + Dashboard (v2)

**Files owned:** `main.py`, `requirements.txt`

**Branch:** `feat/cre-{id}-dashboard`

Four changes in one PR:

1. **Migrate deal_context to v2 schema** — update `get_deal_input()` to collect
   `purchase_price` (int), `cap_rate` (float), `anchor_tenant`, `tenant_noi_pct`,
   `dscr_covenant` (float). Remove v1 field names.

2. **Parallelize the four fetcher calls** — replace sequential calls with
   `ThreadPoolExecutor(max_workers=4)`:

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as pool:
    f_fred   = pool.submit(fred.fetch, submarket)
    f_census = pool.submit(census.fetch, submarket)
    f_tavily = pool.submit(tavily.fetch, submarket, asset_type)
    f_finder = pool.submit(finder.find_offers, submarket, asset_type, deal_context["purchase_price"])

fred_signals   = f_fred.result()
census_signals = f_census.result()
tavily_signals = f_tavily.result()
offer_signals  = f_finder.result()
```

3. **Wire `ai/closer.py`** — call `draft_outreach_email()`, `draft_loi_email()`,
   or `draft_counter_email()` based on `loi_urgency` from DealBrief. Catch
   `RuntimeError` from closer and display error panel in dashboard.

4. **Terminal dashboard using `rich`** — add `rich` to `requirements.txt`.
   Panel layout described in `ARCHITECTURE.md`. Email draft prints in its own
   panel after checkpoint approval.

**v2 checklist:**
- [ ] Migrate `get_deal_input()` to v2 deal_context schema
- [ ] Update demo scenario dict to v2 schema
- [ ] Parallelize four fetcher calls with `ThreadPoolExecutor`
- [ ] Wire `finder.find_offers()` into the main loop
- [ ] Wire `closer.draft_loi_email()` — fires when `loi_urgency != "hold"`
- [ ] Wire `closer.draft_outreach_email()` for competing offer contacts
- [ ] Add `rich` to `requirements.txt`
- [ ] Build dashboard panel layout
- [ ] `python main.py --demo` runs end-to-end — all panels render, email prints after approval
- [ ] `ruff check main.py` passes

---

## Integration & Review — v2

- [ ] All v2 branches rebased to latest `main` before opening PRs
- [ ] PR merge order: Manny → Joel (finder + analyzer) → Joel (closer) → Victor
- [ ] Ibrahima's prompts tested against demo before Joel opens analyzer v2 PR
- [ ] All CI checks pass on each PR
- [ ] `python main.py --demo` runs end-to-end with all four fetchers parallel
- [ ] Dashboard renders all panels without errors
- [ ] Email draft prints after checkpoint approval
- [ ] Counter offer flow tested: LOI → counter → response
