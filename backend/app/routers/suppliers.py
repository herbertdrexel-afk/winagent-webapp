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


@router.get("/{code}", response_model=schemas.SupplierOut)
def get_supplier(code: str, db: Session = Depends(get_db)):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    return supplier


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
