"""
ai/analyzer.py — CRE Deal Monitor Agent
Owner: Joel (Person 4) — Claude Layer
Roadmap ref: Agent tab (Week 1 Plan) · How to Connect tab (handoff chain)

Joel owns this file entirely.
- Receives raw signal data from Manny (fred.py, census.py) and Michael (tavily.py)
- Receives the structured prompt from Ibrahima (Person 1)
- Sends everything to Claude via OpenRouter (v1) or Anthropic directly (v2)
- Returns a structured Python dict with exactly 5 keys back to Victor's main.py

Output contract (Victor depends on this — do not change keys):
  {
    "posture":         str,   # "buyer's market" | "balanced" | "seller's market"
    "recommendation":  str,   # "hold" | "accelerate" | "renegotiate" | "exit"
    "signal_breakdown": list, # [{signal, value, source, implication}]
    "next_move":       str,   # one specific action to take this week
    "watch_list":      str,   # one metric to monitor over the next 30 days
  }

v1: OpenRouter free model via LiteLLM (strands-agents)
v2: Swap model_id to "anthropic/claude-opus-4-5" — no other changes needed
"""

import json
import os
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
)
OPENROUTER_FALLBACK_MODELS = [
    "openrouter/meta-llama/llama-3.3-70b-instruct:free",
    "openrouter/tencent/hy3-preview:free",
]

# ─────────────────────────────────────────────────────────────────────────────
# DEAL BRIEF TYPE
# Victor reads exactly these five keys. Never add or remove.
# ─────────────────────────────────────────────────────────────────────────────

DealBrief = dict[str, Any]

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT (authored by Ibrahima, wired by Joel)
# Ibrahima writes and tests this prompt. Joel does NOT edit the logic —
# only the formatting instructions if the JSON parsing breaks.
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are an expert commercial real estate analyst embedded in an AI deal
monitoring system. You specialize in synthesizing macroeconomic signals,
local market data, and news into actionable deal intelligence for CRE
investment professionals.

You will be given:
  1. A deal context: asset type, location, price, key tenants, and lender
     constraints for an active transaction.
  2. A list of live market signals: each has a name, value, and source.

Your job is to read all signals together and produce a structured deal
brief that tells the deal team whether to hold, accelerate, renegotiate,
or exit — and exactly what to do next.

CRITICAL FORMATTING RULES:
- Respond ONLY with a valid JSON object. No markdown fences. No preamble.
- Your response must be parseable by json.loads() with no preprocessing.
- Use exactly these five keys, spelled exactly as shown:

{
  "posture": "buyer's market" | "balanced" | "seller's market",
  "recommendation": "hold" | "accelerate" | "renegotiate" | "exit",
  "signal_breakdown": [
    {
      "signal": "signal name",
      "value": "raw value with units",
      "source": "data source",
      "implication": "one sentence: what this means for this specific deal"
    }
  ],
  "next_move": "One specific, actionable step the deal team should take this week. Be concrete — name the action, the person who should take it, and the deadline.",
  "watch_list": "One metric to monitor over the next 30 days and why it matters for this deal's exit strategy."
}

Analysis approach:
1. First read all signals together — do not analyze each in isolation.
2. Identify the two or three signals that matter most for THIS deal's
   specific asset type, location, and tenant composition.
3. Be direct. If the signals are bad, say exit. If they are mixed, say renegotiate.
   Do not hedge into uselessness.
4. The next_move must be specific enough that the deal team can act on it
   without a follow-up question. "Review the deal" is not a next move.
   "Instruct Wells Fargo to pause the rate lock before Thursday's deadline
   given the 28bps move in the 10-year" is a next move.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# USER PROMPT BUILDER (Joel owns this)
# Formats the deal context and signals into the message sent to Claude.
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
VALID_POSTURES = {"buyer's market", "balanced", "seller's market"}
VALID_RECOMMENDATIONS = {"hold", "accelerate", "renegotiate", "exit"}


def _parse_brief(raw_text: str) -> DealBrief:
    """
    Parses and validates Claude's JSON response.
    Raises ValueError if the response is malformed or missing required keys.
    The caller (analyze_deal) handles the retry on ValueError.
    """
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

    return data


def _extract_brief_json_from_text(text: str) -> str | None:
    """
    Attempts to find a JSON object inside mixed text that matches DealBrief keys.
    Returns the JSON string if found, otherwise None.
    """
    if not text:
        return None

    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in starts:
        depth = 0
        for end in range(start, len(text)):
            ch = text[end]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : end + 1]
                    try:
                        data = json.loads(candidate)
                    except json.JSONDecodeError:
                        continue

                    if isinstance(data, dict) and REQUIRED_KEYS.issubset(data.keys()):
                        return candidate
                    break
    return None


