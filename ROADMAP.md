# Roadmap — cre-deal-agent

See `docs/PRD.md` for full requirements and data contracts. See `ARCHITECTURE.md` for the full v2 system design.

---

## v2.0 — 6-stage multi-agent pipeline

> **Owner assignment coming soon.** Tasks are listed by role (Person 1–5) as placeholders until the team assigns names.

See `ARCHITECTURE.md` for the full design: state schema, agent map, error path, and data contracts.

---

### Person 1 — finder.py (Stage 2 — Deal Discovery)

**File:** `ai/finder.py`

**What you build:**
- `finder.search(mandate: dict) -> dict` — takes the mandate object from state and searches for matching deals
- Returns a match object or a structured null (see `ARCHITECTURE.md` data contracts)
- Sources: Crexi, Ten-X, internal databases

**Done looks like:** `finder.search()` returns a clean match or a structured no-match dict for the demo scenario. The orchestrator can route on `result["status"]` without any extra parsing.

**Checklist:**
- [ ] Read mandate object shape from `ARCHITECTURE.md`
- [ ] Write `finder.search()` — query deal sources against buy box criteria
- [ ] Return structured null on no match — `status`, `reason`, `criteria_tested`, `markets_searched`
- [ ] Handle search failures gracefully — never crash the orchestrator
- [ ] Test against demo scenario (Phoenix-Mesa-Chandler industrial)

---

### Person 2 — sealer.py (Stage 5–6 — LOI + Negotiation)

**File:** `ai/sealer.py`

**What you build:**
- `sealer.draft_loi(bid: dict) -> dict` — takes the bid object from state and drafts LOI terms
- `sealer.negotiate(loi_status: dict) -> dict` — handles counter-offer logic; returns updated `loi_status`
- Hard stop: human approval is required before any LOI is sent

**Done looks like:** `sealer.draft_loi()` produces clean LOI terms from the demo bid. `sealer.negotiate()` handles a counter-offer and updates `loi_status` correctly. Human checkpoint fires before anything leaves the system.

**Checklist:**
- [ ] Read bid and loi_status field shapes from `ARCHITECTURE.md`
- [ ] Write `sealer.draft_loi()` — produces LOI terms from bid object
- [ ] Wire human approval checkpoint before LOI send
- [ ] Write `sealer.negotiate()` — margin holds → auto-counter, margin gone → auto-withdraw
- [ ] Test against demo scenario bid

---

### Person 3 — State schema + orchestrator updates (main.py)

**File:** `main.py`

**What you build:**
- Initialize the full state object at Stage 1 (all 8 fields — see `ARCHITECTURE.md`)
- Update `main.py` to pass state through all 6 stages in sequence
- Wire Stage 3 parallel subagent calls (FRED, Census, Tavily fire simultaneously)

**Done looks like:** `main.py` initializes a complete state object, sequences all 6 stages, and passes the correct state slice to each agent at each handoff.

**Checklist:**
- [ ] Define state object with all 8 fields from `ARCHITECTURE.md`
- [ ] Update main loop to sequence Stages 1–6
- [ ] Wire parallel calls for Stage 3 subagents
- [ ] Confirm each agent receives only the state fields it needs

---

### Person 4 — inspect_state() + park & monitor (main.py)

**File:** `main.py`

**What you build:**
- `inspect_state(state: dict) -> dict` — reads the error field and identifies which constraint failed
- Park & monitor loop — retries `finder.py` on schedule, increments `retry_count`
- Exit conditions: loosen buy box (flag human) or `retry_count ≥ max` (alert human, stop)

**Done looks like:** When `finder.py` returns a no-match, `inspect_state()` correctly identifies the blocking constraint. The retry loop increments `retry_count` and stops cleanly at max without looping forever.

**Checklist:**
- [ ] Write `inspect_state()` — reads error field, returns diagnosis
- [ ] Wire park & monitor retry loop with `retry_count` increment
- [ ] Implement exit conditions — buy box loosen path and max retry path
- [ ] Test no-match scenario end-to-end

---

### Person 5 — Integration + end-to-end testing

**What you own:**
- Run the full 6-stage pipeline against the demo scenario
- Verify all state handoffs are clean — no missing fields, no wrong shapes
- Confirm human checkpoints fire correctly at Stage 4 and Stage 5–6
- Confirm park & monitor loop exits cleanly

**Done looks like:** `python main.py` runs the full v2 loop against the Phoenix-Mesa-Chandler demo scenario without errors. All stage transitions produce correct state. Human checkpoints fire. Park & monitor exits cleanly on no-match.

**Checklist:**
- [ ] Run full loop against demo scenario
- [ ] Verify state object at each stage transition
- [ ] Test human checkpoint — approve path and kill path
- [ ] Test no-match path — park & monitor loop and max retry exit
- [ ] Confirm `ruff check .` and `bandit` pass on all new files

---

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
