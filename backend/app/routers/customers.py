from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/customers", tags=["customers"])


def _next_ku_nr(db: Session) -> str:
    """Nächste freie KU_NR: MAX(numerische ku_nr) + 1."""
    result = db.execute(
        text("SELECT MAX(ku_nr::int) FROM customers WHERE ku_nr ~ '^[0-9]+$'")
    ).scalar()
    return str((result or 5531) + 1)


@router.get("", response_model=list[schemas.CustomerOut])
def list_customers(
    q: str | None = Query(None, description="Suche in Name/Code"),
    limit: int = Query(200, le=100000),
    db: Session = Depends(get_db),
):
    query = db.query(models.Customer)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Customer.name.ilike(like))
            | (models.Customer.code.ilike(like))
            | (models.Customer.city.ilike(like))
            | (models.Customer.ku_nr.ilike(like))
        )
    return query.order_by(models.Customer.name).limit(limit).all()


@router.post("", response_model=schemas.CustomerOut, status_code=201)
def create_customer(payload: schemas.CustomerCreate, db: Session = Depends(get_db)):
    code = payload.code.upper().strip()
    if len(code) < 4:
        raise HTTPException(422, "Code muss mindestens 4 Zeichen haben")
    if db.query(models.Customer).filter(models.Customer.code == code).first():
        raise HTTPException(409, f"Code '{code}' ist bereits vergeben")
    ku_nr = _next_ku_nr(db)
    customer = models.Customer(**{**payload.model_dump(), "code": code, "ku_nr": ku_nr})
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{code}", response_model=schemas.CustomerOut)
def get_customer(code: str, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.code == code.upper()).first()
    if not customer:
        raise HTTPException(404, "Kunde nicht gefunden")
    return customer


@router.patch("/{code}", response_model=schemas.CustomerOut)
def update_customer(code: str, payload: schemas.CustomerUpdate, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.code == code.upper()).first()
    if not customer:
        raise HTTPException(404, "Kunde nicht gefunden")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{code}", status_code=204)
def delete_customer(code: str, db: Session = Depends(get_db)):
    """Kunde löschen. Nicht möglich, solange noch Umsätze/Rechnungen oder andere
    Datensätze auf ihn verweisen."""
    customer = db.query(models.Customer).filter(models.Customer.code == code.upper()).first()
    if not customer:
        raise HTTPException(404, "Kunde nicht gefunden")
    LIMIT = 10
    refs: list[str] = []

    txs = (
        db.query(models.Transaction, models.Supplier.code)
        .join(models.Supplier, models.Transaction.supplier_id == models.Supplier.id)
        .filter(models.Transaction.customer_id == customer.id)
        .order_by(models.Transaction.invoice_date.desc())
        .all()
    )
    for t, sup_code in txs:
        d = t.invoice_date.strftime("%d.%m.%Y") if t.invoice_date else "?"
        amt = f"{float(t.total_amount or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        refs.append(
            f"Rechnung {t.invoice_number} · Lieferant {sup_code} · {d} · {amt} {t.currency or ''}".strip()
        )

    buds = (
        db.query(models.Budget, models.Supplier.code)
        .join(models.Supplier, models.Budget.supplier_id == models.Supplier.id)
        .filter(models.Budget.customer_id == customer.id).all()
    )
    for b, sup_code in buds:
        refs.append(f"Budget {b.year} · Lieferant {sup_code}")

    items = (
        db.query(models.CommissionStatementItem, models.CommissionStatement)
        .join(models.CommissionStatement,
              models.CommissionStatementItem.statement_id == models.CommissionStatement.id)
        .filter(models.CommissionStatementItem.customer_id == customer.id).all()
    )
    for it, st in items:
        per = f"{st.period_from.strftime('%d.%m.%Y')}–{st.period_to.strftime('%d.%m.%Y')}" if st.period_from and st.period_to else ""
        refs.append(f"Provisionsabrechnung #{st.id} {per}".strip())

    if refs:
        shown = "; ".join(refs[:LIMIT])
        more = f" … und {len(refs) - LIMIT} weitere" if len(refs) > LIMIT else ""
        raise HTTPException(
            409,
            f"Kunde kann nicht gelöscht werden – noch verwendet in {len(refs)} Datensatz/Datensätzen: "
            f"{shown}{more}. Bitte diese Datensätze entfernen oder einem anderen Kunden zuordnen.",
        )
    db.delete(customer)
    db.commit()
