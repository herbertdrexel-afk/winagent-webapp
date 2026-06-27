"""Generate combined PDF reports with charts."""
from __future__ import annotations

import io
import logging
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, SimpleDocTemplate,
    HRFlowable, Image,
)

logger = logging.getLogger(__name__)

PAGE_W, PAGE_H = A4
MARGIN     = 18 * mm
CONTENT_W  = PAGE_W - 2 * MARGIN

BLUE       = colors.HexColor("#2563eb")
LIGHT_BLUE = colors.HexColor("#dbeafe")
GRAY       = colors.HexColor("#6b7280")
LIGHT_GRAY = colors.HexColor("#f9fafb")
DARK       = colors.HexColor("#1f2937")
GREEN      = colors.HexColor("#059669")
RED        = colors.HexColor("#dc2626")

H1   = ParagraphStyle("rh1", fontSize=14, textColor=BLUE,  leading=18,
    spaceAfter=3*mm, fontName="Helvetica-Bold")
H2   = ParagraphStyle("rh2", fontSize=11, textColor=DARK,  leading=15,
    spaceBefore=5*mm, spaceAfter=2*mm, fontName="Helvetica-Bold")
BODY = ParagraphStyle("rb",  fontSize=9,  textColor=DARK,  leading=13, spaceAfter=1*mm)
SMALL= ParagraphStyle("rs",  fontSize=8,  textColor=GRAY,  leading=12)


# ── Period helpers ────────────────────────────────────────────────────────────

ALL_REPORT_TYPES = [
    "supplier_summary", "customer_provision", "customer_turnover",
    "supplier_detail", "transactions",
]


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
        import calendar
        q = (today.month - 1) // 3
        if q == 0:
            q, y = 4, today.year - 1
        else:
            y = today.year
        sm = (q - 1) * 3 + 1
        em = q * 3
        ed = calendar.monthrange(y, em)[1]
        return date(y, sm, 1), date(y, em, ed)
    monday = today - timedelta(days=today.weekday() + 7)
    return monday, monday + timedelta(days=6)


def _period_label(d1: date, d2: date) -> str:
    return f"{d1.strftime('%d.%m.%Y')} – {d2.strftime('%d.%m.%Y')}"


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt(n: float) -> str:
    if n == 0:
        return "0"
    return f"{n:,.0f}".replace(",", ".")


def _pct(curr: float, prev: float) -> str:
    if not prev:
        return "–"
    p = (curr / prev - 1) * 100
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.1f}%"