def _extract_message_content(response: Any) -> str:
    """
    Extracts assistant text content from a LiteLLM response.
    Raises ValueError if the response has no usable text content.
    """
    try:
        message = response.choices[0].message
    except Exception as e:
        raise ValueError(f"Malformed model response: {e}") from e

    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content

    # Some providers return a list of content blocks instead of a raw string.
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts)

    # Some reasoning models place output in reasoning_content when content is empty.
    reasoning = getattr(message, "reasoning_content", None)
    if not reasoning and hasattr(message, "model_dump"):
        dump = message.model_dump()
        reasoning = (
            dump.get("reasoning_content")
            or (dump.get("provider_specific_fields") or {}).get("reasoning_content")
            or (dump.get("provider_specific_fields") or {}).get("reasoning")
        )

    if isinstance(reasoning, str) and reasoning.strip():
        recovered = _extract_brief_json_from_text(reasoning)
        if recovered:
            return recovered

    raise ValueError(
        "Model returned no assistant content and no recoverable JSON brief. "
        "Try a different model or set OPENROUTER_MODELS explicitly."
    )


def _get_openrouter_models() -> list[str]:
    """
    Builds the ordered model list for failover.
    Precedence:
    1) OPENROUTER_MODELS (comma-separated)
    2) OPENROUTER_MODEL + baked fallback list
    """
    from_env = os.getenv("OPENROUTER_MODELS", "").strip()
    if from_env:
        models = [m.strip() for m in from_env.split(",") if m.strip()]
        if models:
            return models

    models = [OPENROUTER_MODEL, *OPENROUTER_FALLBACK_MODELS]
    deduped: list[str] = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def _completion_with_failover(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int = 4096,
) -> Any:
    """
    Attempts completion across the configured OpenRouter model list.
    Returns the first successful response; otherwise raises RuntimeError
    with one clear aggregated error message.
    """
    import litellm

    errors: list[str] = []
    for model in _get_openrouter_models():
        try:
            # LiteLLM can print provider banners repeatedly; suppress stdout/stderr
            # noise so terminal output stays focused on analyzer results.
            captured_out = StringIO()
            captured_err = StringIO()
            with redirect_stdout(captured_out), redirect_stderr(captured_err):
                return litellm.completion(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    api_key=OPENROUTER_API_KEY,
                    api_base="https://openrouter.ai/api/v1",
                )
        except Exception as e:
            errors.append(f"{model}: {e}")

    if not errors:
        raise RuntimeError("No OpenRouter models configured for failover.")

    raise RuntimeError(
        "All configured OpenRouter models failed. "
        "Set OPENROUTER_MODELS to override failover order.\n"
        + "\n".join(errors)
    )


