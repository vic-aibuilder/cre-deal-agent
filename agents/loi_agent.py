"""
agents/loi_agent.py — Letter of Intent generation agent.

Generates LOI PDFs from deal state and sends via EmailAgent.
Uses reportlab for PDF generation.

Build 2, Sprint 3.
"""

from __future__ import annotations

import time
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# LOI TERMS CALCULATOR
# Derives LOI terms from analyzer output and mandate.
# ─────────────────────────────────────────────────────────────────────────────


def calculate_dd_period(analysis: dict[str, Any]) -> int:
    """
    Determine due diligence period length based on risk signals.
    Longer DD if elevated risk detected.

    Args:
        analysis: the DealBrief from the analyzer

    Returns:
        DD period in days (30 or 45)
    """
    confidence = analysis.get("confidence", 1.0)
    posture = analysis.get("negotiation_posture", "measured")

    # Low confidence or cautious posture = longer DD
    if confidence < 0.60:
        return 45
    if posture == "cautious":
        return 45
    return 30


def calculate_earnest_money(offer_price: float) -> float:
    """Standard earnest money: 1% of offer price."""
    return round(offer_price * 0.01)


def calculate_offer_price(
    analysis: dict[str, Any],
    deal_context: dict[str, Any],
    mandate: dict[str, Any],
) -> float:
    """
    Derive the offer price from analyzer output and mandate constraints.

    Priority:
    1. Use bid_floor_usd from analyzer if available (Claude's DSCR-derived floor)
    2. Otherwise, discount asking price based on recommendation
    3. Never exceed mandate absolute_max_price

    Returns:
        Offer price in dollars, rounded to nearest $100k
    """
    max_price = mandate.get("absolute_max_price", float("inf"))
    asking = deal_context.get("price", 0)

    # Use Claude's bid floor if available
    bid_floor = analysis.get("bid_floor_usd")
    bid_ceiling = analysis.get("bid_ceiling_usd")

    if bid_floor and bid_ceiling:
        # Start at midpoint of Claude's range
        offer = (bid_floor + bid_ceiling) / 2
    else:
        # Fallback: discount based on recommendation
        rec = analysis.get("recommendation", "hold")
        discounts = {
            "accelerate": 0.02,  # 2% below asking — competitive
            "renegotiate": 0.08,  # 8% below asking — leverage
            "hold": 0.10,  # 10% below — cautious
            "exit": 0.15,  # 15% below — defensive if still bidding
        }
        discount = discounts.get(rec, 0.08)
        offer = asking * (1 - discount)

    # Never exceed mandate max
    offer = min(offer, max_price)

    # Round to nearest $100k
    return round(offer / 100_000) * 100_000


def build_loi_terms(
    analysis: dict[str, Any],
    deal_context: dict[str, Any],
    mandate: dict[str, Any],
) -> dict[str, Any]:
    """
    Build complete LOI terms from analyzer output, deal context, and mandate.

    Returns:
        Dict with all LOI fields ready for PDF generation and email.
    """
    offer_price = calculate_offer_price(analysis, deal_context, mandate)
    earnest_money = calculate_earnest_money(offer_price)
    dd_period = calculate_dd_period(analysis)

    return {
        "offer_price": offer_price,
        "earnest_money": earnest_money,
        "dd_period_days": dd_period,
        "closing_days": 45,
        "financing_contingency": False,  # assume all-cash for now
        "as_is_purchase": True,
        "expiration_hours": 72,
        "governing_law_state": _extract_state(deal_context),
    }


def _extract_state(deal_context: dict[str, Any]) -> str:
    """Extract state abbreviation from deal location. Defaults to AZ."""
    location = deal_context.get("location", "")
    # Simple mapping for demo — expand as submarkets are added
    state_map = {
        "phoenix": "AZ",
        "atlanta": "GA",
        "dallas": "TX",
        "los angeles": "CA",
        "miami": "FL",
    }
    location_lower = location.lower()
    for city, abbrev in state_map.items():
        if city in location_lower:
            return abbrev
    return "AZ"


# ─────────────────────────────────────────────────────────────────────────────
# LOI PDF GENERATION (text-based for now, reportlab upgrade in Sprint 4)
# ─────────────────────────────────────────────────────────────────────────────


