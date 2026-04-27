# Agent Guidelines — cre-deal-agent

## Run commands

- `python main.py` — run the agent
- `pip install -r requirements.txt` — install dependencies
- `ruff check .` — lint all Python files
- `ruff format .` — format all Python files
- `bandit -r . --exclude .venv` — security scan
- `python -m py_compile fetchers/fred.py fetchers/census.py fetchers/tavily.py ai/analyzer.py main.py` — verify all files import without errors

**Important:** Always run `ruff check .` before opening a PR. Fix all lint errors before pushing.

## Code style

- Python only — no type: ignore comments unless unavoidable
- Use type hints on all function signatures
- Use f-strings for string formatting
- Use `snake_case` for all variable and function names
- No classes — functions only
- Return early with guard clauses rather than deep nesting
- Each fetcher function must return a list of signal dicts — never a raw API response

## Branch naming

Format: `feat/cre-{issue-id}-{short-description}`

Allowed prefixes: `feat/`, `fix/`, `chore/`, `test/`, `docs/`

Direct pushes to `main` are blocked. All changes go through a PR with 1 required approval.

Examples:
- `feat/cre-1-fred-fetcher`
- `feat/cre-2-census-fetcher`
- `feat/cre-3-tavily-fetcher`
- `feat/cre-4-analyzer`
- `feat/cre-5-main-loop`

## File ownership

Nobody touches another person's file without asking first.

| File | Owner |
|---|---|
| `main.py` | Victor |
| `fetchers/fred.py` | Manny |
| `fetchers/census.py` | Manny |
| `fetchers/tavily.py` | Michael |
| `ai/analyzer.py` | Ibrahima (prompt) + Joel (API call) |
| `.env.example` | Victor |
| `docs/PRD.md` | Victor (updates require team sign-off) |

## Data contracts

All fetchers must return a list of signal dicts matching this exact shape:

```python
{"name": str, "value": str, "source": str}
```

`analyzer.analyze()` must return a DealBrief dict matching this exact shape:

```python
{
    "posture":          str,
    "recommendation":  str,
    "signal_breakdown": list,
    "next_move":        str,
    "watch_list":       str
}
```

See `docs/PRD.md §7` for full contract details.

## Shared file coordination

`ai/analyzer.py` is modified by Ibrahima (prompt) and Joel (API call). Coordinate who pushes first — the second person must rebase, not merge.

## PR checklist

- [ ] Branch name follows `feat/cre-{id}-{description}` format
- [ ] `ruff check .` passes with no errors
- [ ] `bandit -r . --exclude .venv` passes with no high-severity findings
- [ ] `python -m py_compile` passes on all files you touched
- [ ] Return shape matches the contract in `docs/PRD.md §7`
- [ ] Tested against the demo scenario (Phoenix-Mesa-Chandler industrial)
- [ ] PR title is semantic: `feat: ...` / `fix: ...` / `chore: ...`
- [ ] PR targets `main`
