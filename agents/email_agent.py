"""Email agent for autonomous broker outreach and inbox monitoring."""

from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

import requests

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
DEFAULT_INBOX_QUERY = "in:inbox newer_than:7d"
COUNTER_KEYWORDS = [
    "counter",
    "counteroffer",
    "counter-offer",
    "revised terms",
    "price change",
    "best and final",
]


def _require_access_token(access_token: str | None) -> str:
    token = access_token or os.getenv("GMAIL_ACCESS_TOKEN", "")
    if token:
        return token
    raise ValueError("Missing Gmail access token. Set GMAIL_ACCESS_TOKEN or pass access_token.")


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def _build_message(
    to_email: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    attachment_path: str | None = None,
) -> dict[str, str]:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    if attachment_path:
        file_path = Path(attachment_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Attachment not found: {attachment_path}")
        if file_path.suffix.lower() != ".pdf":
            raise ValueError("LOI attachment must be a PDF file.")

        payload = file_path.read_bytes()
        message.add_attachment(
            payload,
            maintype="application",
            subtype="pdf",
            filename=file_path.name,
        )

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    request_body: dict[str, str] = {"raw": encoded_message}
    if thread_id:
        request_body["threadId"] = thread_id
    return request_body


def _send_message(access_token: str, body: dict[str, str]) -> dict:
    response = requests.post(
        f"{GMAIL_API_BASE}/messages/send",
        headers=_headers(access_token),
        json=body,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _contains_counter_language(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in COUNTER_KEYWORDS)


def send_broker_inquiry(
    broker_email: str,
    deal_context: dict[str, str | float],
    access_token: str | None = None,
) -> dict[str, str]:
    """Generate and send the first-touch broker inquiry email."""
    token = _require_access_token(access_token)

    asset_type = str(deal_context.get("asset_type", "the asset"))
    submarket = str(deal_context.get("location", deal_context.get("submarket", "the submarket")))
    price = deal_context.get("price")

    price_line = ""
    if isinstance(price, (int, float)) and price > 0:
        price_line = f"We are underwriting this at approximately ${price:,.0f}."

    subject = f"Inquiry: {asset_type} Opportunity in {submarket}"
    body = "\n".join(
        [
            "Hi Broker Team,",
            "",
            f"Our acquisitions team is actively pursuing {asset_type} opportunities in {submarket}.",
            price_line,
            "Please share the latest OM, trailing-12 financials, current rent roll, and any known lease rollover schedule.",
            "If available, please also include debt assumptions and recent capex history.",
            "",
            "Thanks,",
            "CRE Deal Agent",
        ]
    ).strip()

    payload = _build_message(to_email=broker_email, subject=subject, body=body)
    sent = _send_message(token, payload)

    return {
        "status": "sent",
        "message_id": str(sent.get("id", "")),
        "thread_id": str(sent.get("threadId", "")),
        "to": broker_email,
        "subject": subject,
    }


def monitor_broker_inbox(
    access_token: str | None = None,
    active_thread_ids: list[str] | None = None,
    query: str = DEFAULT_INBOX_QUERY,
    max_results: int = 20,
    on_counter_detected: Callable[[dict[str, str]], None] | None = None,
) -> list[dict[str, str]]:
    """Poll Gmail for broker replies and trigger negotiation callback on counter language."""
    token = _require_access_token(access_token)

    params: dict[str, str | int] = {"q": query, "maxResults": max_results}
    list_response = requests.get(
        f"{GMAIL_API_BASE}/messages",
        headers=_headers(token),
        params=params,
        timeout=20,
    )
    list_response.raise_for_status()

    raw_messages = list_response.json().get("messages", [])
    if not raw_messages:
        return []

    observed_events: list[dict[str, str]] = []
    thread_filter = set(active_thread_ids or [])

    for message in raw_messages:
        message_id = str(message.get("id", ""))
        if not message_id:
            continue

        detail_response = requests.get(
            f"{GMAIL_API_BASE}/messages/{message_id}",
            headers=_headers(token),
            params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
            timeout=20,
        )
        detail_response.raise_for_status()
        detail = detail_response.json()

        thread_id = str(detail.get("threadId", ""))
        if thread_filter and thread_id not in thread_filter:
            continue

        headers = detail.get("payload", {}).get("headers", [])
        header_map = {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in headers}

        sender = header_map.get("from", "")
        subject = header_map.get("subject", "")
        snippet = str(detail.get("snippet", ""))

        event = {
            "message_id": message_id,
            "thread_id": thread_id,
            "from": sender,
            "subject": subject,
            "snippet": snippet,
            "action": "none",
        }

        if _contains_counter_language(f"{subject} {snippet}"):
            event["action"] = "trigger_negotiation_agent"
            if on_counter_detected:
                on_counter_detected(event)

        observed_events.append(event)

    return observed_events


def send_loi_cover_email(
    broker_email: str,
    property_address: str,
    loi_pdf_path: str,
    access_token: str | None = None,
    thread_id: str | None = None,
) -> dict[str, str]:
    """Send the LOI cover email with the LOI PDF attached."""
    token = _require_access_token(access_token)

    subject = f"LOI Submission - {property_address}"
    body = "\n".join(
        [
            "Hi Broker Team,",
            "",
            "Attached is our Letter of Intent for the opportunity.",
            "Please confirm receipt and advise on timing for seller response.",
            "",
            "Best,",
            "CRE Deal Agent",
        ]
    )

    payload = _build_message(
        to_email=broker_email,
        subject=subject,
        body=body,
        thread_id=thread_id,
        attachment_path=loi_pdf_path,
    )
    sent = _send_message(token, payload)

    return {
        "status": "sent",
        "message_id": str(sent.get("id", "")),
        "thread_id": str(sent.get("threadId", "")),
        "to": broker_email,
        "subject": subject,
        "attachment": loi_pdf_path,
    }
