import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..pdf_import_parser import parse_pdf_auto, extract_commission_schedule_company

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
def list_suppliers(db: Session = Depends(get_db)):
    return db.query(models.Supplier).order_by(models.Supplier.name).all()


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
def get_supplier(code: str, db: Session = Depends(get_db)):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    return supplier


@router.patch("/{code}", response_model=schemas.SupplierOut)
def update_supplier(code: str, payload: schemas.SupplierUpdate, db: Session = Depends(get_db)):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
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
):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    from sqlalchemy import extract
    year = int(payload.invoice_date.split("-")[0]) if isinstance(payload.invoice_date, str) else payload.invoice_date.year
    tx = models.Transaction(**{**payload.model_dump(), "supplier_id": supplier.id, "year": year})
    db.add(tx)
    db.commit()
    db.refresh(tx)
    db.refresh(tx, ["customer"])
    return _tx_to_out(tx)


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(404, "Position nicht gefunden")
    db.delete(tx)
    db.commit()


@router.patch("/transactions/{transaction_id}", response_model=schemas.TransactionOut)
def update_transaction(
    transaction_id: int,
    payload: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
):
    tx = db.query(models.Transaction).options(
        joinedload(models.Transaction.customer)
    ).filter(models.Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(404, "Transaktion nicht gefunden")
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
):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
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


@router.post("/{code}/transactions/parse-pdf")
async def parse_pdf(
    code: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")

    pdf_bytes = await file.read()

    # Validate Commission-Schedule company matches selected supplier
    pdf_company = extract_commission_schedule_company(pdf_bytes)
    if pdf_company:
        c_pdf = re.sub(r'\s+', '', pdf_company.lower())
        c_sup = re.sub(r'\s+', '', supplier.name.lower())
        prefix = min(6, len(c_pdf), len(c_sup))
        if c_pdf[:prefix] not in c_sup and c_sup[:prefix] not in c_pdf:
            raise HTTPException(
                422,
                f"Dieses PDF gehört zu '{pdf_company}' – bitte den richtigen Lieferanten auswählen."
            )

    try:
        entries = parse_pdf_auto(pdf_bytes)
    except Exception as e:
        raise HTTPException(400, f"PDF konnte nicht gelesen werden: {e}")

    # For each unique customer find DB matches (by ku_nr first, then by name)
    name_cache: dict[str, list] = {}
    for entry in entries:
        clean = entry["customer_name_clean"]
        if clean in name_cache:
            continue
        if not clean:
            name_cache[clean] = []
            continue

        ku_nr = entry.get("customer_nr", "")
        customers = []
        if ku_nr:
            customers = (
                db.query(models.Customer)
                .filter(models.Customer.ku_nr == ku_nr)
                .limit(5)
                .all()
            )
        if not customers:
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

    result = []
    for entry in entries:
        result.append({**entry, "customer_suggestions": name_cache[entry["customer_name_clean"]]})
    return result


@router.post("/{code}/transactions/parse-pdf-debug")
async def parse_pdf_debug(code: str, file: UploadFile = File(...)):
    """Debug: return raw text + word positions extracted by PyMuPDF and pdfplumber."""
    from io import BytesIO
    pdf_bytes = await file.read()
    out: dict = {}

    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        out["fitz_page_count"] = len(doc)
        if len(doc) > 0:
            p = doc[0]
            out["fitz_text_p1"] = p.get_text()[:3000]
            words = p.get_text("words")
            out["fitz_words_p1"] = [
                {"x": round(w[0], 1), "y": round(w[1], 1), "text": w[4]}
                for w in words[:80]
            ]
    except Exception as e:
        out["fitz_error"] = str(e)

    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            if pdf.pages:
                out["plumber_text_p1"] = (pdf.pages[0].extract_text() or "")[:1000]
                words = pdf.pages[0].extract_words()
                out["plumber_words_p1"] = [
                    {"x": round(w["x0"], 1), "y": round(w["top"], 1), "text": w["text"]}
                    for w in words[:40]
                ]
    except Exception as e:
        out["plumber_error"] = str(e)

    return out
