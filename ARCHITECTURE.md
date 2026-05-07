# Architecture — cre-deal-agent

## Overview

cre-deal-agent is a multi-agent orchestrator/subagent system that automates commercial real estate deal evaluation. The orchestrator (`main.py`) sequences 6 stages and coordinates 7 agents. A shared state object flows through every stage — each agent reads from it and writes back to it before passing control forward.

---

## Why multi-agent

Three sharp specialists instead of one generalist. The find agent runs broad searches without dragging that context into analysis. The analyzer runs deep reasoning on the deal without listings noise. The seal agent handles structured negotiation with clean state. Each runs on a focused prompt with only the context it needs.

It also unlocks parallelism — FRED, Census, and Tavily fire simultaneously in Stage 3. Wall-clock time drops from sequential to whichever subagent is slowest.

The infrastructure was already proven in v1. `main.py` was always the orchestrator. `fred.py`, `census.py`, `tavily.py`, and `analyzer.py` were already subagents. v2 adds two new subagents to a pattern that was already running.

---

## Agent map

```
main.py (orchestrator)
├── finder.py      ← Stage 2 — deal discovery (NEW in v2)
├── fred.py        ← Stage 3 — interest rates, treasury yields
├── census.py      ← Stage 3 — population, demographics, permits
├── tavily.py      ← Stage 3 — live news, brokerage reports
├── analyzer.py    ← Stage 3 — synthesizes all subagent outputs
└── sealer.py      ← Stage 5–6 — LOI drafting and negotiation (NEW in v2)
```

---

## 6-Stage pipeline

State flows left to right. Error path drops down to park & monitor.

| Stage | Name | Agent | Output to state |
|---|---|---|---|
| 1 | Mandate setup | `main.py` | `mandate{}` |
| 2 | Deal discovery | `finder.py` | `raw_data.finder` |
| 3 | Full analysis | `fred.py` + `census.py` + `tavily.py` → `analyzer.py` | `raw_data`, `data_quality`, `metrics`, `sensitivity` |
| 4 | Bid generation | `main.py` | `bid{}` |
| 5 | LOI drafting | `sealer.py` | `loi_status` |
| 6 | Negotiation | `sealer.py` | `loi_status.counter_terms` or withdrawal |

Stage 3 subagents fire in parallel. `analyzer.py` waits for all three before synthesizing.

Stage 5–6 has a hard legal boundary — human approval is required before `sealer.py` sends any LOI.

---

## State object

One object flows through the entire pipeline. Every field is immutable once set — downstream agents read but do not overwrite upstream fields.

| Field | Type | What it holds | Set at stage |
|---|---|---|---|
| `mandate` | object | cap ceiling, asset class, buy box rules, metric thresholds | 1 |
| `raw_data` | object | FRED, Census, Tavily, finder outputs — untouched | 2–3 |
| `data_quality` | object | per-source flags: `direct` / `regional_fallback` / `missing` | 3 |
| `metrics` | object | Manny's 10: NOI, cap rate, cash-on-cash, IRR, equity multiple, DSCR, LTV, debt yield, OpEx ratio, occupancy | 3 |
| `sensitivity` | object | IRR at exit cap +50bps, occupancy −10%, etc. | 3 |
| `bid` | object | offer price, target cap rate, decision confidence | 4 |
| `loi_status` | object | `sent_at`, broker response, deadline, counter terms | 5–6 |
| `error` | object \| null | `agent`, `reason`, `retry_count`, `fallback_triggered` | any |

### Why data_quality matters

If FRED lacks direct data for a tertiary market and falls back to a regional average, the cap rate input could be 180bps off. Without a `data_quality` flag, the analyzer treats that number as reliable, propagates the error through the spread calculation, and the deal team negotiates on a number that's wrong three layers deep. The flag tells the analyzer to widen its sensitivity range or caveat the output explicitly.

---

## Deal analysis metrics (Manny's 10)

