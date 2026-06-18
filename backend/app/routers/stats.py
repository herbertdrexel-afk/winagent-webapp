"""Supplier statistics summary endpoint."""
from datetime import date
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..pdf_stats import build_supplier_stats_pdf

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/supplier-summary")
def supplier_summary(
    period_from: date,
    period_to: date,
    db: Session = Depends(get_db),
):
    # Last-year same period
    ly_from = period_from.replace(year=period_from.year - 1)
    ly_to = period_to.replace(year=period_to.year - 1)

    rows = (
        db.query(
            models.Supplier.id,
            models.Supplier.code,
            models.Supplier.name,
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(period_from, period_to),
                      models.Transaction.total_amount), else_=0)
            ), 0).label("curr_turnover"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(period_from, period_to),
                      models.Transaction.total_amount * func.coalesce(models.Transaction.provision_rate, 0) / 100),
                     else_=0)
            ), 0).label("curr_commission"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(ly_from, ly_to),
                      models.Transaction.total_amount), else_=0)
            ), 0).label("prev_turnover"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(ly_from, ly_to),
                      models.Transaction.total_amount * func.coalesce(models.Transaction.provision_rate, 0) / 100),
                     else_=0)
            ), 0).label("prev_commission"),
        )
        .outerjoin(models.Transaction, models.Transaction.supplier_id == models.Supplier.id)
        .filter(models.Supplier.is_active == True)
        .group_by(models.Supplier.id, models.Supplier.code, models.Supplier.name)
        .order_by(models.Supplier.name)
        .all()
    )

    result = []
    for r in rows:
        curr_t = float(r.curr_turnover or 0)
        curr_c = float(r.curr_commission or 0)
        prev_t = float(r.prev_turnover or 0)
        prev_c = float(r.prev_commission or 0)
        diff = curr_c - prev_c
        pct = ((curr_c / prev_c - 1) * 100) if prev_c else None
        result.append({
            "code": r.code,
            "name": r.name,
            "curr_turnover": curr_t,
            "curr_commission": curr_c,
            "prev_turnover": prev_t,
            "prev_commission": prev_c,
            "comm_diff": diff,
            "comm_pct": pct,
        })
    return {
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "rows": result,
    }


@router.get("/supplier-summary/pdf")
def supplier_summary_pdf(
    period_from: date,
    period_to: date,
    db: Session = Depends(get_db),
):
    data = supplier_summary(period_from, period_to, db)
    pdf_bytes = build_supplier_stats_pdf(data)
    filename = f"Lieferant_Statistik_{period_from}_{period_to}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
