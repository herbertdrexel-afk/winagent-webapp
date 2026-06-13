from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
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
