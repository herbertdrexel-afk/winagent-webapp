"""HTTP-Ingest: externe Systeme (z. B. Reybex-Wochenexport) pushen Import-Dateien
per HTTP-POST. Authentifizierung über ein statisches Token (INGEST_TOKEN).

Zwei Wege:
  - POST /ingest/{supplier_code}/file  → "Bereich pro Lieferant". Datei (CSV/XML/JSON/
    Excel, gleiche Spaltenstruktur wie die CSV-Vorlage) wird für DIESEN Lieferanten importiert.
    Reybex konfiguriert je Lieferant ein eigenes Ziel: /ingest/AM/file, /ingest/GW/file, …
  - POST /ingest/file  → selbstbeschreibende Dateien ohne Lieferant-Angabe
    (DBF via F_CODE, E-Rechnung via Verkäufername).

Token: Header X-Ingest-Token, Authorization: Bearer, HTTP-Basic (Passwort=Token) oder ?token=.
"""
import os
import re
import base64
import httpx
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import require_admin
from .sync import import_dbf_bytes, import_einvoice_bytes
from .suppliers import (
    parse_import_content, import_records_for_supplier, _looks_like_xrechnung,
)

FEEDS_KEY = "reybex_feeds"

router = APIRouter(prefix="/ingest", tags=["ingest"])

TABULAR = ("csv", "json", "xml", "xlsx", "xls")


def _check_token(request: Request, token_q: str | None) -> None:
    expected = os.environ.get("INGEST_TOKEN")
    if not expected:
        raise HTTPException(503, "Ingest ist nicht konfiguriert (INGEST_TOKEN fehlt).")

    supplied = request.headers.get("x-ingest-token")
    if not supplied:
        auth = request.headers.get("authorization", "")
        low = auth.lower()
        if low.startswith("bearer "):
            supplied = auth[7:].strip()
        elif low.startswith("basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8", "replace")
                supplied = decoded.split(":", 1)[1] if ":" in decoded else decoded
            except Exception:
                supplied = None
    if not supplied:
        supplied = token_q
    if not supplied or supplied != expected:
        raise HTTPException(401, "Ungültiges oder fehlendes Ingest-Token.")


def _ext(fname: str) -> str:
    return fname.rsplit(".", 1)[-1].lower() if "." in fname else ""


def _log(db, fname, source, ext, status="ok", imported=0, skipped=0, detail=None):
    row = models.IngestLog(filename=fname[:200], source=(source or "http")[:60],
                           file_type=ext[:10], status=status,
                           imported=imported, skipped=skipped,
                           detail=(detail[:2000] if detail else None))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{supplier_code}/file")
