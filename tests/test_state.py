"""
tests/test_state.py — Unit tests for state.py
Tests state creation, mandate factory, audit log, and validation.
"""

from state import (
    create_state,
    create_mandate,
    log_action,
    set_error,
    validate_state,
    REQUIRED_STATE_KEYS,
)


class TestCreateState:
    """Tests that the state factory produces a valid initial state."""

    def test_creates_all_required_keys(self) -> None:
        state = create_state()
        assert set(state.keys()) == REQUIRED_STATE_KEYS

    def test_deal_context_defaults_to_empty(self) -> None:
        state = create_state()
        assert state["deal_context"] == {}

    def test_deal_context_accepted(self) -> None:
        ctx = {"asset_type": "Industrial", "location": "Phoenix", "price": 95_000_000}
        state = create_state(deal_context=ctx)
        assert state["deal_context"] == ctx

    def test_raw_data_has_three_sources(self) -> None:
        state = create_state()
        assert set(state["raw_data"].keys()) == {"fred", "census", "tavily"}

    def test_audit_log_starts_empty(self) -> None:
        state = create_state()
        assert state["audit_log"] == []

    def test_negotiation_starts_pending(self) -> None:
        state = create_state()
        assert state["negotiation"]["status"] == "pending"

    def test_error_starts_none(self) -> None:
        state = create_state()
        assert state["error"] is None


class TestCreateMandate:
    """Tests the mandate factory."""

    def test_creates_with_defaults(self) -> None:
        mandate = create_mandate(absolute_max_price=100_000_000)
        assert mandate["absolute_max_price"] == 100_000_000
        assert mandate["min_acceptable_dscr"] == 1.20
        assert len(mandate["walk_triggers"]) == 4

    def test_custom_walk_triggers(self) -> None:
        mandate = create_mandate(
            absolute_max_price=50_000_000,
            walk_triggers=["custom_trigger"],
        )
        assert mandate["walk_triggers"] == ["custom_trigger"]

    def test_concessions_structure(self) -> None:
        mandate = create_mandate(absolute_max_price=100_000_000)
        c = mandate["max_concessions"]
        assert "dd_period_days" in c
        assert "earnest_money_pct" in c
        assert "closing_days" in c
        assert "seller_credits" in c


class TestAuditLog:
    """Tests the audit log helpers."""

    def test_log_action_appends(self) -> None:
        state = create_state()
        log_action(state, agent="analyzer", action="analyzed_deal")
        assert len(state["audit_log"]) == 1
        assert state["audit_log"][0]["agent"] == "analyzer"
        assert state["audit_log"][0]["action"] == "analyzed_deal"

    def test_log_action_with_details(self) -> None:
        state = create_state()
        log_action(
            state,
            agent="email_agent",
            action="sent_broker_inquiry",
            details={"email_id": "abc123"},
        )
        assert state["audit_log"][0]["details"]["email_id"] == "abc123"

    def test_log_action_has_timestamp(self) -> None:
        state = create_state()
        log_action(state, agent="test", action="test")
        assert "timestamp" in state["audit_log"][0]
        assert isinstance(state["audit_log"][0]["timestamp"], float)

    def test_multiple_actions_append(self) -> None:
        state = create_state()
        log_action(state, agent="a", action="1")
        log_action(state, agent="b", action="2")
        log_action(state, agent="c", action="3")
        assert len(state["audit_log"]) == 3


class TestSetError:
    """Tests the error state helper."""

    def test_sets_error_fields(self) -> None:
        state = create_state()
        set_error(state, agent="finder", reason="no matches")
        assert state["error"]["agent"] == "finder"
        assert state["error"]["reason"] == "no matches"
        assert state["error"]["retry_count"] == 0

    def test_sets_retry_count(self) -> None:
        state = create_state()
        set_error(state, agent="finder", reason="no matches", retry_count=3)
        assert state["error"]["retry_count"] == 3


class TestValidateState:
    """Tests state validation."""

    def test_valid_state_has_no_errors(self) -> None:
        state = create_state()
        errors = validate_state(state)
        assert errors == []

    def test_missing_key_detected(self) -> None:
        state = create_state()
        del state["bid"]
        errors = validate_state(state)
        assert len(errors) == 1
        assert "Missing state keys" in errors[0]

    def test_bad_raw_data_type_detected(self) -> None:
        state = create_state()
        state["raw_data"] = "not a dict"
        errors = validate_state(state)
        assert any("raw_data" in e for e in errors)

    def test_bad_audit_log_type_detected(self) -> None:
        state = create_state()
        state["audit_log"] = "not a list"
        errors = validate_state(state)
        assert any("audit_log" in e for e in errors)
