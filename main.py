import argparse
import sys

from dotenv import load_dotenv
from fetchers import census, fred, tavily
from ai import analyzer

load_dotenv()

DEMO_DEAL = {
    "asset_type": "Industrial, 412k sqft",
    "location": "Phoenix-Mesa-Chandler",
    "price": 95_000_000.0,
    "cap_rate": "5.8%",
    "tenants": "Amazon · 65% of NOI",
    "lender": "Wells Fargo",
    "dscr_constraint": "1.25",
}


# ── Deal input ────────────────────────────────────────────────────────────────


def get_deal_input(demo: bool = False) -> dict:
    print("\n" + "═" * 60)
    print("  CRE DEAL MONITOR")
    print("═" * 60 + "\n")

    if demo:
        print("  [DEMO MODE] Using preset deal scenario.\n")
        for key, val in DEMO_DEAL.items():
            label = key.replace("_", " ").title()
            print(f"  {label}: {val}")
        print()
        return DEMO_DEAL

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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo", action="store_true", help="Run with preset demo scenario"
    )
    args = parser.parse_args()

    deal_context = get_deal_input(demo=args.demo)

    submarket = deal_context["location"]
    asset_type = deal_context["asset_type"]

    print("\nFetching market signals...")

    fred_signals = fred.fetch(submarket)
    census_signals = census.fetch(submarket)
    tavily_signals = tavily.fetch(submarket, asset_type)

    all_signals = [*fred_signals, *census_signals, *tavily_signals]
    print(f"  {len(all_signals)} signals collected.")

    print("Analyzing signals...")
    brief = analyzer.analyze_deal(
        deal_context, fred_signals, census_signals, tavily_signals
    )

    approved = run_checkpoint(brief)

    if not approved:
        print("\nBrief rejected. Exiting.")
        sys.exit(0)

    print_brief(brief, deal_context)


if __name__ == "__main__":
    main()
