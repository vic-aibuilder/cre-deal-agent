"""
ui/terminal.py — Terminal display for CRE Deal Monitor
Moved from ai/analyzer.py for clean separation of concerns.

Formats the structured DealBrief dict into readable terminal output.
Victor's main.py calls format_brief_for_terminal() after the human checkpoint.
"""

from typing import Any

DealBrief = dict[str, Any]


def format_brief_for_terminal(brief: DealBrief, deal_context: dict) -> str:
    """
    Formats the structured DealBrief dict into a readable terminal output.
    Victor calls this after the human checkpoint is approved.

    Supports both v1 (5-key) and v2 (7-key) DealBrief formats.
    v2 adds confidence and rationale — displayed if present, skipped if not.
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
    ]

    # ── v2: confidence and rationale (displayed if present) ───────────
    if "confidence" in brief:
        conf = brief["confidence"]
        bar_filled = round(conf * 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        lines.append(f"  CONFIDENCE         {bar}  {conf:.0%}")
    if "rationale" in brief:
        lines.append(f"  RATIONALE          {brief['rationale']}")

    lines += [
        "",
        "─" * 64,
        "  SIGNAL BREAKDOWN",
        "─" * 64,
    ]

    for sig in brief.get("signal_breakdown", []):
        lines.append(f"  ▸ {sig.get('name', '')} ({sig.get('source', '')})")
        lines.append(f"    Value: {sig.get('value', '')}")
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
