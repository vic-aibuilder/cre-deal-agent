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


def _build_queries(submarket: str, asset_type: str) -> list[str]:
    # Every query variant intentionally includes both asset type and submarket.
    return [
        f"{submarket} {asset_type} commercial real estate broker report",
        f"{submarket} {asset_type} commercial real estate lease comps vacancy",
        f"{submarket} {asset_type} commercial real estate cap rates transactions",
    ]


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

    query_variants = _build_queries(submarket, asset_type)

    all_results: list[dict] = []
    try:
        for query in query_variants:
            payload = {
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 3,
            }
            response = requests.post(TAVILY_ENDPOINT, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            all_results.extend(data.get("results", []))
    except Exception as exc:
        return [
            {
                "name": "Tavily request failed",
                "value": f"Unable to fetch Tavily results: {exc}",
                "source": "Tavily (unavailable)",
            }
        ]

    if not all_results:
        return []

    deduped_results: list[dict] = []
    seen_urls: set[str] = set()
    for item in all_results:
        url = str(item.get("url") or "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduped_results.append(item)

    signals: list[dict[str, str]] = []
    for item in deduped_results[:5]:
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
