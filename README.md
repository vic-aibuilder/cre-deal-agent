# cre-deal-agent

A terminal-based AI agent that monitors an active commercial real estate deal and surfaces the signals that change what a data analyst does next.

---

## What it does

The agent takes a real estate deal as input, pulls live market data from public APIs, has Claude analyze all the signals together, pauses for a human to approve, and prints a structured deal brief in the terminal. The whole loop runs in under three minutes.

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
| Michael | Search & News | `fetchers/tavily.py` |
| Joel | Claude Layer | `ai/analyzer.py` (API call section) |
| Victor | Core Loop | `main.py`, `.env` setup |

---

## Roadmap

| Version | Model | Capability |
|---|---|---|
| v1.0 | OpenRouter (free) | Terminal loop — input → fetch → analyze → checkpoint → brief |
| v2.0 | Anthropic API | PDF deal memo upload — drop a memo, agent reads it and returns a recommendation |
