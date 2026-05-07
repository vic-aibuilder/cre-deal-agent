"""
ai/closer.py — Claude-powered email and LOI generation.

Consolidates outreach, LOI, and counter-offer drafting for main.py integration.
Does NOT handle sending — Victor's main.py handles SMTP.

Uses the unified email_generator.txt prompt.
"""

from __future__ import annotations

import json
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
    "buyer_contact_name": "Joel Martinez",
    "buyer_contact_phone": "(602) 555-0147",
    "buyer_contact_email": "joel@mesacapitalpartners.com",
}


# ─────────────────────────────────────────────────────────────────────────────
# COMMON EMAIL GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def _generate_email(
    deal_context: dict[str, Any],
    analysis: dict[str, Any],
    email_type_and_action: dict[str, Any]
) -> tuple[str, bool]:
    """
    Core function that calls Claude using the unified email_generator.txt prompt.
    Returns the email body and a boolean indicating if it requires a human gate.
    """
    prompt_template = _load_prompt("email_generator.txt")
    buyer = DEFAULT_BUYER

    # Prepare inputs as JSON strings for the prompt
    prompt = prompt_template.format(
        deal_context=json.dumps(deal_context, indent=2),
        deal_brief=json.dumps(analysis, indent=2),
        email_type_and_action=json.dumps(email_type_and_action, indent=2),
        buyer_contact_name=buyer["buyer_contact_name"],
        buyer_entity=buyer["buyer_entity"],
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
    
    # Handle the HUMAN GATE line injected by Claude
    human_gate_warning = "HUMAN GATE — DO NOT AUTO-SEND. DISPLAY FOR HUMAN REVIEW ONLY."
    requires_human_gate = False
    
    if body.startswith(human_gate_warning):
        requires_human_gate = True
        # Strip the warning from the actual email body so it doesn't get sent to the broker
        body = body[len(human_gate_warning):].lstrip()

    return body, requires_human_gate


# ─────────────────────────────────────────────────────────────────────────────
# DRAFT OUTREACH (Broker Inquiry)
# ─────────────────────────────────────────────────────────────────────────────

def draft_outreach(deal_context: dict[str, Any]) -> dict[str, Any]:
    """
    Generate broker inquiry email via Claude.
    Matches Victor's stub signature in main.py.

    Returns: {"subject": str, "body": str, "to": str, "from": str}
    """
    # In a real app, the analysis wouldn't be fully needed for outreach, but we pass 
    # a dummy dict to satisfy the unified prompt requirements
    analysis = {"negotiation_posture": "measured"}
    
    email_type_and_action = {
        "email_type": "outreach_email",
        "action": None,
        "counter_price": None
    }
    
    body, requires_human_gate = _generate_email(deal_context, analysis, email_type_and_action)
    submarket = deal_context.get("submarket", "Property")
    
    return {
        "subject": f"Inquiry RE: {submarket} {deal_context.get('asset_type', 'Asset')}",
        "body": body,
        "to": deal_context.get("broker_email", "broker@example.com"),
        "from": os.getenv("GMAIL_USER", DEFAULT_BUYER["buyer_contact_email"]),
        "human_gate": requires_human_gate
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
    # The new prompt doesn't explicitly take loi_terms, it uses deal_brief (analysis)
    # We will inject the LOI terms into the analysis dict so the prompt can see them
    analysis_with_terms = analysis.copy()
    offer_price = loi_terms.get("offer_price", analysis.get("bid_floor_usd", 0))
    
    # We pass the offer price as counter_price to satisfy the prompt structure
    email_type_and_action = {
        "email_type": "loi_email",
        "action": None,
        "counter_price": offer_price
    }
    
    body, requires_human_gate = _generate_email(deal_context, analysis_with_terms, email_type_and_action)
    submarket = deal_context.get("submarket", "Property")

    return {
        "subject": f"Letter of Intent — {submarket} {deal_context.get('asset_type', 'Asset')}",
        "body": body,
        "to": deal_context.get("broker_email", "broker@example.com"),
        "from": os.getenv("GMAIL_USER", DEFAULT_BUYER["buyer_contact_email"]),
        "loi_expiry_hours": loi_terms.get("expiration_hours", 72),
        "human_gate": requires_human_gate
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
    # The decision might not have an analysis dict attached natively, so we create a mock one
    # if it's missing, mostly to pass the negotiation posture
    analysis = decision.get("analysis", {"negotiation_posture": "measured"})
    action = decision.get("action", "walk")
    
    email_type_and_action = {
        "email_type": "counter_offer_email",
        "action": action,
        "counter_price": counter_terms.get("price", 0)
    }
    
    # If we are countering, inject the new_offer_price into the analysis context for the prompt
    if action == "counter":
        new_terms = decision.get("new_terms", {}) or {}
        analysis["new_offer_price"] = new_terms.get("offer_price", 0)
    
    body, requires_human_gate = _generate_email(deal_context, analysis, email_type_and_action)
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
        "to": deal_context.get("broker_email", "broker@example.com"),
        "from": os.getenv("GMAIL_USER", DEFAULT_BUYER["buyer_contact_email"]),
        "action": action,
        "human_gate": requires_human_gate
    }
