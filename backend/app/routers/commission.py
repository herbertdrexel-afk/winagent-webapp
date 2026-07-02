from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..pdf_commission import build_pdf
from ..pdf_invoice import generate_invoice_pdf
from ..pdf_aufstellung import generate_aufstellung_pdf
from ..dbf_writer import write_hdubw_dbf

router = APIRouter(prefix="/commission", tags=["commission"])


def _get_supplier(db: Session, code: str) -> models.Supplier:
    supplier = db.query(models.Supplier).filter(models.Supplier.code == code.upper()).first()
    if not supplier:
        raise HTTPException(404, "Lieferant nicht gefunden")
    return supplier


@router.get("/{supplier_code}/statistic", response_model=schemas.CommissionSummaryResponse)
def commission_statistic(
    supplier_code: str,
    period_from: date,
    period_to: date,
    db: Session = Depends(get_db),
):
    """
    Entspricht der alten 'Lieferant Statistik' -> Aufstellung:
    aggregiert die Transaktionen im Zeitraum pro Kunde + Provisionssatz.
    """
    supplier = _get_supplier(db, supplier_code)

    rows = (
        db.query(
            models.Transaction.customer_id,
            models.Customer.code,
            models.Customer.name,
            models.Transaction.provision_rate,
            models.Transaction.currency,
            func.sum(models.Transaction.total_amount).label("total_amount"),
        )
        .outerjoin(models.Customer, models.Transaction.customer_id == models.Customer.id)
        .filter(
            models.Transaction.supplier_id == supplier.id,
            models.Transaction.invoice_date >= period_from,
            models.Transaction.invoice_date <= period_to,
        )
        .group_by(
            models.Transaction.customer_id,
            models.Customer.code,
            models.Customer.name,
            models.Transaction.provision_rate,
            models.Transaction.currency,
        )
        .all()
    )

    result_rows = []
    total_amount = 0
    total_provision = 0
    for r in rows:
        rate = r.provision_rate or 0
        provision_amount = (r.total_amount or 0) * rate / 100
        result_rows.append(
            schemas.CommissionSummaryRow(
                customer_id=r.customer_id,
                customer_code=r.code,
                customer_name=r.name,
                provision_rate=r.provision_rate,
                currency=r.currency,
                total_amount=r.total_amount or 0,
                provision_amount=provision_amount,
            )
        )
        total_amount += r.total_amount or 0
        total_provision += provision_amount

    return schemas.CommissionSummaryResponse(
        supplier_code=supplier.code,
        period_from=period_from,
        period_to=period_to,
        rows=result_rows,
        total_amount=total_amount,
        total_provision=total_provision,
    )


@router.get("/statements/{statement_id}/pdf")
def get_statement_pdf(statement_id: int, db: Session = Depends(get_db)):
    statement = db.get(models.CommissionStatement, statement_id)
    if not statement:
        raise HTTPException(404, "Abrechnung nicht gefunden")
    pdf_bytes = build_pdf(statement)
    filename = f"Provisionsabrechnung_{statement.statement_number or f'Entwurf-{statement_id}'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/statements", response_model=schemas.CommissionStatementOut)
def create_statement(payload: schemas.CommissionStatementCreate, db: Session = Depends(get_db)):
    """Legt eine neue Provisionsabrechnung als 'draft' an, befüllt mit den
    aggregierten Positionen aus der Statistik (siehe /statistic)."""
    supplier = _get_supplier(db, payload.supplier_code)
    summary = commission_statistic(payload.supplier_code, payload.period_from, payload.period_to, db)

    statement = models.CommissionStatement(
        supplier_id=supplier.id,
        period_from=payload.period_from,
        period_to=payload.period_to,
        status="draft",
        total_amount=summary.total_amount,
        total_provision=summary.total_provision,
        currency=supplier.default_currency,
    )
    db.add(statement)
    db.flush()

    for row in summary.rows:
        db.add(models.CommissionStatementItem(
            statement_id=statement.id,
            customer_id=row.customer_id,
            provision_rate=row.provision_rate,
            total_amount=row.total_amount,
            provision_amount=row.provision_amount,
            currency=row.currency,
        ))

    db.commit()
    db.refresh(statement)
    return statement


