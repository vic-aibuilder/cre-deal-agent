"""
agents/negotiation_agent.py — Autonomous negotiation engine.

Evaluates counter-offers and decides whether to accept, counter, or walk.
Operates within pre-set mandate rails — no human in the loop.

Build 2, Sprint 3.
"""

from __future__ import annotations

import time
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# COUNTER-OFFER EVALUATION
# This is the core decision engine. It operates within mandate rails.
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_counter(
    counter: dict[str, Any],
    our_offer: dict[str, Any],
    mandate: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate a broker counter-offer and decide: accept, counter, or walk.

    Decision logic:
    1. Check walk triggers first — immediate exit if any detected
    2. Check if counter exceeds absolute price ceiling → walk
    3. Check price gap:
       - Within 2% of our offer → accept
       - Within 5% of our offer → counter at midpoint
       - Beyond 5% → walk
    4. Check non-price concessions against mandate limits

    Args:
        counter: broker's counter terms
            {price, dd_period_days, earnest_money_pct, closing_days, ...}
        our_offer: our current offer terms
            {offer_price, dd_period_days, earnest_money, closing_days, ...}
        mandate: negotiation mandate with max_concessions and walk_triggers

    Returns:
        {
            action: "accept" | "counter" | "walk",
            new_terms: dict (only if action is "counter"),
            reason: str,
            details: dict with gap_pct, counter_price, etc.
        }
    """
    counter_price = counter.get("price", 0)
    our_price = our_offer.get("offer_price", 0)
    ceiling = mandate.get("absolute_max_price", float("inf"))
    walk_triggers = mandate.get("walk_triggers", [])

    # ── Step 1: Check walk triggers ──────────────────────────────────────
    triggered = _check_walk_triggers(counter, walk_triggers)
    if triggered:
        return {
            "action": "walk",
            "new_terms": None,
            "reason": f"Walk trigger detected: {triggered}",
            "details": {"trigger": triggered, "counter_price": counter_price},
        }

    # ── Step 2: Check absolute ceiling ───────────────────────────────────
    if counter_price > ceiling:
        return {
            "action": "walk",
            "new_terms": None,
            "reason": f"Counter ${counter_price:,.0f} exceeds absolute ceiling ${ceiling:,.0f}",
            "details": {
                "counter_price": counter_price,
                "ceiling": ceiling,
                "excess": counter_price - ceiling,
            },
        }

    # ── Step 3: Evaluate price gap ───────────────────────────────────────
    if our_price <= 0:
        return {
            "action": "walk",
            "new_terms": None,
            "reason": "Invalid offer price — cannot evaluate gap",
            "details": {"our_price": our_price},
        }

    gap_pct = (counter_price - our_price) / our_price

    if gap_pct <= 0:
        # Counter is at or below our offer — accept immediately
        return {
            "action": "accept",
            "new_terms": counter,
            "reason": f"Counter at or below our offer (gap {gap_pct * 100:.1f}%)",
            "details": {"gap_pct": gap_pct, "counter_price": counter_price},
        }

    if gap_pct <= 0.02:
        # Within 2% — accept
        return {
            "action": "accept",
            "new_terms": counter,
            "reason": f"Within acceptance threshold (gap {gap_pct * 100:.1f}%)",
            "details": {"gap_pct": gap_pct, "counter_price": counter_price},
        }

    if gap_pct <= 0.05:
        # Within 5% — counter at midpoint
        midpoint = (counter_price + our_price) / 2
        midpoint = round(midpoint / 100_000) * 100_000  # round to $100k

        # Don't exceed ceiling
        midpoint = min(midpoint, ceiling)

        new_terms = {**our_offer, "offer_price": midpoint}
        return {
            "action": "counter",
            "new_terms": new_terms,
            "reason": f"Counter at midpoint ${midpoint:,.0f} (gap {gap_pct * 100:.1f}%)",
            "details": {
                "gap_pct": gap_pct,
                "counter_price": counter_price,
                "midpoint": midpoint,
            },
        }

    # Beyond 5% — walk
    return {
        "action": "walk",
        "new_terms": None,
        "reason": f"Gap {gap_pct * 100:.1f}% exceeds negotiation range (max 5%)",
        "details": {"gap_pct": gap_pct, "counter_price": counter_price},
    }


def _check_walk_triggers(
    counter: dict[str, Any],
    walk_triggers: list[str],
) -> str | None:
    """
    Check if any walk triggers are present in the counter terms.
    Returns the first triggered condition, or None.
    """
    flags = counter.get("flags", [])
    if isinstance(flags, str):
        flags = [flags]

    for trigger in walk_triggers:
        if trigger in flags:
            return trigger

    return None


# ─────────────────────────────────────────────────────────────────────────────
# CONCESSION EVALUATION
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_concessions(
    requested: dict[str, Any],
    mandate: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate non-price concession requests against mandate limits.

    Args:
        requested: broker's requested concessions
            {dd_extension_days, earnest_increase_pct, closing_extension_days, ...}
        mandate: negotiation mandate with max_concessions

    Returns:
        {
            grantable: list of concessions we can give,
            denied: list of concessions beyond limits,
            response: dict of actual values to grant
        }
    """
    max_c = mandate.get("max_concessions", {})
    grantable = []
    denied = []
    response = {}

    # DD extension
    dd_ext = requested.get("dd_extension_days", 0)
    max_dd = max_c.get("dd_period_days", 0)
    if dd_ext <= max_dd:
        grantable.append(f"DD extension: +{dd_ext} days")
        response["dd_extension_days"] = dd_ext
    elif dd_ext > 0:
        denied.append(f"DD extension: +{dd_ext} days (max {max_dd})")

    # Earnest money increase
    earnest_inc = requested.get("earnest_increase_pct", 0)
    max_earnest = max_c.get("earnest_money_pct", 0)
    if earnest_inc <= max_earnest:
        grantable.append(f"Earnest increase: +{earnest_inc * 100:.1f}%")
        response["earnest_increase_pct"] = earnest_inc
    elif earnest_inc > 0:
        denied.append(
            f"Earnest increase: +{earnest_inc * 100:.1f}% (max {max_earnest * 100:.1f}%)"
        )

    # Closing extension
    close_ext = requested.get("closing_extension_days", 0)
    max_close = max_c.get("closing_days", 0)
    if close_ext <= max_close:
        grantable.append(f"Closing extension: +{close_ext} days")
        response["closing_extension_days"] = close_ext
    elif close_ext > 0:
        denied.append(f"Closing extension: +{close_ext} days (max {max_close})")

    return {
        "grantable": grantable,
        "denied": denied,
        "response": response,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-LEVEL FUNCTION — what the orchestrator calls
# ─────────────────────────────────────────────────────────────────────────────


def handle_counter_offer(
    counter: dict[str, Any],
    state: dict[str, Any],
    mandate: dict[str, Any],
) -> dict[str, Any]:
    """
    Full counter-offer handling: evaluate → decide → update state.

    Args:
        counter: broker's counter-offer terms
        state: pipeline state object
        mandate: negotiation mandate

    Returns:
        Evaluation result with action, reason, and new terms
    """
    from state import log_action

    our_offer = {}
    if state.get("loi") and state["loi"].get("terms"):
        our_offer = state["loi"]["terms"]

    result = evaluate_counter(counter, our_offer, mandate)

    # Update negotiation state
    state["negotiation"]["counter_history"].append(
        {
            "timestamp": time.time(),
            "counter": counter,
            "decision": result["action"],
            "reason": result["reason"],
        }
    )

    if result["action"] == "accept":
        state["negotiation"]["status"] = "accepted"
        state["negotiation"]["current_terms"] = result["new_terms"]
    elif result["action"] == "counter":
        state["negotiation"]["status"] = "active"
        state["negotiation"]["current_terms"] = result["new_terms"]
    else:  # walk
        state["negotiation"]["status"] = "walked"

    log_action(
        state,
        agent="negotiation_agent",
        action=f"counter_{result['action']}",
        details={
            "counter_price": counter.get("price"),
            "decision": result["action"],
            "reason": result["reason"],
        },
    )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from state import create_state, create_mandate

    print("[negotiation_agent] Running standalone test...\n")

    mandate = create_mandate(absolute_max_price=100_000_000)
    state = create_state()
    state["loi"] = {
        "terms": {
            "offer_price": 85_000_000,
            "earnest_money": 850_000,
            "dd_period_days": 30,
            "closing_days": 45,
        }
    }

    scenarios = [
        ("Accept — within 2%", {"price": 86_500_000}),
        ("Counter — within 5%", {"price": 89_000_000}),
        ("Walk — beyond 5%", {"price": 92_000_000}),
        ("Walk — exceeds ceiling", {"price": 105_000_000}),
        (
            "Walk — trigger",
            {"price": 87_000_000, "flags": ["environmental_flag_in_dd"]},
        ),
        ("Accept — below our offer", {"price": 84_000_000}),
    ]

    for label, counter in scenarios:
        # Reset state for each test
        state["negotiation"] = {
            "status": "pending",
            "counter_history": [],
            "current_terms": None,
        }

        result = handle_counter_offer(counter, state, mandate)

        icon = {"accept": "✅", "counter": "🔄", "walk": "🚫"}.get(
            result["action"], "?"
        )
        print(f"  {icon} {label}")
        print(f"     Action: {result['action']}")
        print(f"     Reason: {result['reason']}")
        if result.get("new_terms") and result["action"] == "counter":
            print(f"     New offer: ${result['new_terms']['offer_price']:,.0f}")
        print()

    print("[negotiation_agent] Standalone test complete.")
