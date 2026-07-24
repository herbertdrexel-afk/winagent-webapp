"""Generates a commission invoice PDF (PR26-xxxx style)."""
import base64
from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT


# ── Language helpers ────────────────────────────────────────────────────────

def _t(de: str, en: str, lang: str) -> str:
    """Return German, English, or bilingual label depending on lang setting."""
    if lang == "de":
        return de
    if lang == "en":
        return en
    return f"{de} / {en}"  # "de+en" default


def generate_invoice_pdf(
    pr_number: str,
    invoice_date: date,
    supplier_name: str,
    supplier_address: list[str],
    period_from: date,
    period_to: date,
    totals: list[dict],            # [{"currency": "EUR", "amount": 10666.69}, ...]
    representative_name: str = "AMV Ltd.",
    invoice_language: str = "de+en",
    bank_accounts: dict | None = None,   # {"EUR": {"bank": ..., "iban": ..., "bic": ...}, ...}
    logo_b64: str | None = None,
) -> bytes:
    lang = invoice_language or "de+en"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2.5*cm,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 9

    bold       = ParagraphStyle("bold",      parent=normal, fontName="Helvetica-Bold", fontSize=9)
    right      = ParagraphStyle("right",     parent=normal, alignment=TA_RIGHT)
    boldright  = ParagraphStyle("boldright", parent=bold,   alignment=TA_RIGHT)
    title_sty  = ParagraphStyle("title",     parent=normal, fontName="Helvetica-Bold", fontSize=16)
    grey8      = ParagraphStyle("grey8",     parent=normal, fontSize=8, textColor=colors.grey)

    period_str = f"{period_from.strftime('%m-%m/%y')}"
    date_str   = invoice_date.strftime("%d.%m.%Y")

    story = []

    # ── Header: full-width logo OR small sender text (no address when logo present) ──
    PAGE_W = 16.5 * cm   # A4 usable width (21cm - 2.5cm left - 2cm right)

    if logo_b64:
        try:
            logo_bytes = base64.b64decode(logo_b64)
            logo_img = Image(BytesIO(logo_bytes), width=PAGE_W, height=3*cm,
                             kind="proportional")
            logo_img.hAlign = "CENTER"
            story.append(logo_img)
        except Exception:
            story.append(Paragraph("amv ltd.", grey8))
    else:
        for line in ("amv ltd.", "86, Main Street", "STJ 1015 - St. Julians", "Malta", "amv@nagroup.biz"):
            story.append(Paragraph(line, grey8))

    story.append(Spacer(1, 0.8*cm))

    # ── Recipient ──────────────────────────────────────────────────────────
    for line in [supplier_name] + supplier_address:
        story.append(Paragraph(line, normal))
    story.append(Spacer(1, 1.5*cm))

    # ── Title ──────────────────────────────────────────────────────────────
    story.append(Paragraph(_t("RECHNUNG", "INVOICE", lang).upper(), title_sty))
    story.append(Spacer(1, 0.8*cm))

    # ── Invoice table ──────────────────────────────────────────────────────
    inv_data = [
        [Paragraph(f"<b>{_t('Rechnungsnummer', 'invoice number', lang)}</b>", normal),
         Paragraph(f"<b>{pr_number}</b>", normal),
         Paragraph(date_str, right)],
    ]
    for t in totals:
        amt_fmt = f"{t['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        inv_data.append([
            Paragraph(_t("Provision", "Commission", lang) + f" {period_str}", normal),
            Paragraph(f"<b>{t['currency']}</b>", normal),
            Paragraph(f"<b>{amt_fmt}</b>", right),
        ])
    if len(totals) == 1:
        amt_fmt = f"{totals[0]['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        inv_data.append([
            Paragraph(f"<b>{_t('Betrag', 'amount', lang)}</b>", bold),
            Paragraph(f"<b>{totals[0]['currency']}</b>", bold),
            Paragraph(f"<b>{amt_fmt}</b>", boldright),
        ])

    inv_table = Table(inv_data, colWidths=[9*cm, 3*cm, 4*cm])
    inv_table.setStyle(TableStyle([
        ("BOX",           (0, 0),  (-1, 0),  0.5, colors.black),
        ("BOX",           (0, 1),  (-1, -2), 0.5, colors.black),
        ("BOX",           (0, -1), (-1, -1), 0.5, colors.black),
        ("LINEBELOW",     (0, 0),  (-1, 0),  0.5, colors.black),
        ("TOPPADDING",    (0, 0),  (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 6),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 8),
        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#f5f5f5")),
    ]))
    story.append(inv_table)
    story.append(Spacer(1, 1.5*cm))

    # ── Payment details ────────────────────────────────────────────────────
    ba = bank_accounts or {}
    inv_currency = totals[0]["currency"] if totals else "EUR"
    bank_info    = ba.get(inv_currency, {})
    bank_name    = bank_info.get("bank", "")
    iban         = bank_info.get("iban", "")
    bic          = bank_info.get("bic", "")
    uid_nr       = ba.get("uid_nr", "")
    registration = ba.get("registration", "")

    # Inner 2-column table for the "To credit to:" right cell (label | value)
    # colWidths must sum to 10cm (the right column of the outer table)
    LABEL_W = 3.5 * cm
    VALUE_W = 6.5 * cm
    pad0 = ("LEFTPADDING",   (0, 0), (-1, -1), 0)
    pad1 = ("RIGHTPADDING",  (0, 0), (-1, -1), 0)
    pad2 = ("TOPPADDING",    (0, 0), (-1, -1), 1)
    pad3 = ("BOTTOMPADDING", (0, 0), (-1, -1), 1)
    vtop = ("VALIGN",        (0, 0), (-1, -1), "TOP")

    inner_rows  = []
    inner_spans = []   # (col0, row), (col1, row) pairs for SPAN

    def _span(r_idx):
        inner_spans.append(("SPAN", (0, r_idx), (1, r_idx)))

    def _full(content):
        idx = len(inner_rows)
        inner_rows.append([content, ""])
        _span(idx)

    def _detail(label: str, value: str):
        inner_rows.append([Paragraph(label, normal), Paragraph(value, normal)])

    def _gap():
        idx = len(inner_rows)
        inner_rows.append([Spacer(1, 4), ""])
        _span(idx)

    # Address block
    _full(Paragraph(representative_name, normal))
    _full(Paragraph("86, Main Street", normal))
    _full(Paragraph("STJ 1015 St. Julians / Malta", normal))
    _gap()

    # UID / Registration
    if uid_nr:
        _detail("UID-Nr./VAT-no.:", uid_nr)
    if registration:
        _detail("Registation:", registration)

    # Bank details
    if bank_name or iban or bic:
        _gap()
        if bank_name:
            _detail("Bank account:", bank_name)
        if iban:
            _detail("IBAN:", iban)
        if bic:
            _detail("BIC:", bic)

    inner_tbl = Table(inner_rows, colWidths=[LABEL_W, VALUE_W])
    inner_tbl.setStyle(TableStyle([vtop, pad0, pad1, pad2, pad3, *inner_spans]))

    # Payment text (terms)
    if lang == "de":
        pmt_text = "Prompte Banküberweisung"
    elif lang == "en":
        pmt_text = "immediate bank transfer"
    else:
        pmt_text = "Prompte Banküberweisung<br/>immediate bank transfer"

    payment_data = [
        [Paragraph(f"<b>{_t('Zahlungsbedingung', 'terms of payment', lang)}:</b>", normal),
         Paragraph(pmt_text, normal)],
        [Spacer(1, 0.3*cm), ""],
        [Paragraph(f"<b>{_t('Zu bezahlen an', 'To credit to', lang)}:</b>", normal),
         inner_tbl],
    ]
    pay_table = Table(payment_data, colWidths=[6*cm, 10*cm])
    pay_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(pay_table)
    story.append(Spacer(1, 2*cm))

    # ── Footer ─────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.3, color=colors.grey))
    story.append(Spacer(1, 0.2*cm))
    if lang == "de":
        footer_text = "Steuerlicher Hinweis EG: Umsatzsteuerfreie Lieferung gemäß §4 Nr. 1b und §6a des UStG"
    elif lang == "en":
        footer_text = "EC tax information: VAT-free delivery in accordance with §4 No. 1b and §6a of the UStG"
    else:
        footer_text = (
            "Steuerlicher Hinweis EG: Umsatzsteuerfreie Lieferung gemäß §4 Nr. 1b und §6a des UStG / "
            "EC tax information: VAT-free delivery in accordance with §4 No. 1b and §6a of the UStG"
        )
    story.append(Paragraph(footer_text, ParagraphStyle("footer", parent=normal, fontSize=7, textColor=colors.grey)))

    doc.build(story)
    return buf.getvalue()


