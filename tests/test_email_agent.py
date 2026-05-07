"""
tests/test_email_agent.py — Unit tests for agents/email_agent.py
Tests email generation, formatting, and state integration.
Does NOT test actual Gmail sending — that requires OAuth credentials.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from agents.email_agent import (
    generate_broker_inquiry,
    generate_loi_cover_email,
    send_broker_inquiry,
    send_loi_email,
    DEFAULT_BUYER,
    _log_email,
    _generate_email_id,
)
from state import create_state


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

TEST_PROPERTY = {
    "property_address": "4400 E Huntington Dr, Phoenix, AZ 85050",
    "asset_type": "Industrial / Warehouse",
    "square_footage": "412,000 sqft",
    "asking_price": 95_000_000.0,
    "broker_name": "Sarah Chen",
    "broker_email": "schen@cushwake.com",
}

TEST_LOI_TERMS = {
    "offer_price": 85_000_000,
    "earnest_money": 850_000,
    "dd_period_days": 30,
    "closing_days": 45,
    "expiration_hours": 72,
}


def _mock_claude_response(body_text: str) -> MagicMock:
    """Create a mock litellm.completion response."""
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = body_text
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL ID GENERATION
# ─────────────────────────────────────────────────────────────────────────────


class TestEmailId:
    """Tests for email ID generation."""

    def test_generates_unique_ids(self) -> None:
        ids = {_generate_email_id() for _ in range(100)}
        assert len(ids) == 100

    def test_has_prefix(self) -> None:
        eid = _generate_email_id()
        assert eid.startswith("email_")


# ─────────────────────────────────────────────────────────────────────────────
# LOG EMAIL
# ─────────────────────────────────────────────────────────────────────────────


class TestLogEmail:
    """Tests for the log-mode email output."""

    def test_returns_tracking_record(self) -> None:
        email = {
            "subject": "Test",
            "body": "Hello",
            "to": "broker@test.com",
            "from": "buyer@test.com",
        }
        record = _log_email(email, "test_type")
        assert "email_id" in record
        assert "sent_at" in record
        assert record["type"] == "test_type"
        assert record["mode"] == "log"
        assert record["to"] == "broker@test.com"

    def test_body_preserved(self) -> None:
        email = {
            "subject": "Test",
            "body": "Full email body content here.",
            "to": "a@b.com",
            "from": "c@d.com",
        }
        record = _log_email(email, "inquiry")
        assert record["body"] == "Full email body content here."


# ─────────────────────────────────────────────────────────────────────────────
# BROKER INQUIRY GENERATION
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateBrokerInquiry:
    """Tests for broker inquiry email generation."""

    @patch("agents.email_agent.litellm.completion")
    def test_returns_email_dict(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response(
            "We are writing to express interest in the property."
        )
        email = generate_broker_inquiry(TEST_PROPERTY)
        assert "subject" in email
        assert "body" in email
        assert "to" in email
        assert "from" in email

    @patch("agents.email_agent.litellm.completion")
    def test_subject_contains_address(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("Interest.")
        email = generate_broker_inquiry(TEST_PROPERTY)
        assert "4400 E Huntington" in email["subject"]

    @patch("agents.email_agent.litellm.completion")
    def test_body_has_salutation(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("We are interested.")
        email = generate_broker_inquiry(TEST_PROPERTY)
        assert email["body"].startswith("Dear Sarah Chen")

    @patch("agents.email_agent.litellm.completion")
    def test_to_is_broker_email(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("Interest.")
        email = generate_broker_inquiry(TEST_PROPERTY)
        assert email["to"] == "schen@cushwake.com"

    @patch("agents.email_agent.litellm.completion")
    def test_from_is_buyer_email(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("Interest.")
        email = generate_broker_inquiry(TEST_PROPERTY)
        assert email["from"] == DEFAULT_BUYER["buyer_contact_email"]

    @patch("agents.email_agent.litellm.completion")
    def test_custom_buyer_config(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("Interest.")
        custom = {**DEFAULT_BUYER, "buyer_contact_email": "custom@firm.com"}
        email = generate_broker_inquiry(TEST_PROPERTY, buyer_config=custom)
        assert email["from"] == "custom@firm.com"


# ─────────────────────────────────────────────────────────────────────────────
# LOI COVER EMAIL GENERATION
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateLoiCoverEmail:
    """Tests for LOI cover email generation."""

    @patch("agents.email_agent.litellm.completion")
    def test_returns_email_dict(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response(
            "We are pleased to submit our Letter of Intent."
        )
        email = generate_loi_cover_email(TEST_PROPERTY, TEST_LOI_TERMS)
        assert "subject" in email
        assert "body" in email
        assert "Letter of Intent" in email["subject"]

    @patch("agents.email_agent.litellm.completion")
    def test_subject_contains_address(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("LOI attached.")
        email = generate_loi_cover_email(TEST_PROPERTY, TEST_LOI_TERMS)
        assert "4400 E Huntington" in email["subject"]


# ─────────────────────────────────────────────────────────────────────────────
# STATE INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────


class TestStateIntegration:
    """Tests that email actions are logged to state correctly."""

    @patch("agents.email_agent.litellm.completion")
    def test_inquiry_logs_to_state(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("Interest.")
        state = create_state()
        record = send_broker_inquiry(TEST_PROPERTY, state)

        assert len(state["emails"]) == 1
        assert state["emails"][0]["email_id"] == record["email_id"]
        assert len(state["audit_log"]) == 1
        assert state["audit_log"][0]["agent"] == "email_agent"
        assert state["audit_log"][0]["action"] == "sent_broker_inquiry"

    @patch("agents.email_agent.litellm.completion")
    def test_loi_logs_to_state(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("LOI attached.")
        state = create_state()
        send_loi_email(TEST_PROPERTY, TEST_LOI_TERMS, state)

        assert len(state["emails"]) == 1
        assert state["emails"][0]["type"] == "loi_cover"
        assert len(state["audit_log"]) == 1
        assert state["audit_log"][0]["action"] == "sent_loi_email"
        assert state["audit_log"][0]["details"]["offer_price"] == 85_000_000

    @patch("agents.email_agent.litellm.completion")
    def test_multiple_emails_accumulate(self, mock_completion: MagicMock) -> None:
        mock_completion.return_value = _mock_claude_response("Email body.")
        state = create_state()
        send_broker_inquiry(TEST_PROPERTY, state)
        send_loi_email(TEST_PROPERTY, TEST_LOI_TERMS, state)

        assert len(state["emails"]) == 2
        assert len(state["audit_log"]) == 2
        assert state["emails"][0]["type"] == "broker_inquiry"
        assert state["emails"][1]["type"] == "loi_cover"
