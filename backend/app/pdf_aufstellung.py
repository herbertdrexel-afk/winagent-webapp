"""Generates Provisionsabrechnung (commission breakdown) PDFs — one section per currency."""
from io import BytesIO
from itertools import groupby


def _fmt(n: float, dec: int = 2) -> str:
    """German number format: 1.234,56"""
    s = f"{n:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_date(d) -> str:
    if isinstance(d, str):
        try:
            y, m, day = d.split("-")
            return f"{day}.{m}.{y[2:]}"
        except Exception:
            return d
    try:
        return d.strftime("%d.%m.%y")
    except Exception:
        return str(d)


def generate_aufstellung_pdf(
    supplier_name: str,
    representative_code: str,
    period_from,
    period_to,
    print_date,
    transactions_by_currency: dict,
) -> bytes:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER

    PAGE_W, _ = landscape(A4)
    LM = RM = 15 * mm
    TM = BM = 18 * mm
    AVAIL_W = PAGE_W - LM - RM  # 267mm

    F  = "Helvetica"
    FB = "Helvetica-Bold"
    FD = 7    # data rows
    FH = 8    # header text

    def _s(font=F, size=FH, align="LEFT", leading=10):
        return ParagraphStyle("_", fontName=font, fontSize=size,
                              leading=leading, alignment={"LEFT": 0, "RIGHT": 2, "CENTER": 1}[align])

    sn  = _s()
    sb  = _s(FB)
    sr  = _s(align="RIGHT")
    sbr = _s(FB, align="RIGHT")
    ss  = _s(size=6, leading=8)
    sd  = _s(size=FD, leading=9)
    sdb = _s(FB, size=FD, leading=9)
    sdr = _s(size=FD, leading=9, align="RIGHT")
    sdbr= _s(FB, size=FD, leading=9, align="RIGHT")

    period_str = f"{_fmt_date(period_from)} bis {_fmt_date(period_to)}"
    date_str   = print_date.strftime("%d.%m.%Y")

    # Column widths (sum = 267mm = AVAIL_W)
    # Datum|Re-Nr|Art-Nr|Farbe|Preis|Rab|Re.Betrag|Re.Nett|Prov.Basis|Prov.%|Provision
    CW = [22*mm, 26*mm, 24*mm, 14*mm, 14*mm, 11*mm, 34*mm, 32*mm, 32*mm, 16*mm, 38*mm]
    # sum: 22+26+24+14+14+11+34+32+32+16+38 = 263mm → adjust last col
    # 267 - 229 = 38 for last. Total: 22+26+24+14+14+11+34+32+32+16+38 = 263 → off by 4
    # Adjust: Provision 38→42, total 267 ✓
    CW[-1] = AVAIL_W - sum(CW[:-1])

    COL_HEADERS = [
        "Datum", "Re.-Nummer", "Art.-Nr....:", "Farbe...",
        "Preis", "Rab.", "Re.Betrag", "Re.Nett Betrag",
        "Prov.Basis", "Prov. %", "Provision",
    ]
    NCOLS = len(COL_HEADERS)
    RIGHT_COLS = list(range(4, NCOLS))   # Preis … Provision → right-aligned

    buf  = BytesIO()
    story = []
    first = True

    for currency, txs in transactions_by_currency.items():
        if not first:
            story.append(PageBreak())
        first = False

        # ── Page header ──────────────────────────────────────────────────────
        hdr_data = [
            [Paragraph(f"<b>Provisionsabrechnung:</b>  Firma: <b>{supplier_name}</b>", sb),
             Paragraph(date_str, sr)],
            [Paragraph("", sn),
             Paragraph("Seite: 1", sr)],
            [Paragraph(f"Zeitraum:  {period_str}&nbsp;&nbsp;&nbsp;&nbsp;Provisionsart: 1", sn),
             Paragraph("", sn)],
            [Paragraph(f"Währung :  <b>{currency}</b>&nbsp;&nbsp;&nbsp;&nbsp;"
                       f"Vertreter: {representative_code}&nbsp;&nbsp;{supplier_name}", sn),
             Paragraph("", sn)],
        ]
        hdr_tbl = Table(hdr_data, colWidths=[AVAIL_W - 40*mm, 40*mm])
        hdr_tbl.setStyle(TableStyle([
            ("FONTSIZE",     (0, 0), (-1, -1), FH),
            ("TOPPADDING",   (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 1),
            ("ALIGN",        (1, 0), (1, -1), "RIGHT"),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(hdr_tbl)
        story.append(HRFlowable(width="100%", thickness=0.5, spaceAfter=2))

        # ── Build detail table rows ──────────────────────────────────────────
        rows   = [COL_HEADERS]       # row 0 = column header
        styles = [
            # Column header styling
            ("FONTNAME",     (0, 0), (-1, 0), FB),
            ("FONTSIZE",     (0, 0), (-1, -1), FD),
            ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
            ("ALIGN",        (4, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW",    (0, 0), (-1, 0), 0.5, colors.black),
            ("LINEABOVE",    (0, 0), (-1, 0), 0.5, colors.black),
            ("TOPPADDING",   (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 1),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ]

        ri = 1   # current row index (0 = header)

        # sort by customer name, then date
        def _sort_key(t):
            return (t.get("customer_name") or "", t.get("invoice_date") or "")

        txs_sorted = sorted(txs, key=_sort_key)

        grand_basis = 0.0
        grand_prov  = 0.0

        for cust_key, grp in groupby(txs_sorted, key=lambda t: t.get("customer_name") or ""):
            cust_txs = list(grp)
            loc      = cust_txs[0].get("customer_location", "") or ""
            cust_hdr = f"{cust_key}, {loc}" if loc else cust_key

            # Customer name row (spans all columns, bold, underline via font)
            rows.append([cust_hdr] + [""] * (NCOLS - 1))
            styles += [
                ("FONTNAME", (0, ri), (-1, ri), FB),
                ("SPAN",     (0, ri), (-1, ri)),
            ]
            ri += 1

            cust_basis = 0.0
            cust_prov  = 0.0

            for tx in cust_txs:
                d    = _fmt_date(tx.get("invoice_date", ""))
                nr   = str(tx.get("invoice_number", ""))
                amt  = float(tx.get("total_amount", 0))
                rate = float(tx.get("provision_rate", 0))
                prov = float(tx.get("provision_amount", 0))

                rows.append([
                    d, nr, "DIV", "", "1,000", "0",
                    _fmt(amt), _fmt(amt), _fmt(amt),
                    _fmt(rate), _fmt(prov),
                ])
                # right-align numeric columns
                for c in RIGHT_COLS:
                    styles.append(("ALIGN", (c, ri), (c, ri), "RIGHT"))
                ri += 1
                cust_basis += amt
                cust_prov  += prov

            # Customer subtotal (bold, only Prov.Basis and Provision filled)
            rows.append([""] * NCOLS)
            rows[-1][8]  = _fmt(cust_basis)
            rows[-1][10] = _fmt(cust_prov)
            styles += [
                ("FONTNAME",  (0, ri), (-1, ri), FB),
                ("ALIGN",     (8, ri), (8, ri),  "RIGHT"),
                ("ALIGN",     (10, ri), (10, ri), "RIGHT"),
                ("LINEABOVE", (8, ri), (8, ri),  0.5, colors.black),
                ("LINEABOVE", (10, ri), (10, ri), 0.5, colors.black),
            ]
            ri += 1

            # Separator dot
            rows.append([" ."] + [""] * (NCOLS - 1))
            styles.append(("SPAN", (0, ri), (-1, ri)))
            ri += 1

            grand_basis += cust_basis
            grand_prov  += cust_prov

        # ── Grand total row ──────────────────────────────────────────────────
        total_row = [""] * NCOLS
        total_row[0] = f"Provisionsbetrag in:  {currency}"
        total_row[6]  = _fmt(grand_basis)
        total_row[8]  = _fmt(grand_basis)
        total_row[10] = _fmt(grand_prov)
        rows.append(total_row)
        styles += [
            ("FONTNAME",  (0, ri), (-1, ri), FB),
            ("ALIGN",     (6, ri), (6, ri),  "RIGHT"),
            ("ALIGN",     (8, ri), (8, ri),  "RIGHT"),
            ("ALIGN",     (10, ri), (10, ri), "RIGHT"),
            ("LINEABOVE", (0, ri), (-1, ri), 0.5, colors.black),
            ("SPAN",      (0, ri), (5, ri)),
        ]

        tbl = Table(rows, colWidths=CW, repeatRows=1)
        tbl.setStyle(TableStyle(styles))
        story.append(tbl)
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(
            r"Lib: H:\HDAGENTA\RRW\HdAgenta.RP5 \ Rep.-Name: Provision", ss
        ))

    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=LM, rightMargin=RM,
        topMargin=TM, bottomMargin=BM,
    )
    doc.build(story)
    return buf.getvalue()
