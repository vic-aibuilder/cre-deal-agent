"""
agents/email_agent.py — Autonomous email agent for CRE deal pipeline.

Generates and sends emails to listing brokers via Claude + Gmail API.
Operates in two modes:
  - LOG mode (default): generates emails, prints to terminal, logs to state
  - LIVE mode: sends via Gmail API (requires OAuth credentials)

Set EMAIL_MODE=live in .env to enable actual sending.

Build 2, Sprint 2.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

import litellm
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_MODE = os.getenv("EMAIL_MODE", "log").lower()  # "log" or "live"
MODEL_ID = "anthropic/claude-sonnet-4-20250514"

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "ai" / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from ai/prompts/."""
    path = _PROMPT_DIR / filename
    if path.exists():
        return path.read_text().strip()
    raise FileNotFoundError(f"Prompt file not found: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# BUYER CONFIG
# These would come from a mandate config file in production.
# For now, defaults for the demo scenario.
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_BUYER = {
    "buyer_entity": "Mesa Capital Partners LLC",
    "asset_focus": "industrial and logistics assets in the Sun Belt",
    "buyer_contact_name": "Joel Martinez",
    "buyer_contact_phone": "(602) 555-0147",
    "buyer_contact_email": "joel@mesacapitalpartners.com",
}


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL GENERATION — Claude writes the email body
# ─────────────────────────────────────────────────────────────────────────────


def generate_broker_inquiry(
    property_info: dict[str, Any],
    buyer_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Generate a broker inquiry email using Claude.

    Args:
        property_info: dict with keys:
            property_address, asset_type, square_footage,
            asking_price (float), broker_name, broker_email
        buyer_config: optional override for buyer details

    Returns:
        {"subject": str, "body": str, "to": str, "from": str}
    """
    buyer = buyer_config or DEFAULT_BUYER

    prompt_template = _load_prompt("email_inquiry.txt")
    prompt = prompt_template.format(
        buyer_entity=buyer["buyer_entity"],
        asset_focus=buyer["asset_focus"],
        property_address=property_info.get("property_address", "Unknown"),
        asset_type=property_info.get("asset_type", "Industrial"),
        square_footage=property_info.get("square_footage", "N/A"),
        asking_price=property_info.get("asking_price", 0),
        broker_name=property_info.get("broker_name", "Listing Broker"),
        buyer_contact_name=buyer["buyer_contact_name"],
        buyer_contact_phone=buyer["buyer_contact_phone"],
        buyer_contact_email=buyer["buyer_contact_email"],
    )

    response = litellm.completion(
        model=MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=800,
    )

    body = response.choices[0].message.content.strip()
    broker_name = property_info.get("broker_name", "Broker")
    address = property_info.get("property_address", "the property")

    return {
        "subject": f"Inquiry RE: {address}",
        "body": f"Dear {broker_name},\n\n{body}",
        "to": property_info.get("broker_email", ""),
        "from": buyer["buyer_contact_email"],
    }


def generate_loi_cover_email(
    property_info: dict[str, Any],
    loi_terms: dict[str, Any],
    buyer_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Generate an LOI cover email using Claude.

    Args:
        property_info: property details dict
        loi_terms: dict with keys:
            offer_price, earnest_money, dd_period_days,
            closing_days, expiration_hours
        buyer_config: optional override for buyer details

    Returns:
        {"subject": str, "body": str, "to": str, "from": str}
    """
    buyer = buyer_config or DEFAULT_BUYER

    prompt_template = _load_prompt("email_loi.txt")
    prompt = prompt_template.format(
        buyer_entity=buyer["buyer_entity"],
        property_address=property_info.get("property_address", "Unknown"),
        asking_price=property_info.get("asking_price", 0),
        offer_price=loi_terms.get("offer_price", 0),
        earnest_money=loi_terms.get("earnest_money", 0),
        dd_period_days=loi_terms.get("dd_period_days", 30),
        closing_days=loi_terms.get("closing_days", 45),
        expiration_hours=loi_terms.get("expiration_hours", 72),
        buyer_contact_name=buyer["buyer_contact_name"],
        buyer_contact_phone=buyer["buyer_contact_phone"],
        buyer_contact_email=buyer["buyer_contact_email"],
    )

    response = litellm.completion(
        model=MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=800,
    )

    body = response.choices[0].message.content.strip()
    address = property_info.get("property_address", "the property")

    return {
        "subject": f"Letter of Intent — {address}",
        "body": body,
        "to": property_info.get("broker_email", ""),
        "from": buyer["buyer_contact_email"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL SENDING — LOG mode (prints) or LIVE mode (Gmail API)
# ─────────────────────────────────────────────────────────────────────────────


def _generate_email_id() -> str:
    """Generate a unique email ID for tracking."""
    return f"email_{uuid.uuid4().hex[:12]}"


def _log_email(email: dict[str, str], email_type: str) -> dict[str, Any]:
    """
    LOG mode: print the email to terminal and return tracking record.
    No email is actually sent.
    """
    email_id = _generate_email_id()
    sent_at = time.time()

    print(f"\n{'─' * 60}")
    print(f"  📧 EMAIL [{email_type.upper()}] — LOG MODE (not sent)")
    print(f"{'─' * 60}")
    print(f"  ID:      {email_id}")
    print(f"  To:      {email['to']}")
    print(f"  From:    {email['from']}")
    print(f"  Subject: {email['subject']}")
    print(f"{'─' * 60}")
    print(f"\n{email['body']}\n")
    print(f"{'─' * 60}\n")

    return {
        "email_id": email_id,
        "sent_at": sent_at,
        "to": email["to"],
        "from": email["from"],
        "subject": email["subject"],
        "body": email["body"],
        "type": email_type,
        "mode": "log",
        "thread_id": email_id,  # in log mode, thread_id = email_id
    }


def _send_gmail(email: dict[str, str], email_type: str) -> dict[str, Any]:
    """
    LIVE mode: send via Gmail API.
    Requires OAuth credentials in config/gmail_credentials.json.

    Not yet implemented — will be wired in when Gmail OAuth is configured.
    Falls back to LOG mode with a warning if credentials are missing.
    """
    creds_path = _PROJECT_ROOT / "config" / "gmail_credentials.json"
    if not creds_path.exists():
        print("  ⚠️  Gmail credentials not found at config/gmail_credentials.json")
        print("  ⚠️  Falling back to LOG mode.")
        return _log_email(email, email_type)

    # Gmail API integration placeholder
    # When implemented, this will:
    # 1. Load OAuth credentials from config/gmail_credentials.json
    # 2. Build the Gmail API service
    # 3. Create and send the MIME message
    # 4. Return the message ID and thread ID from Gmail
    print("  ⚠️  Gmail API send not yet implemented. Using LOG mode.")
    return _log_email(email, email_type)


def send_email(email: dict[str, str], email_type: str) -> dict[str, Any]:
    """
    Route email through the configured mode (log or live).
    Returns a tracking record for the state audit log.
    """
    if EMAIL_MODE == "live":
        return _send_gmail(email, email_type)
    return _log_email(email, email_type)


# ─────────────────────────────────────────────────────────────────────────────
# HIGH-LEVEL FUNCTIONS — what the orchestrator calls
# ─────────────────────────────────────────────────────────────────────────────


def send_broker_inquiry(
    property_info: dict[str, Any],
    state: dict[str, Any],
    buyer_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate and send a broker inquiry email.
    Logs the action to state["audit_log"] and state["emails"].

    Args:
        property_info: property details for the email
        state: the pipeline state object
        buyer_config: optional buyer override

    Returns:
        Email tracking record
    """
    from state import log_action

    email = generate_broker_inquiry(property_info, buyer_config)
    record = send_email(email, email_type="broker_inquiry")

    # Log to state
    state["emails"].append(record)
    log_action(
        state,
        agent="email_agent",
        action="sent_broker_inquiry",
        details={
            "email_id": record["email_id"],
            "to": record["to"],
            "mode": record["mode"],
        },
    )

    return record


def send_loi_email(
    property_info: dict[str, Any],
    loi_terms: dict[str, Any],
    state: dict[str, Any],
    buyer_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate and send an LOI cover email.
    Logs the action to state["audit_log"] and state["emails"].

    Args:
        property_info: property details for the email
        loi_terms: LOI terms dict
        state: the pipeline state object
        buyer_config: optional buyer override

    Returns:
        Email tracking record
    """
    from state import log_action

    email = generate_loi_cover_email(property_info, loi_terms, buyer_config)
    record = send_email(email, email_type="loi_cover")

    # Log to state
    state["emails"].append(record)
    log_action(
        state,
        agent="email_agent",
        action="sent_loi_email",
        details={
            "email_id": record["email_id"],
            "to": record["to"],
            "mode": record["mode"],
            "offer_price": loi_terms.get("offer_price"),
        },
    )

    return record


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from state import create_state

    print("[email_agent] Running standalone test...\n")

    test_property = {
        "property_address": "4400 E Huntington Dr, Phoenix, AZ 85050",
        "asset_type": "Industrial / Warehouse",
        "square_footage": "412,000 sqft",
        "asking_price": 95_000_000.0,
        "broker_name": "Sarah Chen",
        "broker_email": "schen@cushwake.com",
    }

    test_loi_terms = {
        "offer_price": 85_000_000,
        "earnest_money": 850_000,
        "dd_period_days": 30,
        "closing_days": 45,
        "expiration_hours": 72,
    }

    state = create_state()

    # Test 1: broker inquiry
    print("=" * 60)
    print("  TEST 1: Broker Inquiry Email")
    print("=" * 60)
    inquiry_record = send_broker_inquiry(test_property, state)
    print(f"  [✓] Email logged: {inquiry_record['email_id']}")

    # Test 2: LOI cover email
    print("\n" + "=" * 60)
    print("  TEST 2: LOI Cover Email")
    print("=" * 60)
    loi_record = send_loi_email(test_property, test_loi_terms, state)
    print(f"  [✓] Email logged: {loi_record['email_id']}")

    # Verify state was updated
    print(
        f"\n  State: {len(state['emails'])} emails, "
        f"{len(state['audit_log'])} audit entries"
    )

    print("\n[email_agent] Standalone test complete.")
