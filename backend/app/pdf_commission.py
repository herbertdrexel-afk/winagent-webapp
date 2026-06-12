"""PDF-Generierung für Provisionsabrechnungen.

Erzeugt ein A4-Dokument mit:
  - Kopfzeile: Lieferantenname, Abrechnungsnummer, Zeitraum, Datum
  - Positionstabelle: Kd-Nr | Kunde | Satz % | Umsatz | Provision | Währung
  - Summenzeile
  - Seitennummerierung im Fuß
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

if TYPE_CHECKING:
    from . import models

# ── Farben ──────────────────────────────────────────────────────────────────
_BLUE_DARK  = colors.HexColor("#1a3a5c")
_BLUE_LIGHT = colors.HexColor("#dce8f5")
_GREY_LINE  = colors.HexColor("#cccccc")

_W, _H = A4
_MARGIN_LEFT  = 20 * mm
_MARGIN_RIGHT = 20 * mm
_MARGIN_TOP   = 20 * mm
_MARGIN_BOT   = 18 * mm
_CONTENT_W = _W - _MARGIN_LEFT - _MARGIN_RIGHT


def _fmt_amount(value) -> str:
    if value is None:
        return "–"
    return f"{Decimal(str(value)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_rate(value) -> str:
    if value is None:
        return "–"
    return f"{Decimal(str(value)):.2f} %"


def _fmt_date(d: date | None) -> str:
    if d is None:
        return "–"
    return d.strftime("%d.%m.%Y")


# ── Seitenrahmen mit Kopf + Fuß ─────────────────────────────────────────────
class _HeaderFooterCanvas:
    """Wird als onPage/onLaterPage Callback genutzt."""

    def __init__(self, statement: "models.CommissionStatement"):
        self.statement = statement

    def __call__(self, canvas, doc):
        s = self.statement
        canvas.saveState()

        # ── Kopf ──
        canvas.setFillColor(_BLUE_DARK)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(_MARGIN_LEFT, _H - 14 * mm,
                          f"Provisionsabrechnung  {s.statement_number or 'ENTWURF'}")

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.black)
        right_x = _W - _MARGIN_RIGHT
        canvas.drawRightString(right_x, _H - 14 * mm,
                               f"Datum: {_fmt_date(s.statement_date or date.today())}")

        canvas.setFont("Helvetica", 9)
        sub_y = _H - 20 * mm
        canvas.drawString(_MARGIN_LEFT, sub_y,
                          f"Lieferant: {s.supplier.name}  ({s.supplier.code})")
        canvas.drawRightString(right_x, sub_y,
                               f"Zeitraum: {_fmt_date(s.period_from)} – {_fmt_date(s.period_to)}")

        # Trennlinie unter Kopf
        canvas.setStrokeColor(_BLUE_DARK)
        canvas.setLineWidth(0.8)
        canvas.line(_MARGIN_LEFT, _H - 23 * mm, _W - _MARGIN_RIGHT, _H - 23 * mm)

        # ── Fuß ──
        canvas.setStrokeColor(_GREY_LINE)
        canvas.setLineWidth(0.5)
        canvas.line(_MARGIN_LEFT, _MARGIN_BOT - 2 * mm,
                    _W - _MARGIN_RIGHT, _MARGIN_BOT - 2 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(_W / 2, _MARGIN_BOT - 6 * mm,
                                 f"Seite {doc.page}")

        canvas.restoreState()


# ── Hauptfunktion ────────────────────────────────────────────────────────────
def build_pdf(statement: "models.CommissionStatement") -> bytes:
    buf = io.BytesIO()

    hf = _HeaderFooterCanvas(statement)

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=_MARGIN_LEFT,
        rightMargin=_MARGIN_RIGHT,
        topMargin=28 * mm,
        bottomMargin=_MARGIN_BOT + 4 * mm,
        title=f"Provisionsabrechnung {statement.statement_number or 'Entwurf'}",
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Status-Badge bei Entwurf ────────────────────────────────────────────
    if statement.status == "draft":
        draft_style = ParagraphStyle(
            "draft", parent=styles["Normal"],
            textColor=colors.orangered, fontSize=9, spaceAfter=4,
        )
        story.append(Paragraph("⚠ ENTWURF – noch keine Rechnungsnummer vergeben", draft_style))

    story.append(Spacer(1, 4 * mm))

    # ── Tabellendaten ────────────────────────────────────────────────────────
    col_widths = [22 * mm, 68 * mm, 20 * mm, 30 * mm, 28 * mm, 12 * mm]
    header = ["Kd-Nr", "Kunde", "Satz", "Umsatz", "Provision", "Währg."]

    rows = [header]
    for item in sorted(statement.items, key=lambda i: (i.customer.name if i.customer else "")):
        cust = item.customer
        rows.append([
            cust.ku_nr or cust.code if cust else "–",
            cust.name if cust else "–",
            _fmt_rate(item.provision_rate),
            _fmt_amount(item.total_amount),
            _fmt_amount(item.provision_amount),
            item.currency or "–",
        ])

    if len(rows) == 1:
        rows.append(["", "Keine Positionen vorhanden", "", "–", "–", "–"])

    # Summenzeile
    rows.append([
        "", "Gesamt",
        "",
        _fmt_amount(statement.total_amount),
        _fmt_amount(statement.total_provision),
        statement.currency or "–",
    ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Kopfzeile
        ("BACKGROUND",   (0, 0), (-1, 0), _BLUE_DARK),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 9),
        ("ALIGN",        (2, 0), (-1, 0), "RIGHT"),
        ("BOTTOMPADDING",(0, 0), (-1, 0), 5),
        ("TOPPADDING",   (0, 0), (-1, 0), 5),
        # Datenzeilen
        ("FONTNAME",     (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -2), 8.5),
        ("ALIGN",        (2, 1), (-1, -2), "RIGHT"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [colors.white, _BLUE_LIGHT]),
        ("TOPPADDING",   (0, 1), (-1, -2), 3),
        ("BOTTOMPADDING",(0, 1), (-1, -2), 3),
        # Summenzeile (letzte Zeile)
        ("FONTNAME",     (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",     (0, -1), (-1, -1), 9),
        ("ALIGN",        (2, -1), (-1, -1), "RIGHT"),
        ("LINEABOVE",    (0, -1), (-1, -1), 1, _BLUE_DARK),
        ("TOPPADDING",   (0, -1), (-1, -1), 5),
        ("BOTTOMPADDING",(0, -1), (-1, -1), 5),
        # Außenrahmen
        ("BOX",          (0, 0), (-1, -1), 0.5, _GREY_LINE),
        ("INNERGRID",    (0, 0), (-1, -2), 0.25, _GREY_LINE),
    ]))

    story.append(tbl)
    doc.build(story, onFirstPage=hf, onLaterPages=hf)

    return buf.getvalue()