def _base_style(has_total: bool = True) -> list:
    s = [
        ("BACKGROUND",    (0, 0), (-1, 0),  BLUE),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID",          (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2 if has_total else -1),
         [colors.white, LIGHT_GRAY]),
    ]
    if has_total:
        s += [
            ("BACKGROUND", (0, -1), (-1, -1), LIGHT_BLUE),
            ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
    return s


# ── Chart helpers (matplotlib) ────────────────────────────────────────────────

def _bar_chart(
    labels: list[str],
    values_a: list[float],
    values_b: list[float],
    label_a: str = "Vorjahr",
    label_b: str = "Aktuell",
    title: str = "",
    width_mm: float = 160,
    height_mm: float = 55,
) -> Image | None:
    """Grouped bar chart as a reportlab Image, or None on error."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mticker
        import numpy as np

        fig, ax = plt.subplots(figsize=(width_mm / 25.4, height_mm / 25.4), dpi=120)
        x = np.arange(len(labels))
        w = 0.35
        ax.bar(x - w / 2, values_a, w, label=label_a,
               color="#dbeafe", edgecolor="#2563eb", linewidth=0.7)
        ax.bar(x + w / 2, values_b, w, label=label_b,
               color="#2563eb", edgecolor="#1d4ed8", linewidth=0.7)

        ax.set_title(title, fontsize=9, pad=6)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7.5)
        ax.tick_params(axis="y", labelsize=7)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
        ax.legend(fontsize=7.5, framealpha=0.7)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linewidth=0.4, alpha=0.5)
        fig.tight_layout(pad=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return Image(buf, width=width_mm * mm, height=height_mm * mm)
    except Exception as e:
        logger.warning("Bar chart generation failed: %s", e)
        return None


def _hbar_chart(
    labels: list[str],
    values: list[float],
    title: str = "",
    width_mm: float = 160,
    height_mm: float = 60,
) -> Image | None:
    """Horizontal bar chart for top customers."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mticker

        n = min(15, len(labels))
        labels = labels[:n]
        values = values[:n]

        fig, ax = plt.subplots(figsize=(width_mm / 25.4, height_mm / 25.4), dpi=120)
        ax.barh(labels, values, color="#2563eb", edgecolor="#1d4ed8", linewidth=0.5)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=9, pad=6)
        ax.tick_params(axis="both", labelsize=7)
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="x", linewidth=0.4, alpha=0.5)
        fig.tight_layout(pad=0.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return Image(buf, width=width_mm * mm, height=height_mm * mm)
    except Exception as e:
        logger.warning("HBar chart generation failed: %s", e)
        return None


# ── DB query helpers ──────────────────────────────────────────────────────────

def _supplier_rows(db, date_from: date, date_to: date) -> list[dict]:
    """Direct SQLAlchemy query for supplier stats (avoids stats router dependency)."""
    from sqlalchemy import func, case
    from . import models

    ly_from = date_from.replace(year=date_from.year - 1)
    ly_to   = date_to.replace(year=date_to.year - 1)

    rows = (
        db.query(
            models.Supplier.code,
            models.Supplier.name,
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(date_from, date_to),
                      models.Transaction.total_amount), else_=0)
            ), 0).label("curr_turnover"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(date_from, date_to),
                      models.Transaction.total_amount *
                      func.coalesce(models.Transaction.provision_rate, 0) / 100),
                     else_=0)
            ), 0).label("curr_commission"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(ly_from, ly_to),
                      models.Transaction.total_amount), else_=0)
            ), 0).label("prev_turnover"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(ly_from, ly_to),
                      models.Transaction.total_amount *
                      func.coalesce(models.Transaction.provision_rate, 0) / 100),
                     else_=0)
            ), 0).label("prev_commission"),
        )
        .outerjoin(models.Transaction,
                   models.Transaction.supplier_id == models.Supplier.id)
        .filter(models.Supplier.is_active == True)
        .group_by(models.Supplier.code, models.Supplier.name)
        .order_by(models.Supplier.name)
        .all()
    )
    return [
        {
            "code":            r.code,
            "name":            r.name,
            "curr_turnover":   float(r.curr_turnover or 0),
            "curr_commission": float(r.curr_commission or 0),
            "prev_turnover":   float(r.prev_turnover or 0),
            "prev_commission": float(r.prev_commission or 0),
        }
        for r in rows
    ]


def _customer_rows(db, date_from: date, date_to: date,
                   sort_by: str = "provision") -> list[dict]:
    """Direct query for customer turnover using Customer join."""
    from sqlalchemy import func, case
    from . import models

    ly_from = date_from.replace(year=date_from.year - 1)
    ly_to   = date_to.replace(year=date_to.year - 1)
    range_from = min(date_from, ly_from)
    range_to   = max(date_to, ly_to)

    rows = (
        db.query(
            models.Customer.name.label("customer_name"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(date_from, date_to),
                      models.Transaction.total_amount), else_=0)
            ), 0).label("curr_turnover"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(date_from, date_to),
                      models.Transaction.total_amount *
                      func.coalesce(models.Transaction.provision_rate, 0) / 100),
                     else_=0)
            ), 0).label("curr_provision"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(ly_from, ly_to),
                      models.Transaction.total_amount), else_=0)
            ), 0).label("prev_turnover"),
        )
        .join(models.Transaction,
              models.Transaction.customer_id == models.Customer.id)
        .filter(models.Transaction.invoice_date.between(range_from, range_to))
        .group_by(models.Customer.id, models.Customer.name)
        .having(
            func.sum(
                case((models.Transaction.invoice_date.between(date_from, date_to),
                      models.Transaction.total_amount), else_=0)
            ) > 0
        )
        .all()
    )

    total_prov = sum(float(r.curr_provision or 0) for r in rows)
    result = []
    for r in rows:
        ct = float(r.curr_turnover or 0)
        cp = float(r.curr_provision or 0)
        pt = float(r.prev_turnover or 0)
        avg   = (cp / ct * 100) if ct else 0
        share = (cp / total_prov * 100) if total_prov else 0
        result.append({
            "customer_name":  r.customer_name or "–",
            "curr_turnover":  ct,
            "curr_provision": cp,
            "prev_turnover":  pt,
            "avg_rate":       round(avg, 2),
            "share_pct":      round(share, 1),
        })

    if sort_by == "provision":
        result.sort(key=lambda x: x["curr_provision"], reverse=True)
    else:
        result.sort(key=lambda x: x["curr_turnover"], reverse=True)
    return result


