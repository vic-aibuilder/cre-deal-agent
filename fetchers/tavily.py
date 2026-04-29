"""Tavily fetcher for CRE news signals."""

import json
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
import requests

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_ENDPOINT = "https://api.tavily.com/search"


def _one_line(text: str, max_len: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3]}..."


def _source_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host or "Tavily"


def fetch(submarket: str, asset_type: str) -> list[dict[str, str]]:
    """
    Fetches live CRE news and report snippets from Tavily.

    Returns a list of signals with shape:
    {"name": str, "value": str, "source": str}
    """
    if not TAVILY_API_KEY:
        return [
            {
                "name": "Tavily key missing",
                "value": "Set TAVILY_API_KEY in .env to enable live news signals.",
                "source": "Tavily (unavailable)",
            }
        ]

    query = f"{submarket} {asset_type} commercial real estate market broker report news"

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
    }

    try:
        response = requests.post(TAVILY_ENDPOINT, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return [
            {
                "name": "Tavily request failed",
                "value": f"Unable to fetch Tavily results: {exc}",
                "source": "Tavily (unavailable)",
            }
        ]

    results = data.get("results", [])
    if not results:
        return []

    signals: list[dict[str, str]] = []
    for item in results:
        title = str(item.get("title") or "Untitled CRE update")
        summary = str(item.get("content") or "No summary provided.")
        url = str(item.get("url") or "")

        signals.append(
            {
                "name": _one_line(title, 120),
                "value": _one_line(summary, 220),
                "source": _source_from_url(url),
            }
        )

    return signals


if __name__ == "__main__":
    sample_submarket = "Phoenix-Mesa-Chandler"
    sample_asset_type = "industrial"
    sample_signals = fetch(sample_submarket, sample_asset_type)
    print(json.dumps(sample_signals, indent=2))
