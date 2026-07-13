"""App-wide settings: bank accounts per currency, AMV logo."""
import base64
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])

_BANK_KEY = "bank_accounts"
_LOGO_KEY = "amv_logo_b64"


def _get(db: Session, key: str) -> Any | None:
    row = db.get(models.AppSetting, key)
    return row.value if row else None


def _set(db: Session, key: str, value: Any):
    row = db.get(models.AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(models.AppSetting(key=key, value=value))
    db.commit()


# ── Bank accounts ──────────────────────────────────────────────────────────

@router.get("/bank-accounts")
def get_bank_accounts(db: Session = Depends(get_db)):
    """Returns dict keyed by currency: {EUR: {bank, iban, bic}, ...}"""
    data = _get(db, _BANK_KEY)
    return data or {}


@router.put("/bank-accounts")
def save_bank_accounts(payload: dict, db: Session = Depends(get_db)):
    """Save bank account dict keyed by currency."""
    _set(db, _BANK_KEY, payload)
    return {"ok": True}


# ── AMV Logo ───────────────────────────────────────────────────────────────

@router.get("/logo")
def get_logo(db: Session = Depends(get_db)):
    """Returns {data_url: 'data:image/png;base64,...'} or {data_url: null}."""
    b64 = _get(db, _LOGO_KEY)
    if not b64:
        return {"data_url": None}
    return {"data_url": f"data:image/png;base64,{b64}"}


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload PNG/JPG logo; stored as base64."""
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg"):
        raise HTTPException(400, "Nur PNG oder JPEG erlaubt")
    content = await file.read()
    if len(content) > 500_000:
        raise HTTPException(400, "Logo zu groß (max. 500 KB)")
    b64 = base64.b64encode(content).decode()
    _set(db, _LOGO_KEY, b64)
    return {"ok": True, "size": len(content)}


@router.delete("/logo")
def delete_logo(db: Session = Depends(get_db)):
    row = db.get(models.AppSetting, _LOGO_KEY)
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}
