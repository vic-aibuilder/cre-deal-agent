"""
state.py — Shared state schema for the CRE Deal Agent pipeline.
Owner: Victor (orchestrator) / Joel (schema definition)

Every agent reads from and writes to this state object.
Fields are set at specific stages and are immutable once set —
downstream agents read but do not overwrite upstream fields.

Build 2 expands the state from 8 fields (Build 1) to 14+ fields
to support the autonomous pipeline.
"""

from __future__ import annotations

from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# STATE FACTORY
# Creates a clean initial state for a new deal pipeline run.
# ─────────────────────────────────────────────────────────────────────────────


def create_state(deal_context: dict | None = None) -> dict[str, Any]:
    """
    Initialize the full pipeline state object.

    All fields start as None or empty. Each stage populates its
    own fields and passes the state forward.

    Fields:
        Stage 1 — Mandate setup:
            deal_context: asset type, location, price, tenants, lender, DSCR
            mandate: buy box rules, metric thresholds, cap ceiling

        Stage 2 — Deal discovery:
            candidates: list of matched deals from FinderAgent
            selected_deal: the candidate chosen for full analysis

        Stage 3 — Full analysis:
            raw_data: untouched fetcher outputs (FRED, Census, Tavily)
            data_quality: per-source flags (direct / regional_fallback / missing)
            analysis: DealBrief from analyzer (posture, recommendation, etc.)

        Stage 4 — Bid generation:
            bid: offer price, target cap rate, decision confidence

        Stage 5–6 — LOI + Negotiation:
            loi: LOI document metadata (terms, PDF path, sent status)
            negotiation: counter-offer history, current status

        Stage 7 — Contract:
            contract: PSA metadata (generated, sent, attorney review status)

        Cross-cutting:
            emails: list of all sent/received email records
            audit_log: list of all agent actions with timestamps
            error: current error state (if any)
    """
    return {
        # Stage 1 — Mandate setup
        "deal_context": deal_context or {},
        "mandate": {},
        # Stage 2 — Deal discovery
        "candidates": [],
        "selected_deal": None,
        # Stage 3 — Full analysis
        "raw_data": {
            "fred": [],
            "census": [],
            "tavily": [],
        },
        "data_quality": {},
        "analysis": None,
        # Stage 4 — Bid generation
        "bid": None,
        # Stage 5–6 — LOI + Negotiation
        "loi": None,
        "negotiation": {
            "status": "pending",  # pending | active | accepted | walked
            "counter_history": [],
            "current_terms": None,
        },
        # Stage 7 — Contract
        "contract": None,
        # Cross-cutting
        "emails": [],
        "audit_log": [],
        "error": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MANDATE FACTORY
# The mandate defines the buy-box rules and negotiation rails.
# Set once at the start of a deal — never changed mid-deal.
# ─────────────────────────────────────────────────────────────────────────────


def create_mandate(
    absolute_max_price: float,
    min_acceptable_dscr: float = 1.20,
    max_dd_extension_days: int = 15,
    max_earnest_money_pct: float = 0.015,
    max_closing_extension_days: int = 15,
    max_seller_credits: float = 500_000,
    walk_triggers: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create the negotiation mandate — the hard rails the agent operates within.

    The agent has full autonomy within these rails:
    - It can bid up to absolute_max_price, never above.
    - It walks if DSCR falls below min_acceptable_dscr.
    - It can grant concessions up to the max limits.
    - It walks immediately if any walk_trigger is detected.
    """
    if walk_triggers is None:
        walk_triggers = [
            "seller_refuses_financials",
            "environmental_flag_in_dd",
            "title_defect_unclearable",
            "dscr_below_min_after_counter",
        ]

    return {
        "absolute_max_price": absolute_max_price,
        "min_acceptable_dscr": min_acceptable_dscr,
        "max_concessions": {
            "dd_period_days": max_dd_extension_days,
            "earnest_money_pct": max_earnest_money_pct,
            "closing_days": max_closing_extension_days,
            "seller_credits": max_seller_credits,
        },
        "walk_triggers": walk_triggers,
    }


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG HELPERS
# Every agent action is logged to state["audit_log"].
# ─────────────────────────────────────────────────────────────────────────────


def log_action(
    state: dict[str, Any],
    agent: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Append an action record to the audit log.

    Args:
        state: the shared pipeline state
        agent: which agent performed the action (e.g. "analyzer", "email_agent")
        action: what was done (e.g. "sent_broker_inquiry", "evaluated_counter")
        details: optional metadata about the action
    """
    import time

    state["audit_log"].append(
        {
            "timestamp": time.time(),
            "agent": agent,
            "action": action,
            "details": details or {},
        }
    )


def set_error(
    state: dict[str, Any],
    agent: str,
    reason: str,
    retry_count: int = 0,
    fallback_triggered: bool = False,
) -> None:
    """
    Set the error field on state. The orchestrator reads this to decide
    whether to retry, loosen the buy box, or park and monitor.
    """
    state["error"] = {
        "agent": agent,
        "reason": reason,
        "retry_count": retry_count,
        "fallback_triggered": fallback_triggered,
    }


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_STATE_KEYS = {
    "deal_context",
    "mandate",
    "candidates",
    "selected_deal",
    "raw_data",
    "data_quality",
    "analysis",
    "bid",
    "loi",
    "negotiation",
    "contract",
    "emails",
    "audit_log",
    "error",
}


def validate_state(state: dict[str, Any]) -> list[str]:
    """
    Check the state object for structural issues.
    Returns a list of error messages (empty = valid).
    """
    errors = []

    missing = REQUIRED_STATE_KEYS - set(state.keys())
    if missing:
        errors.append(f"Missing state keys: {missing}")

    if not isinstance(state.get("raw_data"), dict):
        errors.append("raw_data must be a dict")

    if not isinstance(state.get("audit_log"), list):
        errors.append("audit_log must be a list")

    if not isinstance(state.get("emails"), list):
        errors.append("emails must be a list")

    if not isinstance(state.get("negotiation"), dict):
        errors.append("negotiation must be a dict")

    return errors