# ── Section builders ──────────────────────────────────────────────────────────

def _build_supplier_summary(db, date_from: date, date_to: date,
                            supplier_codes: list | None) -> list:
    rows = _supplier_rows(db, date_from, date_to)
    if supplier_codes:
        rows = [r for r in rows if r["code"] in supplier_codes]
    if not rows:
        return [Paragraph("Keine Daten im gewählten Zeitraum.", BODY)]

    story: list = [Paragraph("Lieferant Statistik", H2)]

    # Grouped bar chart: provision VJ vs. aktuell
    chart = _bar_chart(
        labels=[r["code"] for r in rows],
        values_a=[r["prev_commission"] for r in rows],
        values_b=[r["curr_commission"] for r in rows],
        label_a="Provision Vorjahr",
        label_b="Provision Aktuell",
        title="Provision: Vorjahresvergleich je Lieferant",
        width_mm=CONTENT_W / mm,
        height_mm=52,
    )
    if chart:
        story.append(chart)
        story.append(Spacer(1, 2*mm))

    header = ["Lieferant", "Umsatz VJ", "Umsatz Aktuell",
              "Prov. VJ", "Prov. Aktuell", "Diff.", "+/-%"]
    col_w  = [50*mm, 24*mm, 28*mm, 22*mm, 28*mm, 20*mm, 18*mm]
    tdata  = [header]
    tot_ct = tot_pt = tot_cc = tot_pc = 0.0

    for r in rows:
        ct, pt = r["curr_turnover"], r["prev_turnover"]
        cc, pc = r["curr_commission"], r["prev_commission"]
        diff = cc - pc
        tot_ct += ct; tot_pt += pt; tot_cc += cc; tot_pc += pc
        tdata.append([
            r["name"],
            _fmt(pt), _fmt(ct),
            _fmt(pc), _fmt(cc),
            ("+" if diff >= 0 else "") + _fmt(diff),
            _pct(cc, pc),
        ])

    tot_diff = tot_cc - tot_pc
    tdata.append(["Gesamt", _fmt(tot_pt), _fmt(tot_ct), _fmt(tot_pc), _fmt(tot_cc),
                  ("+" if tot_diff >= 0 else "") + _fmt(tot_diff),
                  _pct(tot_cc, tot_pc)])

    style = _base_style()
    for i, r in enumerate(rows, 1):
        diff = r["curr_commission"] - r["prev_commission"]
        col = GREEN if diff > 0 else (RED if diff < 0 else GRAY)
        style += [("TEXTCOLOR", (5, i), (6, i), col)]
    style += [("ALIGN", (1, 0), (-1, -1), "RIGHT")]

    tbl = Table(tdata, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(style))
    story.append(tbl)
    return story


