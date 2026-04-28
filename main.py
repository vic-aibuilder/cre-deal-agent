import sys

from dotenv import load_dotenv
from fetchers import fred

load_dotenv()

# Integration day — uncomment these and delete the three stub functions below:
# from fetchers import census, tavily
# from ai import analyzer


# ── Stubs ─────────────────────────────────────────────────────────────────────


def _stub_census_fetch(submarket: str) -> list[dict]:
    return [
        {
            "name": "Phoenix population growth",
            "value": "+3.2% YoY (stub)",
            "source": "Census Bureau (stub)",
        },
        {
            "name": "Phoenix industrial permits",
            "value": "14 new permits, Maricopa County (stub)",
            "source": "Census Bureau (stub)",
        },
    ]


def _stub_tavily_fetch(submarket: str, asset_type: str) -> list[dict]:
    return [
        {
            "name": "Amazon logistics rightsizing",
            "value": "AMZN flagged warehouse footprint reduction in Q3 earnings (stub)",
            "source": "Tavily (stub)",
        },
        {
            "name": "Phoenix industrial vacancy rising",
            "value": "6.2% vs 4.1% a year ago (stub)",
            "source": "Tavily (stub)",
        },
    ]


def _stub_analyze(deal_context: dict, signals: list[dict]) -> dict:
    return {
        "posture": "balanced",
        "recommendation": "renegotiate",
        "signal_breakdown": signals[:3],
        "next_move": "Request a 30-day rate lock extension from Wells Fargo before Thursday's deadline given the 28bps move in the 10-yr Treasury.",
        "watch_list": "10-yr Treasury yield — a move above 5.0% would compress cap rates and push this deal below the 1.25x DSCR floor.",
    }


# ── Deal input ────────────────────────────────────────────────────────────────


def get_deal_input() -> dict:
    print("\n" + "═" * 60)
    print("  CRE DEAL MONITOR")
    print("═" * 60 + "\n")

    asset_type = input("Asset type (e.g. Industrial, 412k sqft): ").strip()
    location = input("Submarket (e.g. Phoenix-Mesa-Chandler): ").strip()
    price_raw = input("Price in dollars (e.g. 95000000): ").strip()
    cap_rate = input("Cap rate (e.g. 5.8%): ").strip()
    tenants = input("Key tenants (e.g. Amazon · 65% of NOI): ").strip()
    lender = input("Lender (e.g. Wells Fargo): ").strip()
    dscr_constraint = input("DSCR constraint (e.g. 1.25): ").strip()

    try:
        price = float(price_raw.replace(",", "").replace("$", ""))
    except ValueError:
        price = 0.0

    return {
        "asset_type": asset_type,
        "location": location,
        "price": price,
        "cap_rate": cap_rate,
        "tenants": tenants,
        "lender": lender,
        "dscr_constraint": dscr_constraint,
    }


# ── Checkpoint ────────────────────────────────────────────────────────────────


def run_checkpoint(brief: dict) -> bool:
    print("\n" + "─" * 60)
    print("  CHECKPOINT — DEAL BRIEF PREVIEW")
    print("─" * 60)
    print(f"  Posture:        {brief['posture'].upper()}")
    print(f"  Recommendation: {brief['recommendation'].upper()}")
    print(f"  Next move:      {brief['next_move']}")
    print("─" * 60 + "\n")

    while True:
        answer = input("Approve this brief? (yes/no): ").strip().lower()
        if answer == "yes":
            return True
        if answer == "no":
            return False
        print("  Please enter yes or no.")


# ── Final output ──────────────────────────────────────────────────────────────


def print_brief(brief: dict, deal_context: dict) -> None:
    print("\n" + "═" * 60)
    print("  CRE DEAL MONITOR — FINAL BRIEF")
    print(
        f"  {deal_context.get('asset_type')} · {deal_context.get('location')} · ${deal_context.get('price', 0):,.0f}"
    )
    print("═" * 60)
    print(f"\n  POSTURE:        {brief['posture'].upper()}")
    print(f"  RECOMMENDATION: {brief['recommendation'].upper()}")
    print("\n" + "─" * 60)
    print("  SIGNAL BREAKDOWN")
    print("─" * 60)
    for sig in brief.get("signal_breakdown", []):
        print(f"  ▸ {sig.get('name', '')} ({sig.get('source', '')})")
        print(f"    {sig.get('value', '')}")
    print("\n" + "─" * 60)
    print("  NEXT MOVE")
    print("─" * 60)
    print(f"  {brief.get('next_move', '')}")
    print("\n" + "─" * 60)
    print("  30-DAY WATCH LIST")
    print("─" * 60)
    print(f"  {brief.get('watch_list', '')}")
    print("\n" + "═" * 60 + "\n")


# ── Main loop ─────────────────────────────────────────────────────────────────


def main() -> None:
    deal_context = get_deal_input()

    submarket = deal_context["location"]
    asset_type = deal_context["asset_type"]

    print("\nFetching market signals...")

    fred_signals = fred.fetch(submarket)
    census_signals = _stub_census_fetch(submarket)  # swap: census.fetch(submarket)
    tavily_signals = _stub_tavily_fetch(
        submarket, asset_type
    )  # swap: tavily.fetch(submarket, asset_type)

    all_signals = [*fred_signals, *census_signals, *tavily_signals]
    print(f"  {len(all_signals)} signals collected.")

    print("Analyzing signals...")
    brief = _stub_analyze(
        deal_context, all_signals
    )  # swap: analyzer.analyze(deal_context, all_signals)

    approved = run_checkpoint(brief)

    if not approved:
        print("\nBrief rejected. Exiting.")
        sys.exit(0)

    print_brief(brief, deal_context)


if __name__ == "__main__":
    main()
