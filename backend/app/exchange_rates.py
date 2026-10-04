"""Monats-Durchschnittskurse (ECB via Frankfurter) in die exchange_rates-Tabelle.

Konvention: rate = EUR je 1 Einheit der Fremdwährung, gültig für den Monat
(valid_date = erster Tag des Monats). EUR selbst hat implizit den Kurs 1.
Beispiel: 1 USD ~ 0,866 EUR → total_amount(USD) * rate = Betrag in EUR.
"""
import logging
from datetime import date
from collections import defaultdict

import httpx

from . import models

logger = logging.getLogger(__name__)

# ECB-Referenzkurse, kostenlos und ohne API-Key
FRANKFURTER = "https://api.frankfurter.dev/v1"

# Ab diesem Jahr werden die ECB-Monatskurse verwendet. Rechnungen davor nutzen
# weiterhin den in den Altdaten gespeicherten Rechnungs-KURS (unverändert).
CUTOVER_YEAR = 2026


def _month_start(d: date) -> date:
    return d.replace(day=1)


def transaction_currencies(db) -> list[str]:
    """Alle in Transaktionen vorkommenden Fremdwährungen (ohne EUR/leer)."""
    rows = db.query(models.Transaction.currency).distinct().all()
    curs = {(r[0] or "").strip().upper() for r in rows}
    return sorted(c for c in curs if c and c != "EUR")


def transaction_date_range(db) -> tuple[date, date] | None:
    """Min/Max Rechnungsdatum über alle Transaktionen."""
    from sqlalchemy import func
    row = db.query(func.min(models.Transaction.invoice_date),
                   func.max(models.Transaction.invoice_date)).first()
    if not row or not row[0]:
        return None
    return row[0], row[1]


def _fetch_monthly_avg(currency: str, start: date, end: date) -> dict[tuple[int, int], float]:
    """Tägliche Kurse (Einheiten der Fremdwährung je 1 EUR) holen und je Monat
    mitteln. Konvention wie im Alt-KURS: z. B. 1 EUR = 1,16 USD."""
    url = f"{FRANKFURTER}/{start.isoformat()}..{end.isoformat()}"
    resp = httpx.get(url, params={"base": "EUR", "symbols": currency},
                     timeout=30, follow_redirects=True,
                     headers={"User-Agent": "WinAgent/1.0"})
    resp.raise_for_status()
    rates = resp.json().get("rates", {})
    lo = (start.year, start.month)
    hi = (end.year, end.month)
    by_month: dict[tuple[int, int], list[float]] = defaultdict(list)
    for ds, obj in rates.items():
        val = obj.get(currency)   # Einheiten der Fremdwährung je 1 EUR
        if val is None:
            continue
        y, m, _d = ds.split("-")
        ym = (int(y), int(m))
        if ym < lo or ym > hi:   # Randtage außerhalb des Zeitraums ignorieren
            continue
        by_month[ym].append(float(val))
    return {ym: round(sum(v) / len(v), 5) for ym, v in by_month.items() if v}


def refresh_rates(db, currencies: list[str] | None = None,
                  start: date | None = None, end: date | None = None,
                  overwrite: bool = False) -> dict:
    """Durchschnittskurse holen und in exchange_rates upserten.

    Ohne Parameter: alle Fremdwährungen aus den Transaktionen, Zeitraum vom
    ersten bis zum letzten Rechnungsdatum (mind. laufendes Jahr).

    Abgeschlossene Monate werden NICHT neu berechnet: existiert ein Kurs für
    einen vergangenen Monat bereits, bleibt er unverändert. Nur fehlende Monate
    werden ergänzt und der laufende Monat aktualisiert. `overwrite=True` erzwingt
    das Neuberechnen aller Monate."""
    if currencies is None:
        currencies = transaction_currencies(db) or ["USD", "CHF"]
    # Zeitraum bestimmen
    if start is None or end is None:
        rng = transaction_date_range(db)
        today = date.today()
        if rng:
            start = start or _month_start(rng[0])
            end = end or today
        else:
            start = start or date(today.year, 1, 1)
            end = end or today
    # ECB-Kurse erst ab dem Cutover-Jahr; Alt-Rechnungen nutzen ihren eigenen KURS
    cutover = date(CUTOVER_YEAR, 1, 1)
    if start < cutover:
        start = cutover
    # Bis Monatsende des Endmonats (ECB liefert bis heute)
    today = date.today()
    cur_ym = (today.year, today.month)   # laufender Monat darf aktualisiert werden
    written = 0
    skipped = 0
    per_currency: dict[str, int] = {}
    errors: list[str] = []
    for cur in currencies:
        cur = cur.strip().upper()
        if not cur or cur == "EUR":
            continue
        try:
            monthly = _fetch_monthly_avg(cur, start, end)
        except Exception as e:  # Netzwerk/HTTP
            errors.append(f"{cur}: {e}")
            logger.warning("Kursabruf %s fehlgeschlagen: %s", cur, e)
            continue
        cnt = 0
        for (y, m), avg in monthly.items():
            vd = date(y, m, 1)
            existing = (db.query(models.ExchangeRate)
                        .filter_by(currency=cur, valid_date=vd).first())
            if existing:
                # Abgeschlossene Monate NICHT neu kalkulieren – nur laufenden Monat
                if overwrite or (y, m) == cur_ym:
                    existing.rate = avg
                    cnt += 1
                else:
                    skipped += 1
            else:
                db.add(models.ExchangeRate(currency=cur, valid_date=vd, rate=avg))
                cnt += 1
        per_currency[cur] = cnt
        written += cnt
    db.commit()
    return {"written": written, "skipped": skipped, "per_currency": per_currency,
            "currencies": currencies,
            "from": start.isoformat() if start else None,
            "to": end.isoformat() if end else None,
            "errors": errors}


def rate_lookup(db) -> dict[tuple[str, int, int], float]:
    """{(WÄHRUNG, Jahr, Monat): rate} für die Umrechnung in den Berichten."""
    out: dict[tuple[str, int, int], float] = {}
    for r in db.query(models.ExchangeRate).all():
        if r.valid_date is None or r.rate is None:
            continue
        out[((r.currency or "").upper(), r.valid_date.year, r.valid_date.month)] = float(r.rate)
    return out


def to_eur(amount: float, currency: str | None, d: date | None,
           lookup: dict[tuple[str, int, int], float],
           tx_rate: float | None = None) -> float:
    """Betrag in EUR umrechnen. Kurs-Konvention überall: Einheiten je 1 EUR
    (z. B. 1 EUR = 1,16 USD) → EUR = Betrag / Kurs.

    Reihenfolge:
    1. Manuell gesetzter Kurs auf der Rechnung (exchange_rate ≠ 1) hat Vorrang.
    2. Ab CUTOVER_YEAR sonst der ECB-Monatskurs aus der Tabelle.
    3. EUR oder kein Kurs bekannt → unverändert.
    """
    cur = (currency or "EUR").strip().upper()
    if cur == "EUR" or d is None:
        return amount
    # 1. Rechnungs-eigener Kurs (Einheiten je EUR)
    if tx_rate and tx_rate not in (0, 1):
        return amount / tx_rate
    # 2. ECB-Monatskurs aus der Tabelle (Einheiten je EUR)
    if d.year >= CUTOVER_YEAR:
        rate = lookup.get((cur, d.year, d.month))
        if rate:
            return amount / rate
    return amount
