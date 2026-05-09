import argparse
import os
import smtplib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fetchers import census, fred, tavily, finder
from ai import analyzer, closer

load_dotenv()

console = Console()

DEMO_DEAL = {
    "asset_type": "Industrial, 412k sqft",
    "submarket": "Phoenix-Mesa-Chandler",
    "purchase_price": 95_000_000,
    "cap_rate": 0.058,
    "anchor_tenant": "Amazon",
    "tenant_noi_pct": 0.65,
    "lender": "Wells Fargo",
    "dscr_covenant": 1.25,
}


# ── Deal input ────────────────────────────────────────────────────────────────


def get_deal_input(demo: bool = False) -> dict:
    console.print(Panel("CRE DEAL MONITOR", style="bold"))

    if demo:
        console.print("[dim]Demo mode — using preset Phoenix scenario.[/dim]\n")
        table = Table(show_header=False, box=None, padding=(0, 2))
        for key, val in DEMO_DEAL.items():
            table.add_row(f"[cyan]{key.replace('_', ' ').title()}[/cyan]", str(val))
        console.print(table)
        console.print()
        return DEMO_DEAL

    asset_type = input("Asset type (e.g. Industrial, 412k sqft): ").strip()
    submarket = input("Submarket (e.g. Phoenix-Mesa-Chandler): ").strip()
    purchase_price_raw = input("Purchase price in dollars (e.g. 95000000): ").strip()
    cap_rate_raw = input("Cap rate as decimal (e.g. 0.058): ").strip()
    anchor_tenant = input("Anchor tenant (e.g. Amazon): ").strip()
    tenant_noi_pct_raw = input(
        "Anchor tenant % of NOI as decimal (e.g. 0.65): "
    ).strip()
    lender = input("Lender (e.g. Wells Fargo): ").strip()
    dscr_covenant_raw = input("DSCR covenant (e.g. 1.25): ").strip()

    try:
        purchase_price = int(purchase_price_raw.replace(",", "").replace("$", ""))
    except ValueError:
        purchase_price = 0

    return {
        "asset_type": asset_type,
        "submarket": submarket,
        "purchase_price": purchase_price,
        "cap_rate": float(cap_rate_raw),
        "anchor_tenant": anchor_tenant,
        "tenant_noi_pct": float(tenant_noi_pct_raw),
        "lender": lender,
        "dscr_covenant": float(dscr_covenant_raw),
    }


# ── Email sender ──────────────────────────────────────────────────────────────


def send_email(email_dict: dict) -> bool:
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        raise EnvironmentError("GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env")

    msg = MIMEText(email_dict["body"])
    msg["Subject"] = email_dict["subject"]
    msg["From"] = email_dict.get("from") or gmail_user
    msg["To"] = email_dict["to"]

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(gmail_user, gmail_password)
            smtp.sendmail(gmail_user, [email_dict["to"]], msg.as_string())
        return True
    except smtplib.SMTPException as e:
        console.print(Panel(f"[red]Send failed: {e}[/red]", title="EMAIL ERROR"))
        return False


# ── Dashboard ─────────────────────────────────────────────────────────────────


def _signals_panel(signals: list[dict], title: str) -> Panel:
    table = Table(show_header=False, box=None, padding=(0, 1))
    if not signals:
        table.add_row("[dim]None[/dim]")
    for sig in signals:
        table.add_row(
            f"[cyan]{sig.get('name', '')}[/cyan]",
            sig.get("value", ""),
            f"[dim]{sig.get('source', '')}[/dim]",
        )
    return Panel(table, title=title)


def _email_panel(email_dict: dict, sent: bool = False) -> Panel:
    status = "[green]SENT[/green]" if sent else "[yellow]AWAITING YOUR REVIEW[/yellow]"
    body = (
        f"[bold]To:[/bold]      {email_dict.get('to', '')}\n"
        f"[bold]Subject:[/bold] {email_dict.get('subject', '')}\n\n"
        f"{email_dict.get('body', '')}"
    )
    return Panel(body, title=f"EMAIL — {status}")


def _human_gate(email_dict: dict) -> bool:
    console.print(_email_panel(email_dict, sent=False))
    console.print(
        "\n[bold yellow]This email requires your review before sending.[/bold yellow]"
    )
    while True:
        answer = input("Send? (yes/no): ").strip().lower()
        if answer == "yes":
            return True
        if answer == "no":
            return False
        console.print("Please enter yes or no.")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run preset demo scenario")
    args = parser.parse_args()

    deal_context = get_deal_input(demo=args.demo)
    submarket = deal_context["submarket"]
    asset_type = deal_context["asset_type"]
    price = float(deal_context["purchase_price"])

    # ── Stage 2: Parallel fetch ───────────────────────────────────────────────

    fred_signals: list[dict] = []
    census_signals: list[dict] = []
    tavily_signals: list[dict] = []
    offer_signals: list[dict] = []

    fetch_tasks: dict = {
        "FRED": (fred.fetch, (submarket,)),
        "Census": (census.fetch, (submarket,)),
        "Tavily": (tavily.fetch, (submarket, asset_type)),
        "Finder": (finder.find_offers, (submarket, asset_type, price)),
    }

    console.print("\n[bold]Fetching market signals...[/bold]")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(fn, *fn_args): name
            for name, (fn, fn_args) in fetch_tasks.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                result: list[dict] = future.result()
            except Exception as e:
                console.print(f"  [red]✗[/red] {name} — {e}")
                result = []

            if name == "FRED":
                fred_signals = result
            elif name == "Census":
                census_signals = result
            elif name == "Tavily":
                tavily_signals = result
            elif name == "Finder":
                offer_signals = result

            console.print(f"  [green]✓[/green] {name} — {len(result)} signals")

    # ── Stage 3: Analysis (internal) ─────────────────────────────────────────

    console.print("\n[bold]Analyzing deal...[/bold]")
    analysis = analyzer.analyze_deal(
        deal_context, fred_signals, census_signals, tavily_signals
    )

    # ── Dashboard ─────────────────────────────────────────────────────────────

    all_signals = [*fred_signals, *census_signals, *tavily_signals]
    console.print()
    console.print(_signals_panel(all_signals, "LIVE SIGNALS"))
    console.print(
        _signals_panel(offer_signals, "COMPETING OFFERS")
        if offer_signals
        else Panel("[dim]No competing offers found.[/dim]", title="COMPETING OFFERS")
    )

    # ── Stage 4: Email + send ─────────────────────────────────────────────────

    loi_urgency = analysis.get("loi_urgency", "hold")

    if loi_urgency in ("submit_within_24h", "submit_within_72h"):
        # LOI cover — human gate (needs signed document attached)
        email = closer.draft_loi(deal_context, analysis, {})
        if _human_gate(email):
            sent = send_email(email)
            console.print(_email_panel(email, sent=sent))
        else:
            console.print("\n[dim]LOI email cancelled.[/dim]")
            sys.exit(0)
    else:
        # Outreach — auto-send, no gate
        email = closer.draft_outreach(deal_context)
        console.print("\n[bold]Sending outreach email...[/bold]")
        sent = send_email(email)
        console.print(_email_panel(email, sent=sent))


if __name__ == "__main__":
    main()
