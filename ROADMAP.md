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

## Michael — Search & News

**File owned:** `fetchers/tavily.py`

**What you write:**
- `tavily.fetch(submarket: str, asset_type: str) -> list[dict]` — pulls live brokerage reports and news

**Input:**
```python
submarket:  str  # e.g. "Phoenix-Mesa-Chandler"
asset_type: str  # e.g. "industrial"
```

**Output** (same signal shape as Manny — see PRD §7.1):
```python
[
    {"name": str, "value": str, "source": str},
    ...
]
```

**Done looks like:** Function returns 3–5 news signals for the demo submarket. `source` is the publication name (e.g. `"CoStar News"`). Each `value` is a one-sentence summary of the article.

**Riskiest part:** Tavily returning irrelevant results for niche submarkets. Fix: craft the search query to include `"commercial real estate"` + asset type + submarket in the string.

**Checklist:**
- [ ] Write `tavily.fetch()` with targeted search query
- [ ] Parse Tavily response into signal list — name = headline, value = summary, source = publication
- [ ] Handle zero results — return empty list, do not crash
- [ ] Test against Phoenix-Mesa-Chandler industrial query
- [ ] Confirm output matches PRD §7.1 signal shape exactly

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

## Integration & Review

- [ ] All branches rebased to latest `main` before opening PRs
- [ ] PRs opened in dependency order: Manny + Michael (parallel) → Joel → Victor
- [ ] Ibrahima's prompt landed and tested before Joel opens his PR
- [ ] All CI checks pass: Branch Guard, Quality Checks, Security Checks, Build App
- [ ] Demo scenario runs end-to-end without errors
- [ ] Human checkpoint fires correctly — approve path and kill path both tested
- [ ] `python main.py` works on a clean clone with only `.env` filled in
