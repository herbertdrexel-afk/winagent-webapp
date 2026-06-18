from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from .. import models

router = APIRouter(prefix="/mandants", tags=["mandants"])


class MandantCreate(BaseModel):
    name: str
    mandant_id: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    supplier_ids: list[int] = []


class MandantUpdate(BaseModel):
    name: Optional[str] = None
    mandant_id: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    supplier_ids: Optional[list[int]] = None


class SupplierShort(BaseModel):
    id: int
    code: str
    name: str

    class Config:
        from_attributes = True


class MandantOut(BaseModel):
    id: int
    name: str
    mandant_id: Optional[str]
    is_active: bool
    notes: Optional[str]
    suppliers: list[SupplierShort] = []

    class Config:
        from_attributes = True


def _to_out(m: models.ReybexMandant) -> MandantOut:
    return MandantOut(
        id=m.id,
        name=m.name,
        mandant_id=m.mandant_id,
        is_active=m.is_active,
        notes=m.notes,
        suppliers=[SupplierShort(id=lnk.supplier.id, code=lnk.supplier.code, name=lnk.supplier.name)
                   for lnk in m.supplier_links],
    )


@router.get("", response_model=list[MandantOut])
def list_mandants(db: Session = Depends(get_db)):
    mandants = db.query(models.ReybexMandant).order_by(models.ReybexMandant.name).all()
    return [_to_out(m) for m in mandants]


@router.post("", response_model=MandantOut, status_code=201)
def create_mandant(body: MandantCreate, db: Session = Depends(get_db)):
    m = models.ReybexMandant(
        name=body.name,
        mandant_id=body.mandant_id,
        is_active=body.is_active,
        notes=body.notes,
    )
    db.add(m)
    db.flush()
    _set_links(m, body.supplier_ids, db)
    db.commit()
    db.refresh(m)
    return _to_out(m)


@router.patch("/{mandant_id}", response_model=MandantOut)
def update_mandant(mandant_id: int, body: MandantUpdate, db: Session = Depends(get_db)):
    m = db.query(models.ReybexMandant).filter_by(id=mandant_id).first()
    if not m:
        raise HTTPException(404, "Mandant nicht gefunden")
    if body.name is not None:
        m.name = body.name
    if body.mandant_id is not None:
        m.mandant_id = body.mandant_id
    if body.is_active is not None:
        m.is_active = body.is_active
    if body.notes is not None:
        m.notes = body.notes
    if body.supplier_ids is not None:
        _set_links(m, body.supplier_ids, db)
    db.commit()
    db.refresh(m)
    return _to_out(m)


@router.delete("/{mandant_id}", status_code=204)
def delete_mandant(mandant_id: int, db: Session = Depends(get_db)):
    m = db.query(models.ReybexMandant).filter_by(id=mandant_id).first()
    if not m:
        raise HTTPException(404, "Mandant nicht gefunden")
    db.delete(m)
    db.commit()


def _set_links(m: models.ReybexMandant, supplier_ids: list[int], db: Session):
    # Remove existing links
    for lnk in list(m.supplier_links):
        db.delete(lnk)
    db.flush()
    # Add new links
    for sid in supplier_ids:
        supplier = db.query(models.Supplier).filter_by(id=sid).first()
        if supplier:
            db.add(models.MandantSupplier(mandant_id_fk=m.id, supplier_id=sid))
