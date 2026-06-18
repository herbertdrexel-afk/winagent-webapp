import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .routers import suppliers, customers, commission, sync
from .routers import auth as auth_router
from .routers.sync import run_customer_sync
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


@app.get("/health")
def health():
    return {"status": "ok"}
