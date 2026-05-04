"""
tests/test_analyzer.py — Unit tests for ai/analyzer.py
Tests the JSON parser, validator, and output contract without calling the LLM.
"""

import json
import pytest

from ai.analyzer import (
    _parse_brief,
    REQUIRED_KEYS,
    OPTIONAL_KEYS,
    VALID_POSTURES,
    VALID_RECOMMENDATIONS,
)


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES — valid and invalid model responses
# ─────────────────────────────────────────────────────────────────────────────


def _valid_brief_v1() -> dict:
    """Returns a valid v1 DealBrief (5 keys, no confidence/rationale)."""
    return {
        "posture": "balanced",
        "recommendation": "renegotiate",
        "signal_breakdown": [
            {"name": "10-Year Treasury Yield", "value": "4.78%", "source": "FRED"},
        ],
        "next_move": "Renegotiate cap rate with seller.",
        "watch_list": "Monitor Amazon leasing activity over 30 days.",
    }


def _valid_brief_v2() -> dict:
    """Returns a valid v2 DealBrief (5 required + 2 optional keys)."""
    brief = _valid_brief_v1()
    brief["confidence"] = 0.72
    brief["rationale"] = (
        "Rising vacancy and Amazon rightsizing offset strong employment."
    )
    return brief


# ─────────────────────────────────────────────────────────────────────────────
# HAPPY PATH TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestParseValidBrief:
    """Tests that valid JSON responses parse correctly."""

    def test_v1_brief_parses(self) -> None:
        raw = json.dumps(_valid_brief_v1())
        result = _parse_brief(raw)
        assert set(result.keys()) == REQUIRED_KEYS

    def test_v2_brief_parses_with_optional_keys(self) -> None:
        raw = json.dumps(_valid_brief_v2())
        result = _parse_brief(raw)
        assert REQUIRED_KEYS.issubset(set(result.keys()))
        assert "confidence" in result
        assert "rationale" in result

    def test_all_postures_accepted(self) -> None:
        for posture in VALID_POSTURES:
            brief = _valid_brief_v1()
            brief["posture"] = posture
            result = _parse_brief(json.dumps(brief))
            assert result["posture"] == posture

    def test_all_recommendations_accepted(self) -> None:
        for rec in VALID_RECOMMENDATIONS:
            brief = _valid_brief_v1()
            brief["recommendation"] = rec
            result = _parse_brief(json.dumps(brief))
            assert result["recommendation"] == rec

    def test_confidence_clamped_to_range(self) -> None:
        brief = _valid_brief_v2()
        brief["confidence"] = 1.5  # over 1.0
        result = _parse_brief(json.dumps(brief))
        assert result["confidence"] == 1.0

        brief["confidence"] = -0.3  # under 0.0
        result = _parse_brief(json.dumps(brief))
        assert result["confidence"] == 0.0

    def test_extra_keys_stripped(self) -> None:
        brief = _valid_brief_v1()
        brief["hallucinated_key"] = "should be removed"
        brief["another_fake"] = 42
        result = _parse_brief(json.dumps(brief))
        assert "hallucinated_key" not in result
        assert "another_fake" not in result

    def test_markdown_fences_stripped(self) -> None:
        raw = "```json\n" + json.dumps(_valid_brief_v1()) + "\n```"
        result = _parse_brief(raw)
        assert set(result.keys()) == REQUIRED_KEYS


# ─────────────────────────────────────────────────────────────────────────────
# ERROR PATH TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestParseInvalidBrief:
    """Tests that malformed responses raise ValueError."""

    def test_empty_response_raises(self) -> None:
        with pytest.raises(ValueError, match="empty response"):
            _parse_brief("")

    def test_none_response_raises(self) -> None:
        with pytest.raises(ValueError, match="empty response"):
            _parse_brief(None)

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="JSON decode failed"):
            _parse_brief("not json at all")

    def test_missing_required_key_raises(self) -> None:
        brief = _valid_brief_v1()
        del brief["posture"]
        with pytest.raises(ValueError, match="missing required keys"):
            _parse_brief(json.dumps(brief))

    def test_invalid_posture_raises(self) -> None:
        brief = _valid_brief_v1()
        brief["posture"] = "hot market"
        with pytest.raises(ValueError, match="Invalid posture"):
            _parse_brief(json.dumps(brief))

    def test_invalid_recommendation_raises(self) -> None:
        brief = _valid_brief_v1()
        brief["recommendation"] = "yolo"
        with pytest.raises(ValueError, match="Invalid recommendation"):
            _parse_brief(json.dumps(brief))

    def test_signal_breakdown_not_list_raises(self) -> None:
        brief = _valid_brief_v1()
        brief["signal_breakdown"] = "should be a list"
        with pytest.raises(ValueError, match="signal_breakdown must be a list"):
            _parse_brief(json.dumps(brief))

    def test_malformed_confidence_dropped(self) -> None:
        brief = _valid_brief_v2()
        brief["confidence"] = "not a number"
        result = _parse_brief(json.dumps(brief))
        assert "confidence" not in result


# ─────────────────────────────────────────────────────────────────────────────
# CONTRACT TESTS
# ─────────────────────────────────────────────────────────────────────────────


class TestContract:
    """Tests that the contract constants match PRD §7.2."""

    def test_required_keys_count(self) -> None:
        assert len(REQUIRED_KEYS) == 5

    def test_required_keys_match_prd(self) -> None:
        expected = {
            "posture",
            "recommendation",
            "signal_breakdown",
            "next_move",
            "watch_list",
        }
        assert REQUIRED_KEYS == expected

    def test_optional_keys_are_v2(self) -> None:
        expected = {"confidence", "rationale"}
        assert OPTIONAL_KEYS == expected

    def test_posture_enum_values(self) -> None:
        expected = {"buyer's market", "balanced", "seller's market"}
        assert VALID_POSTURES == expected

    def test_recommendation_enum_values(self) -> None:
        expected = {"hold", "accelerate", "renegotiate", "exit"}
        assert VALID_RECOMMENDATIONS == expected
