import csv
import re
from datetime import date
from io import StringIO, BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user, get_allowed_supplier_ids, check_supplier_access
from ..database import get_db

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _tx_to_out(tx: models.Transaction) -> schemas.TransactionOut:
    """Transaction ORM → schema, Kundenfelder aus der Relation befüllen."""
    data = schemas.TransactionOut.model_validate(tx)
    if tx.customer:
        data.customer_code  = tx.customer.code
        data.customer_ku_nr = tx.customer.ku_nr
        data.customer_name  = tx.customer.name
    return data


@router.get("", response_model=list[schemas.SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Supplier)
    allowed = get_allowed_supplier_ids(current_user, db)
    if allowed is not None:
        q = q.filter(models.Supplier.id.in_(allowed))
    return q.order_by(models.Supplier.code).all()


@router.post("", response_model=schemas.SupplierOut, status_code=201)
def create_supplier(payload: schemas.SupplierCreate, db: Session = Depends(get_db)):
    code = payload.code.upper().strip()
    if db.query(models.Supplier).filter(models.Supplier.code == code).first():
        raise HTTPException(409, f"Code '{code}' ist bereits vergeben")
    supplier = models.Supplier(**{**payload.model_dump(), "code": code})
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/{code}", response_model=schemas.SupplierOut)
def get_supplier(
    code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    check_supplier_access(current_user, db, supplier.id)
    return supplier


@router.patch("/{code}", response_model=schemas.SupplierOut)
def update_supplier(
    code: str,
    payload: schemas.SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    check_supplier_access(current_user, db, supplier.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.post("/{code}/transactions", response_model=schemas.TransactionOut, status_code=201)
def create_transaction(
    code: str,
    payload: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    check_supplier_access(current_user, db, supplier.id)
    from sqlalchemy import extract
    year = int(payload.invoice_date.split("-")[0]) if isinstance(payload.invoice_date, str) else payload.invoice_date.year
    tx = models.Transaction(**{**payload.model_dump(), "supplier_id": supplier.id, "year": year})
    db.add(tx)
    db.commit()
    db.refresh(tx)
    db.refresh(tx, ["customer"])
    return _tx_to_out(tx)


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tx = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(404, "Position nicht gefunden")
    check_supplier_access(current_user, db, tx.supplier_id)
    db.delete(tx)
    db.commit()


@router.patch("/transactions/{transaction_id}", response_model=schemas.TransactionOut)
def update_transaction(
    transaction_id: int,
    payload: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tx = db.query(models.Transaction).options(
        joinedload(models.Transaction.customer)
    ).filter(models.Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(404, "Transaktion nicht gefunden")
    check_supplier_access(current_user, db, tx.supplier_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tx, field, value)
    db.commit()
    db.refresh(tx)
    # customer neu laden nach commit
    db.refresh(tx, ["customer"])
    return _tx_to_out(tx)


@router.get("/{code}/transactions", response_model=list[schemas.TransactionOut])
def list_transactions(
    code: str,
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    check_supplier_access(current_user, db, supplier.id)
    txs = (
        db.query(models.Transaction)
        .options(joinedload(models.Transaction.customer))
        .filter(
            models.Transaction.supplier_id == supplier.id,
            models.Transaction.invoice_date >= date_from,
            models.Transaction.invoice_date <= date_to,
        )
        .order_by(models.Transaction.invoice_date)
        .all()
    )
    return [_tx_to_out(tx) for tx in txs]


def _parse_num_de(s: object) -> float:
    """Parse German decimal number (comma = decimal sep, dot = thousands sep)."""
    try:
        return float(str(s).strip().replace('.', '').replace(',', '.'))
    except (ValueError, AttributeError):
        return 0.0


def _parse_date_de(s: object) -> str:
    """Convert DD.MM.YYYY → YYYY-MM-DD. Returns original string on failure."""
    m = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', str(s).strip())
    if not m:
        return str(s).strip()
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return str(s).strip()


def _parse_csv_content(content: bytes) -> list[dict]:
    for enc in ('utf-8-sig', 'cp1252', 'utf-8', 'latin-1'):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode('utf-8', errors='replace')

    delimiter = ';' if ';' in text.split('\n')[0] else ','
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    entries = []
    for row in reader:
        waehrung = (row.get('Währung') or row.get('Waehrung') or row.get('Currency') or '').strip()
        kunde    = (row.get('Kunde') or row.get('Customer') or '').strip()
        datum    = (row.get('Datum') or row.get('Date') or '').strip()
        re_nr    = str(row.get('Rechnungsnummer') or row.get('Invoice Number') or row.get('Invoice') or '').strip()
        basis    = _parse_num_de(row.get('Provisionsbasis') or row.get('Commission Basis') or row.get('Basis') or 0)
        rate     = _parse_num_de(row.get('Provision %') or row.get('Provision%')
                                 or row.get('Commission %') or row.get('Commission%') or 0)
        prov     = _parse_num_de(row.get('Provision') or row.get('Commission') or 0)
        lief     = (row.get('Lieferant') or row.get('Supplier') or '').strip()
        if not waehrung or not kunde or not datum:
            continue
        entries.append({
            'customer_name_raw':   kunde,
            'customer_name_clean': kunde,
            'customer_nr':         None,
            'invoice_date':        _parse_date_de(datum),
            'invoice_number':      re_nr,
            'art_nr':              '',
            'total_amount':        basis,
            'provision_rate':      rate,
            'provision_amount':    prov,
            'currency':            waehrung,
            'supplier_code':       lief.upper() or None,
        })
    return entries


def _parse_excel_content(content: bytes) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [str(h or '').strip().lower() for h in rows[0]]

    def _idx(*names: str) -> int | None:
        for name in names:
            for i, h in enumerate(headers):
                if name in h:
                    return i
        return None

    i_sup = _idx('lieferant', 'supplier')
    i_cur = _idx('währung', 'waehrung', 'currency')
    i_knd = _idx('kunde', 'customer')
    i_dat = _idx('datum', 'date')
    i_rnr = _idx('rechnungsnummer', 'invoice')
    i_bas = _idx('provisionsbasis', 'commission basis', 'basis')
    i_rat = _idx('provision %', 'provision%', '% provision',
                 'commission %', 'commission%', '% commission')
    # 'provision'/'commission' (Betrag) darf nicht mit Basis-/%-Spalte kollidieren
    i_prv = next((k for k, h in enumerate(headers) if h in ('provision', 'commission')), None)
    if i_prv is None:
        i_prv = next((k for k, h in enumerate(headers)
                      if ('provision' in h or 'commission' in h) and k not in (i_bas, i_rat)), None)

    def cell(row: tuple, idx: int | None):
        return row[idx] if idx is not None and idx < len(row) else None

    entries = []
    for row in rows[1:]:
        if not any(row):
            continue
        waehrung = str(cell(row, i_cur) or '').strip()
        kunde    = str(cell(row, i_knd) or '').strip()
        datum    = cell(row, i_dat)
        re_nr    = str(cell(row, i_rnr) or '').strip()
        basis    = float(cell(row, i_bas) or 0)
        rate     = float(cell(row, i_rat) or 0)
        prov     = float(cell(row, i_prv) or 0)
        if not waehrung or not kunde:
            continue
        # Excel dates may be datetime objects
        if hasattr(datum, 'strftime'):
            inv_date = datum.strftime('%Y-%m-%d')
        else:
            inv_date = _parse_date_de(datum)
        entries.append({
            'customer_name_raw':   kunde,
            'customer_name_clean': kunde,
            'customer_nr':         None,
            'invoice_date':        inv_date,
            'invoice_number':      re_nr,
            'art_nr':              '',
            'total_amount':        round(basis, 2),
            'provision_rate':      round(rate, 4),
            'provision_amount':    round(prov, 2),
            'currency':            waehrung,
            'supplier_code':       (str(cell(row, i_sup) or '').strip().upper() or None),
        })
    return entries


def _match_customers(entries: list[dict], db: Session) -> list[dict]:
    """Add customer_suggestions to each entry by matching name against DB."""
    name_cache: dict[str, list] = {}
    for entry in entries:
        clean = entry["customer_name_clean"]
        if clean in name_cache:
            continue
        if not clean:
            name_cache[clean] = []
            continue
        first_word = clean.split()[0]
        customers = (
            db.query(models.Customer)
            .filter(models.Customer.name.ilike(f"%{first_word}%"))
            .limit(5)
            .all()
        )
        name_cache[clean] = [
            {"id": c.id, "code": c.code, "ku_nr": c.ku_nr, "name": c.name, "city": c.city}
            for c in customers
        ]
    return [{**e, "customer_suggestions": name_cache[e["customer_name_clean"]]} for e in entries]


# ── Einheitlicher Import: CSV / Excel / JSON / XML (gleiche Spaltenstruktur) ──

def _to_num(v) -> float:
    """Zahl aus JSON (echte Zahl) oder Text (dt. '1.234,56' oder engl. '1234.56')."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    if ',' in s:                       # deutsches Format 1.234,56
        return _parse_num_de(s)
    if '.' in s:
        # kein Komma: im dt. Umfeld ist '.' Tausendertrenner (3.904 → 3904),
        # außer es sieht nach Dezimalzahl mit 1–2 Nachkommastellen aus (3.90 → 3.9)
        frac = s.rpartition('.')[2]
        if frac.isdigit() and len(frac) == 3:
            return _parse_num_de(s)
    try:
        return float(s)                # 1234.56 oder 1234
    except ValueError:
        return _parse_num_de(s)


def _to_iso_date(v) -> str:
    if v is None:
        return ''
    if hasattr(v, 'strftime'):
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    if re.match(r'\d{4}-\d{2}-\d{2}', s):
        return s[:10]
    return _parse_date_de(s)


def _normalize_row(raw: dict) -> dict | None:
    """Beliebiges Zeilen-Dict (JSON-Objekt / XML-Row) → Standard-Eintrag.
    Spalten wie in der CSV-Vorlage, deutsch oder englisch."""
    low = {str(k).strip().lower(): val for k, val in raw.items()}

    def pick(*keys):
        for k in keys:
            if k in low and low[k] not in (None, ''):
                return low[k]
        return None

    cur   = str(pick('währung', 'waehrung', 'currency') or '').strip()
    kunde = str(pick('kunde', 'customer') or '').strip()
    if not cur or not kunde:
        return None
    return {
        'customer_name_raw':   kunde,
        'customer_name_clean': kunde,
        'customer_nr':         None,
        'invoice_date':        _to_iso_date(pick('datum', 'date')),
        'invoice_number':      str(pick('rechnungsnummer', 'invoice number', 'invoice', 'belegnr') or '').strip(),
        'art_nr':              '',
        'total_amount':        round(_to_num(pick('provisionsbasis', 'commission basis', 'basis', 'umsatz', 'nettoumsatz')), 2),
        'provision_rate':      round(_to_num(pick(
            'provision %', 'provision%', 'commission %', 'commission%',
            'provisionssatz', 'provisionsprozent', 'provsatz', 'satz', 'rate', 'commissionrate')), 4),
        'provision_amount':    round(_to_num(pick('provision', 'commission', 'provisionsbetrag')), 2),
        'currency':            cur,
        'supplier_code':       (str(pick('lieferant', 'supplier') or '').strip().upper() or None),
    }


def _parse_json_content(content: bytes) -> list[dict]:
    import json
    obj = json.loads(content.decode('utf-8-sig', errors='replace'))
    if isinstance(obj, dict):
        # erstes Listen-Feld nehmen (z. B. {"rows":[...]}), sonst als Einzelobjekt
        lst = next((v for v in obj.values() if isinstance(v, list)), None)
        obj = lst if lst is not None else [obj]
    out = []
    for item in obj if isinstance(obj, list) else []:
        if isinstance(item, dict):
            n = _normalize_row(item)
            if n:
                out.append(n)
    return out


def _looks_like_xrechnung(content: bytes) -> bool:
    head = content[:4000].lower()
    return (b'crossindustryinvoice' in head
            or b'oasis:names:specification:ubl' in head)


def _parse_xml_content(content: bytes) -> list[dict]:
    """Tabellarisches XML (gleiche Spalten wie CSV). Sucht sich wiederholende
    Zeilen-Elemente und liest deren Kind-Elemente/Attribute als Spalten."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(content)

    def local(tag: str) -> str:
        return tag.split('}')[-1].strip().lower()

    def rowdict(el) -> dict:
        d = {}
        for child in el:
            kids = list(child)
            if kids:
                for cc in kids:
                    if (cc.text or '').strip():
                        d[local(cc.tag)] = cc.text.strip()
            elif (child.text or '').strip():
                d[local(child.tag)] = child.text.strip()
        for k, v in el.attrib.items():
            d[local(k)] = v
        return d

    best: list[dict] = []
    for parent in root.iter():
        kids = [k for k in parent if list(k)]
        if kids:
            norm = [x for x in (_normalize_row(rowdict(k)) for k in kids) if x]
            if len(norm) > len(best):
                best = norm
    if not best:  # flache Struktur: direkte Kinder als Zeilen
        norm = [x for x in (_normalize_row(rowdict(k)) for k in root) if x]
        best = norm
    return best


def parse_import_content(content: bytes, ext: str) -> list[dict]:
    """Dispatcher: CSV / Excel / JSON / XML → Liste von Standard-Einträgen."""
    ext = (ext or '').lower().lstrip('.')
    if ext in ('xlsx', 'xls'):
        return _parse_excel_content(content)
    if ext == 'json':
        return _parse_json_content(content)
    if ext == 'xml':
        return _parse_xml_content(content)
    return _parse_csv_content(content)


def import_records_for_supplier(records: list[dict], supplier, db: Session) -> dict:
    """Erzeugt/aktualisiert Transaktionen aus Standard-Einträgen.
    Der Lieferant kommt aus der 'Lieferant'-Spalte je Zeile, sonst aus `supplier`.
    Kundenzuordnung über Name (exakt, sonst erster Namensteil). provision_rate = netto."""
    customers = db.query(models.Customer).all()
    by_name = {}
    for c in customers:
        if c.name:
            by_name.setdefault(c.name.strip().lower(), c)
    suppliers_by_code = {s.code.upper(): s for s in db.query(models.Supplier).all()}

    new = updated = unchanged = skipped = unmatched = 0
    for e in records:
        cur = (e.get('currency') or '').strip()
        iso = (e.get('invoice_date') or '').strip()
        if not cur or not iso:
            skipped += 1
            continue
        try:
            d = date.fromisoformat(iso[:10])
        except ValueError:
            skipped += 1
            continue

        # Lieferant je Zeile (Spalte 'Lieferant') hat Vorrang, sonst Standard
        sup = supplier
        row_code = (e.get('supplier_code') or '').strip().upper()
        if row_code:
            sup = suppliers_by_code.get(row_code)
            if sup is None:
                skipped += 1
                continue

        name = (e.get('customer_name_clean') or '').strip()
        cust = by_name.get(name.lower())
        if not cust and name:
            fw = name.split()[0].lower()
            cust = next((c for c in customers if c.name and fw in c.name.lower()), None)
        if not cust:
            unmatched += 1

        inv_nr = (e.get('invoice_number') or '').strip()[:10]
        new_total = round(float(e.get('total_amount') or 0), 2)
        new_rate = round(float(e.get('provision_rate') or 0), 4)

        # Bestehende Rechnung über (Lieferant + Rechnungsnummer) finden
        existing = None
        if inv_nr:
            existing = (
                db.query(models.Transaction)
                .filter_by(supplier_id=sup.id, invoice_number=inv_nr)
                .first()
            )

        # Schon vorhanden UND unverändert (Betrag + Provisionssatz gleich) → überspringen
        if existing is not None and \
           round(float(existing.total_amount or 0), 2) == new_total and \
           round(float(existing.provision_rate or 0), 4) == new_rate:
            unchanged += 1
            continue

        fields = dict(
            supplier_id=sup.id,
            customer_id=cust.id if cust else None,
            year=d.year,
            invoice_number=inv_nr,
            invoice_date=d,
            provision_rate=new_rate,
            currency=cur,
            total_amount=new_total,
            exchange_rate=1,
            notes=None if cust else (f"Kunde nicht zugeordnet: {name}"[:200] or None),
        )
        if existing is not None:
            # Betrag/Provision hat sich geändert → bestehende Rechnung überschreiben
            for k, v in fields.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(models.Transaction(**fields))
            new += 1

    db.commit()
    return {"new": new, "updated": updated, "unchanged": unchanged,
            "skipped": skipped, "unmatched": unmatched,
            "imported": new + updated}


@router.post("/{code}/transactions/parse-csv")
async def parse_csv(
    code: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Import transactions from a CSV or Excel file (Provisionsabrechnung format)."""
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    check_supplier_access(current_user, db, supplier.id)

    content = await file.read()
    fname = (file.filename or "").lower()

    try:
        if fname.endswith('.xlsx') or fname.endswith('.xls'):
            entries = _parse_excel_content(content)
        else:
            entries = _parse_csv_content(content)
    except Exception as e:
        raise HTTPException(400, f"Datei konnte nicht gelesen werden: {e}")

    if not entries:
        raise HTTPException(400, "Keine Einträge in der Datei gefunden")

    return _match_customers(entries, db)
