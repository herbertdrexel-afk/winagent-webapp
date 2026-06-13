import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .routers import suppliers, customers, commission
from .routers import auth as auth_router
from .auth import get_current_user
from .database import engine
from . import models

# Create any missing tables (e.g. users) without touching existing ones
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="WinAgent Webapp API",
    description="Neuentwicklung des Lieferanten-/Provisionsabrechnungssystems "
                 "(ehemals Delphi/dBase) als Web-API.",
    version="0.1.0",
)

_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
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


@app.get("/health")
def health():
    return {"status": "ok"}
