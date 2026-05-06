# ADR V2 — Autonomous EmailAgent via Gmail API

- Status: Accepted
- Date: 2026-05-05
- Owner: Michael

## Context

V2 requires autonomous broker communication with no manual review before outbound messages are sent. The workflow must support:

- Initial broker inquiry emails requesting OM and financials
- Inbox monitoring for broker replies on active deal threads
- Counter-language detection that triggers negotiation logic
- LOI cover emails with generated LOI PDF attachment

## Decision

Implement a dedicated module at `agents/email_agent.py` with function-first APIs:

- `send_broker_inquiry(...)`
- `monitor_broker_inbox(...)`
- `send_loi_cover_email(...)`

Use Gmail REST API directly through `requests` and OAuth access tokens supplied at runtime (`GMAIL_ACCESS_TOKEN`).

## Rationale

- Keeps the implementation lightweight and dependency-minimal.
- Fits existing codebase style (functions, no classes).
- Easy integration for `main.py`, `agents/sealer.py`, and negotiation orchestration.
- Provides deterministic handoff contracts for downstream agents.

## Consequences

Positive:

- Enables fully autonomous broker outreach and follow-up.
- Provides thread-aware monitoring and callback trigger surface for negotiation.
- Supports LOI attachments as PDFs without additional mail infrastructure.

Tradeoffs:

- Access tokens are short-lived; robust refresh-token handling is out of scope in this iteration.
- Thread filtering uses active thread IDs supplied by orchestrator state.

## Integration Contract

`send_broker_inquiry(...)` returns:

```python
{
    "status": "sent",
    "message_id": str,
    "thread_id": str,
    "to": str,
    "subject": str,
}
```

`monitor_broker_inbox(...)` returns a list of events:

```python
[
    {
        "message_id": str,
        "thread_id": str,
        "from": str,
        "subject": str,
        "snippet": str,
        "action": "none" | "trigger_negotiation_agent",
    }
]
```

`send_loi_cover_email(...)` returns:

```python
{
    "status": "sent",
    "message_id": str,
    "thread_id": str,
    "to": str,
    "subject": str,
    "attachment": str,
}
```

## Notes

- Counter trigger detection currently relies on keyword matching in subject + snippet.
- Sealer should pass the generated LOI PDF path and broker thread ID when available.
