from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[schemas.CustomerOut])
def list_customers(
    q: str | None = Query(None, description="Suche in Name/Code"),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(models.Customer)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Customer.name.ilike(like)) | (models.Customer.code.ilike(like))
        )
    return query.order_by(models.Customer.name).limit(limit).all()


@router.get("/{code}", response_model=schemas.CustomerOut)
def get_customer(code: str, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.code == code.upper()).first()
    if not customer:
        raise HTTPException(404, "Kunde nicht gefunden")
    return customer
