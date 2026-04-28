import os

import requests
from dotenv import load_dotenv

load_dotenv()

CENSUS_KEY = os.getenv("CENSUS_API_KEY")
ACS_BASE = "https://api.census.gov/data/2024/acs/acs5"

# MSA codes for the demo. Extend as the team adds cities.
SUBMARKET_TO_MSA = {
    "phoenix-mesa-chandler": "38060",
    "atlanta-sandy-springs-alpharetta": "12060",
    "dallas-fort-worth-arlington": "19100",
}

# ACS variables. Names match the PRD §7.1 lowercase-descriptive style.
ACS_VARIABLES = {
    "Phoenix MSA population": "B01003_001E",
    "Phoenix MSA median household income": "B19013_001E",
}


def _msa_code(submarket: str) -> str | None:
    return SUBMARKET_TO_MSA.get(submarket.strip().lower())


def _fetch_acs(msa_code: str, variable_id: str) -> str | None:
    params = {
        "get": f"NAME,{variable_id}",
        "for": f"metropolitan statistical area/micropolitan statistical area:{msa_code}",
    }
    if CENSUS_KEY:
        params["key"] = CENSUS_KEY
    try:
        r = requests.get(ACS_BASE, params=params, timeout=8)
        if r.status_code != 200:
            return None
        rows = r.json()
        if len(rows) < 2:
            return None
        header, data = rows[0], rows[1]
        idx = header.index(variable_id)
        raw = data[idx]
        if raw in ("", None) or raw.startswith("-"):
            return None
        return f"{int(raw):,} ({data[0]}, 2024 ACS 5-year)"
    except (requests.RequestException, ValueError, IndexError, KeyError):
        return None


def fetch(submarket: str) -> list[dict]:
    msa = _msa_code(submarket)
    if not msa:
        return [
            {
                "name": name,
                "value": "unavailable",
                "source": "Census Bureau (unavailable)",
            }
            for name in ACS_VARIABLES
        ]

    signals = []
    for name, variable_id in ACS_VARIABLES.items():
        value = _fetch_acs(msa, variable_id)
        if value is None:
            signals.append(
                {
                    "name": name,
                    "value": "unavailable",
                    "source": "Census Bureau (unavailable)",
                }
            )
        else:
            signals.append({"name": name, "value": value, "source": "Census Bureau"})
    return signals


if __name__ == "__main__":
    import json

    print(json.dumps(fetch("Phoenix-Mesa-Chandler"), indent=2))
