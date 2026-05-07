"""
ai/closer.py — Claude-powered email and LOI generation.

Consolidates outreach, LOI, and counter-offer drafting for main.py integration.
Does NOT handle sending — Victor's main.py handles SMTP.

Joel's deliverable for Build 2 Sprint 3/4.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import litellm

# Use Anthropic direct for reliable JSON and precise tone
MODEL_ID = "anthropic/claude-sonnet-4-20250514"

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from ai/prompts/."""
    path = _PROMPT_DIR / filename
    if path.exists():
        return path.read_text().strip()
    raise FileNotFoundError(f"Prompt file not found: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# BUYER CONFIG (Default for demo)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_BUYER = {
    "buyer_entity": "Mesa Capital Partners LLC",
    "asset_focus": "industrial and logistics assets in the Sun Belt",
    "buyer_contact_name": "Joel Martinez",
    "buyer_contact_phone": "(602) 555-0147",
    "buyer_contact_email": "joel@mesacapitalpartners.com",
}


# ─────────────────────────────────────────────────────────────────────────────
# DRAFT OUTREACH (Broker Inquiry)
# ─────────────────────────────────────────────────────────────────────────────

def draft_outreach(deal_context: dict[str, Any]) -> dict[str, str]:
    """
    Generate broker inquiry email via Claude.
    Matches Victor's stub signature in main.py.

    Returns: {"subject": str, "body": str, "to": str, "from": str}
    """
    buyer = DEFAULT_BUYER
    prompt_template = _load_prompt("email_inquiry.txt")
    
    prompt = prompt_template.format(
        buyer_entity=buyer["buyer_entity"],
        asset_focus=buyer["asset_focus"],
        property_address=deal_context.get("submarket", "Target Market") + " property", # Fallback if specific address missing
        asset_type=deal_context.get("asset_type", "Industrial"),
        square_footage=deal_context.get("asset_type", "N/A"), # Often bundled in asset_type in demo
        asking_price=deal_context.get("purchase_price", 0),
        broker_name="Listing Broker", # We don't have broker name in deal_context yet
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
    submarket = deal_context.get("submarket", "Property")

    return {
        "subject": f"Inquiry RE: {submarket} {deal_context.get('asset_type', 'Asset')}",
        "body": f"Dear Listing Broker,\n\n{body}",
        "to": "broker@example.com", # Placeholder until finder provides real broker emails
        "from": os.getenv("GMAIL_USER", buyer["buyer_contact_email"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DRAFT LOI COVER
# ─────────────────────────────────────────────────────────────────────────────

def draft_loi(
    deal_context: dict[str, Any], 
    analysis: dict[str, Any], 
    loi_terms: dict[str, Any]
) -> dict[str, Any]:
    """
    Generate LOI cover email via Claude.
    Matches Victor's stub signature in main.py.

    Returns: {"subject": str, "body": str, "to": str, "from": str, "loi_expiry_hours": int}
    """
    buyer = DEFAULT_BUYER
    prompt_template = _load_prompt("email_loi.txt")
    
    # Extract terms (handling both our loi_agent structure and potential direct passing)
    offer_price = loi_terms.get("offer_price", analysis.get("bid_floor_usd", 0))
    earnest_money = loi_terms.get("earnest_money", offer_price * 0.01)
    dd_period_days = loi_terms.get("dd_period_days", 30)
    closing_days = loi_terms.get("closing_days", 45)
    expiration_hours = loi_terms.get("expiration_hours", 72)

    prompt = prompt_template.format(
        buyer_entity=buyer["buyer_entity"],
        property_address=deal_context.get("submarket", "Target Market") + " property",
        asking_price=deal_context.get("purchase_price", 0),
        offer_price=offer_price,
        earnest_money=earnest_money,
        dd_period_days=dd_period_days,
        closing_days=closing_days,
        expiration_hours=expiration_hours,
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
    submarket = deal_context.get("submarket", "Property")

    return {
        "subject": f"Letter of Intent — {submarket} {deal_context.get('asset_type', 'Asset')}",
        "body": body,
        "to": "broker@example.com", # Placeholder
        "from": os.getenv("GMAIL_USER", buyer["buyer_contact_email"]),
        "loi_expiry_hours": expiration_hours,
    }


# ─────────────────────────────────────────────────────────────────────────────
# DRAFT COUNTER RESPONSE
# ─────────────────────────────────────────────────────────────────────────────

def draft_counter(
    deal_context: dict[str, Any], 
    counter_terms: dict[str, Any], 
    decision: dict[str, Any]
) -> dict[str, Any]:
    """
    Generate counter-response email via Claude.
    Matches Victor's stub signature in main.py.

    Args:
        decision: from negotiation_agent containing 'action' (accept/counter/walk),
                  'new_terms', and 'reason'.
                  
    Returns: {"subject": str, "body": str, "to": str, "from": str, "action": str}
    """
    buyer = DEFAULT_BUYER
    prompt_template = _load_prompt("counter_response.txt")
    
    action = decision.get("action", "walk")
    new_terms = decision.get("new_terms", {}) or {}
    
    prompt = prompt_template.format(
        buyer_entity=buyer["buyer_entity"],
        property_address=deal_context.get("submarket", "Target Market") + " property",
        action=action,
        counter_price=counter_terms.get("price", 0),
        new_offer_price=new_terms.get("offer_price", 0),
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
    submarket = deal_context.get("submarket", "Property")
    
    subject_prefix = "RE: "
    if action == "accept":
        subject_prefix = "Offer Accepted — "
    elif action == "counter":
        subject_prefix = "Revised Offer — "
    else:
        subject_prefix = "Declined — "

    return {
        "subject": f"{subject_prefix}{submarket} {deal_context.get('asset_type', 'Asset')}",
        "body": body,
        "to": "broker@example.com",
        "from": os.getenv("GMAIL_USER", buyer["buyer_contact_email"]),
        "action": action,
    }