async def ingest_for_supplier(
    supplier_code: str,
    request: Request,
    file: UploadFile = File(...),
    source: str = Query("reybex"),
    token: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Import einer Datei für EINEN Lieferanten (Bereich pro Lieferant)."""
    _check_token(request, token)

    supplier = db.query(models.Supplier).filter(
        models.Supplier.code == supplier_code.upper()
    ).first()
    if not supplier:
        raise HTTPException(404, f"Lieferant '{supplier_code}' nicht gefunden.")

    fname = (file.filename or "upload").strip()
    ext = _ext(fname)
    data = await file.read()

    try:
        if ext == "dbf":
            res = import_dbf_bytes(data, db)  # F_CODE-basiert
            row = _log(db, fname, source, ext, "ok",
                       res.get("imported", 0), res.get("skipped", 0),
                       "; ".join(res.get("errors", [])) or None)
        elif ext == "xml" and _looks_like_xrechnung(data):
            res = import_einvoice_bytes(data, db, supplier_code=supplier.code)
            row = _log(db, fname, source, ext, "ok", res.get("lines_imported", 0), 0,
                       f"E-Rechnung {res.get('invoice_number')}")
        elif ext in TABULAR:
            records = parse_import_content(data, ext)
            if not records:
                row = _log(db, fname, source, ext, "error", detail="Keine gültigen Zeilen erkannt.")
            else:
                res = import_records_for_supplier(records, supplier, db)
                detail = f"{res['new']} neu, {res['updated']} aktualisiert, {res['unchanged']} unverändert"
                if res["unmatched"]:
                    detail += f", {res['unmatched']} ohne Kunde"
                row = _log(db, fname, source, ext, "ok",
                           res["imported"], res["skipped"], detail)
        else:
            row = _log(db, fname, source, ext, "error",
                       detail=f"Dateityp '.{ext}' wird nicht unterstützt (csv, xml, json, xlsx, dbf).")
    except HTTPException as e:
        db.rollback()
        row = _log(db, fname, source, ext, "error", detail=str(e.detail))
    except Exception as e:  # pragma: no cover
        db.rollback()
        row = _log(db, fname, source, ext, "error", detail=str(e))

    return {"id": row.id, "supplier": supplier.code, "filename": row.filename,
            "type": row.file_type, "status": row.status,
            "imported": row.imported, "skipped": row.skipped, "detail": row.detail}


@router.post("/file")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    token: str | None = Query(None),
    source: str = Query("http"),
    db: Session = Depends(get_db),
):
    """Selbstbeschreibende Datei ohne Lieferant-Angabe (DBF via F_CODE, E-Rechnung)."""
    _check_token(request, token)
    fname = (file.filename or "upload").strip()
    ext = _ext(fname)
    data = await file.read()
    try:
        if ext == "dbf":
            res = import_dbf_bytes(data, db)
            row = _log(db, fname, source, ext, "ok",
                       res.get("imported", 0), res.get("skipped", 0),
                       "; ".join(res.get("errors", [])) or None)
        elif ext == "xml":
            res = import_einvoice_bytes(data, db)
            row = _log(db, fname, source, ext, "ok", res.get("lines_imported", 0), 0,
                       f"E-Rechnung {res.get('invoice_number')}")
        else:
            row = _log(db, fname, source, ext, "error",
                       detail=f"Ohne Lieferant nur DBF/E-Rechnung. Für CSV/XML/JSON bitte "
                              f"/ingest/<LIEFERANT>/file verwenden.")
    except HTTPException as e:
        db.rollback()
        row = _log(db, fname, source, ext, "error", detail=str(e.detail))
    except Exception as e:  # pragma: no cover
        db.rollback()
        row = _log(db, fname, source, ext, "error", detail=str(e))
    return {"id": row.id, "filename": row.filename, "type": row.file_type,
            "status": row.status, "imported": row.imported, "skipped": row.skipped,
            "detail": row.detail}


# ── Reybex-Abhol-Feeds (Pull): pro Lieferant eine dataExportFeed-URL ──────────

def _load_feeds(db: Session) -> dict:
    row = db.get(models.AppSetting, FEEDS_KEY)
    return dict(row.value) if row and isinstance(row.value, dict) else {}


def _save_feeds(db: Session, feeds: dict) -> None:
    row = db.get(models.AppSetting, FEEDS_KEY)
    if row:
        row.value = feeds
    else:
        db.add(models.AppSetting(key=FEEDS_KEY, value=feeds))
    db.commit()


def _mask_url(u: str) -> str:
    return re.sub(r'(feedToken=)([^&]+)',
                  lambda m: m.group(1) + m.group(2)[:4] + '…' + m.group(2)[-2:], u or "")


def pull_feed(supplier, url: str, db: Session, source: str = "reybex-feed") -> dict:
    """Ruft eine Feed-URL ab und importiert die Zeilen für den Lieferanten."""
    name = f"feed:{supplier.code}"
    try:
        with httpx.Client(timeout=45, follow_redirects=True) as client:
            r = client.get(url)
        r.raise_for_status()
    except Exception as e:
        _log(db, name, source, "csv", "error", detail=f"Abruf fehlgeschlagen: {e}")
        return {"status": "error", "detail": str(e)}

    content = r.content
    ct = (r.headers.get("content-type") or "").lower()
    ext = "json" if "json" in ct else "xml" if "xml" in ct else "csv"
    try:
        records = parse_import_content(content, ext)
    except Exception as e:
        _log(db, name, source, ext, "error", detail=f"Parsen fehlgeschlagen: {e}")
        return {"status": "error", "detail": str(e)}
    if not records:
        _log(db, name, source, ext, "error", detail="Keine gültigen Zeilen im Feed.")
        return {"status": "error", "detail": "leer"}

    res = import_records_for_supplier(records, supplier, db)
    detail = f"{res['new']} neu, {res['updated']} aktualisiert, {res['unchanged']} unverändert"
    if res["unmatched"]:
        detail += f", {res['unmatched']} ohne Kunde"
    _log(db, name, source, ext, "ok", res["imported"], res["skipped"], detail)
    return {"status": "ok", **res}


def pull_all_feeds(db: Session, source: str = "reybex-feed") -> dict:
    feeds = _load_feeds(db)
    out = {}
    for code, url in feeds.items():
        supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
        if supplier:
            out[code] = pull_feed(supplier, url, db, source)
    return out


class FeedsBody(BaseModel):
    feeds: dict[str, str]


@router.get("/feeds")
def list_feeds(_: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    return {code: {"url": _mask_url(u)} for code, u in _load_feeds(db).items()}


@router.put("/feeds")
def set_feeds(body: FeedsBody, _: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    incoming = {c.upper(): u.strip() for c, u in body.feeds.items()}
    codes = set(incoming)
    found = {s.code for s in db.query(models.Supplier).filter(models.Supplier.code.in_(codes)).all()}
    missing = codes - found
    if missing:
        raise HTTPException(400, f"Unbekannte Lieferanten: {', '.join(sorted(missing))}")
    # Merge: gesetzte URLs übernehmen, leere entfernen, übrige behalten
    feeds = _load_feeds(db)
    for code, url in incoming.items():
        if url:
            feeds[code] = url
        else:
            feeds.pop(code, None)
    _save_feeds(db, feeds)
    return {"ok": True, "count": len(feeds)}


@router.post("/feeds/{supplier_code}/pull")
def pull_feed_now(supplier_code: str, _: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    supplier = db.query(models.Supplier).filter(models.Supplier.code == supplier_code.upper()).first()
    if not supplier:
        raise HTTPException(404, f"Lieferant '{supplier_code}' nicht gefunden.")
    url = _load_feeds(db).get(supplier_code.upper())
    if not url:
        raise HTTPException(404, f"Kein Feed für '{supplier_code}' konfiguriert.")
    return pull_feed(supplier, url, db, source="reybex-feed-manual")


@router.post("/feeds/pull-all")
def pull_feeds_now(_: models.User = Depends(require_admin), db: Session = Depends(get_db)):
    return pull_all_feeds(db, source="reybex-feed-manual")


@router.get("/log")
def ingest_log(
    _: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Letzte 100 Ingest-Vorgänge (nur Admin)."""
    rows = (
        db.query(models.IngestLog)
        .order_by(models.IngestLog.id.desc())
        .limit(100)
        .all()
    )
    return [{
        "id": r.id, "filename": r.filename, "source": r.source, "file_type": r.file_type,
        "status": r.status, "imported": r.imported, "skipped": r.skipped,
        "detail": r.detail,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]