def _build_customer_turnover(db, date_from: date, date_to: date,
                              sort_by: str) -> list:
    rows = _customer_rows(db, date_from, date_to, sort_by)
    rows_50 = rows[:50]
    if not rows_50:
        return [Paragraph("Keine Kunden-Daten im gewählten Zeitraum.", BODY)]

    label = "AdrUms nach Provision" if sort_by == "provision" else "AdrUms nach Umsatz"
    story: list = [Paragraph(label, H2)]

    # Horizontal bar chart: top 12 customers
    top = rows[:12]
    value_key  = "curr_provision" if sort_by == "provision" else "curr_turnover"
    chart_title = f"Top Kunden nach {'Provision' if sort_by == 'provision' else 'Umsatz'}"
    chart = _hbar_chart(
        labels=[r["customer_name"][:22] for r in top],
        values=[r[value_key] for r in top],
        title=chart_title,
        width_mm=CONTENT_W / mm,
        height_mm=max(45, min(80, len(top) * 6)),
    )
    if chart:
        story.append(chart)
        story.append(Spacer(1, 2*mm))

    header = ["Name / Firma", "Umsatz VJ", "Umsatz Aktuell", "Provision", "DuPr %", "Anteil %"]
    col_w  = [58*mm, 22*mm, 25*mm, 22*mm, 18*mm, 18*mm]
    tdata  = [header]
    tot_t = tot_p = 0.0

    for r in rows_50:
        tot_t += r["curr_turnover"]
        tot_p += r["curr_provision"]
        tdata.append([
            r["customer_name"][:35],
            _fmt(r["prev_turnover"]),
            _fmt(r["curr_turnover"]),
            _fmt(r["curr_provision"]),
            f"{r['avg_rate']:.2f}",
            f"{r['share_pct']:.1f}%",
        ])
    tdata.append([
        "Gesamtsumme",
        _fmt(sum(r["prev_turnover"] for r in rows_50)),
        _fmt(tot_t), _fmt(tot_p), "", "",
    ])

    tbl = Table(tdata, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(_base_style() + [("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    story.append(tbl)
    if len(rows) > 50:
        story.append(Paragraph(
            f"(Nur Top 50 von {len(rows)} Kunden dargestellt)", SMALL))
    return story


def _build_supplier_detail(db, year: int, supplier_codes: list | None) -> list:
    from . import models
    import calendar

    quarters = [
        ("1.Q",  date(year, 1, 1),  date(year, 3, 31)),
        ("2.Q",  date(year, 4, 1),  date(year, 6, 30)),
        ("3.Q",  date(year, 7, 1),  date(year, 9, 30)),
        ("4.Q",  date(year, 10, 1), date(year, 12, 31)),
        ("1.HY", date(year, 1, 1),  date(year, 6, 30)),
        ("2.HY", date(year, 7, 1),  date(year, 12, 31)),
        ("Jahr", date(year, 1, 1),  date(year, 12, 31)),
    ]
    prev_year = year - 1

    txns = (
        db.query(
            models.Transaction.supplier_id,
            models.Transaction.invoice_date,
            models.Transaction.total_amount,
            models.Transaction.provision_rate,
        )
        .filter(models.Transaction.invoice_date.between(
            date(prev_year, 1, 1), date(year, 12, 31)))
        .all()
    )

    suppliers_q = db.query(models.Supplier).filter(models.Supplier.is_active == True)
    if supplier_codes:
        suppliers_q = suppliers_q.filter(models.Supplier.code.in_(supplier_codes))
    suppliers = suppliers_q.order_by(models.Supplier.name).all()

    if not suppliers:
        return [Paragraph("Keine Lieferanten-Daten gefunden.", BODY)]

    story: list = [Paragraph(f"Lieferant Detail – Quartale {year}", H2)]
    BOLD_LABELS = {"1.HY", "2.HY", "Jahr"}

    def agg(sid, d_from, d_to, yr):
        total = prov = 0.0
        for t in txns:
            if t.supplier_id != sid or t.invoice_date.year != yr:
                continue
            if not (d_from <= t.invoice_date <= d_to):
                continue
            amt  = float(t.total_amount or 0)
            rate = float(t.provision_rate or 0)
            total += amt
            prov  += amt * rate / 100
        return total, prov

    for s in suppliers:
        story.append(Paragraph(
            f"{s.code} – {s.name}",
            ParagraphStyle("sq", fontSize=9, textColor=DARK,
                fontName="Helvetica-Bold", spaceBefore=4*mm, spaceAfter=1*mm)))

        header = ["", "Umsatz VJ", "Umsatz Aktuell", "+/-%",
                  "Prov. VJ", "Prov. Aktuell", "+/-%", "Diff."]
        col_w  = [10*mm, 22*mm, 26*mm, 14*mm, 22*mm, 26*mm, 14*mm, 18*mm]
        tdata  = [header]
        row_objects = []

        for label, qf, qt in quarters:
            ly_f = date(prev_year, qf.month, qf.day)
            ly_t = date(prev_year, qt.month, qt.day)
            ct, cp = agg(s.id, qf, qt, year)
            pt, pp = agg(s.id, ly_f, ly_t, prev_year)
            diff = cp - pp
            row_objects.append((label, ct, cp, pt, pp, diff))
            tdata.append([
                label,
                _fmt(pt), _fmt(ct), _pct(ct, pt),
                _fmt(pp), _fmt(cp), _pct(cp, pp),
                ("+" if diff >= 0 else "") + _fmt(diff),
            ])

        tbl = Table(tdata, colWidths=col_w, repeatRows=1)
        base = _base_style(has_total=False)
        base += [("ALIGN", (1, 0), (-1, -1), "RIGHT")]
        for i, (label, ct, cp, pt, pp, diff) in enumerate(row_objects, 1):
            if label in BOLD_LABELS:
                base += [
                    ("BACKGROUND", (0, i), (-1, i), LIGHT_BLUE),
                    ("FONTNAME",   (0, i), (-1, i), "Helvetica-Bold"),
                ]
            col = GREEN if diff > 0 else (RED if diff < 0 else GRAY)
            base += [("TEXTCOLOR", (7, i), (7, i), col)]
        tbl.setStyle(TableStyle(base))
        story.append(tbl)

    return story


def _build_transactions(db, date_from: date, date_to: date,
                        supplier_codes: list | None) -> list:
    from . import models
    from sqlalchemy.orm import joinedload

    suppliers_q = db.query(models.Supplier).filter(models.Supplier.is_active == True)
    if supplier_codes:
        suppliers_q = suppliers_q.filter(models.Supplier.code.in_(supplier_codes))
    suppliers = suppliers_q.order_by(models.Supplier.name).all()

    story: list = [Paragraph("Rechnungsübersicht", H2)]
    summary_rows: list = []

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

        story.append(Paragraph(
            f"{supplier.code} – {supplier.name}",
            ParagraphStyle("ts", fontSize=10, textColor=DARK,
                fontName="Helvetica-Bold", spaceBefore=4*mm, spaceAfter=1*mm)))

        header = ["Datum", "Re.-Nr.", "Kunde", "Betrag", "Whg", "Pr.%", "Provision"]
        col_w  = [20*mm, 26*mm, 55*mm, 22*mm, 12*mm, 14*mm, 21*mm]
        tdata  = [header]
        totals: dict[str, float] = {}
        prov_totals: dict[str, float] = {}

        for tx in txs:
            cust = (tx.customer.name or "")[:30] if tx.customer else ""
            cur  = tx.currency or "EUR"
            amt  = float(tx.total_amount or 0)
            rate = float(tx.provision_rate) if tx.provision_rate is not None else None
            prov = (amt * rate / 100) if rate is not None else None

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

        for cur, total in sorted(totals.items()):
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
        sum_data = [["Lieferant", "Whg", "Umsatz gesamt", "Provision gesamt"]] + [
            [name, cur, f"{amt:,.2f}", f"{prov:,.2f}" if prov is not None else ""]
            for name, cur, amt, prov in summary_rows
        ]
        sum_tbl = Table(sum_data, colWidths=[68*mm, 14*mm, 40*mm, 40*mm],
                        repeatRows=1)
        sum_tbl.setStyle(TableStyle(
            _base_style(has_total=False) + [("ALIGN", (2, 0), (3, -1), "RIGHT")]))
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
    active_types = report_types if report_types else ALL_REPORT_TYPES
    period_str   = _period_label(date_from, date_to)

    story: list = []
    story.append(Paragraph("WinAgent Bericht",
        ParagraphStyle("title", fontSize=16, textColor=BLUE,
            fontName="Helvetica-Bold", spaceAfter=1*mm)))
    story.append(Paragraph(f"Zeitraum: {period_str}", SMALL))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=4*mm))

    for rtype in active_types:
        try:
            if rtype == "supplier_summary":
                story.extend(_build_supplier_summary(
                    db, date_from, date_to, supplier_codes))
                story.append(Spacer(1, 3*mm))
            elif rtype == "customer_provision":
                story.extend(_build_customer_turnover(
                    db, date_from, date_to, "provision"))
                story.append(Spacer(1, 3*mm))
            elif rtype == "customer_turnover":
                story.extend(_build_customer_turnover(
                    db, date_from, date_to, "turnover"))
                story.append(Spacer(1, 3*mm))
            elif rtype == "supplier_detail":
                story.extend(_build_supplier_detail(
                    db, date_from.year, supplier_codes))
                story.append(Spacer(1, 3*mm))
            elif rtype == "transactions":
                story.extend(_build_transactions(
                    db, date_from, date_to, supplier_codes))
        except Exception as e:
            logger.error("Report section '%s' failed: %s", rtype, e, exc_info=True)
            story.append(Paragraph(
                f"Fehler in Abschnitt '{rtype}': {e}",
                ParagraphStyle("err", fontSize=9, textColor=RED)))

    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        f"Erstellt am {date.today().strftime('%d.%m.%Y')} · WinAgent", SMALL))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"WinAgent Bericht {period_str}",
    )
    doc.build(story)
    return buf.getvalue()
