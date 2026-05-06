"""Gmail connectivity smoke test for EmailAgent integration."""

from __future__ import annotations

import os

from dotenv import load_dotenv
import requests

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _get_token() -> str:
    token = os.getenv("GMAIL_ACCESS_TOKEN", "").strip()
    if token:
        return token
    raise ValueError("Missing GMAIL_ACCESS_TOKEN in environment.")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def run_smoke_test() -> None:
    load_dotenv()
    token = _get_token()
    headers = _headers(token)

    profile_response = requests.get(
        f"{GMAIL_API_BASE}/profile",
        headers=headers,
        timeout=20,
    )
    profile_response.raise_for_status()
    profile = profile_response.json()

    list_response = requests.get(
        f"{GMAIL_API_BASE}/messages",
        headers=headers,
        params={"maxResults": 1, "q": "in:inbox newer_than:30d"},
        timeout=20,
    )
    list_response.raise_for_status()
    payload = list_response.json()

    print("Gmail smoke test passed.")
    print(f"Email address: {profile.get('emailAddress', '')}")
    print(f"Mailbox messages total: {profile.get('messagesTotal', 0)}")
    print(f"Threads total: {profile.get('threadsTotal', 0)}")
    print(f"Recent inbox sample count: {len(payload.get('messages', []))}")


if __name__ == "__main__":
    run_smoke_test()
