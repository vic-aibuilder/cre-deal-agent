import sys
from pathlib import Path

from dotenv import load_dotenv
from agents.email_agent import (
    monitor_broker_inbox,
    send_broker_inquiry,
    send_loi_cover_email,
)
from ai import analyzer
from fetchers import census, fred, tavily

load_dotenv()


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
    broker_email = input("Listing broker email (optional): ").strip()
    property_address = input("Property address (optional): ").strip()
    loi_pdf_path = input("LOI PDF path (optional, for auto-send): ").strip()

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
        "broker_email": broker_email,
        "property_address": property_address,
        "loi_pdf_path": loi_pdf_path,
    }


def _run_email_agent(deal_context: dict) -> None:
    broker_email = str(deal_context.get("broker_email", "")).strip()
    if not broker_email:
        print("EmailAgent: broker email not provided, skipping autonomous outreach.")
        return

    try:
        inquiry = send_broker_inquiry(broker_email=broker_email, deal_context=deal_context)
    except Exception as exc:
        print(f"EmailAgent: inquiry send failed: {exc}")
        return

    thread_id = inquiry.get("thread_id", "")
    print(f"EmailAgent: inquiry sent (thread={thread_id or 'unknown'}).")

    try:
        events = monitor_broker_inbox(
            active_thread_ids=[thread_id] if thread_id else None,
            max_results=20,
        )
        flagged = sum(1 for event in events if event.get("action") == "trigger_negotiation_agent")
        print(
            f"EmailAgent: inbox scan complete ({len(events)} events, {flagged} negotiation triggers)."
        )
    except Exception as exc:
        print(f"EmailAgent: inbox monitor failed: {exc}")

    loi_pdf_path = str(deal_context.get("loi_pdf_path", "")).strip()
    if not loi_pdf_path:
        print("EmailAgent: LOI path not provided, skipping LOI cover email.")
        return
    if not Path(loi_pdf_path).exists():
        print(f"EmailAgent: LOI file not found at {loi_pdf_path}, skipping LOI send.")
        return

    property_address = str(deal_context.get("property_address", "")).strip() or str(
        deal_context.get("location", "")
    ).strip()

    try:
        loi_send = send_loi_cover_email(
            broker_email=broker_email,
            property_address=property_address,
            loi_pdf_path=loi_pdf_path,
            thread_id=thread_id or None,
        )
        print(f"EmailAgent: LOI cover email sent (thread={loi_send.get('thread_id', '')}).")
    except Exception as exc:
        print(f"EmailAgent: LOI cover email failed: {exc}")


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
    census_signals = census.fetch(submarket)
    tavily_signals = tavily.fetch(submarket, asset_type)

    all_signals = [*fred_signals, *census_signals, *tavily_signals]
    print(f"  {len(all_signals)} signals collected.")

    print("Analyzing signals...")
    brief = analyzer.analyze_deal(
        deal_context, fred_signals, census_signals, tavily_signals
    )

    # V2 autonomous outreach: send first-touch broker email and monitor replies.
    _run_email_agent(deal_context)

    approved = run_checkpoint(brief)

    if not approved:
        print("\nBrief rejected. Exiting.")
        sys.exit(0)

    print_brief(brief, deal_context)


if __name__ == "__main__":
    main()