NOI is the engine everything else derives from — Cap Rate is just NOI ÷ Price, so you can't start the conversation without it. The list leads with investor-facing metrics before lender-facing ones, which is the right mental model for a deal maker. Debt Yield at #8 is a practitioner tell — not a beginner metric. Equity Multiple at #5 catches IRR's blind spot: a 20% IRR on a 12-month hold and a 20% IRR on a 5-year hold are very different animals in terms of actual wealth creation.

| # | Metric | Formula | Why it matters |
|---|---|---|---|
| 1 | NOI | Revenue − operating expenses (before debt service) | The engine every other metric runs on — Cap Rate can't exist without it |
| 2 | Cap Rate | NOI ÷ Purchase Price | Unlevered yield — the market's pricing language |
| 3 | Cash-on-Cash Return | Annual pre-tax cash flow ÷ total cash invested | What equity actually earns in year one |
| 4 | IRR | Time-weighted return across the full hold | Captures cash flows + exit in one number |
| 5 | Equity Multiple | Total distributions ÷ equity invested | IRR's blind spot — a 20% IRR on 12 months vs. 5 years are very different animals |
| 6 | DSCR | NOI ÷ annual debt service | Lenders require 1.20–1.30+. Below 1.0 you're feeding the deal |
| 7 | LTV | Loan ÷ appraised value | Caps leverage; drives your rate |
| 8 | Debt Yield | NOI ÷ loan amount | Lender-favorite — pure cushion check, ignores rate and amortization |
| 9 | Operating Expense Ratio | OpEx ÷ effective gross income | Sniff test for underwriting; multifamily typically 35–50% |
| 10 | Occupancy / Vacancy | Physical and economic | Trailing 12 vs. pro forma is where deals get exposed |

---

## Error path — park & monitor

When `finder.py` returns no results, the orchestrator routes through `inspect_state()` — a function inside `main.py`, not a separate agent — which reads the `error` field and determines which buy box constraint blocked every candidate.

```
finder.py returns null
        ↓
inspect_state()  ← which constraint failed?
    ↙                       ↘
loosen buy box           park & monitor
(flag human first)       (status: watching, retry on schedule)
                                 ↓
                            retry_count++
                                 ↓
                   retry_count ≥ max → stop, alert human
```

The `error` field in state holds:
- `agent` — which agent produced the null or failure
- `reason` — which constraint eliminated every candidate
- `retry_count` — how many times the orchestrator has looped
- `fallback_triggered` — whether a buy box relaxation was attempted

The retry counter is critical. Without it a persistent null from `finder.py` becomes an infinite loop.

---

## File structure

```
cre-deal-agent/
├── main.py               # orchestrator — core loop, inspect_state(), human checkpoint
├── fetchers/
│   ├── fred.py           # interest rates, treasury yields (FRED API)
│   ├── census.py         # demographics, building permits (Census Bureau)
│   └── tavily.py         # live news, brokerage reports (Tavily)
├── ai/
│   ├── analyzer.py       # synthesizes all subagent outputs → metrics + sensitivity
│   ├── finder.py         # deal discovery — scans Crexi, Ten-X, internal databases (NEW)
│   └── sealer.py         # LOI drafting + negotiation loop (NEW)
├── docs/
│   ├── PRD.md
│   └── assets/           # whiteboard diagrams, design references
└── .env                  # local only — never committed
```

---

## Data contracts

All fetchers return a list of signal dicts:

```python
{"name": str, "value": str, "source": str}
```

`analyzer.analyze()` returns a DealBrief dict:

```python
{
    "posture":           str,
    "recommendation":    str,
    "signal_breakdown":  list,
    "next_move":         str,
    "watch_list":        str
}
```

`finder.py` returns either a match or a structured null:

```python
# match found
{"status": "match", "asset": {...}, "comps": [...], "markets_searched": [...]}

# no match
{"status": "no_match", "reason": str, "criteria_tested": {...}, "markets_searched": [...]}
```

See `docs/PRD.md §7` for full contract details.
