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
from ..einvoice_parser import parse_einvoice

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


@router.post("/einvoice/import")
async def import_einvoice(
    file: UploadFile = File(...),
    supplier_code: str | None = None,
    provision_rate: float | None = None,
    db: Session = Depends(get_db),
):
    """Import a single XRechnung XML (UBL or CII) as a transaction."""
    data = await file.read()
    try:
        inv = parse_einvoice(data)
    except Exception as e:
        raise HTTPException(400, f"XML konnte nicht gelesen werden: {e}")

    # Resolve supplier — by explicit code or by matching seller name
    supplier = None
    if supplier_code:
        supplier = db.query(models.Supplier).filter_by(code=supplier_code.upper()).first()
    if not supplier and inv.seller_name:
        name_lower = inv.seller_name.lower()
        for s in db.query(models.Supplier).filter_by(is_active=True).all():
            if name_lower in s.name.lower() or s.name.lower() in name_lower:
                supplier = s
                break
    if not supplier:
        raise HTTPException(422, f"Lieferant nicht gefunden. Verkäufer laut Rechnung: '{inv.seller_name}'. Bitte supplier_code angeben.")

    # Resolve customer — by number or name
    customer = None
    if inv.buyer_customer_no:
        customer = db.query(models.Customer).filter(
            models.Customer.ku_nr == inv.buyer_customer_no
        ).first() or db.query(models.Customer).filter(
            models.Customer.code == inv.buyer_customer_no.upper()
        ).first()
    if not customer and inv.buyer_name:
        name_lower = inv.buyer_name.lower()
        for c in db.query(models.Customer).all():
            if c.name and name_lower in c.name.lower():
                customer = c
                break

    if not inv.invoice_date:
        raise HTTPException(422, "Rechnungsdatum konnte nicht gelesen werden.")

    prov_rate = provision_rate

    imported = 0
    if inv.lines:
        for line in inv.lines:
            inv_nr = f"{inv.invoice_number}"[:10]
            existing = db.query(models.Transaction).filter_by(
                supplier_id=supplier.id, invoice_number=inv_nr, invoice_date=inv.invoice_date
            ).first()
            fields = dict(
                supplier_id=supplier.id,
                customer_id=customer.id if customer else None,
                year=inv.invoice_date.year,
                invoice_number=inv_nr,
                invoice_date=inv.invoice_date,
                art_nr=(line.art_nr or "")[:20] or None,
                quantity=line.quantity,
                unit=(line.unit or "")[:2] or None,
                provision_rate=prov_rate,
                price=line.unit_price,
                currency=inv.currency,
                total_amount=line.line_total,
                exchange_rate=1,
                notes=line.description[:200] if line.description else None,
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                db.add(models.Transaction(**fields))
            imported += 1
    else:
        # No line items — create single summary transaction
        inv_nr = inv.invoice_number[:10]
        existing = db.query(models.Transaction).filter_by(
            supplier_id=supplier.id, invoice_number=inv_nr, invoice_date=inv.invoice_date
        ).first()
        fields = dict(
            supplier_id=supplier.id,
            customer_id=customer.id if customer else None,
            year=inv.invoice_date.year,
            invoice_number=inv_nr,
            invoice_date=inv.invoice_date,
            provision_rate=prov_rate,
            currency=inv.currency,
            total_amount=inv.net_total,
            exchange_rate=1,
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(models.Transaction(**fields))
        imported = 1

    db.commit()
    return {
        "ok": True,
        "format": inv.raw_format,
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "seller": inv.seller_name,
        "buyer": inv.buyer_name,
        "supplier_matched": supplier.name,
        "customer_matched": customer.name if customer else None,
        "lines_imported": imported,
        "net_total": float(inv.net_total),
        "currency": inv.currency,
    }



async def test_price_endpoints():
    """One-time test: which Reybex price/article endpoints are accessible with current credentials."""
    username, password = _reybex_creds()
    auth = (username, password)
    results = {}
    paths = [
        # Artikel-Varianten
        "/domains/article",
        "/domains/articles",
        "/domains/item",
        "/domains/items",
        "/domains/product",
        "/domains/products",
        "/domains/catalogue",
        "/domains/catalog",
        "/domains/stockItem",
        "/domains/stock",
        "/domains/goods",
        # Preis-Varianten
        "/domains/price",
        "/domains/prices",
        "/domains/priceList",
        "/domains/pricelist",
        "/domains/salesPrice",
        "/domains/salesprice",
        "/domains/scalePrice",
        "/domains/scaleprice",
        "/domains/purchasePrice",
        "/domains/supplierPrice",
        "/domains/buyPrice",
        "/domains/articlePrice",
        "/domains/itemPrice",
        "/domains/tierPrice",
        "/domains/graduatedPrice",
    ]
    async with httpx.AsyncClient(timeout=20) as client:
        for path in paths:
            try:
                r = await client.get(
                    f"{REYBEX_BASE}{path}",
                    params={"take": 2, "skip": 0, "responseFormat": "api"},
                    auth=auth,
                )
                if r.status_code == 200:
                    try:
                        data = r.json()
                        keys = list(data[0].keys()) if isinstance(data, list) and data else (list(data.keys()) if isinstance(data, dict) else [])
                        results[path] = {"status": 200, "count": len(data) if isinstance(data, list) else 1, "fields": keys}
                    except Exception:
                        results[path] = {"status": 200, "raw": r.text[:300]}
                else:
                    try:
                        body = r.json()
                    except Exception:
                        body = r.text[:100]
                    results[path] = {"status": r.status_code, "body": body}
            except Exception as e:
                results[path] = {"status": "error", "error": str(e)}
    return results


async def test_mandant(mandant_id: str | None = None):
    """Reybex connection test — checks credentials and returns customer count."""
    username, password = _reybex_creds()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{REYBEX_BASE}/domains/customer",
            params={"take": 1, "skip": 0, "responseFormat": "api", "contactType.type": 1},
            auth=(username, password),
        )
    if r.status_code == 200:
        return {"ok": True, "note": "Reybex-Verbindung OK. Rechnungen bitte als DBF aus Reybex exportieren und über 'Reybex Sync' hochladen."}
    return {"ok": False, "status": r.status_code, "error": r.text[:200]}
