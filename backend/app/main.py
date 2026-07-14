import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .routers import suppliers, customers, commission, sync, stats, mandants
from .routers import auth as auth_router, reports as reports_router, settings as settings_router
from .routers.sync import run_customer_sync, test_mandant
from .auth import get_current_user
from .database import engine, SessionLocal
from . import models

logger = logging.getLogger(__name__)


async def _scheduled_sync():
    """Run customer sync every hour; skip silently if credentials missing."""
    while True:
        await asyncio.sleep(3600)
        try:
            result = await run_customer_sync()
            logger.info("Reybex auto-sync: %s", result)
        except Exception as e:
            logger.warning("Reybex auto-sync skipped: %s", e)


async def _report_scheduler():
    """Hourly check: send report schedules whose day_of_week + send_hour matches now."""
    import datetime
    from .report_generator import generate_report_pdf, period_dates
    from .email_sender import send_report_email

    while True:
        await asyncio.sleep(3600)
        try:
            now = datetime.datetime.now()
            today = now.date()
            db = SessionLocal()
            try:
                schedules = db.query(models.ReportSchedule).filter(
                    models.ReportSchedule.enabled == True
                ).all()
                for s in schedules:
                    # Check weekday and hour
                    if s.day_of_week != now.weekday():
                        continue
                    if s.send_hour != now.hour:
                        continue
                    # Skip if already sent today
                    if s.last_sent_at and s.last_sent_at.date() >= today:
                        continue

                    recipients = [
                        r for r in db.query(models.ReportRecipient)
                        .filter_by(schedule_id=s.id).all()
                        if r.user and r.user.email
                    ]
                    if not recipients:
                        continue

                    date_from, date_to = period_dates(s.report_period)
                    period_label = (
                        f"{date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}"
                    )
                    subject = f"WinAgent Bericht – {period_label}"
                    filename = f"winagent_bericht_{date_from.isoformat()}_{date_to.isoformat()}.pdf"

                    pdf = generate_report_pdf(
                        db,
                        date_from=date_from,
                        date_to=date_to,
                        supplier_codes=s.supplier_codes,
                        report_types=s.report_types,
                    )
                    addresses = [r.user.email for r in recipients]
                    send_report_email(addresses, subject, pdf, period_label, filename)

                    s.last_sent_at = datetime.datetime.now(datetime.timezone.utc)
                    db.commit()
                    logger.info("Report '%s' sent to %s", s.name, addresses)
            except Exception as e:
                logger.warning("Report scheduler error: %s", e)
            finally:
                db.close()
        except Exception as e:
            logger.warning("Report scheduler outer error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_scheduled_sync())
    asyncio.create_task(_report_scheduler())
    yield

# Create any missing tables without touching existing ones
models.Base.metadata.create_all(bind=engine)

# Add columns that may not exist in older DB versions
from sqlalchemy import text as _sql
with engine.connect() as _conn:
    _conn.execute(_sql("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(120)"))
    _conn.execute(_sql("ALTER TABLE report_schedules ADD COLUMN IF NOT EXISTS report_types JSONB"))
    _conn.execute(_sql("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS invoice_language VARCHAR(5) DEFAULT 'de+en'"))
    _conn.execute(_sql("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS address2 VARCHAR(100)"))
    _conn.execute(_sql("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS zip VARCHAR(20)"))
    _conn.execute(_sql("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS city VARCHAR(60)"))
    _conn.execute(_sql("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS country VARCHAR(60)"))
    _conn.execute(_sql("ALTER TABLE commission_invoices ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'offen'"))
    _conn.commit()

app = FastAPI(
    lifespan=lifespan,
    title="WinAgent Webapp API",
    description="Neuentwicklung des Lieferanten-/Provisionsabrechnungssystems "
                 "(ehemals Delphi/dBase) als Web-API.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes (login + register)
app.include_router(auth_router.router)

# Protected routes — require valid JWT
_auth = {"dependencies": [Depends(get_current_user)]}
app.include_router(suppliers.router, **_auth)
app.include_router(customers.router, **_auth)
app.include_router(commission.router, **_auth)
app.include_router(sync.router, **_auth)
app.include_router(stats.router, **_auth)
app.include_router(mandants.router, **_auth)
app.include_router(reports_router.router, **_auth)
app.include_router(settings_router.router, **_auth)


@app.get("/health")
def health():
    return {"status": "ok"}


# Public test endpoint — no JWT needed, only server-side Reybex credentials
app.add_api_route("/sync/reybex/test-mandant", test_mandant, methods=["GET"], tags=["sync"])
