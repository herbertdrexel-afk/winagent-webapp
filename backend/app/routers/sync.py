"""Reybex → WinAgent customer sync + DBF invoice import."""
import os
import logging
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db, SessionLocal
from ..dbf_reader import read_dbf

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


@router.post("/dbf/import")
async def import_dbf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import transactions from an *_INV.DBF file."""
    if not file.filename or not file.filename.upper().endswith(".DBF"):
        raise HTTPException(400, "Bitte eine .DBF Datei hochladen")

    data = await file.read()
    try:
        rows = read_dbf(data)
    except Exception as e:
        raise HTTPException(400, f"DBF konnte nicht gelesen werden: {e}")

    if not rows:
        return {"imported": 0, "skipped": 0, "errors": []}

    # Build lookup caches
    suppliers = {s.code.strip().upper(): s for s in db.query(models.Supplier).all()}
    customers_by_ku = {
        (str(c.ku_nr).strip() if c.ku_nr else None): c
        for c in db.query(models.Customer).all()
        if c.ku_nr
    }
    customers_by_code = {
        (c.code.strip().upper() if c.code else None): c
        for c in db.query(models.Customer).all()
        if c.code
    }

    imported = skipped = 0
    errors: list[str] = []

    for r in rows:
        inv_nr = (r.get("NUMMER") or "").strip()
        if not inv_nr:
            skipped += 1
            continue

        f_code = (r.get("F_CODE") or "").strip().upper()
        supplier = suppliers.get(f_code)
        if not supplier:
            errors.append(f"Lieferant '{f_code}' nicht gefunden (Rg {inv_nr})")
            skipped += 1
            continue

        inv_date = r.get("DATUM")
        if not inv_date:
            skipped += 1
            continue

        # Resolve customer
        ku_nr = (r.get("KU_NR") or "").strip()
        code = (r.get("CODE") or "").strip().upper()
        customer = customers_by_ku.get(ku_nr) or customers_by_code.get(code)

        # Check for existing transaction (upsert by supplier + invoice_number + date)
        existing = (
            db.query(models.Transaction)
            .filter_by(supplier_id=supplier.id, invoice_number=inv_nr, invoice_date=inv_date)
            .first()
        )

        fields = dict(
            supplier_id=supplier.id,
            customer_id=customer.id if customer else None,
            year=inv_date.year,
            invoice_number=inv_nr,
            invoice_date=inv_date,
            art_nr=(r.get("ART_NR") or "").strip() or None,
            color=(r.get("FARBE") or "").strip() or None,
            quantity=r.get("MENGE"),
            unit=(r.get("ME_MENGE") or "").strip() or None,
            discount=r.get("RABATT"),
            provision_rate=r.get("PROVISION"),
            price=r.get("PREIS"),
            currency=(r.get("WAEHRUNG") or "").strip() or None,
            total_amount=r.get("TOTAL_S") or 0,
            exchange_rate=r.get("KURS") or 1,
            customer_order_no=(r.get("CUST_ORDNO") or "").strip() or None,
            notes=None,
        )

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(models.Transaction(**fields))
        imported += 1

    db.commit()
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:20],
        "filename": file.filename,
    }


async def test_mandant(mandant_id: str | None = None):
    """Probe Reybex finance document endpoints — try with and without /domains/."""
    username, password = _reybex_creds()
    results = {}
    names = ["finHead", "finHeads", "finPos", "finPositions", "finance",
             "finDocument", "finDocuments", "finInvoice", "finInvoices"]
    async with httpx.AsyncClient(timeout=45) as client:
        for name in names:
            params = {"take": 2, "skip": 0, "responseFormat": "api"}
            if mandant_id:
                params["mandantId"] = mandant_id
            # Try with /domains/ prefix
            r = await client.get(f"{REYBEX_BASE}/domains/{name}", params=params, auth=(username, password))
            if r.status_code == 200:
                data = r.json()
                results[f"domains/{name}"] = {"ok": True, "count": len(data) if isinstance(data, list) else "?",
                    "fields": list(data[0].keys()) if isinstance(data, list) and data else []}
            # Try directly without /domains/
            r2 = await client.get(f"{REYBEX_BASE}/{name}", params=params, auth=(username, password))
            if r2.status_code == 200:
                data2 = r2.json()
                results[name] = {"ok": True, "count": len(data2) if isinstance(data2, list) else "?",
                    "fields": list(data2[0].keys()) if isinstance(data2, list) and data2 else []}
            elif r2.status_code not in (400, 404):
                results[name] = {"status": r2.status_code, "body": r2.text[:100]}
    return results if results else {"note": "Alle Versuche schlugen fehl (400/404)"}
