import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .routers import suppliers, customers, commission, sync, stats, mandants
from .routers import auth as auth_router
from .routers.sync import run_customer_sync, test_mandant
from .auth import get_current_user
from .database import engine
from . import models

logger = logging.getLogger(__name__)


async def _scheduled_sync():
    """Run customer sync every hour; skip silently if credentials missing."""
    while True:
        await asyncio.sleep(3600)  # wait 1 hour before first run, then repeat
        try:
            result = await run_customer_sync()
            logger.info("Reybex auto-sync: %s", result)
        except Exception as e:
            logger.warning("Reybex auto-sync skipped: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_scheduled_sync())
    yield

# Create any missing tables (e.g. users) without touching existing ones
models.Base.metadata.create_all(bind=engine)

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


@app.get("/health")
def health():
    return {"status": "ok"}


# Public test endpoint — no JWT needed, only server-side Reybex credentials
app.add_api_route("/sync/reybex/test-mandant", test_mandant, methods=["GET"], tags=["sync"])


# Temporary public Reybex invoice probe — no JWT
@app.get("/debug/reybex-probe")
async def reybex_probe():
    import os, httpx
    username = os.environ.get("REYBEX_USERNAME", "")
    password = os.environ.get("REYBEX_PASSWORD", "")
    base = "https://core-backend.reybex.com/api"
    paths = [
        "domains/finHead", "domains/fin-head", "domains/invoice",
        "domains/order", "domains/salesOrder", "domains/voucher",
        "domains/document", "domains/booking", "domains/delivery",
        "domains/shipment", "domains/article", "domains/product",
        "finHead", "invoices", "orders", "vouchers",
        "domains/finHead/list", "domains/invoice/list",
    ]
    results = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for p in paths:
            try:
                r = await client.get(
                    f"{base}/{p}",
                    params={"take": 1, "responseFormat": "api"},
                    auth=(username, password),
                )
                results[p] = r.status_code
            except Exception as e:
                results[p] = str(e)
    return results


@app.get("/debug/reybex-finhead")
async def reybex_finhead(mandant_id: str | None = None):
    """Read finHead records — try multiple parameter combinations."""
    import os, httpx
    from fastapi.responses import PlainTextResponse
    username = os.environ.get("REYBEX_USERNAME", "")
    password = os.environ.get("REYBEX_PASSWORD", "")
    base = "https://core-backend.reybex.com/api"
    lines = []
    combos = [
        {"take": 3, "responseFormat": "api"},
        {"take": 3},
        {"limit": 3},
        {"take": 3, "skip": 0, "responseFormat": "api"},
        {"take": 3, "responseFormat": "api", "mandantId": mandant_id or "19584"},
        {"take": 3, "responseFormat": "api", "mandant": mandant_id or "19584"},
    ]
    async with httpx.AsyncClient(timeout=15) as client:
        for p in combos:
            r = await client.get(f"{base}/finHead", params=p, auth=(username, password))
            body = r.text[:800] if r.text else "(empty)"
            lines.append(f"params={p}\nstatus={r.status_code} ct={r.headers.get('content-type','?')}\nbody={body}\n---")
    return PlainTextResponse("\n".join(lines))


# Temporary public debug endpoint — no JWT
@app.post("/debug/pdf-words")
async def debug_pdf_words(file: __import__("fastapi").UploadFile = __import__("fastapi").File(...)):
    from io import BytesIO
    pdf_bytes = await file.read()
    out: dict = {}
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        out["fitz_pages"] = len(doc)
        if len(doc) > 0:
            p = doc[0]
            out["fitz_text"] = p.get_text()[:3000]
            words = p.get_text("words")
            out["fitz_words"] = [
                {"x": round(w[0], 1), "y": round(w[1], 1), "text": w[4]}
                for w in words[:100]
            ]
    except Exception as e:
        out["fitz_error"] = str(e)
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            out["plumber_text"] = (pdf.pages[0].extract_text() or "")[:500] if pdf.pages else ""
            words = pdf.pages[0].extract_words()[:30] if pdf.pages else []
            out["plumber_words"] = [{"x": round(w["x0"], 1), "y": round(w["top"], 1), "text": w["text"]} for w in words]
    except Exception as e:
        out["plumber_error"] = str(e)
    return out
