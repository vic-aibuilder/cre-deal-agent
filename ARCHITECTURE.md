# Architecture — cre-deal-agent v2

## System Overview

CRE Deal Monitor is a terminal-based AI agent that ingests live market
signals, runs structured financial math against an active deal, and drives
the full negotiation lifecycle — from initial outreach through LOI
submission and counter-offer response.

---

## Pipeline — 6 Stages

```
Stage 1   Deal Input          get_deal_input() in main.py
Stage 2   Parallel Fetch      fred + census + tavily + finder (ThreadPoolExecutor)
Stage 3   AI Analysis         analyzer.analyze_deal() → DealBrief
Stage 4   Human Checkpoint    run_checkpoint() in main.py
Stage 5   Email Draft         closer.draft_email() → email dict
Stage 6   Terminal Output     rich dashboard in main.py
```

### Stage 1 — Deal Input
`main.py: get_deal_input()`

User provides deal context via prompt. In `--demo` mode, the preset
Phoenix-Mesa-Chandler scenario is used. deal_context is the v2 schema
(see Data Schemas below) — Victor owns the migration from v1.

### Stage 2 — Parallel Market Fetch
`ThreadPoolExecutor(max_workers=4)` fires all four fetchers simultaneously:

```
fred.fetch(submarket)                          → FRED economic signals
census.fetch(submarket)                        → Demographics and permits
tavily.fetch(submarket, asset_type)            → Live news and vacancy
finder.find_offers(location, asset_type, price) → Competing listings
```

### Stage 3 — AI Analysis
`ai/analyzer.py: analyze_deal(deal_context, fred, census, tavily, offers)`

Claude runs Ibrahima's 12-step financial math using `analysis_system.txt`.
Returns the extended DealBrief (v2) including bid floor, bid ceiling,
negotiation posture, LOI urgency, and key negotiation levers.

### Stage 4 — Human Checkpoint
`main.py: run_checkpoint(brief)`

Displays posture, recommendation, and next move. Requires explicit human
approval before any email is drafted or output is printed.

### Stage 5 — Email Draft
`ai/closer.py`

Three email types, each backed by a separate Ibrahima prompt:

```
outreach_email       First contact to listing broker (before LOI)
loi_email            LOI cover letter (fires when loi_urgency != "hold")
counter_offer_email  Response to broker counter (fires on broker reply)
```

### Stage 6 — Terminal Output
`main.py: rich dashboard`

```
┌─────────────────────────────┬──────────────────────────────┐
│  LIVE SIGNALS               │  MARKET POSTURE              │
│  (stream in as fetched)     │  RECOMMENDATION              │
├─────────────────────────────┴──────────────────────────────┤
│  NEXT MOVE  ·  30-DAY WATCH LIST                           │
├─────────────────────────────────────────────────────────────┤
│  COMPETING OFFERS                                           │
├─────────────────────────────────────────────────────────────┤
│  DRAFT EMAIL — REVIEW BEFORE SENDING                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent Map

| File                         | Owner                              | Notes      |
|------------------------------|------------------------------------|------------|
| `main.py`                    | Victor                             |            |
| `fetchers/fred.py`           | Manny                              |            |
| `fetchers/census.py`         | Manny                              |            |
| `fetchers/tavily.py`         | Manny                              |            |
| `fetchers/finder.py`         | Joel                               | New — v2   |
| `ai/analyzer.py`             | Ibrahima (prompt) + Joel (API)     |            |
| `ai/closer.py`               | Ibrahima (prompt) + Joel (API)     | New — v2   |
| `ai/prompts/`                | Ibrahima                           | New — v2   |
| `.env.example`               | Victor                             |            |
| `docs/PRD.md`                | Victor                             | Team sign-off required for changes |

Nobody touches another person's file without asking first.

---

## Data Schemas

### deal_context — v2 (breaking change from v1)

```python
{
    "asset_type":      str,    # e.g. "Industrial, 412k sqft"
    "submarket":       str,    # e.g. "Phoenix-Mesa-Chandler"
    "purchase_price":  int,    # e.g. 95000000
    "cap_rate":        float,  # e.g. 0.058  ← was str "5.8%" in v1
    "anchor_tenant":   str,    # e.g. "Amazon"
    "tenant_noi_pct":  float,  # e.g. 0.65   ← new field
    "lender":          str,    # e.g. "Wells Fargo"
    "dscr_covenant":   float,  # e.g. 1.25   ← was str in v1
}
```

Victor updates `get_deal_input()` in `main.py` to produce this shape.
Joel updates `ai/analyzer.py` to accept and pass it through unchanged.

### DealBrief — v2 (extended from v1)

```python
{
    "posture":                  str,   # "buyer's market" | "balanced" | "seller's market"
    "recommendation":           str,   # "hold" | "accelerate" | "renegotiate" | "exit"
    "signal_breakdown":         list,  # [{name, value, source, impact}] — impact field is new
    "next_move":                str,   # must include a specific dollar amount or metric
    "watch_list":               str,
    "bid_floor_usd":            int,   # new — NOI / 1.20, rounded to nearest 100k
    "bid_ceiling_usd":          int,   # new — NOI / (cap_rate - 0.005), rounded to nearest 100k
    "negotiation_posture":      str,   # new — "aggressive" | "measured" | "cautious"
    "loi_urgency":              str,   # new — "submit_within_24h" | "submit_within_72h" | "hold"
    "key_negotiation_levers":   list,  # new — subset of fixed vocabulary below
}
```

Valid values for `key_negotiation_levers`:
`"due_diligence_period"`, `"earnest_money"`, `"closing_timeline"`,
`"purchase_price"`, `"seller_credits"`

### Signal — all fetchers including finder.py

```python
{"name": str, "value": str, "source": str}
```

### Email output — outreach and counter offer

```python
{"subject": str, "body": str, "to": str, "from": str}
```

### Email output — LOI cover

```python
{"subject": str, "body": str, "to": str, "from": str, "loi_expiry_hours": 72}
```

---

## Prompt Architecture

Four system prompts, all authored by Ibrahima, stored in `ai/prompts/`.
Joel loads and passes them; Ibrahima edits the text. Neither touches the
other's side without asking.

| File                       | Used by          | Purpose                                       |
|----------------------------|------------------|-----------------------------------------------|
| `analysis_system.txt`      | `ai/analyzer.py` | 12-step financial analysis → DealBrief JSON   |
| `outreach_email.txt`       | `ai/closer.py`   | First contact email to listing broker         |
| `loi_email.txt`            | `ai/closer.py`   | LOI cover email after analysis clears mandate |
| `counter_offer_email.txt`  | `ai/closer.py`   | Counter offer response to broker reply        |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Fetcher returns unavailable signal | Flagged in `signal_breakdown`, confidence range widens |
| Claude parse failure | Retry once with simplified prompt; `RuntimeError` on second failure |
| Email agent failure | `RuntimeError` raised; Victor catches in `main.py`, displays error panel |
| `finder.py` returns zero results | Empty list returned; dashboard shows "No competing offers found" |
| Missing `OPENROUTER_API_KEY` | `EnvironmentError` raised before any API call |
