from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

FRED_KEY = os.getenv("FRED_API_KEY")
BASE = "https://api.stlouisfed.org/fred/series/observations"

# Series IDs from PRD §6, signal names from PRD §7.1 — both team-confirmed.
# Scope tag flows into the `source` string so the analyzer can widen sensitivity
# on non-direct data (V2 deliverable 3, flag-only — no fallback fetching).
SERIES = {
    "30-Year Fixed Mortgage Rate": ("MORTGAGE30US", "national"),
    "federal funds rate": ("FEDFUNDS", "national"),
    "10-Year Treasury Yield": ("DGS10", "national"),
    "Arizona Unemployment Rate": ("AZUR", "state-level"),
    "National Construction Spending": ("TTLCONS", "national"),
    "industrial production index": ("INDPRO", "national"),
}


def _latest_value(series_id: str) -> str | None:
    if not FRED_KEY:
        return None
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 5,
    }
    try:
        r = requests.get(BASE, params=params, timeout=5)
        if r.status_code != 200:
            return None
        for obs in r.json().get("observations", []):
            if obs["value"] not in (".", "", None):
                return f"{obs['value']} (as of {obs['date']})"
        return None
    except (requests.RequestException, ValueError, KeyError):
        return None


def fetch(submarket: str) -> list[dict]:
    signals = []
    for name, (series_id, scope) in SERIES.items():
        value = _latest_value(series_id)
        if value is None:
            signals.append(
                {
                    "name": name,
                    "value": "unavailable",
                    "source": "FRED (unavailable)",
                }
            )
        else:
            signals.append({"name": name, "value": value, "source": f"FRED ({scope})"})
    return signals


if __name__ == "__main__":
    import json

    print(json.dumps(fetch("Phoenix-Mesa-Chandler"), indent=2))
