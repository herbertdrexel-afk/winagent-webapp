"""Generate combined PDF reports (transactions + statistics)."""
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

BLUE       = colors.HexColor("#2563eb")
LIGHT_BLUE = colors.HexColor("#dbeafe")
GRAY       = colors.HexColor("#6b7280")
LIGHT_GRAY = colors.HexColor("#f9fafb")
DARK       = colors.HexColor("#1f2937")
GREEN      = colors.HexColor("#059669")
RED        = colors.HexColor("#dc2626")

styles = getSampleStyleSheet()
H1    = ParagraphStyle("rh1", fontSize=14, textColor=BLUE, leading=18, spaceAfter=3*mm, fontName="Helvetica-Bold")
H2    = ParagraphStyle("rh2", fontSize=11, textColor=DARK, leading=15, spaceBefore=5*mm, spaceAfter=2*mm, fontName="Helvetica-Bold")
BODY  = ParagraphStyle("rb",  fontSize=9,  textColor=DARK, leading=13, spaceAfter=1*mm)
SMALL = ParagraphStyle("rs",  fontSize=8,  textColor=GRAY, leading=12)


# ── Period helpers ────────────────────────────────────────────────────────────

PERIOD_LABELS = {
    "last_week":     "Letzte Woche (Mo–So)",
    "last_month":    "Letzter Monat",
    "current_month": "Aktueller Monat",
    "current_year":  "Aktuelles Jahr",
    "last_year":     "Letztes Jahr",
    "last_30_days":  "Letzte 30 Tage",
    "last_90_days":  "Letzte 90 Tage",
    "last_quarter":  "Letztes Quartal",
}

REPORT_TYPE_LABELS = {
    "supplier_summary":   "Lieferant Statistik",
    "customer_provision": "AdrUms nach Provision",
    "customer_turnover":  "AdrUms nach Umsatz",
    "supplier_detail":    "Lieferant Detail (Quartale)",
    "transactions":       "Rechnungsübersicht",
}

ALL_REPORT_TYPES = list(REPORT_TYPE_LABELS.keys())


def period_dates(report_period: str) -> tuple[date, date]:
    today = date.today()
    if report_period == "last_week":
        monday = today - timedelta(days=today.weekday() + 7)
        return monday, monday + timedelta(days=6)
    if report_period == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if report_period == "current_month":
        return today.replace(day=1), today
    if report_period == "current_year":
        return today.replace(month=1, day=1), today
    if report_period == "last_year":
        y = today.year - 1
        return date(y, 1, 1), date(y, 12, 31)
    if report_period == "last_30_days":
        return today - timedelta(days=30), today
    if report_period == "last_90_days":
        return today - timedelta(days=90), today
    if report_period == "last_quarter":
        q = (today.month - 1) // 3          # 0..3
        if q == 0:
            q, y = 4, today.year - 1
        else:
            y = today.year
        sm = (q - 1) * 3 + 1
        em = q * 3
        import calendar
        ed = calendar.monthrange(y, em)[1]
        return date(y, sm, 1), date(y, em, ed)
    # fallback
    monday = today - timedelta(days=today.weekday() + 7)
    return monday, monday + timedelta(days=6)


def period_year(report_period: str) -> int:
    if report_period in ("last_year",):
        return date.today().year - 1
    return date.today().year


def _period_label(date_from: date, date_to: date) -> str:
    return f"{date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}"


# ── Table style helpers ───────────────────────────────────────────────────────

def _base_style(has_total=True):
    n = -1 if has_total else -999
    style = [
        ("BACKGROUND",    (0, 0), (-1, 0),  BLUE),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID",          (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS",(0, 1), (-1, n),  [colors.white, LIGHT_GRAY]),
    ]
    if has_total:
        style += [
            ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
            ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
    return style


def _fmt(n: float, zero="0") -> str:
    if n == 0:
        return zero
    return f"{n:,.0f}".replace(",", ".")


def _pct(curr: float, prev: float) -> str:
    if not prev:
        return "***"
    p = (curr / prev - 1) * 100
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.1f}%"


