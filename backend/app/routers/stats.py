"""Supplier statistics summary endpoint."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..pdf_stats import build_supplier_stats_pdf, build_customer_turnover_pdf, build_supplier_detail_pdf

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
        .order_by(models.Supplier.code)
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


@router.get("/customer-turnover")
def customer_turnover(
    period_from: date,
    period_to: date,
    sort_by: Literal["provision", "turnover"] = "provision",
    db: Session = Depends(get_db),
):
    ly_from = period_from.replace(year=period_from.year - 1)
    ly_to = period_to.replace(year=period_to.year - 1)

    rows = (
        db.query(
            func.coalesce(models.Transaction.customer_name, "–").label("customer_name"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(period_from, period_to),
                      models.Transaction.total_amount), else_=0)
            ), 0).label("curr_turnover"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(period_from, period_to),
                      models.Transaction.total_amount * func.coalesce(models.Transaction.provision_rate, 0) / 100),
                     else_=0)
            ), 0).label("curr_provision"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(ly_from, ly_to),
                      models.Transaction.total_amount), else_=0)
            ), 0).label("prev_turnover"),
            func.coalesce(func.sum(
                case((models.Transaction.invoice_date.between(ly_from, ly_to),
                      models.Transaction.total_amount * func.coalesce(models.Transaction.provision_rate, 0) / 100),
                     else_=0)
            ), 0).label("prev_provision"),
            # avg provision rate (weighted) for current period
            func.coalesce(
                func.sum(
                    case((models.Transaction.invoice_date.between(period_from, period_to),
                          models.Transaction.total_amount * func.coalesce(models.Transaction.provision_rate, 0) / 100),
                         else_=0)
                ) * 100 / func.nullif(func.sum(
                    case((models.Transaction.invoice_date.between(period_from, period_to),
                          models.Transaction.total_amount), else_=0)
                ), 0),
                0,
            ).label("avg_rate"),
        )
        .group_by(func.coalesce(models.Transaction.customer_name, "–"))
        .having(
            func.sum(case((models.Transaction.invoice_date.between(period_from, period_to),
                           models.Transaction.total_amount), else_=0)) > 0
        )
        .all()
    )

    result = []
    total_provision = sum(float(r.curr_provision or 0) for r in rows)
    for r in rows:
        ct = float(r.curr_turnover or 0)
        cp = float(r.curr_provision or 0)
        pt = float(r.prev_turnover or 0)
        share = (cp / total_provision * 100) if total_provision else 0
        result.append({
            "customer_name": r.customer_name,
            "curr_turnover": ct,
            "curr_provision": cp,
            "prev_turnover": pt,
            "prev_provision": float(r.prev_provision or 0),
            "avg_rate": float(r.avg_rate or 0),
            "share_pct": round(share, 1),
        })

    if sort_by == "provision":
        result.sort(key=lambda x: x["curr_provision"], reverse=True)
    else:
        result.sort(key=lambda x: x["curr_turnover"], reverse=True)

    return {
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "sort_by": sort_by,
        "rows": result,
    }


@router.get("/customer-turnover/pdf")
def customer_turnover_pdf(
    period_from: date,
    period_to: date,
    sort_by: Literal["provision", "turnover"] = "provision",
    db: Session = Depends(get_db),
):
    data = customer_turnover(period_from, period_to, sort_by, db)
    pdf_bytes = build_customer_turnover_pdf(data)
    label = "Provision" if sort_by == "provision" else "Umsatz"
    filename = f"AdrUms_{label}_{period_from}_{period_to}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/supplier-detail")
def supplier_detail(year: int, db: Session = Depends(get_db)):
    from datetime import date as date_cls
    quarters = [
        ("1.Q", date_cls(year, 1, 1),  date_cls(year, 3, 31)),
        ("2.Q", date_cls(year, 4, 1),  date_cls(year, 6, 30)),
        ("3.Q", date_cls(year, 7, 1),  date_cls(year, 9, 30)),
        ("4.Q", date_cls(year, 10, 1), date_cls(year, 12, 31)),
        ("1.HY", date_cls(year, 1, 1), date_cls(year, 6, 30)),
        ("2.HY", date_cls(year, 7, 1), date_cls(year, 12, 31)),
        ("Jahr", date_cls(year, 1, 1), date_cls(year, 12, 31)),
    ]
    prev_year = year - 1

    # Fetch all transactions for both years
    txns = (
        db.query(
            models.Transaction.supplier_id,
            models.Transaction.invoice_date,
            models.Transaction.total_amount,
            models.Transaction.provision_rate,
        )
        .filter(
            models.Transaction.invoice_date.between(
                date_cls(prev_year, 1, 1), date_cls(year, 12, 31)
            )
        )
        .all()
    )

    suppliers = db.query(models.Supplier).filter_by(is_active=True).order_by(models.Supplier.code).all()
    budgets = db.query(models.Budget).filter_by(year=year).all()
    # budget_turnover[supplier_id] = sum of amount_budget
    budget_t: dict[int, float] = {}
    budget_c: dict[int, float] = {}
    for b in budgets:
        sid = b.supplier_id
        bt = float(b.amount_budget or 0)
        bp = float(b.amount_budget or 0) * 0.05  # approx — no direct provision budget
        budget_t[sid] = budget_t.get(sid, 0) + bt
        budget_c[sid] = budget_c.get(sid, 0) + bp

    def agg(supplier_id: int, from_date: date, to_date: date, yr: int):
        total = prov = 0.0
        for t in txns:
            if t.supplier_id != supplier_id:
                continue
            if not (from_date <= t.invoice_date <= to_date):
                continue
            if t.invoice_date.year != yr:
                continue
            amt = float(t.total_amount or 0)
            rate = float(t.provision_rate or 0)
            total += amt
            prov += amt * rate / 100
        return total, prov

    result = []
    for s in suppliers:
        rows = []
        for label, qfrom, qto in quarters:
            d_from = qfrom
            d_to = qto
            ly_from = date_cls(prev_year, qfrom.month, qfrom.day)
            ly_to = date_cls(prev_year, qto.month, qto.day)
            ct, cp = agg(s.id, d_from, d_to, year)
            pt, pp = agg(s.id, ly_from, ly_to, prev_year)
            bt = budget_t.get(s.id, 0) if label == "Jahr" else 0
            bc = budget_c.get(s.id, 0) if label == "Jahr" else 0
            rows.append({
                "label": label,
                "prev_turnover": pt, "budget_turnover": bt,
                "curr_turnover": ct,
                "prev_commission": pp, "budget_commission": bc,
                "curr_commission": cp,
            })
        result.append({"code": s.code, "name": s.name, "rows": rows})

    return {"year": year, "suppliers": result}


@router.get("/supplier-detail/pdf")
def supplier_detail_pdf(year: int, db: Session = Depends(get_db)):
    data = supplier_detail(year, db)
    pdf_bytes = build_supplier_detail_pdf(data)
    filename = f"Lieferant_Detail_{year}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


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
