import re
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text, case, extract
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/customers", tags=["customers"])


def _norm_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9äöüß]+", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def _next_ku_nr(db: Session) -> str:
    """Nächste freie KU_NR: MAX(numerische ku_nr) + 1."""
    result = db.execute(
        text("SELECT MAX(ku_nr::int) FROM customers WHERE ku_nr ~ '^[0-9]+$'")
    ).scalar()
    return str((result or 5531) + 1)


@router.get("", response_model=list[schemas.CustomerOut])
def list_customers(
    q: str | None = Query(None, description="Suche in Name/Code"),
    limit: int = Query(200, le=100000),
    db: Session = Depends(get_db),
):
    query = db.query(models.Customer)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (models.Customer.name.ilike(like))
            | (models.Customer.code.ilike(like))
            | (models.Customer.city.ilike(like))
            | (models.Customer.ku_nr.ilike(like))
        )
    return query.order_by(models.Customer.name).limit(limit).all()


@router.get("/duplicates")
def customer_duplicates(
    cutover_year: int = Query(2026),
    db: Session = Depends(get_db),
):
    """Kunden, die mehrfach vorkommen (gleicher Name, verschiedene Adressnummern),
    mit Angabe, welche Adressnummer in den Rechnungen VOR `cutover_year` verwendet
    wurde. Für den Abgleich/die Bereinigung doppelter Adressen."""
    # Transaktions-Kennzahlen je Kunde in einem Rutsch
    agg = dict()
    rows = (
        db.query(
            models.Transaction.customer_id,
            func.count().label("n"),
            func.sum(case((extract("year", models.Transaction.invoice_date) < cutover_year, 1), else_=0)).label("n_before"),
            func.sum(case((extract("year", models.Transaction.invoice_date) >= cutover_year, 1), else_=0)).label("n_after"),
            func.min(models.Transaction.invoice_date).label("first"),
            func.max(models.Transaction.invoice_date).label("last"),
        )
        .filter(models.Transaction.customer_id.isnot(None))
        .group_by(models.Transaction.customer_id)
        .all()
    )
    for r in rows:
        agg[r.customer_id] = r

    # Kunden nach normalisiertem Namen gruppieren
    groups: dict[str, list] = defaultdict(list)
    for c in db.query(models.Customer).all():
        if c.name:
            groups[_norm_name(c.name)].append(c)

    result = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        entry_customers = []
        total_tx = 0
        for c in members:
            a = agg.get(c.id)
            n = int(a.n) if a else 0
            n_before = int(a.n_before or 0) if a else 0
            n_after = int(a.n_after or 0) if a else 0
            total_tx += n
            entry_customers.append({
                "id": c.id, "code": c.code, "ku_nr": c.ku_nr,
                "name": c.name, "city": c.city, "zip": c.zip,
                "country_code": c.country_code,
                "tx_total": n, "tx_before": n_before, "tx_from_cutover": n_after,
                "first_invoice": a.first.isoformat() if a and a.first else None,
                "last_invoice": a.last.isoformat() if a and a.last else None,
                "used_before_cutover": n_before > 0,
            })
        # Nur Gruppen zeigen, in denen überhaupt Rechnungen vorkommen
        if total_tx == 0:
            continue
        # sortiert: die mit Rechnungen vor dem Cutover zuerst
        entry_customers.sort(key=lambda x: (-x["tx_before"], -x["tx_total"]))
        addr_before = [c["ku_nr"] or c["code"] for c in entry_customers if c["used_before_cutover"]]
        result.append({
            "name": members[0].name,
            "customer_count": len(members),
            "address_numbers_before_cutover": addr_before,
            "customers": entry_customers,
        })

    result.sort(key=lambda g: g["name"].lower())
    return {"cutover_year": cutover_year, "count": len(result), "groups": result}