def _diff_color(val: float):
    return GREEN if val > 0 else (RED if val < 0 else GRAY)


# ── Section builders ──────────────────────────────────────────────────────────

def _build_supplier_summary(db, date_from: date, date_to: date, supplier_codes) -> list:
    from .routers.stats import supplier_summary
    data = supplier_summary(date_from, date_to, db)
    rows = data["rows"]
    if supplier_codes:
        rows = [r for r in rows if r["code"] in supplier_codes]
    if not rows:
        return [Paragraph("Keine Daten im gewählten Zeitraum.", BODY)]

    story = []
    story.append(Paragraph("Lieferant Statistik", H2))

    header = ["Lieferant", "Umsatz VJ", "Umsatz Aktuell", "Prov. VJ", "Prov. Aktuell", "Diff.", "+/-%"]
    col_w  = [55*mm, 25*mm, 25*mm, 22*mm, 25*mm, 20*mm, 18*mm]
    tdata  = [header]

    tot_ct = tot_pt = tot_cc = tot_pc = 0.0
    for r in rows:
        ct, pt = r["curr_turnover"], r["prev_turnover"]
        cc, pc = r["curr_commission"], r["prev_commission"]
        diff   = cc - pc
        tot_ct += ct; tot_pt += pt; tot_cc += cc; tot_pc += pc
        tdata.append([
            r["name"],
            _fmt(pt), _fmt(ct),
            _fmt(pc), _fmt(cc),
            ("+" if diff > 0 else "") + _fmt(diff),
            _pct(cc, pc),
        ])

    tot_diff = tot_cc - tot_pc
    tdata.append(["Gesamt", _fmt(tot_pt), _fmt(tot_ct), _fmt(tot_pc), _fmt(tot_cc),
                  ("+" if tot_diff > 0 else "") + _fmt(tot_diff), _pct(tot_cc, tot_pc)])

    tbl = Table(tdata, colWidths=col_w, repeatRows=1)
    style = _base_style()
    for i, r in enumerate(rows, 1):
        diff = r["curr_commission"] - r["prev_commission"]
        col = _diff_color(diff)
        style += [("TEXTCOLOR", (5, i), (6, i), col)]
    tbl.setStyle(TableStyle(style + [("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    story.append(tbl)
    return story


def _build_customer_turnover(db, date_from: date, date_to: date, sort_by: str) -> list:
    from .routers.stats import customer_turnover
    data = customer_turnover(date_from, date_to, sort_by, db)
    rows = data["rows"][:50]  # limit to top 50 in email report
    if not rows:
        return [Paragraph("Keine Daten im gewählten Zeitraum.", BODY)]

    label = "AdrUms nach Provision" if sort_by == "provision" else "AdrUms nach Umsatz"
    story = [Paragraph(label, H2)]

    header = ["Name / Firma", "Umsatz VJ", "Umsatz Aktuell", "Provision", "DuPr %", "Anteil %"]
    col_w  = [60*mm, 22*mm, 25*mm, 22*mm, 18*mm, 18*mm]
    tdata  = [header]

    tot_t = tot_p = 0.0
    for r in rows:
        tot_t += r["curr_turnover"]; tot_p += r["curr_provision"]
        tdata.append([
            r["customer_name"][:35],
            _fmt(r["prev_turnover"]), _fmt(r["curr_turnover"]),
            _fmt(r["curr_provision"]),
            f"{r['avg_rate']:.2f}",
            f"{r['share_pct']:.1f}%",
        ])
    tdata.append(["Gesamtsumme (EUR)", _fmt(sum(r["prev_turnover"] for r in rows)),
                  _fmt(tot_t), _fmt(tot_p), "", ""])

    tbl = Table(tdata, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(_base_style() + [("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    story.append(tbl)
    if len(data["rows"]) > 50:
        story.append(Paragraph(f"(Nur Top 50 von {len(data['rows'])} Kunden dargestellt)", SMALL))
    return story


def _build_supplier_detail(db, year: int, supplier_codes) -> list:
    from .routers.stats import supplier_detail
    data = supplier_detail(year, db)
    suppliers = data["suppliers"]
    if supplier_codes:
        suppliers = [s for s in suppliers if s["code"] in supplier_codes]
    if not suppliers:
        return [Paragraph("Keine Daten für das gewählte Jahr.", BODY)]

    story = [Paragraph(f"Lieferant Detail – Quartale {year}", H2)]
    BOLD = {"1.HY", "2.HY", "Jahr"}

    for s in suppliers:
        story.append(Paragraph(f"{s['code']} – {s['name']}", ParagraphStyle(
            "sn", fontSize=9, textColor=DARK, fontName="Helvetica-Bold",
            spaceBefore=3*mm, spaceAfter=1*mm)))

        header = ["", "Umsatz VJ", "Budget", "+/-", "Umsatz Aktuell", "+/-",
                  "Prov. VJ", "Prov. Budget", "Prov. Aktuell", "+/-", "Diff.", "+/-"]
        col_w  = [10*mm, 17*mm, 14*mm, 10*mm, 20*mm, 10*mm,
                  16*mm, 16*mm, 20*mm, 10*mm, 14*mm, 10*mm]
        tdata  = [header]

        for r in s["rows"]:
            ct, pt = r["curr_turnover"], r["prev_turnover"]
            cc, pc = r["curr_commission"], r["prev_commission"]
            bt, bc = r["budget_turnover"], r["budget_commission"]
            diff   = cc - pc
            bold   = r["label"] in BOLD
            row = [
                r["label"],
                _fmt(pt), _fmt(bt) if bt else "", _pct(bt, pt) if bt and pt else "",
                _fmt(ct), _pct(ct, pt),
                _fmt(pc), _fmt(bc) if bc else "",
                _fmt(cc), _pct(cc, pc),
                ("+" if diff > 0 else "") + _fmt(diff), _pct(cc, pc),
            ]
            tdata.append(row)

        tbl = Table(tdata, colWidths=col_w, repeatRows=1)
        bold_rows = [i+1 for i, r in enumerate(s["rows"]) if r["label"] in BOLD]
        style = _base_style(has_total=False) + [("ALIGN", (1, 0), (-1, -1), "RIGHT")]
        for bi in bold_rows:
            style += [("BACKGROUND", (0, bi), (-1, bi), LIGHT_BLUE),
                      ("FONTNAME",   (0, bi), (-1, bi), "Helvetica-Bold")]
        tbl.setStyle(TableStyle(style))
        story.append(tbl)

    return story


def _build_transactions(db, date_from: date, date_to: date, supplier_codes) -> list:
    from . import models
    from sqlalchemy.orm import joinedload

    supplier_q = db.query(models.Supplier).filter(models.Supplier.is_active == True)
    if supplier_codes:
        supplier_q = supplier_q.filter(models.Supplier.code.in_(supplier_codes))
    suppliers = supplier_q.order_by(models.Supplier.name).all()

    story = [Paragraph("Rechnungsübersicht", H2)]
    summary_rows = []

    for supplier in suppliers:
        txs = (
            db.query(models.Transaction)
            .options(joinedload(models.Transaction.customer))
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

        story.append(Paragraph(f"{supplier.code} – {supplier.name}", ParagraphStyle(
            "ts", fontSize=10, textColor=DARK, fontName="Helvetica-Bold",
            spaceBefore=4*mm, spaceAfter=1*mm)))

        header = ["Datum", "Re.-Nr.", "Kunde", "Betrag", "Währung", "Prov.%", "Provision"]
        col_w  = [22*mm, 28*mm, 55*mm, 22*mm, 14*mm, 16*mm, 20*mm]
        tdata  = [header]
        totals: dict[str, float] = {}
        prov_totals: dict[str, float] = {}

        for tx in txs:
            cust = tx.customer.name[:30] if tx.customer else ""
            cur = tx.currency or "EUR"
            amt = float(tx.total_amount or 0)
            prov = float(tx.provision_amount) if hasattr(tx, "provision_amount") and tx.provision_amount is not None else None
            rate = float(tx.provision_rate) if tx.provision_rate is not None else None
            totals[cur] = totals.get(cur, 0) + amt
            if prov is not None:
                prov_totals[cur] = prov_totals.get(cur, 0) + prov
            tdata.append([
                tx.invoice_date.strftime("%d.%m.%Y") if tx.invoice_date else "",
                tx.invoice_number or "",
                cust,
                f"{amt:,.2f}",
                cur,
                f"{rate:.2f}" if rate is not None else "",
                f"{prov:,.2f}" if prov is not None else "",
            ])

        for cur, total in totals.items():
            prov_t = prov_totals.get(cur)
            tdata.append(["", "Gesamt", "", f"{total:,.2f}", cur, "",
                          f"{prov_t:,.2f}" if prov_t is not None else ""])
            summary_rows.append((supplier.name, cur, total, prov_t))

        tbl = Table(tdata, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle(_base_style() + [
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("ALIGN", (5, 0), (6, -1), "RIGHT"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 2*mm))

    if summary_rows:
        story.append(Paragraph("Gesamtübersicht", H2))
        sum_header = ["Lieferant", "Währung", "Umsatz gesamt", "Provision gesamt"]
        sum_data = [sum_header] + [
            [name, cur, f"{amt:,.2f}", f"{prov:,.2f}" if prov is not None else ""]
            for name, cur, amt, prov in summary_rows
        ]
        sum_tbl = Table(sum_data, colWidths=[70*mm, 18*mm, 38*mm, 38*mm], repeatRows=1)
        sum_tbl.setStyle(TableStyle(_base_style() + [("ALIGN", (2, 0), (3, -1), "RIGHT")]))
        story.append(sum_tbl)

    return story


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_report_pdf(
    db,
    date_from: date,
    date_to: date,
    supplier_codes: list[str] | None = None,
    report_types: list[str] | None = None,
) -> bytes:
    """Generate combined PDF report.

    report_types: list from supplier_summary, customer_provision,
                  customer_turnover, supplier_detail, transactions.
                  None = all.
    """
    active_types = report_types if report_types else ALL_REPORT_TYPES
    period_str   = _period_label(date_from, date_to)
    year         = date_from.year  # for supplier_detail

    story = []

    # Title
    story.append(Paragraph("WinAgent Bericht", ParagraphStyle(
        "title", fontSize=16, textColor=BLUE, fontName="Helvetica-Bold",
        spaceAfter=1*mm)))
    story.append(Paragraph(f"Zeitraum: {period_str}", SMALL))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=4*mm))

    for rtype in active_types:
        if rtype == "supplier_summary":
            story.extend(_build_supplier_summary(db, date_from, date_to, supplier_codes))
            story.append(Spacer(1, 3*mm))
        elif rtype == "customer_provision":
            story.extend(_build_customer_turnover(db, date_from, date_to, "provision"))
            story.append(Spacer(1, 3*mm))
        elif rtype == "customer_turnover":
            story.extend(_build_customer_turnover(db, date_from, date_to, "turnover"))
            story.append(Spacer(1, 3*mm))
        elif rtype == "supplier_detail":
            story.extend(_build_supplier_detail(db, year, supplier_codes))
            story.append(Spacer(1, 3*mm))
        elif rtype == "transactions":
            story.extend(_build_transactions(db, date_from, date_to, supplier_codes))

    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        f"Erstellt am {date.today().strftime('%d.%m.%Y')} · WinAgent",
        SMALL))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"WinAgent Bericht {period_str}",
    )
    doc.build(story)
    return buf.getvalue()
