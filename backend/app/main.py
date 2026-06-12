from fastapi import FastAPI

from .routers import suppliers, customers, commission

app = FastAPI(
    title="WinAgent Webapp API",
    description="Neuentwicklung des Lieferanten-/Provisionsabrechnungssystems "
                 "(ehemals Delphi/dBase) als Web-API.",
    version="0.1.0",
)

app.include_router(suppliers.router)
app.include_router(customers.router)
app.include_router(commission.router)


@app.get("/health")
def health():
    return {"status": "ok"}
