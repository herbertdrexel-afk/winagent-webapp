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

    # ── Header: Sender (left) + Logo (right) ──────────────────────────────
    sender_lines = [
        "amv ltd.",
        "86, Main Street",
        "STJ 1015 - St. Julians",
        "Malta",
        "amv@nagroup.biz",
    ]

    if logo_b64:
        try:
            logo_bytes = base64.b64decode(logo_b64)
            logo_img = Image(BytesIO(logo_bytes), width=3.5*cm, height=2*cm)
            logo_img.hAlign = "RIGHT"
            sender_cell = [[Paragraph(line, grey8) for line in sender_lines]]
            logo_cell   = [[logo_img]]
            header_table = Table(
                [[sender_cell[0], logo_img]],
                colWidths=[10*cm, 5*cm],
            )
            header_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN",  (1, 0), (1, 0),   "RIGHT"),
            ]))
            story.append(header_table)
        except Exception:
            for line in sender_lines:
                story.append(Paragraph(line, grey8))
    else:
        for line in sender_lines:
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
    # Select bank account for the invoice currency (first total's currency)
    inv_currency = totals[0]["currency"] if totals else "EUR"
    bank_info = (bank_accounts or {}).get(inv_currency, {})
    bank_name = bank_info.get("bank", "UBS Europe")
    iban      = bank_info.get("iban", "")
    bic       = bank_info.get("bic", "")

    bank_block = (
        f"{representative_name}<br/>"
        "86, Main Street<br/>STJ 1015 St. Julians / Malta<br/><br/>"
        "UID-Nr./VAT-no.:&nbsp;&nbsp;MT27557923<br/>"
        "Registation:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C 96538"
    )
    if bank_name or iban or bic:
        bank_block += (
            f"<br/><br/>"
            f"Bank account:&nbsp;&nbsp;&nbsp;{bank_name}<br/>"
            f"IBAN:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{iban}<br/>"
            f"BIC:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{bic}"
        )

    payment_data = [
        [Paragraph(f"<b>{_t('Zahlungsbedingung', 'terms of payment', lang)}:</b>", normal),
         Paragraph(
             _t("Prompte Banküberweisung", "immediate bank transfer", lang)
             .replace(" / ", "<br/>"),
             normal
         )],
        [Spacer(1, 0.3*cm), ""],
        [Paragraph(f"<b>{_t('Zu bezahlen an', 'To credit to', lang)}:</b>", normal),
         Paragraph(bank_block, normal)],
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