@router.get("/statements", response_model=list[schemas.CommissionStatementOut])
def list_statements(supplier_code: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.CommissionStatement)
    if supplier_code:
        supplier = _get_supplier(db, supplier_code)
        query = query.filter(models.CommissionStatement.supplier_id == supplier.id)
    return query.order_by(models.CommissionStatement.id.desc()).all()


@router.get("/statements/{statement_id}", response_model=schemas.CommissionStatementOut)
def get_statement(statement_id: int, db: Session = Depends(get_db)):
    statement = db.get(models.CommissionStatement, statement_id)
    if not statement:
        raise HTTPException(404, "Abrechnung nicht gefunden")
    return statement


@router.get("/{supplier_code}/invoice-summary")
def invoice_summary(
    supplier_code: str,
    period_from: date,
    period_to: date,
    db: Session = Depends(get_db),
):
    """Provision totals per currency for the given period — used by invoice modal."""
    supplier = _get_supplier(db, supplier_code)
    rows = (
        db.query(
            models.Transaction.currency,
            func.sum(models.Transaction.total_amount).label("total_amount"),
            func.sum(
                models.Transaction.total_amount * func.coalesce(models.Transaction.provision_rate, 0) / 100
            ).label("provision_amount"),
        )
        .filter(
            models.Transaction.supplier_id == supplier.id,
            models.Transaction.invoice_date >= period_from,
            models.Transaction.invoice_date <= period_to,
        )
        .group_by(models.Transaction.currency)
        .all()
    )

    # Next PR number from app_settings
    setting = db.get(models.AppSetting, "commission_statement_number")
    year_suffix = date.today().strftime("%y")
    if setting:
        val = dict(setting.value)
        if str(val.get("year")) == year_suffix:
            next_seq = val.get("next_seq", 1)
        else:
            next_seq = 1
    else:
        next_seq = 174  # fallback based on HDUBW history

    return {
        "supplier_code": supplier.code,
        "supplier_name": supplier.name,
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "next_pr_seq": next_seq,
        "totals": [
            {
                "currency": r.currency or "EUR",
                "total_amount": float(r.total_amount or 0),
                "provision_amount": float(r.provision_amount or 0),
            }
            for r in rows if (r.provision_amount or 0) != 0
        ],
    }


@router.post("/{supplier_code}/invoice-pdf")
def create_invoice_pdf(
    supplier_code: str,
    payload: schemas.CommissionInvoiceCreate,
    db: Session = Depends(get_db),
):
    """Generate PR invoice PDF and save statement_number to DB."""
    supplier = _get_supplier(db, supplier_code)

    # Save PR numbers to app_settings
    year_suffix = payload.invoice_date.strftime("%y")
    setting = db.get(models.AppSetting, "commission_statement_number")
    if setting is None:
        setting = models.AppSetting(
            key="commission_statement_number",
            value={"prefix": "PR", "year": int(year_suffix), "next_seq": payload.pr_seq + len(payload.totals)},
        )
        db.add(setting)
    else:
        val = dict(setting.value)
        val["year"] = int(year_suffix)
        val["next_seq"] = payload.pr_seq + len(payload.totals)
        setting.value = val
    db.commit()

    address_lines = []
    if supplier.address:
        address_lines.append(supplier.address)

    # Save each PR entry to commission_invoices (skip if already exists)
    period_text = f"Provision {payload.period_from.strftime('%m')}-{payload.period_to.strftime('%m/%y')}"
    for i, t in enumerate(payload.totals):
        pr_nr = f"PR{year_suffix}-{payload.pr_seq + i:04d}"
        existing = db.query(models.CommissionInvoice).filter_by(pr_number=pr_nr).first()
        if not existing:
            db.add(models.CommissionInvoice(
                supplier_id=supplier.id,
                pr_number=pr_nr,
                invoice_date=payload.invoice_date,
                description=period_text,
                currency=t["currency"],
                amount=round(t["provision_amount"], 2),
                total_amount=round(t.get("total_amount", 0), 2),
                period_from=payload.period_from,
                period_to=payload.period_to,
                v_code="NA",
            ))
    db.commit()

    pdf_bytes = generate_invoice_pdf(
        pr_number=f"PR{year_suffix}-{payload.pr_seq:04d}",
        invoice_date=payload.invoice_date,
        supplier_name=supplier.name,
        supplier_address=address_lines,
        period_from=payload.period_from,
        period_to=payload.period_to,
        totals=[{"currency": t["currency"], "amount": t["provision_amount"]} for t in payload.totals],
    )
    pr_label = f"PR{year_suffix}-{payload.pr_seq:04d}"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pr_label}.pdf"'},
    )


