# Architecture — cre-deal-agent v2

## System Overview

CRE Deal Monitor ingests live market signals, runs structured financial math
against an active deal, and drives the full negotiation lifecycle — from
initial outreach through LOI submission and counter-offer response.

The output of the agent is emails sent. Analysis is internal plumbing that
feeds the email prompts. No deal brief is printed to the terminal.

---

## Pipeline — 4 Stages

```
Stage 1   Deal Input       get_deal_input() in main.py
Stage 2   Parallel Fetch   fred + census + tavily + finder (ThreadPoolExecutor)
Stage 3   AI Analysis      analyzer.analyze_deal() → internal analysis dict
Stage 4   Email + Send     closer drafts → send_email() fires or human gate
```

### Stage 1 — Deal Input
`main.py: get_deal_input()`

User provides deal context via prompt. In `--demo` mode, the preset
Phoenix-Mesa-Chandler scenario is used. Uses the v2 schema (see Data
Schemas below) — Victor owns the migration from v1.

### Stage 2 — Parallel Market Fetch
`ThreadPoolExecutor(max_workers=4)` fires all four fetchers simultaneously:

```
fred.fetch(submarket)                           → FRED economic signals
census.fetch(submarket)                         → Demographics and permits
tavily.fetch(submarket, asset_type)             → Live news and vacancy
finder.find_offers(location, asset_type, price) → Competing listings
```

Signals stream into the dashboard as each future completes.

### Stage 3 — AI Analysis (internal)
`ai/analyzer.py: analyze_deal(deal_context, fred, census, tavily, offers)`

Claude runs Ibrahima's 12-step financial math using `analysis_system.txt`.
Returns an analysis dict with bid floor, bid ceiling, negotiation posture,
LOI urgency, and key negotiation levers. Passed directly into the email
functions — never printed as standalone output.

### Stage 4 — Email Draft + Send
`ai/closer.py` drafts · `main.py: send_email()` sends

The agent auto-sends everything that proposes or withdraws. It stops the
moment a human must accept terms — that is when the legal clock starts.

```
outreach_email                        AUTO-SENT   requesting OM, no commitment
counter_offer_email  action="counter" AUTO-SENT   proposes new terms, no commitment
counter_offer_email  action="walk"    AUTO-SENT   withdrawing, no commitment
loi_email                             HUMAN GATE  needs signed LOI doc attached
counter_offer_email  action="accept"  HUMAN GATE  accepts terms — triggers LOI execution
```

The legal boundary is the statute of frauds: real property contracts must be
in writing and signed by an authorized person. The LOI document (not the
cover email) requires that signature — that is what stops the agent.

`send_email(email_dict)` uses `smtplib` over Gmail SMTP (port 587, STARTTLS).
Credentials: `GMAIL_USER` and `GMAIL_APP_PASSWORD` in `.env`.
Returns `True` on success. On failure, displays error panel in dashboard.

For human-gate emails, the dashboard shows the draft with a warning and
waits for a keypress before anything goes out.

### Dashboard
`main.py: rich panels`

```
┌─────────────────────────────┬──────────────────────────────┐
│  LIVE SIGNALS               │  COMPETING OFFERS            │
│  (stream in as fetched)     │                              │
├─────────────────────────────┴──────────────────────────────┤
│  EMAIL SENT  /  AWAITING YOUR REVIEW                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent Map

| File                        | Owner                           | Notes    |
|-----------------------------|---------------------------------|----------|
| `main.py`                   | Victor                          |          |
| `fetchers/fred.py`          | Manny                           |          |
| `fetchers/census.py`        | Manny                           |          |
| `fetchers/tavily.py`        | Manny                           |          |
| `fetchers/finder.py`        | Joel                            | New — v2 |
| `ai/analyzer.py`            | Ibrahima (prompt) + Joel (API)  |          |
| `ai/closer.py`              | Ibrahima (prompt) + Joel (API)  | New — v2 |
| `ai/prompts/`               | Ibrahima                        | New — v2 |
| `.env.example`              | Victor                          |          |
| `docs/PRD.md`               | Victor                          | Team sign-off required for changes |

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

### Analysis dict — internal (v2, extended from v1)

```python
{
    "posture":                  str,   # "buyer's market" | "balanced" | "seller's market"
    "recommendation":           str,   # "hold" | "accelerate" | "renegotiate" | "exit"
    "signal_breakdown":         list,  # [{name, value, source, impact}]
    "next_move":                str,
    "watch_list":               str,
    "bid_floor_usd":            int,
    "bid_ceiling_usd":          int,
    "negotiation_posture":      str,   # "aggressive" | "measured" | "cautious"
    "loi_urgency":              str,   # "submit_within_24h" | "submit_within_72h" | "hold"
    "key_negotiation_levers":   list,
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

Four system prompts authored by Ibrahima, stored in `ai/prompts/`.
Joel loads them at runtime — do not rename files without telling Joel.

| File                      | Used by          | Purpose                                     |
|---------------------------|------------------|---------------------------------------------|
| `analysis_system.txt`     | `ai/analyzer.py` | 12-step financial analysis → analysis dict  |
| `outreach_email.txt`      | `ai/closer.py`   | First contact email to listing broker       |
| `loi_email.txt`           | `ai/closer.py`   | LOI cover email — human gate                |
| `counter_offer_email.txt` | `ai/closer.py`   | Counter offer response (accept/counter/walk)|

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Fetcher returns unavailable signal | Flagged in analysis, confidence range widens |
| Claude parse failure | Retry once with simplified prompt; `RuntimeError` on second failure |
| Email agent failure | `RuntimeError` raised; Victor catches in `main.py`, shows error panel |
| `finder.py` returns zero results | Empty list; dashboard shows "No competing offers found" |
| Missing `ANTHROPIC_API_KEY` | `EnvironmentError` raised before any API call |
| Outreach email send failure | SMTP error caught; error panel shown, no auto-retry |
| Missing `GMAIL_USER` or `GMAIL_APP_PASSWORD` | `EnvironmentError` raised before send |
