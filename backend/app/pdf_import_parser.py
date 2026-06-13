"""Parser für Provisionsabrechnungs-PDFs (HdAgenta RP5 Format)."""
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
