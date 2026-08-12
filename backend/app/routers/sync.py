"""WinAgent DBF-/E-Rechnungs-Import (+ Reybex-Verbindungstest)."""
import os
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
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


@router.post("/dbf/import")
async def import_dbf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import transactions from an *_INV.DBF file."""
    if not file.filename or not file.filename.upper().endswith(".DBF"):
        raise HTTPException(400, "Bitte eine .DBF Datei hochladen")
    data = await file.read()
    result = import_dbf_bytes(data, db)
    result["filename"] = file.filename
    return result


def import_dbf_bytes(data: bytes, db: Session) -> dict:
    """Import transactions from *_INV.DBF bytes. Netto-Provision, Lieferant via F_CODE."""
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

    imported = skipped = unchanged = 0
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

        # Bestehende Rechnung (supplier + invoice_number + date)

        # Netto-Provision = PROVISION - PROV2..PROV6 (Sub-Vertreter-Anteile).
        # Die Anteile werden zusaetzlich in provision_splits abgelegt.
        def _n(key: str) -> float:
            try:
                return float(r.get(key) or 0)
            except (TypeError, ValueError):
                return 0.0

        gross_rate = _n("PROVISION")
        splits = []
        for i in range(2, 7):
            sub_rate = _n(f"PROV{i}")
            if sub_rate:
                rep = (r.get(f"REP{i}") or "").strip()
                splits.append({"rate": round(sub_rate, 2), "rep_code": rep or None})
        net_rate = round(gross_rate - sum(s["rate"] for s in splits), 2)

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
            provision_rate=net_rate,
            provision_splits=splits or None,
            price=r.get("PREIS"),
            currency=(r.get("WAEHRUNG") or "").strip() or None,
            total_amount=r.get("TOTAL_S") or 0,
            exchange_rate=r.get("KURS") or 1,
            customer_order_no=(r.get("CUST_ORDNO") or "").strip() or None,
            notes=None,
        )

        outcome = models.upsert_transaction(
            db,
            {"supplier_id": supplier.id, "invoice_number": inv_nr, "invoice_date": inv_date},
            fields,
        )
        if outcome == "unchanged":
            unchanged += 1
        else:
            imported += 1

    db.commit()
    return {
        "imported": imported,
        "unchanged": unchanged,
        "skipped": skipped,
        "errors": errors[:20],
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
    return import_einvoice_bytes(data, db, supplier_code, provision_rate)


def import_einvoice_bytes(
    data: bytes, db: Session,
    supplier_code: str | None = None, provision_rate: float | None = None,
) -> dict:
    """Import a single XRechnung XML (UBL or CII) from bytes as transaction(s)."""
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

    imported = unchanged = 0
    if inv.lines:
        for line in inv.lines:
            inv_nr = f"{inv.invoice_number}"[:10]
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
            outcome = models.upsert_transaction(
                db, {"supplier_id": supplier.id, "invoice_number": inv_nr, "invoice_date": inv.invoice_date}, fields)
            if outcome == "unchanged":
                unchanged += 1
            else:
                imported += 1
    else:
        # No line items — create single summary transaction
        inv_nr = inv.invoice_number[:10]
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
        outcome = models.upsert_transaction(
            db, {"supplier_id": supplier.id, "invoice_number": inv_nr, "invoice_date": inv.invoice_date}, fields)
        if outcome == "unchanged":
            unchanged += 1
        else:
            imported += 1

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
