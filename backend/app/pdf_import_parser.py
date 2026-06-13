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
    # Remove trailing ", CC-XXXXX City" or ", CC- City"
    m = re.match(r'^(.+?),\s*[A-Z]{2}[-\s]', raw)
    if m:
        return m.group(1).strip()
    return raw.split(',')[0].strip()


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

                # Currency detection
                m = re.search(r'Währung\s*:\s*(\w+)', line)
                if m:
                    currency = m.group(1)
                    continue

                # Skip header/footer lines
                if _SKIP_RE.search(line):
                    continue

                # Skip pure number lines (subtotals)
                if re.match(r'^[-\d.,\s]+$', line):
                    continue

                # Invoice line
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

                # Customer header line (anything else that has content)
                current_customer_raw = line

    return entries


# ── Commission-Schedule (STANASIA / VESTAS format) ─────────────────────────

def parse_commission_schedule(pdf_bytes: bytes) -> list[dict]:
    """Parse 'Commission-Schedule Agent by Turnover' PDFs (STANASIA/VESTAS).

    The Amount column frequently garbles with address/city text. Strategy:
    - commission (x>=505) and rate (x>=461) are always clean
    - amount is back-calculated from commission / rate
    - name tokens are words before the first decimal-containing token in col_name
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber nicht installiert")

    def _extract_rate(tokens: list[str]) -> float | None:
        for t in reversed(tokens):
            # Direct match (e.g. "6.00")
            m = re.search(r'(\d+\.\d+)', t)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
            # Strip alpha chars first (e.g. "rg-Sc3h.2e4rf" → "3.24")
            stripped = re.sub(r'[^0-9.]', '', re.sub(r'[a-zA-Z]', '', t))
            m2 = re.search(r'(\d+\.\d+)', stripped)
            if m2:
                try:
                    val = float(m2.group(1))
                    if 0 < val <= 100:  # sanity: rates are percentages
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

    entries = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=2, y_tolerance=3)
            if not words:
                continue

            rows: dict[float, list] = {}
            for w in words:
                y = w['top']
                matched = next((k for k in rows if abs(k - y) <= 3), None)
                if matched is None:
                    matched = y
                rows.setdefault(matched, []).append(w)

            for y_key in sorted(rows):
                row_words = sorted(rows[y_key], key=lambda w: w['x0'])
                if not row_words or row_words[0]['text'] not in ('IV', 'CN'):
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
                    elif x < 461:    col_name.append(t)  # name + garbled amount merged here
                    elif x < 485:    col_rate_t.append(t)
                    elif x < 505:    col_curr.append(t)
                    else:            col_comm.append(t)

                inv_type = col_type[0] if col_type else 'IV'
                inv_nr = ' '.join(col_num)
                date_str = col_date[0] if col_date else ''
                cust_nr = col_custnum[0] if col_custnum else ''
                currency = col_curr[0] if col_curr else 'EUR'

                # Split name from garbled-amount tokens: stop at first token with decimal
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
                # Rate: try clean column first, fallback to garbled tokens (e.g. "Sibiu0.59")
                rate = _extract_rate(col_rate_t) or _extract_rate(garbled_tokens)

                # Amount: back-calculate from commission/rate (most reliable)
                amount: float | None = None
                if commission is not None and rate and rate > 0:
                    amount = round(abs(commission) / (rate / 100), 2)
                else:
                    # Last resort: strip alpha chars from garbled token
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

                if inv_type == 'CN':
                    if amount is not None and amount > 0:
                        amount = -amount
                    if commission is not None and commission > 0:
                        commission = -commission

                entries.append({
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

    return entries


def parse_pdf_auto(pdf_bytes: bytes) -> list[dict]:
    """Detect PDF format and dispatch to the correct parser."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber nicht installiert")

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        first_text = pdf.pages[0].extract_text() if pdf.pages else ''

    if 'Commission-Schedule' in first_text and 'Agent by Turnover' in first_text:
        return parse_commission_schedule(pdf_bytes)
    return parse_provisionsabrechnung(pdf_bytes)
