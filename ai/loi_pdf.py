"""
ai/loi_pdf.py - Generates a PDF Letter of Intent document.
Returns raw bytes suitable for attaching to an email.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fpdf import FPDF


def generate(deal_context: dict[str, Any], analysis: dict[str, Any], offer_price: int) -> bytes:
    buyer = {
        "entity": "Mesa Capital Partners LLC",
        "contact": "Joel Martinez",
        "phone": "(602) 555-0147",
        "email": "joel@mesacapitalpartners.com",
    }

    today = date.today()
    expiry = today + timedelta(hours=72)
    dd_days = 30
    closing_days = 45
    earnest = int(offer_price * 0.01)

    pdf = FPDF()
    pdf.set_margins(25, 20, 25)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Header ────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "LETTER OF INTENT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Non-Binding - For Discussion Purposes Only", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.5)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 160, pdf.get_y())
    pdf.ln(6)

    # ── Date + Parties ────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Date: {today.strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "BUYER", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, buyer["entity"], new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Attn: {buyer['contact']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Phone: {buyer['phone']}  |  Email: {buyer['email']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "PROPERTY", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Asset Type:  {deal_context.get('asset_type', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Submarket:   {deal_context.get('submarket', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Anchor Tenant: {deal_context.get('anchor_tenant', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # ── Terms ─────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "PROPOSED TERMS", new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 160, pdf.get_y())
    pdf.ln(4)

    def term_row(label: str, value: str) -> None:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(65, 7, label)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    term_row("Purchase Price:", f"${offer_price:,.0f}")
    term_row("Earnest Money Deposit:", f"${earnest:,.0f}  (1% of purchase price, hard at signing)")
    term_row("Due Diligence Period:", f"{dd_days} days from execution")
    term_row("Closing:", f"{closing_days} days from execution")
    term_row("Financing Contingency:", "None - all-equity acquisition")
    term_row("LOI Expiration:", expiry.strftime("%B %d, %Y") + "  (72 hours from date above)")
    pdf.ln(6)

    # ── Conditions ────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "CONDITIONS", new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 160, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    conditions = [
        "1. Satisfactory completion of due diligence including review of rent roll, T-12 financials, and physical inspection.",
        "2. Title review free of material encumbrances.",
        "3. Execution of a mutually acceptable Purchase and Sale Agreement.",
        "4. No material adverse change to the property or tenancy prior to closing.",
    ]
    for c in conditions:
        pdf.multi_cell(0, 6, c, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    pdf.ln(4)

    # ── Non-binding disclaimer ────────────────────────────────────────────────
    pdf.set_font("Helvetica", "I", 9)
    disclaimer = (
        "This Letter of Intent is non-binding and is intended solely to outline the proposed terms "
        "of a potential transaction. Neither party shall have any legal obligation to the other until "
        "a definitive Purchase and Sale Agreement has been fully executed by both parties."
    )
    pdf.multi_cell(0, 5, disclaimer, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    # ── Signature blocks ──────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "SIGNATURES", new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 160, pdf.get_y())
    pdf.ln(8)

    sig_y = pdf.get_y()
    left_x = 25
    right_x = 120

    def sig_block(x: float, title: str, name: str, entity: str) -> None:
        pdf.set_xy(x, sig_y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(75, 6, title)
        pdf.set_xy(x, sig_y + 8)
        pdf.set_font("Helvetica", "", 10)
        pdf.line(x, sig_y + 22, x + 70, sig_y + 22)
        pdf.set_xy(x, sig_y + 24)
        pdf.cell(75, 6, f"Name: {name}")
        pdf.set_xy(x, sig_y + 31)
        pdf.cell(75, 6, f"Title: Authorized Signatory")
        pdf.set_xy(x, sig_y + 38)
        pdf.cell(75, 6, f"Entity: {entity}")
        pdf.set_xy(x, sig_y + 45)
        pdf.cell(75, 6, f"Date: _______________________")

    sig_block(left_x, "BUYER", buyer["contact"], buyer["entity"])
    sig_block(right_x, "SELLER / BROKER", "________________________", "________________________")

    return bytes(pdf.output())