def generate_invoice_pdf_alt(
    pr_number: str,
    invoice_date: date,
    supplier_name: str,
    supplier_address: list[str],
    description: str,
    currency: str,
    amount: float,
    place: str = "Zuzwil",
    representative_name: str = "AMV Ltd.",
    invoice_language: str = "de+en",
    bank_accounts: dict | None = None,
    logo_b64: str | None = None,
) -> bytes:
    """Alternatives Rechnungs-Layout: zeigt den freien Beschreibungstext als
    Position + Hinweis auf beiliegende Abrechnung, Ort vor dem Datum."""
    lang = invoice_language or "de+en"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2.5*cm,
    )
    styles = getSampleStyleSheet()
    normal = styles["Normal"]; normal.fontName = "Helvetica"; normal.fontSize = 9
    bold      = ParagraphStyle("bold",      parent=normal, fontName="Helvetica-Bold", fontSize=9)
    right     = ParagraphStyle("right",     parent=normal, alignment=TA_RIGHT)
    boldright = ParagraphStyle("boldright", parent=bold,   alignment=TA_RIGHT)
    title_sty = ParagraphStyle("title",     parent=normal, fontName="Helvetica-Bold", fontSize=16)
    grey8     = ParagraphStyle("grey8",     parent=normal, fontSize=8, textColor=colors.grey)
    italic    = ParagraphStyle("italic",    parent=normal, fontName="Helvetica-Oblique", fontSize=8, textColor=colors.grey)

    date_str = invoice_date.strftime("%d.%m.%Y")
    place_date = f"{place}, {date_str}" if place else date_str

    def _amt(v: float) -> str:
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    story = []
    PAGE_W = 16.5 * cm

    # Header (Logo oder Absenderzeilen)
    if logo_b64:
        try:
            logo_img = Image(BytesIO(base64.b64decode(logo_b64)), width=PAGE_W, height=3*cm, kind="proportional")
            logo_img.hAlign = "CENTER"
            story.append(logo_img)
        except Exception:
            story.append(Paragraph("amv ltd.", grey8))
    else:
        for line in ("amv ltd.", "86, Main Street", "STJ 1015 - St. Julians", "Malta", "amv@nagroup.biz"):
            story.append(Paragraph(line, grey8))
    story.append(Spacer(1, 0.8*cm))

    # Empfänger
    for line in [supplier_name] + supplier_address:
        story.append(Paragraph(line, normal))
    story.append(Spacer(1, 1.5*cm))

    # Titel
    story.append(Paragraph(_t("RECHNUNG", "INVOICE", lang).upper(), title_sty))
    story.append(Spacer(1, 0.8*cm))

    # Rechnungstabelle: Nummer + Ort/Datum, Beschreibungszeile, Hinweis, Betrag
    inv_data = [
        [Paragraph(f"<b>{_t('Nummer', 'Number', lang)}</b>", normal),
         Paragraph(f"<b>{pr_number}</b>", normal),
         Paragraph(place_date, right)],
        [Paragraph(description or _t("Provision", "Commission", lang), normal),
         Paragraph(f"<b>{currency}</b>", normal),
         Paragraph(f"<b>{_amt(amount)}</b>", right)],
        [Paragraph(_t("( Siehe beiliegende Abrechnung )", "( See enclosed account )", lang), italic),
         Paragraph("", normal), Paragraph("", right)],
        [Paragraph(f"<b>{_t('Betrag', 'amount', lang)}</b>", bold),
         Paragraph(f"<b>{currency}</b>", bold),
         Paragraph(f"<b>{_amt(amount)}</b>", boldright)],
    ]
    inv_table = Table(inv_data, colWidths=[9*cm, 3*cm, 4*cm])
    inv_table.setStyle(TableStyle([
        ("BOX",           (0, 0),  (-1, 0),  0.5, colors.black),
        ("LINEBELOW",     (0, 0),  (-1, 0),  0.5, colors.black),
        ("BOX",           (0, 1),  (-1, 2),  0.5, colors.black),
        ("SPAN",          (0, 2),  (-1, 2)),
        ("BOX",           (0, 3),  (-1, 3),  0.5, colors.black),
        ("BACKGROUND",    (0, 3),  (-1, 3),  colors.HexColor("#f5f5f5")),
        ("TOPPADDING",    (0, 0),  (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 6),
        ("LEFTPADDING",   (0, 0),  (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0),  (-1, -1), 8),
    ]))
    story.append(inv_table)
    story.append(Spacer(1, 1.5*cm))

    # Zahlungsblock (wie Standard-Layout)
    ba = bank_accounts or {}
    bank_info = ba.get(currency, {})
    bank_name = bank_info.get("bank", ""); iban = bank_info.get("iban", ""); bic = bank_info.get("bic", "")
    uid_nr = ba.get("uid_nr", ""); registration = ba.get("registration", "")

    LABEL_W, VALUE_W = 3.5*cm, 6.5*cm
    inner_rows, inner_spans = [], []
    def _full(content):
        idx = len(inner_rows); inner_rows.append([content, ""]); inner_spans.append(("SPAN", (0, idx), (1, idx)))
    def _detail(label, value):
        inner_rows.append([Paragraph(label, normal), Paragraph(value, normal)])
    def _gap():
        idx = len(inner_rows); inner_rows.append([Spacer(1, 4), ""]); inner_spans.append(("SPAN", (0, idx), (1, idx)))

    _full(Paragraph(representative_name, normal))
    _full(Paragraph("86, Main Street", normal))
    _full(Paragraph("STJ 1015 St. Julians / Malta", normal))
    _gap()
    if uid_nr: _detail("UID-Nr./VAT-no.:", uid_nr)
    if registration: _detail("Registration:", registration)
    if bank_name or iban or bic:
        _gap()
        if bank_name: _detail("Bank account:", bank_name)
        if iban: _detail("IBAN:", iban)
        if bic: _detail("BIC:", bic)

    inner_tbl = Table(inner_rows, colWidths=[LABEL_W, VALUE_W])
    inner_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        *inner_spans,
    ]))

    if lang == "de":
        pmt_text = "Prompte Banküberweisung"
    elif lang == "en":
        pmt_text = "immediate bank transfer"
    else:
        pmt_text = "Prompte Banküberweisung<br/>immediate bank transfer"

    pay_table = Table([
        [Paragraph(f"<b>{_t('Zahlungsbedingung', 'terms of payment', lang)}:</b>", normal), Paragraph(pmt_text, normal)],
        [Spacer(1, 0.3*cm), ""],
        [Paragraph(f"<b>{_t('Zu bezahlen an', 'To credit to', lang)}:</b>", normal), inner_tbl],
    ], colWidths=[6*cm, 10*cm])
    pay_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    story.append(pay_table)
    story.append(Spacer(1, 2*cm))

    story.append(HRFlowable(width="100%", thickness=0.3, color=colors.grey))
    story.append(Spacer(1, 0.2*cm))
    footer_text = _t(
        "Steuerlicher Hinweis EG: Umsatzsteuerfreie Lieferung gemäß §4 Nr. 1b und §6a des UStG",
        "EC tax information: VAT-free delivery in accordance with §4 No. 1b and §6a of the UStG", lang)
    story.append(Paragraph(footer_text, ParagraphStyle("footer", parent=normal, fontSize=7, textColor=colors.grey)))

    doc.build(story)
    return buf.getvalue()