@router.post("/{supplier_code}/ubw-export")
def ubw_export(
    supplier_code: str,
    payload: schemas.CommissionInvoiceCreate,
    db: Session = Depends(get_db),
):
    """Generate HDUBW.DBF rows for the given period as a downloadable DBF file."""
    supplier = _get_supplier(db, supplier_code)
    year_suffix = payload.invoice_date.strftime("%y")
    period_text = f"Provision {payload.period_from.strftime('%m')}-{payload.period_to.strftime('%m/%y')}"

    records = []
    for i, t in enumerate(payload.totals):
        pr_nr = f"PR{year_suffix}-{payload.pr_seq + i:04d}"
        records.append({
            "BANK_EIGEN": "",
            "F_CODE": supplier.code,
            "UBW_DATUM": payload.invoice_date,
            "BETRAG": round(t["provision_amount"], 2),
            "WAEHRUNG": t["currency"],
            "NAME_KUNDE": supplier.name[:30],
            "CODE": "NA",
            "TEXT1": period_text[:30],
            "TEXT2": supplier.name[:30],
            "VON_DATUM": payload.period_from,
            "BIS_DATUM": payload.period_to,
            "VALUTASOLL": None,
            "SELECTED": "",
            "RE_NUMMER": pr_nr,
        })

    dbf_bytes = write_hdubw_dbf(records)
    return Response(
        content=dbf_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="HDUBW_new.DBF"'},
    )


@router.get("/invoices", response_model=list[schemas.CommissionInvoiceOut])
def list_commission_invoices(supplier_code: str | None = None, db: Session = Depends(get_db)):
    q = (
        db.query(models.CommissionInvoice)
        .join(models.Supplier)
        .order_by(models.Supplier.code, models.CommissionInvoice.invoice_date.desc())
    )
    if supplier_code:
        supplier = _get_supplier(db, supplier_code)
        q = q.filter(models.CommissionInvoice.supplier_id == supplier.id)
    rows = q.all()
    result = []
    for inv in rows:
        out = schemas.CommissionInvoiceOut.model_validate(inv)
        out.supplier_code = inv.supplier.code
        out.supplier_name = inv.supplier.name
        result.append(out)
    return result


@router.patch("/invoices/{inv_id}", response_model=schemas.CommissionInvoiceOut)
def update_commission_invoice(
    inv_id: int,
    payload: schemas.CommissionInvoiceUpdate,
    db: Session = Depends(get_db),
):
    inv = db.get(models.CommissionInvoice, inv_id)
    if not inv:
        raise HTTPException(404, "Rechnung nicht gefunden")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(inv, k, v)
    db.commit()
    db.refresh(inv)
    out = schemas.CommissionInvoiceOut.model_validate(inv)
    out.supplier_code = inv.supplier.code
    out.supplier_name = inv.supplier.name
    return out


@router.delete("/invoices/{inv_id}")
def delete_commission_invoice(inv_id: int, db: Session = Depends(get_db)):
    inv = db.get(models.CommissionInvoice, inv_id)
    if not inv:
        raise HTTPException(404, "Rechnung nicht gefunden")
    db.delete(inv)
    db.commit()
    return {"ok": True}


@router.post("/invoices/{inv_id}/pdf")
def reprint_commission_invoice_pdf(inv_id: int, db: Session = Depends(get_db)):
    inv = db.get(models.CommissionInvoice, inv_id)
    if not inv:
        raise HTTPException(404, "Rechnung nicht gefunden")
    supplier = db.get(models.Supplier, inv.supplier_id)
    address_lines = [supplier.address] if supplier.address else []
    pdf_bytes = generate_invoice_pdf(
        pr_number=inv.pr_number,
        invoice_date=inv.invoice_date,
        supplier_name=supplier.name,
        supplier_address=address_lines,
        period_from=inv.period_from,
        period_to=inv.period_to,
        totals=[{"currency": inv.currency, "amount": float(inv.amount)}],
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inv.pr_number}.pdf"'},
    )


