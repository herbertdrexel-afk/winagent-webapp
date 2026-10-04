"""Wechselkurse: Monats-Durchschnittskurse ansehen und aus dem Netz aktualisieren."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..exchange_rates import refresh_rates, derive_used_rates

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])


@router.get("")
def list_rates(
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alle hinterlegten Monats-Durchschnittskurse (neueste zuerst)."""
    rows = (
        db.query(models.ExchangeRate)
        .order_by(models.ExchangeRate.valid_date.desc(), models.ExchangeRate.currency)
        .all()
    )
    return [
        {"currency": r.currency, "month": r.valid_date.isoformat() if r.valid_date else None,
         "rate": float(r.rate) if r.rate is not None else None}
        for r in rows
    ]


@router.post("/refresh")
def refresh(
    _: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Durchschnittskurse (ECB) für alle Fremdwährungen der Transaktionen holen
    und in die exchange_rates-Tabelle schreiben."""
    return refresh_rates(db)


@router.post("/derive")
def derive(
    before_year: int = Query(2026, description="nur Monate vor diesem Jahr"),
    invert: bool = Query(False, description="KURS ist Einheiten je EUR → invertieren"),
    apply: bool = Query(False, description="False = nur Vorschau, True = schreiben"),
    _: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Verwendete Kurse aus den Altdaten (Feld exchange_rate) je Monat ableiten.
    apply=false liefert eine Vorschau, apply=true schreibt sie in die Tabelle."""
    return derive_used_rates(db, before_year=before_year, invert=invert, apply=apply)
