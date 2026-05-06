# cre-deal-agent

A terminal-based AI agent that monitors an active commercial real estate deal and surfaces the signals that change what a data analyst does next.

V2 adds autonomous broker outreach with Gmail: the agent can send first-touch inquiry emails, monitor broker replies, and send LOI cover emails with a PDF attachment.

---

## What it does

The agent takes a real estate deal as input, pulls live market data from public APIs, has Claude analyze all the signals together, pauses for a human to approve, and prints a structured deal brief in the terminal. The whole loop runs in under three minutes.

For v2 automation, the email agent can execute outbound broker communication without human review in the loop.

---

## Demo scenario

| Field | Value |
|---|---|
| Asset type | Industrial, 412k sqft |
| Submarket | Phoenix-Mesa-Chandler |
| Anchor tenant | Amazon · 65% of NOI |
| Pricing | $95M · 5.8% cap rate |
| Lender | Wells Fargo · 1.25 DSCR |
| Event replayed | Real recent rate move + AMZN 8-K |

---

## How it works

```
1. User enters deal details — asset type, location, price
2. Agent pulls live economic data from FRED and Census Bureau
3. Agent pulls live news and market reports via Tavily search
4. All raw signals are passed to Claude for analysis
5. Claude drafts a structured deal brief
6. Agent pauses — human reviews and approves or kills
7. Final brief prints to terminal
```

---

## Output

| Field | Description |
|---|---|
| `posture` | buyer's market · balanced · seller's market |
| `recommendation` | hold · accelerate · renegotiate · exit |
| `signal_breakdown` | each signal with value, change, and source |
| `next_move` | one specific action to take this week |
| `watch_list` | one metric to monitor over the next 30 days |

---

## File structure

```
cre-deal-agent/
├── main.py               # Victor — core loop, human checkpoint
├── agents/
│   └── email_agent.py    # Michael — autonomous broker outreach + inbox monitor
├── fetchers/
│   ├── fred.py           # Manny — FRED API (interest rates, employment)
│   ├── census.py         # Manny — Census Bureau (demographics, permits)
│   └── tavily.py         # Michael — live news and brokerage reports
├── ai/
│   └── analyzer.py       # Joel (Claude layer) + Ibrahima (prompts)
└── .env                  # local only — never committed
```

---

## Setup

```bash
git clone https://github.com/vic-aibuilder/cre-deal-agent.git
cd cre-deal-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env
python main.py
```

### Gmail setup for v2 EmailAgent

1. Create a Google Cloud OAuth app with Gmail API enabled.
2. Obtain an OAuth access token with `gmail.send` and `gmail.readonly` scopes.
3. Add the token to `.env` as `GMAIL_ACCESS_TOKEN`.

Environment variables used by email automation:

```bash
GMAIL_ACCESS_TOKEN=your_short_lived_oauth_access_token
```

Note: this repository currently expects a valid runtime access token. Token refresh flow can be added in a follow-up.

Run connectivity smoke test:

```bash
python3 scripts/email_smoke_test.py
```

---

## EmailAgent tools (v2)

The EmailAgent lives in `agents/email_agent.py` and provides:

- `send_broker_inquiry(broker_email, deal_context, access_token=None)`
- `monitor_broker_inbox(access_token=None, active_thread_ids=None, query="in:inbox newer_than:7d", max_results=20, on_counter_detected=None)`
- `send_loi_cover_email(broker_email, property_address, loi_pdf_path, access_token=None, thread_id=None)`

Example:

```python
from agents.email_agent import monitor_broker_inbox, send_broker_inquiry

deal_context = {
	"asset_type": "industrial",
	"location": "Phoenix-Mesa-Chandler",
	"price": 95_000_000,
}

sent = send_broker_inquiry("broker@example.com", deal_context)
events = monitor_broker_inbox(active_thread_ids=[sent["thread_id"]])
```

---

## APIs used

| API | Data | Key required |
|---|---|---|
| FRED | Interest rates, Treasury yields, employment | Yes — fred.stlouisfed.org |
| Census Bureau | Demographics, building permits | No |
| Tavily | Live news and brokerage reports | Yes — tavily.com |
| OpenRouter | AI model (v1.0) | Yes — openrouter.ai |
| Anthropic | AI model (v2.0) | Yes — anthropic.com |

---

## Team

| Name | Role | File |
|---|---|---|
| Ibrahima | AI Prompts | `ai/analyzer.py` (prompt section) |
| Manny | Data Fetching | `fetchers/fred.py`, `fetchers/census.py` |
| Michael | Search, News & EmailAgent | `fetchers/tavily.py`, `agents/email_agent.py` |
| Joel | Claude Layer & Sealer | `ai/analyzer.py` (API call section), `agents/sealer.py` |
| Victor | Core Loop | `main.py`, `.env` setup |

---

## Roadmap

| Version | Model | Capability |
|---|---|---|
| v1.0 | OpenRouter (free) | Terminal loop — input → fetch → analyze → checkpoint → brief |
| v2.0 | Anthropic API | PDF deal memo upload — drop a memo, agent reads it and returns a recommendation |

---

## Demo Operator Guide

If Michael is unavailable for demo day, use the operator runbook:

- `docs/DEMO_OPERATOR_RUNBOOK.md`
