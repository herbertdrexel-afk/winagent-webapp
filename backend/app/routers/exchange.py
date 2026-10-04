"""Wechselkurse: Monats-Durchschnittskurse ansehen und aus dem Netz aktualisieren."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user, require_admin
from ..database import get_db
from ..exchange_rates import refresh_rates

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
    """Durchschnittskurse (ECB) ab dem Cutover-Jahr für alle Fremdwährungen der
    Transaktionen holen und in die exchange_rates-Tabelle schreiben.
    Rechnungen vor dem Cutover nutzen weiterhin ihren eigenen KURS."""
    return refresh_rates(db)
