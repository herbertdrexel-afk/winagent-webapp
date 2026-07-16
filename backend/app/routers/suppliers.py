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
        waehrung = (row.get('Währung') or row.get('Waehrung') or '').strip()
        kunde    = (row.get('Kunde') or '').strip()
        datum    = (row.get('Datum') or '').strip()
        re_nr    = str(row.get('Rechnungsnummer') or '').strip()
        basis    = _parse_num_de(row.get('Provisionsbasis') or 0)
        rate     = _parse_num_de(row.get('Provision %') or row.get('Provision%') or 0)
        prov     = _parse_num_de(row.get('Provision') or 0)
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

    i_cur = _idx('währung', 'waehrung', 'currency')
    i_knd = _idx('kunde', 'customer')
    i_dat = _idx('datum', 'date')
    i_rnr = _idx('rechnungsnummer', 'invoice')
    i_bas = _idx('provisionsbasis', 'basis')
    i_rat = _idx('provision %', 'provision%', '% provision')
    i_prv = _idx('provision')

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
