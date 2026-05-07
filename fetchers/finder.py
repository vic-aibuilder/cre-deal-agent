"""
fetchers/finder.py — Competing Offer Finder

Uses Tavily to search for competing real estate offers and listings
in the target submarket for similar asset types.

Joel's deliverable for Build 2 Sprint 3/4.
"""

from __future__ import annotations

import os
from typing import Any

from tavily import TavilyClient


def find_offers(submarket: str, asset_type: str, price: float) -> list[dict[str, Any]]:
    """
    Search for competing listings or offers in the market.
    Matches Victor's stub signature in main.py.

    Returns a list of signal dicts: {"name": str, "value": str, "source": str}
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return [
            {
                "name": "Finder Error",
                "value": "TAVILY_API_KEY not set",
                "source": "System",
            }
        ]

    client = TavilyClient(api_key=api_key)

    query = f"commercial real estate '{asset_type}' listings in '{submarket}' price around ${price:,.0f}"

    try:
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
        )
    except Exception as e:
        return [{"name": "Finder Search Failed", "value": str(e), "source": "Tavily"}]

    signals = []
    results = response.get("results", [])

    for i, res in enumerate(results):
        # Create a condensed summary of the finding
        title = res.get("title", f"Listing {i + 1}")
        content = res.get("content", "")[:100] + "..."
        url = res.get("url", "Unknown URL")
        domain = url.split("/")[2] if "//" in url else url

        signals.append(
            {
                "name": f"Competing: {title[:30]}",
                "value": content,
                "source": domain,
            }
        )

    if not signals:
        signals.append(
            {
                "name": "Competing Offers",
                "value": "No direct competing listings found in recent search.",
                "source": "Tavily",
            }
        )

    return signals
