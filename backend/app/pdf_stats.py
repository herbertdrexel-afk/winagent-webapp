"""PDF generator for supplier statistics summary (like 'Lieferant Statistik Summe All')."""
from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT


def _fmt(n: float, zero: str = "0") -> str:
    if n == 0:
        return zero
    return f"{n:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(pct) -> str:
    if pct is None:
        return "***,*%"
    return f"{pct:+.1f}%".replace(".", ",")


def build_customer_turnover_pdf(data: dict) -> bytes:
    """AdrUms report: customer list sorted by provision or turnover."""
    rows = data["rows"]
    sort_by = data.get("sort_by", "provision")
    period_from = data["period_from"]
    period_to = data["period_to"]
    period_label = f"{period_from[5:7]}.{period_from[2:4]} - {period_to[5:7]}.{period_to[2:4]}"
    sort_label = "nach Provision" if sort_by == "provision" else "nach Umsatz"
    today_str = date.today().strftime("%d.%m.%y")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    n = styles["Normal"]; n.fontName = "Helvetica"; n.fontSize = 8
    bold = ParagraphStyle("b", parent=n, fontName="Helvetica-Bold")
    right = ParagraphStyle("r", parent=n, alignment=TA_RIGHT)
    rb = ParagraphStyle("rb", parent=bold, alignment=TA_RIGHT)
    sm = ParagraphStyle("sm", parent=n, fontSize=7)
    smr = ParagraphStyle("smr", parent=sm, alignment=TA_RIGHT)

    story = []
    # Header
    hd = [[
        Paragraph(f"<b>Umsatzliste {period_label} {sort_label}</b>",
                  ParagraphStyle("t", parent=n, fontName="Helvetica-Bold", fontSize=12)),
        Paragraph(today_str, ParagraphStyle("d", parent=n, fontSize=9, alignment=TA_RIGHT)),
    ]]
    ht = Table(hd, colWidths=[20*cm, 8*cm])
    ht.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story.append(ht)
    story.append(Spacer(1, 0.3*cm))

    H_FILL = colors.HexColor("#2563eb")
    COL_W = [6*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.2*cm, 1.8*cm, 1.8*cm, 1.0*cm]

    total_prov = sum(r["curr_provision"] for r in rows)

    thead = [[
        Paragraph("<b>Name / Firma</b>", bold),
        Paragraph("<b>Umsatz VJ</b>", rb),
        Paragraph("<b>Budget</b>", rb),
        Paragraph("<b>Umsatz</b>", rb),
        Paragraph("<b>Budget-Prov</b>", rb),
        Paragraph("<b>Provision</b>", rb),
        Paragraph("<b>DuPr %</b>", rb),
        Paragraph("<b>%</b>", rb),
        Paragraph("<b>P.</b>", ParagraphStyle("c", parent=bold, alignment=TA_CENTER)),
    ]]
    table_data = thead[:]

    for i, r in enumerate(rows, 1):
        ct = r["curr_turnover"]; cp = r["curr_provision"]
        pt = r["prev_turnover"]; rate = r["avg_rate"]
        share = r["share_pct"]
        table_data.append([
            Paragraph(r["customer_name"], sm),
            Paragraph(_fmt(pt), smr),
            Paragraph("", smr),
            Paragraph(_fmt(ct), smr),
            Paragraph("", smr),
            Paragraph(_fmt(cp), smr),
            Paragraph(f"{rate:.2f}".replace(".", ","), smr),
            Paragraph(f"{share:.1f}%".replace(".", ","), smr),
            Paragraph(str(i), ParagraphStyle("c", parent=sm, alignment=TA_CENTER)),
        ])

    # Totals
    tot_t = sum(r["curr_turnover"] for r in rows)
    tot_p = sum(r["curr_provision"] for r in rows)
    table_data.append([
        Paragraph("<b>Gesamtsumme: EUR</b>", bold),
        Paragraph("", rb),
        Paragraph("", rb),
        Paragraph(_fmt(tot_t), rb),
        Paragraph("", rb),
        Paragraph(_fmt(tot_p), rb),
        Paragraph("", rb),
        Paragraph("", rb),
        Paragraph("", rb),
    ])

    t = Table(table_data, colWidths=COL_W, repeatRows=1)
    n_rows = len(rows)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), H_FILL),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1, n_rows), [colors.white, colors.HexColor("#dce8f5")]),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#f0f5fb")),
        ("LINEABOVE",  (0,-1), (-1,-1), 1, H_FILL),
        ("GRID",       (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",(0,0), (-1,-1), 3), ("RIGHTPADDING",  (0,0), (-1,-1), 3),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


def build_supplier_detail_pdf(data: dict) -> bytes:
    """Quarterly supplier detail PDF (one section per supplier)."""
    year = data["year"]
    suppliers = data["suppliers"]
    today_str = date.today().strftime("%d.%m.%Y")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    n = styles["Normal"]; n.fontName = "Helvetica"; n.fontSize = 8
    bold = ParagraphStyle("b", parent=n, fontName="Helvetica-Bold")
    right = ParagraphStyle("r", parent=n, alignment=TA_RIGHT)
    rb = ParagraphStyle("rb", parent=bold, alignment=TA_RIGHT)
    sm = ParagraphStyle("sm", parent=n, fontSize=7)
    smr = ParagraphStyle("smr", parent=sm, alignment=TA_RIGHT)

    def pct_str(curr, prev):
        if not prev:
            return "***%"
        p = (curr / prev - 1) * 100
        return f"{p:+.0f}%".replace(".", ",")

    H_FILL = colors.HexColor("#2563eb")
    H_SUB  = colors.HexColor("#4a7fc1")
    COL_W  = [1.5*cm, 2.4*cm, 2.4*cm, 1.2*cm, 2.4*cm, 1.2*cm, 2.2*cm, 2.2*cm, 2.2*cm, 1.2*cm, 2.2*cm, 1.8*cm, 1.2*cm]

    story = []
    # Global header
    story.append(Paragraph(
        f"<b>Lieferant Statistik Detail — {year}</b>",
        ParagraphStyle("title", parent=n, fontName="Helvetica-Bold", fontSize=13)))
    story.append(Paragraph(f"turnover-quantity-commission-expense-budget-comparison in EUR   {today_str}",
                            ParagraphStyle("sub", parent=n, fontSize=8)))
    story.append(Spacer(1, 0.4*cm))

    col_header = [
        Paragraph("<b>des.</b>", bold),
        Paragraph("<b>turnover last year</b>", rb),
        Paragraph("<b>budget</b>", rb),
        Paragraph("<b>+/-</b>", rb),
        Paragraph("<b>turnover curr y</b>", rb),
        Paragraph("<b>+/-</b>", rb),
        Paragraph("<b>comm.-last y</b>", rb),
        Paragraph("<b>comm. budget net</b>", rb),
        Paragraph("<b>comm. curr y</b>", rb),
        Paragraph("<b>+/-</b>", rb),
        Paragraph("<b>comm. brut</b>", rb),
        Paragraph("<b>difference</b>", rb),
        Paragraph("<b>+/-</b>", rb),
    ]

    for s in suppliers:
        # Supplier header
        story.append(Paragraph(
            f"<b>{s['name']}</b>",
            ParagraphStyle("sh", parent=n, fontName="Helvetica-Bold", fontSize=10)))
        story.append(Spacer(1, 0.1*cm))

        table_data = [col_header]
        BOLD_ROWS = []

        for i, r in enumerate(s["rows"], 1):
            label = r["label"]
            pt = r["prev_turnover"]; bt = r["budget_turnover"]
            ct = r["curr_turnover"]; pp = r["prev_commission"]
            bc = r["budget_commission"]; cp = r["curr_commission"]
            diff = cp - pp
            is_total = label in ("1.HY", "2.HY", "Jahr")
            style = rb if is_total else smr
            label_style = bold if is_total else sm

            table_data.append([
                Paragraph(f"<b>{label}</b>" if is_total else label, label_style),
                Paragraph(_fmt(pt), style),
                Paragraph(_fmt(bt) if bt else "", style),
                Paragraph(pct_str(bt, pt) if bt and pt else "", style),
                Paragraph(_fmt(ct), style),
                Paragraph(pct_str(ct, pt) if pt else "***%", style),
                Paragraph(_fmt(pp), style),
                Paragraph(_fmt(bc) if bc else "", style),
                Paragraph(_fmt(cp), style),
                Paragraph(pct_str(cp, pp) if pp else "***%", style),
                Paragraph(_fmt(cp), style),
                Paragraph((_fmt(diff) if diff != 0 else "0"), style),
                Paragraph(pct_str(cp, pp) if pp else "***%", style),
            ])
            if is_total:
                BOLD_ROWS.append(i)

        t = Table(table_data, colWidths=COL_W, repeatRows=1)
        ts = [
            ("BACKGROUND",  (0,0), (-1,0), H_FILL),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID",        (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
            ("TOPPADDING",  (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING",  (0,0), (-1,-1), 3),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ]
        for row_idx in BOLD_ROWS:
            ts.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#dce8f5")))
            ts.append(("LINEABOVE",  (0, row_idx), (-1, row_idx), 0.5, H_FILL))
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

    doc.build(story)
    return buf.getvalue()


def build_supplier_stats_pdf(data: dict) -> bytes:
    rows = data["rows"]
    period_from = data["period_from"]
    period_to = data["period_to"]

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 8

    bold = ParagraphStyle("bold", parent=normal, fontName="Helvetica-Bold")
    right = ParagraphStyle("right", parent=normal, alignment=TA_RIGHT)
    right_bold = ParagraphStyle("right_bold", parent=bold, alignment=TA_RIGHT)
    center = ParagraphStyle("center", parent=normal, alignment=TA_CENTER)
    small = ParagraphStyle("small", parent=normal, fontSize=7)
    small_right = ParagraphStyle("small_right", parent=small, alignment=TA_RIGHT)

    today_str = date.today().strftime("%d.%m.%y")
    period_label = f"{period_from[5:7]}.{period_from[2:4]} - {period_to[5:7]}.{period_to[2:4]}"

    story = []

    # Header
    header_data = [[
        Paragraph("<b>AMV Ltd.</b>", ParagraphStyle("title", parent=normal, fontName="Helvetica-Bold", fontSize=14)),
        Paragraph(f"<b>{period_label}</b>", ParagraphStyle("period", parent=normal, fontName="Helvetica-Bold", fontSize=11, alignment=TA_RIGHT)),
        Paragraph(today_str, ParagraphStyle("date", parent=normal, fontSize=9, alignment=TA_RIGHT)),
    ]]
    header_table = Table(header_data, colWidths=[10*cm, 10*cm, 8*cm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(header_table)
    story.append(Paragraph("<b>supplier- turnover- expense- budget in EUR</b>",
                            ParagraphStyle("sub", parent=normal, fontName="Helvetica-Bold", fontSize=10)))
    story.append(Spacer(1, 0.4*cm))

    # Table header — two rows
    COL_W = [4.5*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.0*cm, 2.0*cm, 2.0*cm, 2.0*cm, 2.0*cm, 1.8*cm, 1.8*cm]
    # total width: 4.5+2.2+2.2+2.2+2.0+2.0+2.0+2.0+2.0+1.8+1.8 = 26.7cm — fits A4 landscape (26.7cm usable)

    h1 = [
        Paragraph("<b>supplier</b>", bold),
        Paragraph("<b>turnover</b>", ParagraphStyle("ch", parent=bold, alignment=TA_CENTER)),
        "", "",
        Paragraph("<b>commission budget</b>", ParagraphStyle("ch", parent=bold, alignment=TA_CENTER)),
        "",
        Paragraph("<b>last year</b>", ParagraphStyle("ch", parent=bold, alignment=TA_CENTER)),
        Paragraph("<b>curr year</b>", ParagraphStyle("ch", parent=bold, alignment=TA_CENTER)),
        "", "", "",
    ]
    h2 = [
        "",
        Paragraph("last year", small),
        Paragraph("current year", small),
        Paragraph("budget", small),
        Paragraph("brut", small),
        Paragraph("net", small),
        Paragraph("comm. net", small),
        Paragraph("comm. net", small),
        Paragraph("comm. brut", small),
        Paragraph("comm. diff", small),
        Paragraph("%", small),
    ]

    HEADER_FILL = colors.HexColor("#1a3a5c")
    HEADER_SUB = colors.HexColor("#2d5a8e")

    table_data = [h1, h2]

    # Data rows
    tot_curr_t = tot_prev_t = tot_curr_c = tot_prev_c = 0.0

    for r in rows:
        curr_t = r["curr_turnover"]
        curr_c = r["curr_commission"]
        prev_t = r["prev_turnover"]
        prev_c = r["prev_commission"]
        diff = r["comm_diff"]
        pct = r["comm_pct"]

        tot_curr_t += curr_t
        tot_prev_t += prev_t
        tot_curr_c += curr_c
        tot_prev_c += prev_c

        table_data.append([
            Paragraph(r["name"], small),
            Paragraph(_fmt(prev_t), small_right),
            Paragraph(_fmt(curr_t), small_right),
            Paragraph("", small_right),   # budget — not in DB
            Paragraph("", small_right),   # comm budget brut
            Paragraph("", small_right),   # comm budget net
            Paragraph(_fmt(prev_c), small_right),
            Paragraph(_fmt(curr_c), small_right),
            Paragraph(_fmt(curr_c), small_right),
            Paragraph(_fmt(diff, "0") if diff != 0 else "0", small_right),
            Paragraph(_fmt_pct(pct), small_right),
        ])

    # Totals row
    tot_diff = tot_curr_c - tot_prev_c
    tot_pct = ((tot_curr_c / tot_prev_c - 1) * 100) if tot_prev_c else None
    table_data.append([
        Paragraph("<b>totals</b>", bold),
        Paragraph(_fmt(tot_prev_t), right_bold),
        Paragraph(_fmt(tot_curr_t), right_bold),
        Paragraph("", right_bold),
        Paragraph("", right_bold),
        Paragraph("", right_bold),
        Paragraph(_fmt(tot_prev_c), right_bold),
        Paragraph(_fmt(tot_curr_c), right_bold),
        Paragraph(_fmt(tot_curr_c), right_bold),
        Paragraph(_fmt(tot_diff, "0"), right_bold),
        Paragraph(_fmt_pct(tot_pct), right_bold),
    ])

    t = Table(table_data, colWidths=COL_W, repeatRows=2)

    n_data = len(rows)
    t.setStyle(TableStyle([
        # Header row 1
        ("BACKGROUND",   (0, 0), (-1, 0), HEADER_FILL),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("SPAN",         (1, 0), (3, 0)),
        ("SPAN",         (4, 0), (5, 0)),
        ("SPAN",         (7, 0), (8, 0)),
        # Header row 2
        ("BACKGROUND",   (0, 1), (-1, 1), HEADER_SUB),
        ("TEXTCOLOR",    (0, 1), (-1, 1), colors.white),
        # Data rows
        ("ROWBACKGROUNDS", (0, 2), (-1, n_data + 1), [colors.white, colors.HexColor("#dce8f5")]),
        # Totals row
        ("BACKGROUND",   (0, -1), (-1, -1), colors.HexColor("#f0f5fb")),
        ("LINEABOVE",    (0, -1), (-1, -1), 1, colors.HexColor("#1a3a5c")),
        # Grid
        ("GRID",         (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("LINEBELOW",    (0, 1), (-1, 1), 0.5, colors.white),
        # Padding
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(t)
    doc.build(story)
    return buf.getvalue()
