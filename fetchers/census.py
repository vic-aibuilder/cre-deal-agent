import os

import requests
from dotenv import load_dotenv

load_dotenv()

CENSUS_KEY = os.getenv("CENSUS_API_KEY")
FRED_KEY = os.getenv("FRED_API_KEY")

ACS_BASE = "https://api.census.gov/data/{year}/acs/acs5"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

POPULATION_VAR = "B01003_001E"
ACS_LATEST_YEAR = 2024
ACS_BASELINE_YEAR = 2019  # 5-year span for the growth signal

# MSA codes for the demo. Extend as the team adds cities.
SUBMARKET_TO_MSA = {
    "phoenix-mesa-chandler": "38060",
    "atlanta-sandy-springs-alpharetta": "12060",
    "dallas-fort-worth-arlington": "19100",
}

# FRED republishes Census BPS data per MSA. No public source carries
# industrial-specific permits at MSA granularity, so this proxies via
# total private housing permits with a clear qualifier in the value.
SUBMARKET_TO_FRED_PERMITS = {
    "phoenix-mesa-chandler": "PHOE004BPPRIV",
}


def _msa_code(submarket: str) -> str | None:
    return SUBMARKET_TO_MSA.get(submarket.strip().lower())


def _acs_population(year: int, msa_code: str) -> int | None:
    params = {
        "get": f"NAME,{POPULATION_VAR}",
        "for": f"metropolitan statistical area/micropolitan statistical area:{msa_code}",
    }
    if CENSUS_KEY:
        params["key"] = CENSUS_KEY
    try:
        r = requests.get(ACS_BASE.format(year=year), params=params, timeout=8)
        if r.status_code != 200:
            return None
        rows = r.json()
        if len(rows) < 2:
            return None
        idx = rows[0].index(POPULATION_VAR)
        raw = rows[1][idx]
        if raw in ("", None) or raw.startswith("-"):
            return None
        return int(raw)
    except (requests.RequestException, ValueError, IndexError, KeyError):
        return None


def _population_growth(msa_code: str) -> str | None:
    latest = _acs_population(ACS_LATEST_YEAR, msa_code)
    baseline = _acs_population(ACS_BASELINE_YEAR, msa_code)
    if latest is None or baseline is None or baseline == 0:
        return None
    pct = (latest - baseline) / baseline * 100
    return (
        f"+{pct:.2f}% over {ACS_LATEST_YEAR - ACS_BASELINE_YEAR} years "
        f"({baseline:,} → {latest:,}, ACS 5-year)"
    )


def _industrial_permits(submarket_key: str) -> str | None:
    series_id = SUBMARKET_TO_FRED_PERMITS.get(submarket_key)
    if not series_id or not FRED_KEY:
        return None
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 5,
    }
    try:
        r = requests.get(FRED_BASE, params=params, timeout=8)
        if r.status_code != 200:
            return None
        for obs in r.json().get("observations", []):
            if obs["value"] not in (".", "", None):
                # No public source carries industrial-only permits at MSA
                # granularity — qualify as a housing-permits proxy in-band so
                # the analyzer prompt sees the disclaimer.
                return (
                    f"{int(float(obs['value'])):,} housing permits "
                    f"(used as industrial proxy — no public MSA-level "
                    f"industrial-specific data; latest month {obs['date']})"
                )
        return None
    except (requests.RequestException, ValueError, KeyError):
        return None


def fetch(submarket: str) -> list[dict]:
    submarket_key = submarket.strip().lower()
    msa = _msa_code(submarket_key)

    if not msa:
        return [
            {
                "name": "Phoenix population growth",
                "value": "unavailable",
                "source": "Census Bureau (unavailable)",
            },
            {
                "name": "Phoenix industrial permits",
                "value": "unavailable",
                "source": "Census Bureau (unavailable)",
            },
        ]

    growth = _population_growth(msa)
    permits = _industrial_permits(submarket_key)

    return [
        {
            "name": "Phoenix population growth",
            "value": growth if growth else "unavailable",
            "source": "Census Bureau" if growth else "Census Bureau (unavailable)",
        },
        {
            "name": "Phoenix industrial permits",
            "value": permits if permits else "unavailable",
            "source": "Census Bureau" if permits else "Census Bureau (unavailable)",
        },
    ]


if __name__ == "__main__":
    import json

    print(json.dumps(fetch("Phoenix-Mesa-Chandler"), indent=2))