@router.post("/duplicates/cleanup")
def customer_duplicates_cleanup(
    cutover_year: int = Query(2026),
    apply: bool = Query(False, description="False = nur Vorschau, True = ausführen"),
    _: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Doppelte Adressen bereinigen: In jeder Namensgruppe bleiben die Adressen mit
    Rechnungen ab `cutover_year`; Adressen OHNE solche Rechnungen werden gelöscht.
    Ihre Rechnungen (vor dem Stichjahr) werden vorher auf die Adresse mit den
    meisten Rechnungen ab dem Stichjahr umgehängt. Gruppen ohne Adresse mit
    Rechnungen ab dem Stichjahr bleiben unberührt."""
    T = models.Transaction
    after = {
        r.customer_id: int(r.n)
        for r in db.query(T.customer_id, func.count().label("n"))
        .filter(T.customer_id.isnot(None))
        .filter(extract("year", T.invoice_date) >= cutover_year)
        .group_by(T.customer_id).all()
    }
    total = {
        r.customer_id: int(r.n)
        for r in db.query(T.customer_id, func.count().label("n"))
        .filter(T.customer_id.isnot(None)).group_by(T.customer_id).all()
    }

    groups: dict[str, list] = defaultdict(list)
    for c in db.query(models.Customer).all():
        if c.name:
            groups[_norm_name(c.name)].append(c)

    plan = []
    skipped_groups = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        keepers = [c for c in members if after.get(c.id, 0) > 0]
        removable = [c for c in members if after.get(c.id, 0) == 0]
        if not keepers:
            if any(total.get(c.id, 0) for c in members):
                skipped_groups += 1   # nichts in 2026 → nicht eindeutig, nicht anfassen
            continue
        if not removable:
            continue
        target = max(keepers, key=lambda c: after.get(c.id, 0))
        for c in removable:
            plan.append({
                "name": c.name,
                "delete": {"id": c.id, "code": c.code, "ku_nr": c.ku_nr, "city": c.city},
                "keep": {"id": target.id, "code": target.code, "ku_nr": target.ku_nr, "city": target.city},
                "move_transactions": total.get(c.id, 0),
                "other_keepers": len(keepers) - 1,
            })

    moved = deleted = 0
    if apply:
        for p in plan:
            cid, tid = p["delete"]["id"], p["keep"]["id"]
            moved += db.query(models.Transaction).filter_by(customer_id=cid).update({"customer_id": tid})
            db.query(models.Budget).filter_by(customer_id=cid).update({"customer_id": tid})
            db.query(models.CommissionStatementItem).filter_by(customer_id=cid).update({"customer_id": tid})
            cust = db.get(models.Customer, cid)
            if cust:
                db.delete(cust)
                deleted += 1
        db.commit()

    return {
        "applied": apply, "cutover_year": cutover_year,
        "to_delete": len(plan), "transactions_to_move": sum(p["move_transactions"] for p in plan),
        "skipped_groups_without_cutover_invoices": skipped_groups,
        "deleted": deleted, "moved_transactions": moved,
        "plan": plan,
    }


@router.post("", response_model=schemas.CustomerOut, status_code=201)
def create_customer(payload: schemas.CustomerCreate, db: Session = Depends(get_db)):
    code = payload.code.upper().strip()
    if len(code) < 4:
        raise HTTPException(422, "Code muss mindestens 4 Zeichen haben")
    if db.query(models.Customer).filter(models.Customer.code == code).first():
        raise HTTPException(409, f"Code '{code}' ist bereits vergeben")
    ku_nr = _next_ku_nr(db)
    customer = models.Customer(**{**payload.model_dump(), "code": code, "ku_nr": ku_nr})
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{code}", response_model=schemas.CustomerOut)
def get_customer(code: str, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.code == code.upper()).first()
    if not customer:
        raise HTTPException(404, "Kunde nicht gefunden")
    return customer


@router.patch("/{code}", response_model=schemas.CustomerOut)
def update_customer(code: str, payload: schemas.CustomerUpdate, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.code == code.upper()).first()
    if not customer:
        raise HTTPException(404, "Kunde nicht gefunden")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{code}", status_code=204)
def delete_customer(code: str, db: Session = Depends(get_db)):
    """Kunde löschen. Nicht möglich, solange noch Umsätze/Rechnungen oder andere
    Datensätze auf ihn verweisen."""
    customer = db.query(models.Customer).filter(models.Customer.code == code.upper()).first()
    if not customer:
        raise HTTPException(404, "Kunde nicht gefunden")
    n_tx = db.query(models.Transaction).filter_by(customer_id=customer.id).count()
    n_bud = db.query(models.Budget).filter_by(customer_id=customer.id).count()
    n_csi = db.query(models.CommissionStatementItem).filter_by(customer_id=customer.id).count()
    total = n_tx + n_bud + n_csi
    if total:
        detail = f"{n_tx} Umsätze/Rechnungen" if n_tx else f"{total} verknüpfte Datensätze"
        raise HTTPException(
            409,
            f"Kunde kann nicht gelöscht werden: {detail} noch zugeordnet. "
            "Bitte zuerst diese Datensätze entfernen oder einem anderen Kunden zuordnen.",
        )
    db.delete(customer)
    db.commit()
