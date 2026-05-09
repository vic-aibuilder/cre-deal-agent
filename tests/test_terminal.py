"""
tests/test_terminal.py — Unit tests for ui/terminal.py
Tests the terminal formatter with both v1 and v2 DealBrief formats.
"""

from ui.terminal import format_brief_for_terminal


TEST_DEAL = {
    "asset_type": "Industrial / Warehouse",
    "location": "Phoenix-Mesa-Chandler, AZ",
    "price": 95_000_000,
}


def _v1_brief() -> dict:
    return {
        "posture": "balanced",
        "recommendation": "renegotiate",
        "signal_breakdown": [
            {"name": "10-Year Treasury Yield", "value": "4.78%", "source": "FRED"},
        ],
        "next_move": "Renegotiate cap rate.",
        "watch_list": "Monitor Amazon leasing.",
    }


def _v2_brief() -> dict:
    brief = _v1_brief()
    brief["confidence"] = 0.72
    brief["rationale"] = "Mixed signals favor renegotiation."
    return brief


class TestTerminalFormatter:
    """Tests that the terminal output renders correctly."""

    def test_v1_brief_renders(self) -> None:
        output = format_brief_for_terminal(_v1_brief(), TEST_DEAL)
        assert "ANALYST BRIEF" in output
        assert "BALANCED" in output
        assert "RENEGOTIATE" in output
        assert "NEXT MOVE" in output
        assert "WATCH LIST" in output
        assert "$95,000,000" in output

    def test_v2_brief_shows_confidence(self) -> None:
        output = format_brief_for_terminal(_v2_brief(), TEST_DEAL)
        assert "CONFIDENCE" in output
        assert "72%" in output

    def test_v2_brief_shows_rationale(self) -> None:
        output = format_brief_for_terminal(_v2_brief(), TEST_DEAL)
        assert "RATIONALE" in output
        assert "Mixed signals" in output

    def test_v1_brief_no_confidence_line(self) -> None:
        output = format_brief_for_terminal(_v1_brief(), TEST_DEAL)
        assert "CONFIDENCE" not in output

    def test_signal_breakdown_rendered(self) -> None:
        output = format_brief_for_terminal(_v1_brief(), TEST_DEAL)
        assert "10-Year Treasury Yield" in output
        assert "FRED" in output
        assert "4.78%" in output

    def test_all_postures_have_icons(self) -> None:
        for posture in ["buyer's market", "balanced", "seller's market"]:
            brief = _v1_brief()
            brief["posture"] = posture
            output = format_brief_for_terminal(brief, TEST_DEAL)
            assert posture.upper() in output

    def test_all_recommendations_have_icons(self) -> None:
        for rec in ["hold", "accelerate", "renegotiate", "exit"]:
            brief = _v1_brief()
            brief["recommendation"] = rec
            output = format_brief_for_terminal(brief, TEST_DEAL)
            assert rec.upper() in output
