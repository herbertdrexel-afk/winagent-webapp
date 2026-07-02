"""Generates Provisionsabrechnung (commission breakdown) PDFs — one section per currency.

compact=False  → A4 landscape, 11 columns (Datum|Re-Nr|Art-Nr|Farbe|Preis|Rab|…)
compact=True   → A4 portrait,  7 columns  (Datum|Re-Nr|Re.Betrag|Re.Nett|Prov.Basis|Prov.%|Provision)
"""
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
    compact: bool = False,
) -> bytes:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable,
    )
    from reportlab.lib.styles import ParagraphStyle

    LM = RM = 15 * mm
    TM = BM = 18 * mm

    if compact:
        PAGE_SIZE = A4                      # portrait 210×297
        PAGE_W    = A4[0]                   # 210mm
        FD = 8                              # slightly larger font — less columns
    else:
        PAGE_SIZE = landscape(A4)           # landscape 297×210
        PAGE_W    = landscape(A4)[0]        # 297mm
        FD = 7

    AVAIL_W = PAGE_W - LM - RM
    F  = "Helvetica"
    FB = "Helvetica-Bold"
    FH = 8

    def _s(font=F, size=FH, align="LEFT", leading=10):
        return ParagraphStyle("_", fontName=font, fontSize=size,
                              leading=leading, alignment={"LEFT": 0, "RIGHT": 2}[align])

    sn = _s()
    sb = _s(FB)
    sr = _s(align="RIGHT")
    ss = _s(size=6, leading=8)

    period_str = f"{_fmt_date(period_from)} bis {_fmt_date(period_to)}"
    date_str   = print_date.strftime("%d.%m.%Y")

    # ── Column definitions depend on mode ────────────────────────────────────
    if compact:
        # 7 columns, portrait 180mm available
        # Datum|Re-Nr|Re.Betrag|Re.Nett Betrag|Prov.Basis|Prov.%|Provision
        COL_HEADERS = [
            "Datum", "Re.-Nummer",
            "Re.Betrag", "Re.Nett Betrag", "Prov.Basis", "Prov. %", "Provision",
        ]
        CW = [25*mm, 32*mm, 30*mm, 32*mm, 30*mm, 16*mm, 15*mm]
        CW[-1] = AVAIL_W - sum(CW[:-1])   # adjust last to fill exactly
        NCOLS      = len(COL_HEADERS)
        RIGHT_COLS = list(range(2, NCOLS))  # Re.Betrag … Provision

        def _detail_row(d, nr, amt, rate, prov):
            return [d, nr, _fmt(amt), _fmt(amt), _fmt(amt), _fmt(rate), _fmt(prov)]

        I_BASIS = 4   # column index for Prov.Basis (subtotal)
        I_PROV  = 6   # column index for Provision  (subtotal)
        I_RTOT1 = 2   # Re.Betrag in grand total row
        I_RTOT2 = 4   # Prov.Basis in grand total row
        I_PTOT  = 6   # Provision  in grand total row
        SPAN_TOTAL_END = 1  # grand total label spans cols 0–1

    else:
        # 11 columns, landscape 267mm available
        # Datum|Re-Nr|Art-Nr|Farbe|Preis|Rab|Re.Betrag|Re.Nett|Prov.Basis|Prov.%|Provision
        COL_HEADERS = [
            "Datum", "Re.-Nummer", "Art.-Nr....:", "Farbe...",
            "Preis", "Rab.", "Re.Betrag", "Re.Nett Betrag",
            "Prov.Basis", "Prov. %", "Provision",
        ]
        CW = [22*mm, 26*mm, 24*mm, 14*mm, 14*mm, 11*mm, 34*mm, 32*mm, 32*mm, 16*mm, 38*mm]
        CW[-1] = AVAIL_W - sum(CW[:-1])
        NCOLS      = len(COL_HEADERS)
        RIGHT_COLS = list(range(4, NCOLS))

        def _detail_row(d, nr, amt, rate, prov):
            return [d, nr, "DIV", "", "1,000", "0",
                    _fmt(amt), _fmt(amt), _fmt(amt), _fmt(rate), _fmt(prov)]

        I_BASIS = 8
        I_PROV  = 10
        I_RTOT1 = 6
        I_RTOT2 = 8
        I_PTOT  = 10
        SPAN_TOTAL_END = 5

    # ── Build story ───────────────────────────────────────────────────────────
    buf   = BytesIO()
    story = []
    first = True

    for currency, txs in transactions_by_currency.items():
        if not first:
            story.append(PageBreak())
        first = False

        # Header block
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
            ("FONTSIZE",      (0, 0), (-1, -1), FH),
            ("TOPPADDING",    (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("ALIGN",         (1, 0), (1, -1), "RIGHT"),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(hdr_tbl)
        story.append(HRFlowable(width="100%", thickness=0.5, spaceAfter=2))

        # Detail table
        rows   = [COL_HEADERS]
        styles = [
            ("FONTNAME",      (0, 0), (-1, 0), FB),
            ("FONTSIZE",      (0, 0), (-1, -1), FD),
            ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
            ("ALIGN",         (RIGHT_COLS[0], 0), (-1, -1), "RIGHT"),
            ("LINEBELOW",     (0, 0), (-1, 0), 0.5, colors.black),
            ("LINEABOVE",     (0, 0), (-1, 0), 0.5, colors.black),
            ("TOPPADDING",    (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]
        ri = 1

        def _sort_key(t):
            return (t.get("customer_name") or "", t.get("invoice_date") or "")

        txs_sorted  = sorted(txs, key=_sort_key)
        grand_basis = 0.0
        grand_prov  = 0.0

        for cust_key, grp in groupby(txs_sorted, key=lambda t: t.get("customer_name") or ""):
            cust_txs = list(grp)
            loc      = cust_txs[0].get("customer_location", "") or ""
            cust_hdr = f"{cust_key}, {loc}" if loc else cust_key

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

                rows.append(_detail_row(d, nr, amt, rate, prov))
                for c in RIGHT_COLS:
                    styles.append(("ALIGN", (c, ri), (c, ri), "RIGHT"))
                ri += 1
                cust_basis += amt
                cust_prov  += prov

            # Customer subtotal
            sub = [""] * NCOLS
            sub[I_BASIS] = _fmt(cust_basis)
            sub[I_PROV]  = _fmt(cust_prov)
            rows.append(sub)
            styles += [
                ("FONTNAME",  (0, ri), (-1, ri), FB),
                ("ALIGN",     (I_BASIS, ri), (I_BASIS, ri), "RIGHT"),
                ("ALIGN",     (I_PROV,  ri), (I_PROV,  ri), "RIGHT"),
                ("LINEABOVE", (I_BASIS, ri), (I_BASIS, ri), 0.5, colors.black),
                ("LINEABOVE", (I_PROV,  ri), (I_PROV,  ri), 0.5, colors.black),
            ]
            ri += 1

            rows.append([" ."] + [""] * (NCOLS - 1))
            styles.append(("SPAN", (0, ri), (-1, ri)))
            ri += 1

            grand_basis += cust_basis
            grand_prov  += cust_prov

        # Grand total row
        tot = [""] * NCOLS
        tot[0]       = f"Provisionsbetrag in:  {currency}"
        tot[I_RTOT1] = _fmt(grand_basis)
        tot[I_RTOT2] = _fmt(grand_basis)
        tot[I_PTOT]  = _fmt(grand_prov)
        rows.append(tot)
        styles += [
            ("FONTNAME",  (0, ri), (-1, ri), FB),
            ("ALIGN",     (I_RTOT1, ri), (I_RTOT1, ri), "RIGHT"),
            ("ALIGN",     (I_RTOT2, ri), (I_RTOT2, ri), "RIGHT"),
            ("ALIGN",     (I_PTOT,  ri), (I_PTOT,  ri), "RIGHT"),
            ("LINEABOVE", (0, ri), (-1, ri), 0.5, colors.black),
            ("SPAN",      (0, ri), (SPAN_TOTAL_END, ri)),
        ]

        tbl = Table(rows, colWidths=CW, repeatRows=1)
        tbl.setStyle(TableStyle(styles))
        story.append(tbl)
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(r"Lib: H:\HDAGENTA\RRW\HdAgenta.RP5 \ Rep.-Name: Provision", ss))

    doc = SimpleDocTemplate(
        buf, pagesize=PAGE_SIZE,
        leftMargin=LM, rightMargin=RM,
        topMargin=TM, bottomMargin=BM,
    )
    doc.build(story)
    return buf.getvalue()