@router.post("/statements/{statement_id}/issue", response_model=schemas.CommissionStatementOut)
def issue_statement(
    statement_id: int,
    payload: schemas.CommissionStatementIssue,
    db: Session = Depends(get_db),
):
    """Vergibt Rechnungsnummer (PR{Jahr}-{lfd. Nr}) und Datum, setzt Status auf 'issued'.

    Entspricht: 'nach dem Drucken die Rechnungsnummer (PR...) und das heutige
    Datum vergeben'. Die Abrechnung bleibt danach weiterhin abrufbar/druckbar.
    """
    statement = db.get(models.CommissionStatement, statement_id)
    if not statement:
        raise HTTPException(404, "Abrechnung nicht gefunden")

    if statement.status == "issued":
        # Bereits ausgestellt -> einfach erneut zurückgeben (erneuter Druck)
        return statement

    statement_date = payload.statement_date or date.today()
    year_suffix = statement_date.strftime("%y")

    setting = db.get(models.AppSetting, "commission_statement_number")
    if setting is None:
        setting = models.AppSetting(
            key="commission_statement_number",
            value={"prefix": "PR", "year": int(year_suffix), "next_seq": 1},
        )
        db.add(setting)

    value = dict(setting.value)
    if str(value.get("year")) != year_suffix:
        # neues Jahr -> Zähler zurücksetzen
        value["year"] = int(year_suffix)
        value["next_seq"] = 1

    seq = value["next_seq"]
    statement.statement_number = f"{value.get('prefix', 'PR')}{year_suffix}-{seq:04d}"
    statement.statement_date = statement_date
    statement.status = "issued"

    value["next_seq"] = seq + 1
    setting.value = value

    db.commit()
    db.refresh(statement)
    return statement


@router.post("/{supplier_code}/aufstellung-pdf")
def create_aufstellung_pdf(
    supplier_code: str,
    payload: schemas.AufstellungRequest,
    db: Session = Depends(get_db),
):
    """Generate Provisionsabrechnung (breakdown) PDF for all currencies in the period."""
    from datetime import datetime, timezone
    from sqlalchemy.orm import joinedload

    supplier = _get_supplier(db, supplier_code)

    txs = (
        db.query(models.Transaction)
        .options(joinedload(models.Transaction.customer))
        .filter(
            models.Transaction.supplier_id == supplier.id,
            models.Transaction.invoice_date >= payload.period_from,
            models.Transaction.invoice_date <= payload.period_to,
        )
        .order_by(models.Transaction.currency, models.Transaction.invoice_date)
        .all()
    )

    if not txs:
        raise HTTPException(404, "Keine Transaktionen im gewählten Zeitraum")

    # Build location string: "AT-5282 Ranshofen" or "CH- Buron"
    def _location(c: models.Customer | None) -> str:
        if not c:
            return ""
        parts = []
        if c.country_code:
            parts.append(c.country_code)
        zip_city = " ".join(filter(None, [c.zip, c.city]))
        if zip_city:
            parts.append(zip_city)
        return "-".join(parts[:1]) + ("-" + parts[1] if len(parts) > 1 else "") if parts else ""

    # Group by currency (preserving order EUR first, then others)
    by_currency: dict[str, list] = {}
    for tx in txs:
        cur = tx.currency or "EUR"
        rate = float(tx.provision_rate or 0)
        amt  = float(tx.total_amount or 0)
        prov = round(amt * rate / 100, 2)
        by_currency.setdefault(cur, []).append({
            "customer_name":     tx.customer.name if tx.customer else "",
            "customer_location": _location(tx.customer),
            "invoice_date":      tx.invoice_date,
            "invoice_number":    tx.invoice_number,
            "total_amount":      amt,
            "provision_rate":    rate,
            "provision_amount":  prov,
        })

    print_date = payload.print_date or date.today()
    pdf_bytes = generate_aufstellung_pdf(
        supplier_name=supplier.name,
        representative_code=supplier.representative_code or "NA",
        period_from=payload.period_from,
        period_to=payload.period_to,
        print_date=print_date,
        transactions_by_currency=by_currency,
    )

    period_label = f"{payload.period_from.strftime('%Y%m')}-{payload.period_to.strftime('%Y%m')}"
    filename = f"Aufstellung_{supplier.code}_{period_label}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
