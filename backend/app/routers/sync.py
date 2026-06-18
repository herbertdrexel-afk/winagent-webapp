"""Reybex → WinAgent sync endpoints."""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/sync", tags=["sync"])

REYBEX_BASE = "https://core-backend.reybex.com/api"


def _reybex_creds():
    username = os.environ.get("REYBEX_USERNAME")
    password = os.environ.get("REYBEX_PASSWORD")
    if not username or not password:
        raise HTTPException(503, "REYBEX_USERNAME / REYBEX_PASSWORD nicht konfiguriert")
    return username, password


async def _fetch_all(path: str, params: dict, auth: tuple) -> list:
    """Fetch all pages from a Reybex list endpoint."""
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


@router.post("/reybex/customers")
async def sync_customers(db: Session = Depends(get_db)):
    """Fetch all customers (contactType.type=1) from Reybex and upsert into WinAgent."""
    username, password = _reybex_creds()
    auth = (username, password)

    rows = await _fetch_all(
        "/domains/customer",
        {"sort": "id", "contactType.type": 1},
        auth,
    )

    created = updated = skipped = 0

    for r in rows:
        customer_no = r.get("customerNo") or r.get("uniqueName", "")[:6]
        if not customer_no:
            skipped += 1
            continue

        # code: max 6 chars, unique key for upsert
        code = str(customer_no).strip()[:6]
        name = (r.get("name") or "").strip()[:50]
        if not name:
            skipped += 1
            continue

        country_code = None
        if r.get("country") and r["country"].get("code"):
            country_code = r["country"]["code"][:3]

        existing = db.query(models.Customer).filter(models.Customer.code == code).first()
        if existing:
            existing.name = name
            existing.ku_nr = str(customer_no)[:4]
            existing.zip = (r.get("zipcode") or "")[:8] or None
            existing.city = (r.get("city") or "")[:50] or None
            existing.country_code = country_code
            existing.phone = (r.get("phone") or "")[:20] or None
            existing.fax = (r.get("fax") or "")[:20] or None
            existing.email = (r.get("email") or "")[:40] or None
            existing.url = (r.get("web") or "")[:40] or None
            existing.tax_number = (r.get("taxNumber") or "")[:20] or None
            existing.address_lines = _build_address(r)
            updated += 1
        else:
            db.add(models.Customer(
                code=code,
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
                address_lines=_build_address(r),
            ))
            created += 1

    db.commit()
    return {"ok": True, "total": len(rows), "created": created, "updated": updated, "skipped": skipped}


@router.post("/reybex/suppliers")
async def sync_suppliers(db: Session = Depends(get_db)):
    """Fetch contacts with contactType.name='Lieferant' from Reybex and upsert into WinAgent."""
    username, password = _reybex_creds()
    auth = (username, password)

    # First page only to discover available contactTypes
    async with httpx.AsyncClient(timeout=60) as client:
        probe = await client.get(
            f"{REYBEX_BASE}/domains/customer",
            params={"sort": "id", "take": 50, "skip": 0, "responseFormat": "api"},
            auth=auth,
        )
    if probe.status_code != 200:
        raise HTTPException(502, f"Reybex Fehler {probe.status_code}: {probe.text[:300]}")

    probe_data = probe.json()
    found_types = list({
        r["contactType"]["name"]
        for r in probe_data
        if isinstance(r.get("contactType"), dict) and r["contactType"].get("name")
    })

    # Filter by contactType.name containing 'lieferant'
    all_rows = await _fetch_all("/domains/customer", {"sort": "id"}, auth)
    rows = [
        r for r in all_rows
        if isinstance(r.get("contactType"), dict)
        and "lieferant" in (r["contactType"].get("name") or "").lower()
    ]

    if not rows:
        return {
            "ok": True, "total": 0,
            "message": f"Keine Kontakte mit contactType 'Lieferant' gefunden. Gefundene Typen: {found_types}. Gesamt Kontakte: {len(all_rows)}",
        }

    created = updated = skipped = 0

    for r in rows:
        name = (r.get("name") or "").strip()[:60]
        if not name:
            skipped += 1
            continue

        # Generate 2-char code from name initials or customerNo
        customer_no = r.get("customerNo") or ""
        code = _make_supplier_code(name, customer_no, db)
        if not code:
            skipped += 1
            continue

        existing = db.query(models.Supplier).filter(models.Supplier.code == code).first()
        if existing:
            existing.name = name
            existing.address = _street_line(r)
            updated += 1
        else:
            db.add(models.Supplier(
                code=code,
                name=name,
                address=_street_line(r),
                is_active=True,
            ))
            created += 1

    db.commit()
    return {"ok": True, "total": len(rows), "created": created, "updated": updated, "skipped": skipped}


def _build_address(r: dict) -> list:
    parts = []
    if r.get("street"):
        parts.append(r["street"])
    city_line = " ".join(filter(None, [r.get("zipcode"), r.get("city")]))
    if city_line:
        parts.append(city_line)
    if r.get("country") and r["country"].get("name"):
        parts.append(r["country"]["name"])
    return parts or None


def _street_line(r: dict) -> str | None:
    return r.get("street") or None


def _make_supplier_code(name: str, customer_no: str, db: Session) -> str | None:
    """Try to derive a unique 2-char supplier code."""
    # Try initials from name words
    words = name.upper().split()
    candidates = []
    if len(words) >= 2:
        candidates.append(words[0][0] + words[1][0])
    if words:
        candidates.append(words[0][:2])
    if customer_no:
        candidates.append(str(customer_no)[:2].upper())

    for c in candidates:
        c = c[:2].upper()
        if not db.query(models.Supplier).filter(models.Supplier.code == c).first():
            return c
    return None
