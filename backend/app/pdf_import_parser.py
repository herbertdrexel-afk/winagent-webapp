"""Parser für Provisionsabrechnungs-PDFs (HdAgenta RP5 + Commission-Schedule)."""
import re
from datetime import date
from io import BytesIO


# DD.MM.YY or DD.MM.YYYY at line start → invoice line
_INV_RE = re.compile(
    r'^(\d{1,2}\.\d{1,2}\.\d{2,4})'  # date
    r'\s+(\S+)'                        # Re-Nummer
    r'\s+(\S+)'                        # Art-Nr
    r'\s+[\d,.]+\s+\d+'               # Preis + Rab (skipped)
    r'\s+(-?[\d,.]+)'                  # Re.Betrag
    r'\s+(-?[\d,.]+)'                  # Re.Nett (skipped)
    r'\s+(-?[\d,.]+)'                  # Prov.Basis (skipped)
    r'\s+([\d,.]+)'                    # Prov. %
    r'\s+(-?[\d,.]+)'                  # Provision
)

_SKIP_RE = re.compile(
    r'^(Provisionsabrechnung:|Zeitraum:|Datum\s+Re\.|Provisionsbetrag\s+in:|'
    r'Seite:|Lib:|Rep\.-Name:|Währung\s*:)'
)


def _parse_num(s: str) -> float | None:
    if not s:
        return None
    try:
        return float(s.strip().replace('.', '').replace(',', '.'))
    except ValueError:
        return None


def _parse_date(s: str) -> str | None:
    m = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', s.strip())
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _clean_customer_name(raw: str) -> str:
    """'Bönning + Sommer GmbH, DE-34414 Warburg' → 'Bönning + Sommer GmbH'"""
    m = re.match(r'^(.+?),\s*[A-Z]{2}[-\s]', raw)
    if m:
        return m.group(1).strip()
    return raw.split(',')[0].strip()


# ── PyMuPDF helpers (better CID-font handling) ────────────────────────────────

def _fitz_text(pdf_bytes: bytes, page_num: int = 0) -> str:
    """Extract plain text from a page using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_num < len(doc):
            return doc[page_num].get_text()
        return ""
    except Exception:
        return ""


def _fitz_words(pdf_bytes: bytes) -> list[list[dict]]:
    """Extract words with positions per page using PyMuPDF.

    Returns list of pages, each page is a list of word dicts with
    keys: x0, top, x1, bottom, text.
    """
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            raw = page.get_text("words")  # (x0,y0,x1,y1,text,block,line,word)
            pages.append([
                {"x0": w[0], "top": w[1], "x1": w[2], "bottom": w[3], "text": w[4]}
                for w in raw
            ])
        return pages
    except Exception:
        return []


# ── MIVAR-VIVA LTD vendor invoice parser ─────────────────────────────────────

def parse_mivar_invoice(pdf_bytes: bytes) -> list[dict]:
    """Parse a MIVAR-VIVA LTD vendor invoice PDF.

    Returns a single entry: AMOUNT EUR (after discount) minus Transport and
    Europallets.  Provision rate is left at 0 — the endpoint fills it from
    the supplier's provision_splits.
    """
    text = _fitz_text(pdf_bytes, 0)
    if not text:
        try:
            import pdfplumber
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text = pdf.pages[0].extract_text() or ''
        except Exception:
            text = ''

    def _num_sp(s: str) -> float:
        """Parse number that may use space as thousands separator (e.g. '16 814,97')."""
        return _parse_num(s.replace(' ', '')) or 0.0

    def _last_num_on_line(keyword: str) -> float:
        """Return the last decimal number on the line that starts with keyword."""
        m = re.search(rf'{keyword}\b[^\n]+', text, re.IGNORECASE)
        if not m:
            return 0.0
        nums = re.findall(r'[\d]+(?:\s[\d]{3})*[,.][\d]{2}', m.group())
        return _num_sp(nums[-1]) if nums else 0.0

    # Invoice number — 4+ digit sequence after "INVOICE:"
    inv_m = re.search(r'INVOICE:\s*(\d{4,})', text)
    invoice_number = inv_m.group(1) if inv_m else ''

    # Invoice date
    date_m = re.search(r'INVOICE\s+DATE[:\s]*([\d]{1,2}\.[\d]{1,2}\.[\d]{4})', text)
    invoice_date = _parse_date(date_m.group(1)) if date_m else ''

    # Customer / consignee name (first meaningful line after CONSIGNEE:)
    customer_name = ''
    con_m = re.search(r'CONSIGNEE[:\s]*\n\s*(.+)', text)
    if con_m:
        customer_name = con_m.group(1).strip()
    else:
        # Fallback: company name pattern after CONSIGNEE keyword
        con_m2 = re.search(
            r'CONSIGNEE[:\s]+([A-Z][A-Z&\-\s]{3,50}(?:GMBH|GmbH|LTD|Ltd|AG|SA|SRL|KG)\.?)',
            text
        )
        if con_m2:
            customer_name = con_m2.group(1).strip()

    # Final payable amount (after discount)
    am_m = re.search(r'AMOUNT[:\s]+EUR[:\s]*([\d][\d\s,\.]+)', text, re.IGNORECASE)
    total_after_discount = _num_sp(am_m.group(1).strip()) if am_m else 0.0

    # Freight charges to exclude from provision base
    transport = _last_num_on_line(r'Transport')
    pallets   = _last_num_on_line(r'Europallets')

    net_amount = round(total_after_discount - transport - pallets, 2)

    return [{
        'customer_name_raw':   customer_name,
        'customer_name_clean': customer_name,
        'customer_nr':         None,
        'invoice_date':        invoice_date,
        'invoice_number':      invoice_number,
        'art_nr':              '',
        'total_amount':        net_amount,
        'provision_rate':      0.0,
        'provision_amount':    0.0,
        'currency':            'EUR',
    }]


# ── HdAgenta RP5 parser ───────────────────────────────────────────────────────

def parse_provisionsabrechnung(pdf_bytes: bytes) -> list[dict]:
    """Parse PDF and return list of invoice entries."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber nicht installiert")

    entries = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if not text:
                continue

            currency = "EUR"
            current_customer_raw = None

            for line in text.split("\n"):
                line = line.strip()
                if not line or line == ".":
                    continue

                m = re.search(r'Währung\s*:\s*(\w+)', line)
                if m:
                    currency = m.group(1)
                    continue

                if _SKIP_RE.search(line):
                    continue

                if re.match(r'^[-\d.,\s]+$', line):
                    continue

                inv = _INV_RE.match(line)
                if inv:
                    inv_date = _parse_date(inv.group(1))
                    amount = _parse_num(inv.group(4))
                    prov_pct = _parse_num(inv.group(7))
                    provision = _parse_num(inv.group(8))

                    if inv_date and amount is not None:
                        entries.append({
                            "customer_name_raw": current_customer_raw or "",
                            "customer_name_clean": _clean_customer_name(current_customer_raw) if current_customer_raw else "",
                            "invoice_date": inv_date,
                            "invoice_number": inv.group(2),
                            "art_nr": inv.group(3),
                            "total_amount": amount,
                            "provision_rate": prov_pct,
                            "provision_amount": provision,
                            "currency": currency,
                        })
                    continue

                current_customer_raw = line

    return entries


