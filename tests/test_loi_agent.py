"""
tests/test_loi_agent.py — Unit tests for agents/loi_agent.py
Tests LOI term calculation, offer price derivation, and state integration.
"""

from __future__ import annotations

from agents.loi_agent import (
    calculate_dd_period,
    calculate_earnest_money,
    calculate_offer_price,
    build_loi_terms,
    generate_loi_text,
    prepare_loi,
    _extract_state,
)
from state import create_state, create_mandate


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

TEST_DEAL = {
    "asset_type": "Industrial, 412k sqft",
    "location": "Phoenix-Mesa-Chandler",
    "price": 95_000_000.0,
}

TEST_ANALYSIS_V3 = {
    "posture": "buyer's market",
    "recommendation": "renegotiate",
    "confidence": 0.82,
    "bid_floor_usd": 82_000_000,
    "bid_ceiling_usd": 88_000_000,
    "negotiation_posture": "aggressive",
}

TEST_ANALYSIS_V1 = {
    "posture": "balanced",
    "recommendation": "renegotiate",
}

TEST_MANDATE = create_mandate(absolute_max_price=100_000_000)


# ─────────────────────────────────────────────────────────────────────────────
# DD PERIOD
# ─────────────────────────────────────────────────────────────────────────────


class TestDDPeriod:
    def test_standard_period(self) -> None:
        assert calculate_dd_period(TEST_ANALYSIS_V3) == 30

    def test_low_confidence_gets_longer(self) -> None:
        analysis = {**TEST_ANALYSIS_V3, "confidence": 0.50}
        assert calculate_dd_period(analysis) == 45

    def test_cautious_posture_gets_longer(self) -> None:
        analysis = {**TEST_ANALYSIS_V3, "negotiation_posture": "cautious"}
        assert calculate_dd_period(analysis) == 45

    def test_no_confidence_defaults_standard(self) -> None:
        assert calculate_dd_period({}) == 30


# ─────────────────────────────────────────────────────────────────────────────
# EARNEST MONEY
# ─────────────────────────────────────────────────────────────────────────────


class TestEarnestMoney:
    def test_one_percent(self) -> None:
        assert calculate_earnest_money(85_000_000) == 850_000

    def test_rounds_to_integer(self) -> None:
        result = calculate_earnest_money(87_500_000)
        assert result == 875_000


# ─────────────────────────────────────────────────────────────────────────────
# OFFER PRICE
# ─────────────────────────────────────────────────────────────────────────────


class TestOfferPrice:
    def test_uses_bid_range_midpoint(self) -> None:
        price = calculate_offer_price(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE)
        assert price == 85_000_000  # midpoint of 82M-88M

    def test_fallback_when_no_bid_range(self) -> None:
        price = calculate_offer_price(TEST_ANALYSIS_V1, TEST_DEAL, TEST_MANDATE)
        # renegotiate = 8% discount on 95M
        assert price == 87_400_000  # 95M * 0.92 rounded to 100k

    def test_never_exceeds_mandate_max(self) -> None:
        low_mandate = create_mandate(absolute_max_price=80_000_000)
        price = calculate_offer_price(TEST_ANALYSIS_V3, TEST_DEAL, low_mandate)
        assert price <= 80_000_000

    def test_rounds_to_100k(self) -> None:
        price = calculate_offer_price(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE)
        assert price % 100_000 == 0


# ─────────────────────────────────────────────────────────────────────────────
# LOI TERMS
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildLoiTerms:
    def test_all_fields_present(self) -> None:
        terms = build_loi_terms(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE)
        required = {
            "offer_price",
            "earnest_money",
            "dd_period_days",
            "closing_days",
            "financing_contingency",
            "as_is_purchase",
            "expiration_hours",
            "governing_law_state",
        }
        assert required.issubset(set(terms.keys()))

    def test_governing_law_matches_location(self) -> None:
        terms = build_loi_terms(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE)
        assert terms["governing_law_state"] == "AZ"


# ─────────────────────────────────────────────────────────────────────────────
# LOI TEXT
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateLoiText:
    def test_contains_price(self) -> None:
        terms = build_loi_terms(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE)
        text = generate_loi_text(terms, TEST_DEAL)
        assert "$85,000,000" in text

    def test_contains_dd_period(self) -> None:
        terms = build_loi_terms(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE)
        text = generate_loi_text(terms, TEST_DEAL)
        assert "30 days" in text

    def test_contains_expiration(self) -> None:
        terms = build_loi_terms(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE)
        text = generate_loi_text(terms, TEST_DEAL)
        assert "72" in text

    def test_contains_letter_of_intent(self) -> None:
        terms = build_loi_terms(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE)
        text = generate_loi_text(terms, TEST_DEAL)
        assert "LETTER OF INTENT" in text


# ─────────────────────────────────────────────────────────────────────────────
# STATE INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────


class TestPrepareLoi:
    def test_updates_state(self) -> None:
        state = create_state(deal_context=TEST_DEAL)
        prepare_loi(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE, state)
        assert state["loi"] is not None
        assert state["loi"]["status"] == "generated"
        assert len(state["audit_log"]) == 1

    def test_returns_terms_and_text(self) -> None:
        state = create_state(deal_context=TEST_DEAL)
        result = prepare_loi(TEST_ANALYSIS_V3, TEST_DEAL, TEST_MANDATE, state)
        assert "terms" in result
        assert "text" in result
        assert result["terms"]["offer_price"] == 85_000_000


# ─────────────────────────────────────────────────────────────────────────────
# STATE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractState:
    def test_phoenix(self) -> None:
        assert _extract_state({"location": "Phoenix-Mesa-Chandler"}) == "AZ"

    def test_atlanta(self) -> None:
        assert _extract_state({"location": "Atlanta"}) == "GA"

    def test_unknown_defaults_az(self) -> None:
        assert _extract_state({"location": "Unknown City"}) == "AZ"
