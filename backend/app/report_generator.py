"""Generate combined PDF reports for all suppliers."""
from __future__ import annotations

import io
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, SimpleDocTemplate, HRFlowable,
)

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm

BLUE = colors.HexColor("#2563eb")
LIGHT_BLUE = colors.HexColor("#dbeafe")
GRAY = colors.HexColor("#6b7280")
LIGHT_GRAY = colors.HexColor("#f9fafb")
DARK = colors.HexColor("#1f2937")


def _period_label(date_from: date, date_to: date) -> str:
    return f"{date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}"


def _last_week_range() -> tuple[date, date]:
    today = date.today()
    # Previous Monday
    monday = today - timedelta(days=today.weekday() + 7)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _current_month_range() -> tuple[date, date]:
    today = date.today()
    return today.replace(day=1), today


def period_dates(report_period: str) -> tuple[date, date]:
    if report_period == "current_month":
        return _current_month_range()
    return _last_week_range()


def generate_report_pdf(
    db,
    date_from: date,
    date_to: date,
    supplier_codes: list[str] | None = None,
) -> bytes:
    """Generate a combined PDF report for all (or selected) suppliers.

    Returns the PDF as bytes.
    """
    from . import models  # local import to avoid circular deps

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "title", parent=styles["Heading1"],
        fontSize=18, textColor=BLUE, spaceAfter=2 * mm, leading=22,
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["Normal"],
        fontSize=10, textColor=GRAY, spaceAfter=6 * mm,
    )
    section_style = ParagraphStyle(
        "section", parent=styles["Heading2"],
        fontSize=13, textColor=DARK, spaceBefore=8 * mm, spaceAfter=3 * mm,
    )
    small_style = ParagraphStyle(
        "small", parent=styles["Normal"],
        fontSize=8, textColor=GRAY,
    )

    # Load data
    supplier_q = db.query(models.Supplier).filter(models.Supplier.is_active == True)
    if supplier_codes:
        supplier_q = supplier_q.filter(models.Supplier.code.in_(supplier_codes))
    suppliers = supplier_q.order_by(models.Supplier.name).all()

    period_str = _period_label(date_from, date_to)

    story = []

    # Header
    story.append(Paragraph("WinAgent Bericht", title_style))
    story.append(Paragraph(f"Zeitraum: {period_str}", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=6 * mm))

    summary_rows: list[tuple] = []

    for supplier in suppliers:
        txs = (
            db.query(models.Transaction)
            .filter(
                models.Transaction.supplier_id == supplier.id,
                models.Transaction.invoice_date >= date_from,
                models.Transaction.invoice_date <= date_to,
            )
            .order_by(models.Transaction.invoice_date)
            .all()
        )

        if not txs:
            continue

        story.append(Paragraph(f"{supplier.code} – {supplier.name}", section_style))

        # Transaction table
        header = ["Datum", "Re.-Nr.", "Kunde", "Betrag", "Währung", "Provision %", "Provision"]
        col_widths = [22 * mm, 28 * mm, 55 * mm, 24 * mm, 16 * mm, 22 * mm, 22 * mm]

        table_data = [header]
        totals: dict[str, float] = {}
        prov_totals: dict[str, float] = {}

        for tx in txs:
            cust_name = ""
            if tx.customer:
                cust_name = tx.customer.name[:30]
            elif hasattr(tx, "customer_name") and tx.customer_name:
                cust_name = tx.customer_name[:30]

            cur = tx.currency or "EUR"
            amt = float(tx.total_amount or 0)
            prov = float(tx.provision_amount) if tx.provision_amount is not None else None
            rate = float(tx.provision_rate) if tx.provision_rate is not None else None

            totals[cur] = totals.get(cur, 0) + amt
            if prov is not None:
                prov_totals[cur] = prov_totals.get(cur, 0) + prov

            table_data.append([
                tx.invoice_date.strftime("%d.%m.%Y") if tx.invoice_date else "",
                tx.invoice_number or "",
                cust_name,
                f"{amt:,.2f}",
                cur,
                f"{rate:.2f} %" if rate is not None else "",
                f"{prov:,.2f}" if prov is not None else "",
            ])

        # Totals row per currency
        for cur, total in totals.items():
            prov_t = prov_totals.get(cur)
            table_data.append([
                "", "Gesamt", "",
                f"{total:,.2f}", cur, "",
                f"{prov_t:,.2f}" if prov_t is not None else "",
            ])
            summary_rows.append((supplier.name, cur, total, prov_t))

        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("TOPPADDING", (0, 0), (-1, 0), 4),
            # Body
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TOPPADDING", (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
            # Total row
            ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            # Alignment
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("ALIGN", (5, 0), (6, -1), "RIGHT"),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, BLUE),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4 * mm))

    # Summary table
    if summary_rows:
        story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceBefore=8 * mm, spaceAfter=4 * mm))
        story.append(Paragraph("Gesamtübersicht", section_style))

        sum_header = ["Lieferant", "Währung", "Umsatz gesamt", "Provision gesamt"]
        sum_data = [sum_header] + [
            [name, cur, f"{amt:,.2f}", f"{prov:,.2f}" if prov is not None else ""]
            for name, cur, amt, prov in summary_rows
        ]
        sum_col_w = [70 * mm, 20 * mm, 40 * mm, 40 * mm]
        sum_tbl = Table(sum_data, colWidths=sum_col_w, repeatRows=1)
        sum_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("ALIGN", (2, 0), (3, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ]))
        story.append(sum_tbl)

    if not any(True for s in suppliers for _ in [s]):  # if no data at all
        story.append(Paragraph("Keine Transaktionen im gewählten Zeitraum.", styles["Normal"]))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        f"Erstellt am {date.today().strftime('%d.%m.%Y')} · WinAgent",
        small_style,
    ))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"WinAgent Bericht {period_str}",
    )
    doc.build(story)
    return buf.getvalue()