# ── Commission-Schedule (STANASIA / VESTAS / AMV format) ──────────────────────

def parse_commission_schedule(pdf_bytes: bytes) -> list[dict]:
    """Parse 'Commission-Schedule Agent by Turnover' PDFs.

    Uses PyMuPDF for text extraction (better CID-font support),
    falls back to pdfplumber.
    """

    def _extract_rate(tokens: list[str]) -> float | None:
        for t in reversed(tokens):
            m = re.search(r'(\d+\.\d+)', t)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
            stripped = re.sub(r'[^0-9.]', '', re.sub(r'[a-zA-Z]', '', t))
            m2 = re.search(r'(\d+\.\d+)', stripped)
            if m2:
                try:
                    val = float(m2.group(1))
                    if 0 < val <= 100:
                        return val
                except ValueError:
                    pass
        return None

    def _extract_commission(tokens: list[str]) -> float | None:
        joined = ''.join(tokens)
        negative = joined.endswith('-')
        if negative:
            joined = joined[:-1]
        try:
            return -float(joined.replace(',', '')) if negative else float(joined.replace(',', ''))
        except ValueError:
            return None

    def _process_page_words(words: list[dict]) -> list[dict]:
        """Group words into rows by y-coord and parse each invoice row."""
        if not words:
            return []

        rows: dict[float, list] = {}
        for w in words:
            y = w['top']
            matched = next((k for k in rows if abs(k - y) <= 3), None)
            if matched is None:
                matched = y
            rows.setdefault(matched, []).append(w)

        page_entries = []
        for y_key in sorted(rows):
            row_words = sorted(rows[y_key], key=lambda w: w['x0'])
            if not row_words:
                continue

            first_text = row_words[0]['text']
            # Accept IV (Invoice), CN (Credit Note), or RG/RE (German variants)
            if first_text not in ('IV', 'CN', 'RG', 'RE', 'IN'):
                continue

            col_type, col_num, col_date = [], [], []
            col_custnum, col_name = [], []
            col_rate_t, col_curr, col_comm = [], [], []

            for w in row_words:
                x, t = w['x0'], w['text']
                if x < 63:       col_type.append(t)
                elif x < 120:    col_num.append(t)
                elif x < 185:    col_date.append(t)
                elif x < 236:    col_custnum.append(t)
                elif x < 461:    col_name.append(t)
                elif x < 485:    col_rate_t.append(t)
                elif x < 505:    col_curr.append(t)
                else:            col_comm.append(t)

            inv_type = col_type[0] if col_type else 'IV'
            inv_nr = ' '.join(col_num)
            date_str = col_date[0] if col_date else ''
            cust_nr = col_custnum[0] if col_custnum else ''
            currency = col_curr[0] if col_curr else 'EUR'

            name_tokens: list[str] = []
            garbled_tokens: list[str] = []
            for t in col_name:
                if not garbled_tokens and re.search(r'\d.*\.\d', t):
                    garbled_tokens.append(t)
                elif garbled_tokens:
                    garbled_tokens.append(t)
                else:
                    name_tokens.append(t)
            cust_name_raw = ' '.join(name_tokens) if name_tokens else ' '.join(col_name)

            inv_date = _parse_date(date_str)
            if not inv_date:
                continue

            full_inv_nr = f"{inv_type} {inv_nr}".strip()
            commission = _extract_commission(col_comm)
            rate = _extract_rate(col_rate_t) or _extract_rate(garbled_tokens)

            amount: float | None = None
            if commission is not None and rate and rate > 0:
                amount = round(abs(commission) / (rate / 100), 2)
            else:
                for t in reversed(garbled_tokens):
                    stripped = re.sub(r'[^0-9,.]', '', re.sub(r'[a-zA-Z]', '', t))
                    if '.' in stripped:
                        try:
                            amount = float(stripped.replace(',', ''))
                            break
                        except ValueError:
                            pass

            if commission is None and amount is None:
                continue

            if inv_type in ('CN',):
                if amount is not None and amount > 0:
                    amount = -amount
                if commission is not None and commission > 0:
                    commission = -commission

            page_entries.append({
                'customer_name_raw': cust_name_raw,
                'customer_name_clean': _clean_customer_name(cust_name_raw),
                'customer_nr': cust_nr,
                'invoice_date': inv_date,
                'invoice_number': full_inv_nr,
                'art_nr': '',
                'total_amount': amount or 0.0,
                'provision_rate': rate,
                'provision_amount': commission,
                'currency': currency,
            })

        return page_entries

    entries = []

    # Try PyMuPDF first (handles CID-encoded fonts better)
    fitz_pages = _fitz_words(pdf_bytes)
    if fitz_pages:
        for page_words in fitz_pages:
            entries.extend(_process_page_words(page_words))
        if entries:
            return entries

    # Fall back to pdfplumber
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber nicht installiert")

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=2, y_tolerance=3)
            entries.extend(_process_page_words(words))

    return entries