def generate_loi_text(
    loi_terms: dict[str, Any],
    deal_context: dict[str, Any],
    buyer_config: dict[str, Any] | None = None,
) -> str:
    """
    Generate a formatted LOI document as text.
    This is the content that would go into a PDF.

    Args:
        loi_terms: from build_loi_terms()
        deal_context: deal details
        buyer_config: buyer entity details

    Returns:
        Formatted LOI text
    """
    buyer = buyer_config or {
        "buyer_entity": "Mesa Capital Partners LLC",
        "buyer_principal": "Joel Martinez",
    }

    return f"""
LETTER OF INTENT

Date: {time.strftime("%B %d, %Y")}

BUYER:          {buyer.get("buyer_entity", "TBD")}
SELLER:         [Seller Entity Name]

PROPERTY:       {deal_context.get("asset_type", "Industrial")}
                {deal_context.get("location", "Unknown")}

PURCHASE PRICE: ${loi_terms["offer_price"]:,.0f}

EARNEST MONEY:  ${loi_terms["earnest_money"]:,.0f}
                To be deposited within five (5) business days of
                mutual execution of this Letter of Intent.

DUE DILIGENCE:  {loi_terms["dd_period_days"]} days from effective date.
                Buyer may terminate for any reason during the
                due diligence period and receive a full refund
                of earnest money.

CLOSING:        {loi_terms["closing_days"]} days from effective date.

FINANCING:      {"No financing contingency — all cash." if not loi_terms.get("financing_contingency") else "Subject to financing."}

CONDITION:      {"As-is, where-is." if loi_terms.get("as_is_purchase") else "Subject to satisfactory inspection."}

EXPIRATION:     This Letter of Intent expires {loi_terms["expiration_hours"]}
                hours from the timestamp of transmission.

GOVERNING LAW:  State of {loi_terms.get("governing_law_state", "AZ")}

This Letter of Intent is non-binding except for the provisions
regarding confidentiality and exclusivity. A binding Purchase and
Sale Agreement will be negotiated upon acceptance of this LOI.

BUYER:
{buyer.get("buyer_entity", "TBD")}
By: {buyer.get("buyer_principal", "TBD")}

SELLER:
[Signature]
[Printed Name]
[Date]
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-LEVEL FUNCTION — what the orchestrator calls
# ─────────────────────────────────────────────────────────────────────────────


def prepare_loi(
    analysis: dict[str, Any],
    deal_context: dict[str, Any],
    mandate: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Full LOI pipeline: calculate terms → generate document → log to state.

    Args:
        analysis: DealBrief from analyzer
        deal_context: deal details
        mandate: negotiation mandate
        state: pipeline state object

    Returns:
        Dict with loi_terms, loi_text, and metadata
    """
    from state import log_action

    loi_terms = build_loi_terms(analysis, deal_context, mandate)
    loi_text = generate_loi_text(loi_terms, deal_context)

    result = {
        "terms": loi_terms,
        "text": loi_text,
        "generated_at": time.time(),
        "status": "generated",
    }

    # Update state
    state["loi"] = result
    log_action(
        state,
        agent="loi_agent",
        action="generated_loi",
        details={
            "offer_price": loi_terms["offer_price"],
            "dd_period_days": loi_terms["dd_period_days"],
            "closing_days": loi_terms["closing_days"],
        },
    )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from state import create_state, create_mandate

    print("[loi_agent] Running standalone test...\n")

    test_deal = {
        "asset_type": "Industrial, 412k sqft",
        "location": "Phoenix-Mesa-Chandler",
        "price": 95_000_000.0,
        "cap_rate": "5.8%",
        "tenants": "Amazon · 65% of NOI",
    }

    test_analysis = {
        "posture": "buyer's market",
        "recommendation": "renegotiate",
        "confidence": 0.82,
        "bid_floor_usd": 82_000_000,
        "bid_ceiling_usd": 88_000_000,
        "negotiation_posture": "aggressive",
        "loi_urgency": "submit_within_72h",
    }

    mandate = create_mandate(absolute_max_price=100_000_000)
    state = create_state(deal_context=test_deal)

    result = prepare_loi(test_analysis, test_deal, mandate, state)

    print("═" * 60)
    print("  LOI TERMS")
    print("═" * 60)
    for k, v in result["terms"].items():
        if isinstance(v, float) and v > 1000:
            print(f"  {k:25s} ${v:,.0f}")
        else:
            print(f"  {k:25s} {v}")

    print("\n" + "═" * 60)
    print("  LOI DOCUMENT")
    print("═" * 60)
    print(result["text"])

    print(f"\n  State: LOI status = {state['loi']['status']}")
    print(f"  State: {len(state['audit_log'])} audit entries")
    print("\n[loi_agent] Standalone test complete.")