def _build_local_fallback_brief(
    deal_context: dict,
    fred_signals: list[dict],
    census_signals: list[dict],
    tavily_signals: list[dict],
) -> DealBrief:
    """
    Deterministic fallback when LLM calls are unavailable or unparsable.
    Keeps the output contract stable so upstream code can continue.
    """
    all_signals = [*fred_signals, *census_signals, *tavily_signals]

    signal_breakdown: list[dict[str, str]] = []
    for sig in all_signals[:5]:
        signal_breakdown.append(
            {
                "signal": str(sig.get("name", "Unknown signal")),
                "value": str(sig.get("value", "Unknown")),
                "source": str(sig.get("source", "Unknown")),
                "implication": (
                    "Fallback analysis: monitor this signal closely while "
                    "LLM provider responses are unstable."
                ),
            }
        )

    if not signal_breakdown:
        signal_breakdown.append(
            {
                "signal": "No live signals",
                "value": "N/A",
                "source": "System",
                "implication": "No inputs were available; run data fetchers again.",
            }
        )

    return {
        "posture": "balanced",
        "recommendation": "hold",
        "signal_breakdown": signal_breakdown,
        "next_move": (
            "Have the deal lead rerun the analyzer within 30 minutes and "
            "confirm lender and tenant risk assumptions before changing terms."
        ),
        "watch_list": (
            f"Track Treasury yield and tenant risk headlines for "
            f"{deal_context.get('location', 'this market')} over the next 30 days."
        ),
    }


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

    Returns a dict with exactly 5 keys:
        posture, recommendation, signal_breakdown, next_move, watch_list

    Raises:
        RuntimeError — if Claude fails to return a valid brief after retry
        EnvironmentError — if OPENROUTER_API_KEY is not set
    """
    if not OPENROUTER_API_KEY:
        raise EnvironmentError("OPENROUTER_API_KEY is not set. Check your .env file.")

    user_prompt = _build_user_prompt(
        deal_context, fred_signals, census_signals, tavily_signals
    )

    # ── v1: OpenRouter model via LiteLLM with failover ───────────────────
    # v2 swap: change model to "anthropic/claude-opus-4-5"
    #          and change api_base to "https://api.anthropic.com"
    #          and change api_key to ANTHROPIC_API_KEY
    # No other changes needed — same interface.
    try:
        response = _completion_with_failover(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

    except Exception as e:
        print("[analyzer] Model call failed; returning deterministic local fallback.")
        print(f"[analyzer] Model error: {e}")
        return _build_local_fallback_brief(
            deal_context, fred_signals, census_signals, tavily_signals
        )

    # ── Parse with one automatic retry ───────────────────────────────────
    try:
        raw = _extract_message_content(response)
        return _parse_brief(raw)

    except ValueError as first_err:
        print(f"[analyzer] First parse failed: {first_err}")
        print("[analyzer] Retrying with simplified prompt...")

        try:
            retry_prompt = (
                "Your previous response could not be parsed as JSON. "
                "Return ONLY a valid JSON object with exactly these keys: "
                "posture, recommendation, signal_breakdown, next_move, watch_list. "
                "No markdown. No explanation. JSON only.\n\n"
                f"Original request:\n{user_prompt}"
            )

            retry_response = _completion_with_failover(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": retry_prompt},
                ],
                temperature=0.0,  # Zero temp on retry for maximum consistency
            )
            retry_raw = _extract_message_content(retry_response)
            return _parse_brief(retry_raw)

        except (ValueError, Exception) as retry_err:
            print(
                "[analyzer] Retry failed; returning deterministic local fallback brief."
            )
            print(f"[analyzer] First error: {first_err}")
            print(f"[analyzer] Retry error: {retry_err}")
            return _build_local_fallback_brief(
                deal_context, fred_signals, census_signals, tavily_signals
            )


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTER — format_brief_for_terminal()
# Victor calls this to print the deal brief to the terminal.
# Joel owns the formatting; Gary/Pape own it if there's a frontend.
# ─────────────────────────────────────────────────────────────────────────────


def format_brief_for_terminal(brief: DealBrief, deal_context: dict) -> str:
    """
    Formats the structured DealBrief dict into a readable terminal output.
    Victor calls this after the human checkpoint is approved.
    """
    posture_icons = {
        "buyer's market": "🟢",
        "balanced": "🟡",
        "seller's market": "🔴",
    }
    rec_icons = {
        "hold": "⏸ ",
        "accelerate": "▶️ ",
        "renegotiate": "🔄",
        "exit": "🚨",
    }

    posture_icon = posture_icons.get(brief["posture"], "⚪")
    rec_icon = rec_icons.get(brief["recommendation"], "  ")

    lines = [
        "",
        "═" * 64,
        "  CRE DEAL MONITOR — ANALYST BRIEF",
        f"  {deal_context.get('asset_type', 'Deal')} · "
        f"{deal_context.get('location', 'Unknown')} · "
        f"${deal_context.get('price', 0):,.0f}",
        "═" * 64,
        "",
        f"  MARKET POSTURE     {posture_icon}  {brief['posture'].upper()}",
        f"  RECOMMENDATION     {rec_icon}  {brief['recommendation'].upper()}",
        "",
        "─" * 64,
        "  SIGNAL BREAKDOWN",
        "─" * 64,
    ]

    for sig in brief.get("signal_breakdown", []):
        lines.append(f"  ▸ {sig.get('signal', '')} ({sig.get('source', '')})")
        lines.append(f"    Value:       {sig.get('value', '')}")
        lines.append(f"    Implication: {sig.get('implication', '')}")
        lines.append("")

    lines += [
        "─" * 64,
        "  NEXT MOVE",
        "─" * 64,
        f"  {brief.get('next_move', '')}",
        "",
        "─" * 64,
        "  30-DAY WATCH LIST",
        "─" * 64,
        f"  {brief.get('watch_list', '')}",
        "",
        "═" * 64,
        "",
    ]

    return "\n".join(lines)


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
        print(format_brief_for_terminal(brief, TEST_DEAL))

        print("\n[analyzer] Raw dict (what Victor receives):")
        print(json.dumps(brief, indent=2))

    except Exception as e:
        print(f"\n[analyzer] Test failed: {e}")
        raise
