"""Report-Schedule CRUD + manual send."""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RecipientOut(BaseModel):
    id: int
    user_id: int
    username: str
    email: str | None = None

    class Config:
        from_attributes = True


VALID_PERIODS = {
    "last_week", "last_month", "current_month", "current_year",
    "last_year", "last_30_days", "last_90_days", "last_quarter",
}

VALID_REPORT_TYPES = {
    "supplier_summary", "customer_provision", "customer_turnover",
    "supplier_detail", "transactions",
}


class ScheduleOut(BaseModel):
    id: int
    name: str
    enabled: bool
    day_of_week: int
    send_hour: int
    report_period: str
    supplier_codes: list[str] | None = None
    report_types: list[str] | None = None
    last_sent_at: str | None = None
    recipients: list[RecipientOut] = []

    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    name: str
    enabled: bool = True
    day_of_week: int = 0
    send_hour: int = 7
    report_period: str = "last_week"
    supplier_codes: list[str] | None = None
    report_types: list[str] | None = None   # None = all types
    recipient_user_ids: list[int] = []


class ScheduleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    day_of_week: int | None = None
    send_hour: int | None = None
    report_period: str | None = None
    supplier_codes: list[str] | None = None
    report_types: list[str] | None = None
    recipient_user_ids: list[int] | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_schedule(schedule_id: int, db: Session) -> models.ReportSchedule:
    s = (
        db.query(models.ReportSchedule)
        .options(joinedload(models.ReportSchedule.recipients)
                 .joinedload(models.ReportRecipient.user))
        .filter(models.ReportSchedule.id == schedule_id)
        .first()
    )
    if not s:
        raise HTTPException(404, "Report-Zeitplan nicht gefunden")
    return s


def _to_out(s: models.ReportSchedule) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "enabled": s.enabled,
        "day_of_week": s.day_of_week,
        "send_hour": s.send_hour,
        "report_period": s.report_period,
        "supplier_codes": s.supplier_codes,
        "report_types": s.report_types,
        "last_sent_at": s.last_sent_at.isoformat() if s.last_sent_at else None,
        "recipients": [
            {"id": r.id, "user_id": r.user_id,
             "username": r.user.username, "email": r.user.email}
            for r in s.recipients
        ],
    }


def _set_recipients(schedule: models.ReportSchedule, user_ids: list[int], db: Session):
    # Remove old
    db.query(models.ReportRecipient).filter_by(schedule_id=schedule.id).delete()
    # Add new
    for uid in user_ids:
        if not db.get(models.User, uid):
            raise HTTPException(400, f"Benutzer {uid} nicht gefunden")
        db.add(models.ReportRecipient(schedule_id=schedule.id, user_id=uid))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/schedules")
def list_schedules(db: Session = Depends(get_db)):
    schedules = (
        db.query(models.ReportSchedule)
        .options(joinedload(models.ReportSchedule.recipients)
                 .joinedload(models.ReportRecipient.user))
        .order_by(models.ReportSchedule.name)
        .all()
    )
    return [_to_out(s) for s in schedules]


@router.post("/schedules", status_code=201)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    if not (0 <= payload.day_of_week <= 6):
        raise HTTPException(400, "day_of_week muss 0-6 sein")
    if not (0 <= payload.send_hour <= 23):
        raise HTTPException(400, "send_hour muss 0-23 sein")
    if payload.report_period not in VALID_PERIODS:
        raise HTTPException(400, f"Ungültiger report_period: {payload.report_period}")
    if payload.report_types:
        invalid = set(payload.report_types) - VALID_REPORT_TYPES
        if invalid:
            raise HTTPException(400, f"Ungültige report_types: {invalid}")

    schedule = models.ReportSchedule(
        name=payload.name,
        enabled=payload.enabled,
        day_of_week=payload.day_of_week,
        send_hour=payload.send_hour,
        report_period=payload.report_period,
        supplier_codes=payload.supplier_codes,
        report_types=payload.report_types or None,
    )
    db.add(schedule)
    db.flush()
    _set_recipients(schedule, payload.recipient_user_ids, db)
    db.commit()
    db.refresh(schedule)
    return _to_out(_load_schedule(schedule.id, db))


@router.patch("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    schedule = _load_schedule(schedule_id, db)
    if payload.name is not None:
        schedule.name = payload.name
    if payload.enabled is not None:
        schedule.enabled = payload.enabled
    if payload.day_of_week is not None:
        if not (0 <= payload.day_of_week <= 6):
            raise HTTPException(400, "day_of_week muss 0-6 sein")
        schedule.day_of_week = payload.day_of_week
    if payload.send_hour is not None:
        if not (0 <= payload.send_hour <= 23):
            raise HTTPException(400, "send_hour muss 0-23 sein")
        schedule.send_hour = payload.send_hour
    if payload.report_period is not None:
        if payload.report_period not in VALID_PERIODS:
            raise HTTPException(400, f"Ungültiger report_period: {payload.report_period}")
        schedule.report_period = payload.report_period
    if payload.supplier_codes is not None:
        schedule.supplier_codes = payload.supplier_codes or None
    if payload.report_types is not None:
        invalid = set(payload.report_types) - VALID_REPORT_TYPES
        if invalid:
            raise HTTPException(400, f"Ungültige report_types: {invalid}")
        schedule.report_types = payload.report_types or None
    if payload.recipient_user_ids is not None:
        _set_recipients(schedule, payload.recipient_user_ids, db)
    db.commit()
    return _to_out(_load_schedule(schedule_id, db))


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    schedule = db.get(models.ReportSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Report-Zeitplan nicht gefunden")
    db.delete(schedule)
    db.commit()


@router.post("/schedules/{schedule_id}/send-now")
def send_now(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    """Manually trigger sending a report schedule immediately."""
    import traceback
    from ..report_generator import generate_report_pdf, period_dates
    from ..email_sender import send_report_email

    schedule = _load_schedule(schedule_id, db)

    recipients = [r for r in schedule.recipients if r.user and r.user.email]
    if not recipients:
        raise HTTPException(400, "Keine Empfänger mit E-Mail-Adresse konfiguriert")

    date_from, date_to = period_dates(schedule.report_period)
    period_label = f"{date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}"
    subject  = f"WinAgent Bericht – {period_label}"
    filename = f"winagent_bericht_{date_from.isoformat()}_{date_to.isoformat()}.pdf"
    addresses = [r.user.email for r in recipients]

    try:
        pdf = generate_report_pdf(
            db,
            date_from=date_from,
            date_to=date_to,
            supplier_codes=schedule.supplier_codes,
            report_types=schedule.report_types,
        )
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("PDF generation failed: %s\n%s", e, tb)
        raise HTTPException(500, f"PDF-Generierung fehlgeschlagen: {e}")

    try:
        send_report_email(addresses, subject, pdf, period_label, filename)
    except Exception as e:
        logger.error("Email send failed: %s", e)
        raise HTTPException(500, f"E-Mail-Versand fehlgeschlagen: {e}")

    from datetime import datetime, timezone
    schedule.last_sent_at = datetime.now(timezone.utc)
    db.commit()

    return {"sent_to": addresses, "period": period_label}
