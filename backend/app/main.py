import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import suppliers, customers, commission

app = FastAPI(
    title="WinAgent Webapp API",
    description="Neuentwicklung des Lieferanten-/Provisionsabrechnungssystems "
                 "(ehemals Delphi/dBase) als Web-API.",
    version="0.1.0",
)

# Erlaubte Frontend-Origins: ALLOWED_ORIGINS=https://winagent.vercel.app,...
_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(suppliers.router)
app.include_router(customers.router)
app.include_router(commission.router)


@app.get("/health")
def health():
    return {"status": "ok"}
