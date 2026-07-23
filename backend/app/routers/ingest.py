"""HTTP-Ingest: externe Systeme (z. B. Reybex-Wochenexport) pushen Import-Dateien
per HTTP-POST an /ingest/file. Authentifizierung über ein statisches Token
(Umgebungsvariable INGEST_TOKEN) – kein JWT-Login nötig.

Token kann geliefert werden als:
  - Header  X-Ingest-Token: <token>
  - Header  Authorization: Bearer <token>
  - HTTP-Basic (beliebiger Benutzer, Passwort = Token)
  - Query   ?token=<token>   (Fallback, wenn nur eine URL konfigurierbar ist)

DBF (*_INV.DBF) und E-Rechnung (XML) werden automatisch importiert
(Lieferant steckt in den Daten). CSV/Excel benötigen ?supplier=CODE.
"""
import os
import base64
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import require_admin
from .sync import import_dbf_bytes, import_einvoice_bytes

router = APIRouter(prefix="/ingest", tags=["ingest"])


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


@router.post("/file")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    supplier: str | None = Query(None, description="Lieferanten-Code für CSV/Excel"),
    source: str = Query("http"),
    token: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Nimmt genau eine Datei entgegen und importiert sie je nach Typ."""
    _check_token(request, token)

    fname = (file.filename or "upload").strip()
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    data = await file.read()

    log = models.IngestLog(filename=fname[:200], source=(source or "http")[:60],
                           file_type=ext[:10], status="ok", imported=0, skipped=0)
    try:
        if ext == "dbf":
            res = import_dbf_bytes(data, db)
            log.imported = res.get("imported", 0)
            log.skipped = res.get("skipped", 0)
            errs = res.get("errors", [])
            log.detail = ("; ".join(errs))[:2000] if errs else None
        elif ext == "xml":
            res = import_einvoice_bytes(data, db, supplier_code=supplier)
            log.imported = res.get("lines_imported", 0)
            log.detail = f"{res.get('invoice_number')} · {res.get('supplier_matched')}"
        elif ext in ("csv", "xlsx", "xls"):
            # CSV/Excel brauchen Lieferant + Kundenzuordnung → vorerst als 'staged'
            log.status = "staged"
            log.detail = (
                f"CSV/Excel empfangen ({len(data)} Bytes) für Lieferant '{supplier}'. "
                "Automatischer Import wird ergänzt, sobald das Reybex-Exportformat vorliegt."
                if supplier else
                "CSV/Excel empfangen, aber ?supplier=CODE fehlt. Bitte im Webapp importieren "
                "oder Lieferant-Code mitgeben."
            )
        else:
            log.status = "error"
            log.detail = f"Dateityp '.{ext}' wird nicht unterstützt (erlaubt: dbf, xml, csv, xlsx)."
    except HTTPException as e:
        db.rollback()
        log.status = "error"
        log.detail = str(e.detail)[:2000]
    except Exception as e:  # pragma: no cover
        db.rollback()
        log.status = "error"
        log.detail = str(e)[:2000]

    db.add(log)
    db.commit()
    db.refresh(log)
    return {
        "id": log.id, "filename": log.filename, "type": log.file_type,
        "status": log.status, "imported": log.imported, "skipped": log.skipped,
        "detail": log.detail,
    }


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
