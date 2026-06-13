"""Generates a simple commission invoice PDF (PR26-0171 style)."""
from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER


def generate_invoice_pdf(
    pr_number: str,
    invoice_date: date,
    supplier_name: str,
    supplier_address: list[str],
    period_from: date,
    period_to: date,
    totals: list[dict],   # [{"currency": "EUR", "amount": 10666.69}, ...]
    representative_name: str = "AMV Ltd.",
) -> bytes:
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

    bold = ParagraphStyle("bold", parent=normal, fontName="Helvetica-Bold", fontSize=9)
    right = ParagraphStyle("right", parent=normal, alignment=TA_RIGHT)
    title_style = ParagraphStyle("title", parent=normal, fontName="Helvetica-Bold", fontSize=16)

    period_str = f"{period_from.strftime('%m-%m/%y')}"
    date_str = invoice_date.strftime("%d.%m.%Y")

    story = []

    # Sender (top left)
    story.append(Paragraph("amv ltd.", ParagraphStyle("sender", parent=normal, fontSize=8, textColor=colors.grey)))
    story.append(Paragraph("86, Main Street", ParagraphStyle("sender", parent=normal, fontSize=8, textColor=colors.grey)))
    story.append(Paragraph("STJ 1015 - St. Julians", ParagraphStyle("sender", parent=normal, fontSize=8, textColor=colors.grey)))
    story.append(Paragraph("Malta", ParagraphStyle("sender", parent=normal, fontSize=8, textColor=colors.grey)))
    story.append(Spacer(1, 0.8*cm))

    # Recipient
    for line in [supplier_name] + supplier_address:
        story.append(Paragraph(line, normal))
    story.append(Spacer(1, 1.5*cm))

    # Title
    story.append(Paragraph("RECHNUNG / INVOICE", title_style))
    story.append(Spacer(1, 0.8*cm))

    # Invoice table
    inv_data = [
        [Paragraph("<b>Rechnungsnummer / invoice number</b>", normal),
         Paragraph(f"<b>{pr_number}</b>", normal),
         Paragraph(date_str, right)],
    ]
    for t in totals:
        amt_fmt = f"{t['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        inv_data.append([
            Paragraph(f"Provision {period_str}", normal),
            Paragraph(f"<b>{t['currency']}</b>", normal),
            Paragraph(f"<b>{amt_fmt}</b>", right),
        ])
    # Total row
    if len(totals) == 1:
        amt_fmt = f"{totals[0]['amount']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        inv_data.append([
            Paragraph("<b>Betrag / amount</b>", bold),
            Paragraph(f"<b>{totals[0]['currency']}</b>", bold),
            Paragraph(f"<b>{amt_fmt}</b>",
                      ParagraphStyle("boldright", parent=bold, alignment=TA_RIGHT)),
        ])

    inv_table = Table(inv_data, colWidths=[9*cm, 3*cm, 4*cm])
    inv_table.setStyle(TableStyle([
        ("BOX",        (0, 0), (-1, 0), 0.5, colors.black),
        ("BOX",        (0, 1), (-1, -2), 0.5, colors.black),
        ("BOX",        (0, -1), (-1, -1), 0.5, colors.black),
        ("LINEBELOW",  (0, 0), (-1, 0), 0.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f5f5f5")),
    ]))
    story.append(inv_table)
    story.append(Spacer(1, 1.5*cm))

    # Payment details
    payment_data = [
        [Paragraph("<b>Zahlungsbedingung / terms of payment:</b>", normal),
         Paragraph("Prompte Banküberweisung<br/>immediate bank transfer", normal)],
        [Spacer(1, 0.3*cm), ""],
        [Paragraph("<b>Zu bezahlen an / To credit to:</b>", normal),
         Paragraph(
             f"{representative_name}<br/>"
             "86, Main Street<br/>STJ 1015 St. Julians / Malta<br/><br/>"
             "UID-Nr./VAT-no.:&nbsp;&nbsp;MT27557923<br/>"
             "Registation:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C 96538<br/><br/>"
             "Bank account:&nbsp;&nbsp;&nbsp;UBS Europe<br/>"
             "IBAN:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;DE02 5022 0085 3618 2300 18<br/>"
             "BIC:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SMHBDEFFXXX",
             normal
         )],
    ]
    pay_table = Table(payment_data, colWidths=[6*cm, 10*cm])
    pay_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(pay_table)
    story.append(Spacer(1, 2*cm))

    # Footer note
    story.append(HRFlowable(width="100%", thickness=0.3, color=colors.grey))
    story.append(Spacer(1, 0.2*cm))
    footer_text = (
        "Steuerlicher Hinweis EG: Umsatzsteuerfreie Lieferung gemäß §4 Nr. 1b und §6a des UStG / "
        "EC tax information: VAT-free delivery in accordance with §4 No. 1b and §6a of the UStG"
    )
    story.append(Paragraph(footer_text, ParagraphStyle("footer", parent=normal, fontSize=7, textColor=colors.grey)))

    doc.build(story)
    return buf.getvalue()
