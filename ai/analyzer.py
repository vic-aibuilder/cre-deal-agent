"""ai/analyzer.py — CRE Deal Monitor Agent
Owner: Joel (Person 4) — Claude Layer
Roadmap ref: Agent tab (Week 1 Plan) · How to Connect tab (handoff chain)

Joel owns this file entirely.
- Receives raw signal data from Manny (fred.py, census.py) and Michael (tavily.py)
- Receives the structured prompt from Ibrahima (Person 1)
- Sends everything to Claude via OpenRouter (v1) or Anthropic directly (v2)
- Returns a structured Python dict back to Victor's main.py

Output contract (Victor depends on this):
  Required keys (v1+v2 — never remove):
  {
    "posture":         str,   # "buyer's market" | "balanced" | "seller's market"
    "recommendation":  str,   # "hold" | "accelerate" | "renegotiate" | "exit"
    "signal_breakdown": list, # [{name, value, source}]
    "next_move":       str,   # one specific action to take this week
    "watch_list":      str,   # one metric to monitor over the next 30 days
  }
  Optional keys (v2 — present when model provides them):
  {
    "confidence":      float, # 0.0–1.0 — how confident the recommendation is
    "rationale":       str,   # why this recommendation over alternatives
  }

v1: OpenRouter free model via LiteLLM
v2: Swap model_id to "anthropic/claude-opus-4-5" — no other changes needed

Terminal formatting moved to ui/terminal.py in v2.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from pathlib import Path

from dotenv import load_dotenv
from ui.terminal import format_brief_for_terminal  # noqa: F401  # re-export for backward compat

# Resolve .env relative to this file's parent (project root: cre-deal-agent/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ─────────────────────────────────────────────────────────────────────────────
# DEAL BRIEF TYPE
# Victor reads the 5 required keys. v2 adds 2 optional keys.
# ─────────────────────────────────────────────────────────────────────────────

DealBrief = dict[str, Any]

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT (authored by Ibrahima, wired by Joel)
# Ibrahima writes and tests the prompt. Joel does NOT edit the logic —
# only the formatting instructions if the JSON parsing breaks.
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a senior commercial real estate data analyst specializing in
industrial assets. Your job is to analyze live market signals for an active
deal and return a structured JSON brief the deal team can act on immediately.
You must return only valid JSON. No explanation. No prose. No markdown.
Only the JSON object.

The JSON you return must match this exact schema with no extra keys and no
missing keys:

{
    "posture": "buyer's market" | "balanced" | "seller's market",
    "recommendation": "hold" | "accelerate" | "renegotiate" | "exit",
    "signal_breakdown": [{"name": str, "value": str, "source": str}],
    "next_move": str,
    "watch_list": str,
    "confidence": float between 0.0 and 1.0,
    "rationale": str — one sentence explaining why this recommendation over alternatives
}

Return only valid JSON matching this schema. No explanation. No extra keys.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# USER PROMPT BUILDER (Joel owns this)
# Formats the deal context and signals into the message sent to the model.
# Manny and Michael both return a list of dicts: [{name, value, source}]
# Joel merges them and formats them here.
# ─────────────────────────────────────────────────────────────────────────────


def _build_user_prompt(
    deal_context: dict,
    fred_signals: list[dict],
    census_signals: list[dict],
    tavily_signals: list[dict],
) -> str:
    """
    Merges all signal sources into a single formatted prompt string.
    Called internally by analyze_deal().

    deal_context keys (from Victor's main.py):
        asset_type, location, price, tenants, lender, dscr_constraint, cap_rate

    Signal format (from Manny + Michael):
        [{name: str, value: str | float, source: str}]
    """
    all_signals = []

    for sig in fred_signals:
        all_signals.append(f"- [{sig['source']}] {sig['name']}: {sig['value']}")
    for sig in census_signals:
        all_signals.append(f"- [{sig['source']}] {sig['name']}: {sig['value']}")
    for sig in tavily_signals:
        all_signals.append(f"- [{sig['source']}] {sig['name']}: {sig['value']}")

    signal_block = "\n".join(all_signals) if all_signals else "No signals available."

    deal_block = (
        f"Asset type:       {deal_context.get('asset_type', 'Unknown')}\n"
        f"Location:         {deal_context.get('location', 'Unknown')}\n"
        f"Price:            ${deal_context.get('price', 0):,.0f}\n"
        f"Cap rate:         {deal_context.get('cap_rate', 'Unknown')}\n"
        f"Key tenants:      {deal_context.get('tenants', 'Unknown')}\n"
        f"Lender:           {deal_context.get('lender', 'Unknown')}\n"
        f"DSCR constraint:  {deal_context.get('dscr_constraint', 'Unknown')}"
    )

    return (
        f"ACTIVE DEAL:\n{deal_block}\n\n"
        f"LIVE MARKET SIGNALS ({len(all_signals)} total):\n{signal_block}\n\n"
        f"Produce the deal brief JSON now."
    )


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE PARSER (Joel owns this)
# Extracts and validates the JSON from Claude's response.
# If parsing fails, retries once with a simplified prompt before raising.
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_KEYS = {
    "posture",
    "recommendation",
    "signal_breakdown",
    "next_move",
    "watch_list",
}
OPTIONAL_KEYS = {"confidence", "rationale"}
VALID_POSTURES = {"buyer's market", "balanced", "seller's market"}
VALID_RECOMMENDATIONS = {"hold", "accelerate", "renegotiate", "exit"}


def _parse_brief(raw_text: str) -> DealBrief:
    """
    Parses and validates Claude's JSON response.
    Raises ValueError if the response is malformed or missing required keys.
    v2 optional keys (confidence, rationale) are kept if present but not required.
    The caller (analyze_deal) handles the retry on ValueError.
    """
    # Guard against empty responses from free-tier models
    if not raw_text:
        raise ValueError("Model returned empty response (no content).")

    # Strip any accidental markdown fences the model may have added
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON decode failed: {e}\nRaw response: {text[:500]}")

    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Response missing required keys: {missing}")

    if data["posture"] not in VALID_POSTURES:
        raise ValueError(
            f"Invalid posture: '{data['posture']}'. Must be one of: {VALID_POSTURES}"
        )
    if data["recommendation"] not in VALID_RECOMMENDATIONS:
        raise ValueError(
            f"Invalid recommendation: '{data['recommendation']}'. "
            f"Must be one of: {VALID_RECOMMENDATIONS}"
        )
    if not isinstance(data["signal_breakdown"], list):
        raise ValueError("signal_breakdown must be a list.")

    # v2: validate confidence range if present
    if "confidence" in data:
        try:
            conf = float(data["confidence"])
            data["confidence"] = max(0.0, min(1.0, conf))  # clamp to [0, 1]
        except (TypeError, ValueError):
            data.pop("confidence", None)  # drop malformed confidence

    # Strip any extra keys the model hallucinated beyond required + optional
    allowed_keys = REQUIRED_KEYS | OPTIONAL_KEYS
    data = {k: v for k, v in data.items() if k in allowed_keys}

    return data


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION — analyze_deal()
# This is what Victor's main.py calls.
# Joel is responsible for this function's interface and reliability.
# ─────────────────────────────────────────────────────────────────────────────


def analyze_deal(
    deal_context: dict,
    fred_signals: list[dict],
    census_signals: list[dict],
    tavily_signals: list[dict],
) -> DealBrief:
    """
    Core analyzer function. Takes all fetched signals and the deal context,
    sends them to Claude, and returns a structured deal brief.

    Called by: Victor's main.py
    Receives from: Manny (fred_signals, census_signals), Michael (tavily_signals)
    Prompt by: Ibrahima (SYSTEM_PROMPT above)

    Returns a dict with 5 required keys + up to 2 optional v2 keys:
        Required: posture, recommendation, signal_breakdown, next_move, watch_list
        Optional: confidence (float 0-1), rationale (str)

    Raises:
        RuntimeError — if Claude fails to return a valid brief after retry
        EnvironmentError — if OPENROUTER_API_KEY is not set
    """
    if not OPENROUTER_API_KEY:
        raise EnvironmentError("OPENROUTER_API_KEY is not set. Check your .env file.")

    import litellm

    # LiteLLM reads OPENROUTER_API_KEY from env automatically
    # when using the openrouter/ model prefix.
    os.environ["OPENROUTER_API_KEY"] = OPENROUTER_API_KEY

    user_prompt = _build_user_prompt(
        deal_context, fred_signals, census_signals, tavily_signals
    )

    # ── v2: Claude Sonnet 4 via OpenRouter ─────────────────────────────
    # v1 was: "openrouter/openrouter/auto" (free-tier, unreliable)
    # v2 uses Anthropic's Claude for precise JSON and deeper reasoning.
    model_id = "openrouter/anthropic/claude-sonnet-4"

    # ── Retry loop: handles rate limits, content filters, empty responses ─
    max_retries = 3
    backoff_seconds = 2
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            # On retry after parse failure, use a simplified prompt
            if attempt > 1 and last_error and isinstance(last_error, ValueError):
                print(
                    f"[analyzer] Attempt {attempt}/{max_retries} — retrying with simplified prompt..."
                )
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Your previous response could not be parsed as JSON. "
                            "Return ONLY a valid JSON object with exactly these keys: "
                            "posture, recommendation, signal_breakdown, next_move, "
                            "watch_list, confidence, rationale. "
                            "No markdown. No explanation. JSON only.\n\n"
                            f"Original request:\n{user_prompt}"
                        ),
                    },
                ]
                temperature = 0.0  # Zero temp on retry for maximum consistency
            else:
                if attempt > 1:
                    print(f"[analyzer] Attempt {attempt}/{max_retries} — retrying...")
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
                temperature = 0.2

            response = litellm.completion(
                model=model_id,
                messages=messages,
                max_tokens=2048,
                temperature=temperature,
            )

            raw = response.choices[0].message.content
            return _parse_brief(raw)

        except ValueError as e:
            # Parse failure — retry with simplified prompt
            last_error = e
            print(f"[analyzer] Parse failed on attempt {attempt}: {e}")

        except Exception as e:
            # Rate limit, content filter, or network error — backoff and retry
            last_error = e
            err_str = str(e).lower()
            is_retryable = any(
                keyword in err_str
                for keyword in ["429", "rate", "content", "filter", "loop", "flagged"]
            )

            if is_retryable and attempt < max_retries:
                wait = backoff_seconds * (2 ** (attempt - 1))
                print(f"[analyzer] Retryable error on attempt {attempt}: {e}")
                print(f"[analyzer] Waiting {wait}s before retry...")
                time.sleep(wait)
            elif not is_retryable:
                raise RuntimeError(f"API call failed (non-retryable): {e}") from e

    raise RuntimeError(
        f"Analyzer failed after {max_retries} attempts.\nLast error: {last_error}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTER — moved to ui/terminal.py in v2
# Kept as a re-export for backward compatibility with main.py imports.
# ─────────────────────────────────────────────────────────────────────────────

# Re-exported at top of file: from ui.terminal import format_brief_for_terminal


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST (Joel uses this for D3–D4 integration testing)
# Runs with hardcoded mock signals so Joel can test analyzer.py independently
# before Manny and Michael's fetchers are wired in.
# Victor does NOT call this — it is Joel's dev tool only.
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("[analyzer] Running standalone test with mock signals...")

    # ── Locked demo scenario (from roadmap "Agent Analyses" section) ──────
    TEST_DEAL = {
        "asset_type": "Industrial / Warehouse",
        "location": "Phoenix-Mesa-Chandler, AZ submarket",
        "price": 95_000_000,
        "cap_rate": "5.8%",
        "tenants": "Amazon (65% NOI), secondary tenants (35%)",
        "lender": "Wells Fargo",
        "dscr_constraint": "1.25x minimum",
    }

    # Mock FRED signals (what Manny returns from fred.py)
    MOCK_FRED = [
        {
            "name": "10-Year Treasury Yield",
            "value": "4.78% (+28bps this week)",
            "source": "FRED",
        },
        {"name": "30-Year Fixed Mortgage", "value": "7.12%", "source": "FRED"},
        {
            "name": "Phoenix Metro Employment",
            "value": "+2.1% YoY",
            "source": "FRED/BLS",
        },
        {
            "name": "Construction Spending",
            "value": "+4.3% MoM nationally",
            "source": "FRED",
        },
    ]

    # Mock Census signals (what Manny returns from census.py)
    MOCK_CENSUS = [
        {
            "name": "Phoenix Population Growth",
            "value": "+3.2% YoY (2nd fastest in US)",
            "source": "Census Bureau",
        },
        {
            "name": "Industrial Permits Filed",
            "value": "14 new permits, Maricopa County",
            "source": "Census BPS",
        },
    ]

    # Mock Tavily signals (what Michael returns from tavily.py)
    MOCK_TAVILY = [
        {
            "name": "Amazon Earnings Warning",
            "value": "AMZN Q3 earnings call flagged 'rightsizing' of logistics footprint",
            "source": "Tavily / CNBC",
        },
        {
            "name": "Prologis Phoenix Submarket Report",
            "value": "Industrial vacancy rising: 6.2% vs 4.1% a year ago",
            "source": "Tavily / Prologis 10-Q",
        },
    ]

    try:
        brief = analyze_deal(TEST_DEAL, MOCK_FRED, MOCK_CENSUS, MOCK_TAVILY)

        from ui.terminal import format_brief_for_terminal as fmt

        print(fmt(brief, TEST_DEAL))

        print("\n[analyzer] Raw dict (what Victor receives):")
        print(json.dumps(brief, indent=2))

        # v2: show confidence and rationale if present
        if "confidence" in brief:
            print(f"\n[analyzer] Confidence: {brief['confidence']:.0%}")
        if "rationale" in brief:
            print(f"[analyzer] Rationale: {brief['rationale']}")

    except Exception as e:
        print(f"\n[analyzer] Test failed: {e}")
        raise
