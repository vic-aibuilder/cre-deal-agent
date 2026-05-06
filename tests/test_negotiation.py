"""
tests/test_negotiation.py — Red-team tests for agents/negotiation_agent.py
Exhaustive counter-offer scenarios to ensure the agent never accepts a bad deal.
"""

from __future__ import annotations

from agents.negotiation_agent import (
    evaluate_counter,
    evaluate_concessions,
    handle_counter_offer,
    _check_walk_triggers,
)
from state import create_state, create_mandate


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

OUR_OFFER = {
    "offer_price": 85_000_000,
    "earnest_money": 850_000,
    "dd_period_days": 30,
    "closing_days": 45,
}

MANDATE = create_mandate(absolute_max_price=100_000_000)


# ─────────────────────────────────────────────────────────────────────────────
# ACCEPT SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────


class TestAcceptScenarios:
    """Counter-offers that should be accepted."""

    def test_exact_match(self) -> None:
        result = evaluate_counter({"price": 85_000_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "accept"

    def test_below_our_offer(self) -> None:
        result = evaluate_counter({"price": 83_000_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "accept"

    def test_within_one_percent(self) -> None:
        # 1% of 85M = 850k → counter at 85.85M
        result = evaluate_counter({"price": 85_850_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "accept"

    def test_within_two_percent(self) -> None:
        # 2% of 85M = 1.7M → counter at 86.7M
        result = evaluate_counter({"price": 86_700_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "accept"

    def test_at_two_percent_boundary(self) -> None:
        # Exactly 2% above = 86.7M
        counter_price = int(85_000_000 * 1.02)
        result = evaluate_counter({"price": counter_price}, OUR_OFFER, MANDATE)
        assert result["action"] == "accept"


# ─────────────────────────────────────────────────────────────────────────────
# COUNTER SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────


class TestCounterScenarios:
    """Counter-offers that should trigger a midpoint counter."""

    def test_three_percent_gap(self) -> None:
        # 3% of 85M = 2.55M → counter at 87.55M
        result = evaluate_counter({"price": 87_550_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "counter"

    def test_midpoint_calculation(self) -> None:
        # Counter at 89M → midpoint = (85M + 89M) / 2 = 87M
        result = evaluate_counter({"price": 89_000_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "counter"
        assert result["new_terms"]["offer_price"] == 87_000_000

    def test_midpoint_rounded_to_100k(self) -> None:
        result = evaluate_counter({"price": 88_750_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "counter"
        midpoint = result["new_terms"]["offer_price"]
        assert midpoint % 100_000 == 0

    def test_at_five_percent_boundary(self) -> None:
        # Exactly 5% above = 89.25M
        counter_price = int(85_000_000 * 1.05)
        result = evaluate_counter({"price": counter_price}, OUR_OFFER, MANDATE)
        assert result["action"] == "counter"

    def test_midpoint_never_exceeds_ceiling(self) -> None:
        low_mandate = create_mandate(absolute_max_price=86_000_000)
        result = evaluate_counter({"price": 89_000_000}, OUR_OFFER, low_mandate)
        if result["action"] == "counter":
            assert result["new_terms"]["offer_price"] <= 86_000_000


# ─────────────────────────────────────────────────────────────────────────────
# WALK SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────


class TestWalkScenarios:
    """Counter-offers that should cause the agent to walk."""

    def test_beyond_five_percent(self) -> None:
        # 6% of 85M = 5.1M → counter at 90.1M
        result = evaluate_counter({"price": 90_100_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "walk"

    def test_exceeds_ceiling(self) -> None:
        result = evaluate_counter({"price": 105_000_000}, OUR_OFFER, MANDATE)
        assert result["action"] == "walk"
        assert "ceiling" in result["reason"].lower()

    def test_walk_trigger_environmental(self) -> None:
        counter = {"price": 85_000_000, "flags": ["environmental_flag_in_dd"]}
        result = evaluate_counter(counter, OUR_OFFER, MANDATE)
        assert result["action"] == "walk"
        assert "trigger" in result["reason"].lower()

    def test_walk_trigger_title_defect(self) -> None:
        counter = {"price": 85_000_000, "flags": ["title_defect_unclearable"]}
        result = evaluate_counter(counter, OUR_OFFER, MANDATE)
        assert result["action"] == "walk"

    def test_walk_trigger_seller_refuses_financials(self) -> None:
        counter = {"price": 85_000_000, "flags": ["seller_refuses_financials"]}
        result = evaluate_counter(counter, OUR_OFFER, MANDATE)
        assert result["action"] == "walk"

    def test_walk_trigger_dscr_below_min(self) -> None:
        counter = {"price": 85_000_000, "flags": ["dscr_below_min_after_counter"]}
        result = evaluate_counter(counter, OUR_OFFER, MANDATE)
        assert result["action"] == "walk"

    def test_zero_offer_price_walks(self) -> None:
        result = evaluate_counter({"price": 85_000_000}, {"offer_price": 0}, MANDATE)
        assert result["action"] == "walk"


# ─────────────────────────────────────────────────────────────────────────────
# WALK TRIGGER DETECTOR
# ─────────────────────────────────────────────────────────────────────────────


class TestWalkTriggers:
    def test_no_flags_returns_none(self) -> None:
        result = _check_walk_triggers({}, MANDATE["walk_triggers"])
        assert result is None

    def test_unrelated_flag_returns_none(self) -> None:
        result = _check_walk_triggers(
            {"flags": ["some_other_flag"]}, MANDATE["walk_triggers"]
        )
        assert result is None

    def test_matching_flag_returns_trigger(self) -> None:
        result = _check_walk_triggers(
            {"flags": ["environmental_flag_in_dd"]}, MANDATE["walk_triggers"]
        )
        assert result == "environmental_flag_in_dd"


# ─────────────────────────────────────────────────────────────────────────────
# CONCESSION EVALUATION
# ─────────────────────────────────────────────────────────────────────────────


class TestConcessions:
    def test_within_limits_grantable(self) -> None:
        requested = {"dd_extension_days": 10, "closing_extension_days": 10}
        result = evaluate_concessions(requested, MANDATE)
        # DD and closing are grantable; earnest at 0 is also grantable (within limits)
        assert len(result["denied"]) == 0

    def test_beyond_limits_denied(self) -> None:
        requested = {"dd_extension_days": 30}  # max is 15
        result = evaluate_concessions(requested, MANDATE)
        assert len(result["denied"]) == 1

    def test_earnest_within_limits(self) -> None:
        requested = {"earnest_increase_pct": 0.01}  # max is 0.015
        result = evaluate_concessions(requested, MANDATE)
        assert len(result["denied"]) == 0
        assert result["response"]["earnest_increase_pct"] == 0.01


# ─────────────────────────────────────────────────────────────────────────────
# STATE INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────


class TestHandleCounterOffer:
    def _make_state(self) -> dict:
        state = create_state()
        state["loi"] = {"terms": OUR_OFFER.copy()}
        return state

    def test_accept_updates_state(self) -> None:
        state = self._make_state()
        result = handle_counter_offer({"price": 85_500_000}, state, MANDATE)
        assert result["action"] == "accept"
        assert state["negotiation"]["status"] == "accepted"
        assert len(state["audit_log"]) == 1

    def test_counter_updates_state(self) -> None:
        state = self._make_state()
        result = handle_counter_offer({"price": 89_000_000}, state, MANDATE)
        assert result["action"] == "counter"
        assert state["negotiation"]["status"] == "active"
        assert state["negotiation"]["current_terms"] is not None

    def test_walk_updates_state(self) -> None:
        state = self._make_state()
        result = handle_counter_offer({"price": 92_000_000}, state, MANDATE)
        assert result["action"] == "walk"
        assert state["negotiation"]["status"] == "walked"

    def test_counter_history_grows(self) -> None:
        state = self._make_state()
        handle_counter_offer({"price": 89_000_000}, state, MANDATE)
        assert len(state["negotiation"]["counter_history"]) == 1
        assert state["negotiation"]["counter_history"][0]["decision"] == "counter"
