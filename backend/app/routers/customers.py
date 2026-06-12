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
    limit: int = Query(200, le=1000),
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
