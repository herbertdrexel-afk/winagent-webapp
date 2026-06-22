"""Reybex → WinAgent customer sync."""
import os
import logging
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db, SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])
REYBEX_BASE = "https://core-backend.reybex.com/api"


def _reybex_creds() -> tuple[str, str]:
    username = os.environ.get("REYBEX_USERNAME")
    password = os.environ.get("REYBEX_PASSWORD")
    if not username or not password:
        raise HTTPException(503, "REYBEX_USERNAME / REYBEX_PASSWORD nicht konfiguriert")
    return username, password


async def _fetch_all(path: str, params: dict, auth: tuple) -> list:
    PAGE = 100
    results = []
    skip = 0
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            p = {**params, "take": PAGE, "skip": skip, "responseFormat": "api"}
            r = await client.get(f"{REYBEX_BASE}{path}", params=p, auth=auth)
            if r.status_code != 200:
                raise HTTPException(502, f"Reybex Fehler {r.status_code}: {r.text[:200]}")
            batch = r.json()
            if not isinstance(batch, list) or len(batch) == 0:
                break
            results.extend(batch)
            if len(batch) < PAGE:
                break
            skip += PAGE
    return results


def _upsert_customers(rows: list, db: Session) -> dict:
    created = updated = skipped = 0
    for r in rows:
        customer_no = r.get("customerNo") or r.get("uniqueName", "")[:6]
        if not customer_no:
            skipped += 1
            continue
        code = str(customer_no).strip()[:6]
        name = (r.get("name") or "").strip()[:50]
        if not name:
            skipped += 1
            continue

        country_code = None
        if r.get("country") and r["country"].get("code"):
            country_code = r["country"]["code"][:3]

        parts = []
        if r.get("street"):
            parts.append(r["street"])
        city_line = " ".join(filter(None, [r.get("zipcode"), r.get("city")]))
        if city_line:
            parts.append(city_line)
        if r.get("country") and r["country"].get("name"):
            parts.append(r["country"]["name"])
        address_lines = parts or None

        fields = dict(
            ku_nr=str(customer_no)[:4],
            name=name,
            zip=(r.get("zipcode") or "")[:8] or None,
            city=(r.get("city") or "")[:50] or None,
            country_code=country_code,
            phone=(r.get("phone") or "")[:20] or None,
            fax=(r.get("fax") or "")[:20] or None,
            email=(r.get("email") or "")[:40] or None,
            url=(r.get("web") or "")[:40] or None,
            tax_number=(r.get("taxNumber") or "")[:20] or None,
            address_lines=address_lines,
        )
        existing = db.query(models.Customer).filter(models.Customer.code == code).first()
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(models.Customer(code=code, **fields))
            created += 1

    db.commit()
    return {"total": len(rows), "created": created, "updated": updated, "skipped": skipped}


async def run_customer_sync() -> dict:
    """Core sync logic — callable from scheduler and HTTP endpoint."""
    username = os.environ.get("REYBEX_USERNAME")
    password = os.environ.get("REYBEX_PASSWORD")
    if not username or not password:
        raise RuntimeError("REYBEX_USERNAME / REYBEX_PASSWORD nicht konfiguriert")

    rows = await _fetch_all(
        "/domains/customer",
        {"sort": "id", "contactType.type": 1},
        (username, password),
    )

    db: Session = SessionLocal()
    try:
        result = _upsert_customers(rows, db)

        # Save last sync timestamp
        setting = db.get(models.AppSetting, "reybex_last_customer_sync")
        now_iso = datetime.now(timezone.utc).isoformat()
        if setting:
            setting.value = {"last_sync": now_iso, **result}
        else:
            db.add(models.AppSetting(
                key="reybex_last_customer_sync",
                value={"last_sync": now_iso, **result},
            ))
        db.commit()
        return result
    finally:
        db.close()


@router.post("/reybex/customers")
async def sync_customers_endpoint():
    """Manual trigger: sync customers from Reybex."""
    _reybex_creds()  # validate creds first
    result = await run_customer_sync()
    return {"ok": True, **result}


@router.get("/reybex/status")
def sync_status(db: Session = Depends(get_db)):
    """Return last sync timestamp and result."""
    setting = db.get(models.AppSetting, "reybex_last_customer_sync")
    if not setting:
        return {"last_sync": None}
    return setting.value


async def test_mandant(mandant_id: str | None = None):
    """Probe Reybex API for available invoice-related domains."""
    username, password = _reybex_creds()
    # Try plural domain names + alternative base paths
    domain_candidates = [
        "salesInvoices", "invoices", "orders", "salesOrders", "purchaseInvoices",
        "documents", "vouchers", "billings", "sales", "deliveryNotes", "creditNotes",
        "outgoingInvoices", "incomingInvoices", "commissions",
    ]
    alt_paths = [
        "/erp/invoice", "/erp/order", "/erp/salesInvoice",
        "/accounting/invoice", "/sales/invoice", "/sales/order",
    ]
    results = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for domain in domain_candidates:
            params = {"take": 1, "skip": 0, "responseFormat": "api"}
            r = await client.get(f"{REYBEX_BASE}/domains/{domain}", params=params, auth=(username, password))
            results[f"domains/{domain}"] = {"status": r.status_code} if r.status_code != 200 else {
                "ok": True,
                "fields": list(r.json()[0].keys()) if isinstance(r.json(), list) and r.json() else [],
            }
        for path in alt_paths:
            r = await client.get(f"{REYBEX_BASE}{path}", params={"take": 1, "responseFormat": "api"}, auth=(username, password))
            results[path] = {"status": r.status_code} if r.status_code != 200 else {"ok": True}
    return {k: v for k, v in results.items() if v.get("ok") or v.get("status") != 400}