# ── Public helpers ───────────────────────────────────────────────────────────

def extract_commission_schedule_company(pdf_bytes: bytes) -> str | None:
    """Return the company name from a Commission-Schedule PDF header, or None."""
    text = _fitz_text(pdf_bytes, 0)
    if not text:
        try:
            import pdfplumber
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text = pdf.pages[0].extract_text() if pdf.pages else ''
        except Exception:
            pass
    if not text:
        return None
    # Header line: "Company  0001  STANASIA Shanghai"
    m = re.search(r'Company\s+\S+\s+(.+?)[\n\r]', text)
    if m:
        return m.group(1).strip()
    return None


# ── Public entry point ────────────────────────────────────────────────────────

def parse_pdf_auto(pdf_bytes: bytes) -> list[dict]:
    """Detect PDF format and dispatch to the correct parser."""
    # Try PyMuPDF first for text detection (better CID-font support)
    first_text = _fitz_text(pdf_bytes, 0)

    # Fall back to pdfplumber if PyMuPDF returns empty
    if not first_text:
        try:
            import pdfplumber
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                first_text = pdf.pages[0].extract_text() if pdf.pages else ''
        except Exception:
            first_text = ''

    # MIVAR-VIVA LTD vendor invoice
    if 'MIVAR' in first_text and 'INVOICE' in first_text and 'VENDOR' in first_text:
        return parse_mivar_invoice(pdf_bytes)

    # 'Turnover' is sometimes clipped to 'Turnov' by PyMuPDF on narrow headers
    if ('Commission-Schedule' in first_text or 'Commission Schedule' in first_text) \
            and 'Agent by Turnov' in first_text:
        return parse_commission_schedule(pdf_bytes)

    return parse_provisionsabrechnung(pdf_bytes)
