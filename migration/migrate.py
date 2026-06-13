#!/usr/bin/env python3
"""
Migration: WinAgent (dBase/.dbf) -> PostgreSQL (schema.sql)

Erwartet alle .dbf-Dateien in einem flachen Verzeichnis (--source).
Erkennt automatisch alle {CODE}{YY}_INV.DBF / _BUD.DBF / _art.DBF
Dateien für beliebig viele Lieferanten-Codes und Jahre.

Verwendung:
    python migrate.py --source /pfad/zu/dbf --dsn postgresql://user:pw@host/db [--dry-run]

Hinweise:
- Encoding der .dbf-Dateien ist latin1 (cp850-Sonderzeichen kommen vor,
  notfalls --encoding cp850 versuchen und Ergebnis prüfen).
- Das Skript ist bewusst idempotent angelegt (DELETE+INSERT je Tabelle),
  damit es bei Bedarf mehrfach laufen kann. Für produktive Migration ggf.
  anpassen (z.B. Transaktionen pro Lieferant).
"""

import argparse
import re
import sys
from pathlib import Path
from decimal import Decimal, InvalidOperation

from dbfread import DBF
import psycopg2
import psycopg2.extras


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def open_dbf(path: Path, encoding="latin1"):
    return DBF(str(path), encoding=encoding, ignore_missing_memofile=True, lowernames=False)


def num(value, default=None):
    if value is None:
        return default
    if isinstance(value, (int, float, Decimal)):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def clean(value):
    """Strip strings, turn empty strings into None."""
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


# ------------------------------------------------------------------
# Stammdaten-Migration
# ------------------------------------------------------------------

def migrate_countries(cur, source: Path, encoding):
    print("-> countries (HDLAND.DBF)")
    table = open_dbf(source / "HDLAND.DBF", encoding)
    rows = []
    for rec in table:
        code = clean(rec["FA_LAND"])
        if not code:
            continue
        invoice_texts = {
            k: clean(rec.get(k))
            for k in (
                "LIEFERUNG", "RECHNUNG", "RECNR", "DATUM", "BETRIFFT", "ARTIKEL",
                "MENGE", "EINHEIT", "PREIS", "TOTAL", "MWST", "TOTALHT", "STEUNETT",
                "STEUER", "GESNETTO", "NETTO", "MWSTBETR", "GESBETR", "BETRIN",
                "ZAHLKON", "ZAHLENAN", "SWIFTADR", "KONTONR", "VERSANDKOS",
                "MAHNUNG", "GUTSCHRIFT", "FAELLIG",
            )
            if clean(rec.get(k)) is not None
        }
        rows.append((
            code,
            clean(rec["LAND"]) or code,
            clean(rec["SPRACHE"]),
            num(rec["MWSTEUER"]),
            psycopg2.extras.Json(invoice_texts) if invoice_texts else None,
        ))
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO countries (code, name, language, vat_rate, invoice_texts)
           VALUES %s
           ON CONFLICT (code) DO UPDATE SET
             name=EXCLUDED.name, language=EXCLUDED.language,
             vat_rate=EXCLUDED.vat_rate, invoice_texts=EXCLUDED.invoice_texts""",
        rows,
    )
    print(f"   {len(rows)} Länder")


def migrate_representatives(cur, source: Path, encoding):
    print("-> representatives (HDVERT.DBF)")
    table = open_dbf(source / "HDVERT.DBF", encoding)
    rows = []
    for rec in table:
        code = clean(rec["CODE"])
        if not code:
            continue
        address = {
            k: clean(rec.get(k))
            for k in ("NAME_EXT", "FA_NAME", "FA_ADR1", "FA_ADR2", "FA_ADR3",
                      "FA_LAND", "FA_PLZ", "FA_ORT", "BA_NAME", "BA_ADR1",
                      "BA_ADR2", "BA_ADR3", "BA_LAND", "BA_PLZ", "BA_ORT")
            if clean(rec.get(k)) is not None
        }
        rows.append((
            code,
            clean(rec["NAME"]),
            psycopg2.extras.Json(address) if address else None,
            clean(rec["KONTO"]),
            clean(rec["BLZ"]),
            clean(rec["WAEHRUNG"]),
            clean(rec["MAILTO"]),
            clean(rec["MAILTOCC"]),
            clean(rec["MAILTOBCC"]),
        ))
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO representatives
             (code, name, address, bank_account, bank_blz, currency, mail_to, mail_cc, mail_bcc)
           VALUES %s
           ON CONFLICT (code) DO UPDATE SET
             name=EXCLUDED.name, address=EXCLUDED.address,
             bank_account=EXCLUDED.bank_account, bank_blz=EXCLUDED.bank_blz,
             currency=EXCLUDED.currency, mail_to=EXCLUDED.mail_to,
             mail_cc=EXCLUDED.mail_cc, mail_bcc=EXCLUDED.mail_bcc""",
        rows,
    )
    print(f"   {len(rows)} Vertreter")


def migrate_suppliers(cur, source: Path, encoding):
    print("-> suppliers (HDFIRMA.DBF)")
    table = open_dbf(source / "HDFIRMA.DBF", encoding)
    rows = []
    for rec in table:
        code = clean(rec["F_CODE"])
        if not code:
            continue

        # Provisionssätze + zugehörige Reps zusammenfassen
        splits = []
        for rate_field, rep_field in (
            ("PROVISION", "REP1"), ("PROV2", "REP2"), ("PROV3", "REP3"),
            ("PROV4", "REP4"), ("PROV5", "REP5"), ("PROV6", "REP6"),
        ):
            rate = num(rec.get(rate_field))
            rep = clean(rec.get(rep_field))
            if rate or rep:
                splits.append({"rate": float(rate) if rate is not None else 0.0,
                                "rep_code": rep})

        display_config = {
            k: clean(rec.get(k))
            for k in ("ME_GEWICHT", "BEZ_BREITE", "ME_BREITE", "ME_MENGE",
                      "BEZ_ART_NR", "BEZ_ARTIKE", "BEZ_FARBE", "BEZ_GEWICH",
                      "BEZ_NOTIZ", "BEZ_COMP", "LNGE_ARTNR", "LNGE_ARTIK", "LNGE_FARBE")
            if clean(rec.get(k)) is not None
        }

        rows.append((
            code,
            clean(rec["LIEFERANT"]) or code,
            clean(rec["LI_STRASSE"]),
            None,  # country_code - nicht direkt in HDFIRMA, ggf. später aus LI_STRASSE/HDADR ableiten
            clean(rec["LISTE1"]),
            psycopg2.extras.Json(splits) if splits else None,
            clean(rec["VERTRETER"]) or clean(rec["REP1"]),
            clean(rec["KONTAKT"]),
            psycopg2.extras.Json(display_config) if display_config else None,
        ))
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO suppliers
             (code, name, address, country_code, default_currency,
              provision_splits, representative_code, contact_person, display_config)
           VALUES %s
           ON CONFLICT (code) DO UPDATE SET
             name=EXCLUDED.name, address=EXCLUDED.address,
             default_currency=EXCLUDED.default_currency,
             provision_splits=EXCLUDED.provision_splits,
             representative_code=EXCLUDED.representative_code,
             contact_person=EXCLUDED.contact_person,
             display_config=EXCLUDED.display_config""",
        rows,
    )
    print(f"   {len(rows)} Lieferanten")
    # ACHTUNG: F_CODE 'BH' (siehe hdprovBH.dbf) ist NICHT Teil von HDFIRMA.
    # Wird unten in migrate_commission_history als Pseudo-Lieferant angelegt,
    # falls noch nicht vorhanden -- fachlich bitte klären!


def migrate_customers(cur, source: Path, encoding):
    print("-> customers (HDADR.DBF)")
    cur.execute("SELECT code FROM countries")
    valid_countries = {r[0] for r in cur.fetchall()}
    table = open_dbf(source / "HDADR.DBF", encoding)
    seen = {}
    for rec in table:
        code = clean(rec["CODE"])
        if not code:
            continue
        address_lines = [x for x in (
            clean(rec["FA_ADR1"]), clean(rec["FA_ADR2"]),
            clean(rec["FA_ADR3"]), clean(rec["FA_ADR4"]),
        ) if x]
        seen[code] = (
            code,
            clean(rec["KU_NR"]),
            clean(rec["FA_NAME"]) or code,
            psycopg2.extras.Json(address_lines) if address_lines else None,
            clean(rec["FA_LAND"]) if clean(rec["FA_LAND"]) in valid_countries else None,
            clean(rec["FA_PLZ"]),
            clean(rec["FA_ORT"]),
            clean(rec["FA_TEL"]),
            clean(rec["FA_FAX"]),
            clean(rec["FA_EMAIL"]),
            clean(rec["FA_URL"]),
            clean(rec["BRANCHE"]),
            clean(rec["SPRACHE"]),
            clean(rec["STEUERNR"]),
            clean(rec["NAME1"]),
            clean(rec["TITEL1"]),
            clean(rec["POS1"]),
            clean(rec["PRIORITAET"]),
        )
    rows = list(seen.values())
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO customers
             (code, ku_nr, name, address_lines, country_code, zip, city, phone, fax,
              email, url, branche, language, tax_number, contact_name, contact_title,
              contact_position, priority)
           VALUES %s
           ON CONFLICT (code) DO UPDATE SET
             ku_nr=EXCLUDED.ku_nr, name=EXCLUDED.name, address_lines=EXCLUDED.address_lines,
             country_code=EXCLUDED.country_code, zip=EXCLUDED.zip, city=EXCLUDED.city,
             phone=EXCLUDED.phone, fax=EXCLUDED.fax, email=EXCLUDED.email, url=EXCLUDED.url,
             branche=EXCLUDED.branche, language=EXCLUDED.language, tax_number=EXCLUDED.tax_number,
             contact_name=EXCLUDED.contact_name, contact_title=EXCLUDED.contact_title,
             contact_position=EXCLUDED.contact_position, priority=EXCLUDED.priority""",
        rows,
        page_size=500,
    )
    print(f"   {len(rows)} Kunden")


def migrate_exchange_rates(cur, source: Path, encoding):
    path = source / "HDKURSE.DBF"
    if not path.exists():
        return
    print("-> exchange_rates (HDKURSE.DBF)")
    table = open_dbf(path, encoding)
    rows = []
    for rec in table:
        currency = clean(rec.get("WAEHRUNG")) or clean(rec.get("WAEH"))
        date_ = rec.get("DATUM")
        rate = num(rec.get("KURS"))
        if not currency or not date_ or rate is None:
            continue
        rows.append((currency, date_, rate))
    if rows:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO exchange_rates (currency, valid_date, rate)
               VALUES %s ON CONFLICT (currency, valid_date) DO UPDATE SET rate=EXCLUDED.rate""",
            rows,
        )
    print(f"   {len(rows)} Kurse")


def migrate_users(cur, source: Path, encoding):
    path = source / "HDMITARB.DBF"
    if not path.exists():
        return
    print("-> users (HDMITARB.DBF)")
    table = open_dbf(path, encoding)
    rows = []
    for rec in table:
        login = clean(rec.get("LOGINNAME"))
        if not login:
            continue
        rows.append((
            login,
            clean(rec.get("FULLNAME")),
            None,  # Passwort NICHT übernehmen - neu setzen!
            clean(rec.get("CODE")),
            bool(rec.get("ENABLED")),
        ))
    if rows:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO users (login_name, full_name, password_hash, rep_code, is_enabled)
               VALUES %s ON CONFLICT (login_name) DO NOTHING""",
            rows,
        )
    print(f"   {len(rows)} Benutzer (Passwörter NICHT migriert!)")


# ------------------------------------------------------------------
# Lieferanten-/Jahres-Tabellen: {CODE}{YY}_INV / _BUD / _art
# ------------------------------------------------------------------

FILE_PATTERN = re.compile(r"^([A-Za-z]{2})(\d{2})_(INV|BUD|ART)\.DBF$", re.IGNORECASE)


def discover_yearly_files(source: Path):
    """Returns dict: {(supplier_code, year): {"INV": path, "BUD": path, "ART": path}}"""
    found = {}
    for path in source.iterdir():
        m = FILE_PATTERN.match(path.name)
        if not m:
            continue
        code, yy, kind = m.group(1).upper(), m.group(2), m.group(3).upper()
        year = 2000 + int(yy)
        found.setdefault((code, year), {})[kind] = path
    return found


def get_supplier_map(cur):
    cur.execute("SELECT code, id FROM suppliers")
    return dict(cur.fetchall())


def get_customer_map(cur):
    cur.execute("SELECT code, id FROM customers")
    return dict(cur.fetchall())


def migrate_articles(cur, supplier_id, path, encoding):
    table = open_dbf(path, encoding)
    rows = []
    for rec in table:
        art_nr = clean(rec.get("ART_NR"))
        if not art_nr:
            continue
        prices = {k: float(num(rec.get(k))) for k in
                  ("PREIS1", "PREIS2", "PREIS3", "PREIS4", "PREIS5",
                   "PREIS11", "PREIS12", "PREIS13", "PREIS14", "PREIS15")
                  if num(rec.get(k)) is not None}
        if clean(rec.get("CURR1")):
            prices["CURR1"] = clean(rec.get("CURR1"))
        if clean(rec.get("CURR11")):
            prices["CURR11"] = clean(rec.get("CURR11"))

        splits = []
        for rate_field, rep_field in (
            ("PROVISION", "REP1"), ("PROV2", "REP2"), ("PROV3", "REP3"),
            ("PROV4", "REP4"), ("PROV5", "REP5"), ("PROV6", "REP6"),
        ):
            rate = num(rec.get(rate_field))
            rep = clean(rec.get(rep_field))
            if rate or rep:
                splits.append({"rate": float(rate) if rate is not None else 0.0, "rep_code": rep})

        rows.append((
            supplier_id, art_nr,
            clean(rec.get("ARTIKEL")), clean(rec.get("ART_NOTIZ")),
            clean(rec.get("FARBE")), clean(rec.get("COMP")),
            clean(rec.get("GEWICHT")), clean(rec.get("BREITE")),
            clean(rec.get("SAISON")), rec.get("KATEGORIE"),
            rec.get("GUELTIG"),
            psycopg2.extras.Json(prices) if prices else None,
            psycopg2.extras.Json(splits) if splits else None,
        ))
    if rows:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO articles
                 (supplier_id, art_nr, name, notes, color, composition, weight, width,
                  season, category, valid_from, prices, provision_splits)
               VALUES %s
               ON CONFLICT (supplier_id, art_nr) DO UPDATE SET
                 name=EXCLUDED.name, notes=EXCLUDED.notes, color=EXCLUDED.color,
                 composition=EXCLUDED.composition, weight=EXCLUDED.weight, width=EXCLUDED.width,
                 season=EXCLUDED.season, category=EXCLUDED.category, valid_from=EXCLUDED.valid_from,
                 prices=EXCLUDED.prices, provision_splits=EXCLUDED.provision_splits""",
            rows,
        )
    return len(rows)


def migrate_transactions(cur, supplier_id, customer_map, year, path, encoding):
    table = open_dbf(path, encoding)
    rows = []
    skipped = 0
    for rec in table:
        ku_nr_code = clean(rec.get("CODE"))  # Kundencode (HDADR.CODE)
        customer_id = customer_map.get(ku_nr_code) if ku_nr_code else None

        total = num(rec.get("TOTAL_S"))
        date_ = rec.get("DATUM")
        if total is None or date_ is None:
            skipped += 1
            continue

        splits = []
        for rate_field, rep_field in (
            ("PROV2", "REP2"), ("PROV3", "REP3"), ("PROV4", "REP4"),
            ("PROV5", "REP5"), ("PROV6", "REP6"),
        ):
            rate = num(rec.get(rate_field))
            rep = clean(rec.get(rep_field))
            if rate or rep:
                splits.append({"rate": float(rate) if rate is not None else 0.0, "rep_code": rep})

        notes = " | ".join(x for x in (
            clean(rec.get("NOTIZ1")), clean(rec.get("NOTIZ2")), clean(rec.get("NOTIZ3"))
        ) if x) or None

        rows.append((
            supplier_id, customer_id, year,
            clean(rec.get("NUMMER")) or "",
            date_,
            clean(rec.get("ART_NR")), clean(rec.get("FARBE")),
            num(rec.get("MENGE")), clean(rec.get("ME_MENGE")),
            num(rec.get("RABATT")), num(rec.get("PROVISION")),
            psycopg2.extras.Json(splits) if splits else None,
            num(rec.get("PREIS")), clean(rec.get("WAEHRUNG")),
            total, num(rec.get("KURS"), default=1),
            clean(rec.get("CUST_ORDNO")), notes,
        ))
    if rows:
        cur.execute("DELETE FROM transactions WHERE supplier_id = %s AND year = %s",
                    (rows[0][0], rows[0][2]))
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO transactions
                 (supplier_id, customer_id, year, invoice_number, invoice_date, art_nr, color,
                  quantity, unit, discount, provision_rate, provision_splits, price, currency,
                  total_amount, exchange_rate, customer_order_no, notes)
               VALUES %s""",
            rows,
            page_size=500,
        )
    return len(rows), skipped


def migrate_budgets(cur, supplier_id, customer_map, year, path, encoding):
    """_BUD-Dateien enthalten das Budget des jeweiligen Jahres je Kunde/Artikel
    (Jahreswerte, keine Monatsaufteilung)."""
    table = open_dbf(path, encoding)
    seen = {}
    for rec in table:
        code = clean(rec.get("CODE"))
        customer_id = customer_map.get(code) if code else None
        art_nr = clean(rec.get("ART_NR"))

        values = (
            num(rec.get("MENGE_LJ")), num(rec.get("PREIS_LJ")), num(rec.get("TOTAL_S_LJ")),
            num(rec.get("MENGE_BUD")), num(rec.get("MENGE_BKG")), num(rec.get("PREIS_BUD")),
            num(rec.get("TOTAL_S_BU")), num(rec.get("TOTAL_S_B1")),
        )
        if all(v is None for v in values):
            continue

        key = (supplier_id, year, customer_id, art_nr)
        seen[key] = (
            supplier_id, year, customer_id, art_nr, rec.get("KATEGORIE"),
            clean(rec.get("WAEHRUNG")), *values,
        )
    rows = list(seen.values())
    if rows:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO budgets
                 (supplier_id, year, customer_id, art_nr, category, currency,
                  quantity_prev_year, price_prev_year, amount_prev_year,
                  quantity_budget, quantity_forecast, price_budget,
                  amount_budget, amount_budget_alt)
               VALUES %s
               ON CONFLICT (supplier_id, year, customer_id, art_nr) DO UPDATE SET
                 category=EXCLUDED.category, currency=EXCLUDED.currency,
                 quantity_prev_year=EXCLUDED.quantity_prev_year,
                 price_prev_year=EXCLUDED.price_prev_year,
                 amount_prev_year=EXCLUDED.amount_prev_year,
                 quantity_budget=EXCLUDED.quantity_budget,
                 quantity_forecast=EXCLUDED.quantity_forecast,
                 price_budget=EXCLUDED.price_budget,
                 amount_budget=EXCLUDED.amount_budget,
                 amount_budget_alt=EXCLUDED.amount_budget_alt""",
            rows,
        )
    return len(rows)


def migrate_yearly_data(cur, source: Path, encoding):
    print("-> Lieferanten-/Jahresdaten ({CODE}YY_INV/BUD/ART.DBF)")
    supplier_map = get_supplier_map(cur)
    customer_map = get_customer_map(cur)
    files = discover_yearly_files(source)

    total_tx, total_skip, total_art, total_bud = 0, 0, 0, 0
    unknown_suppliers = set()

    for (code, year), kinds in sorted(files.items()):
        supplier_id = supplier_map.get(code)
        if supplier_id is None:
            unknown_suppliers.add(code)
            continue
        if "INV" in kinds:
            n, skipped = migrate_transactions(cur, supplier_id, customer_map, year, kinds["INV"], encoding)
            total_tx += n
            total_skip += skipped
        if "ART" in kinds:
            total_art += migrate_articles(cur, supplier_id, kinds["ART"], encoding)
        if "BUD" in kinds:
            total_bud += migrate_budgets(cur, supplier_id, customer_map, year, kinds["BUD"], encoding)

    print(f"   {total_tx} Transaktionen importiert ({total_skip} Zeilen ohne Datum/Betrag übersprungen)")
    print(f"   {total_art} Artikel importiert")
    print(f"   {total_bud} Budget-Zeilen importiert")
    if unknown_suppliers:
        print(f"   WARNUNG: Lieferanten-Codes ohne HDFIRMA-Eintrag übersprungen: "
              f"{sorted(unknown_suppliers)}")


# ------------------------------------------------------------------
# Historische Provisionsabrechnungen: hdprovBH.dbf
# ------------------------------------------------------------------

def migrate_commission_history(cur, source: Path, encoding):
    path = source / "hdprovBH.dbf"
    if not path.exists():
        return
    print("-> commission_statements / items (hdprovBH.dbf)")

    supplier_map = get_supplier_map(cur)
    customer_map = get_customer_map(cur)

    table = open_dbf(path, encoding)

    # Gruppieren nach (F_CODE, NUMMER, DATUM) als "eine Abrechnung"
    # F_CODE='BH' wird ausgelassen (kein echter Lieferant, siehe HDFIRMA).
    groups = {}
    skipped_bh = 0
    for rec in table:
        f_code = clean(rec.get("F_CODE"))
        if f_code == "BH":
            skipped_bh += 1
            continue
        key = (f_code, clean(rec.get("NUMMER")), rec.get("DATUM"))
        groups.setdefault(key, []).append(rec)

    n_statements, n_items, n_unknown = 0, 0, 0
    for (f_code, nummer, datum), recs in groups.items():
        supplier_id = supplier_map.get(f_code)
        if supplier_id is None:
            n_unknown += len(recs)
            continue
        total_amount = sum((num(r.get("TOTAL_S")) or 0) for r in recs)
        total_prov = sum((num(r.get("TOTAL_P")) or 0) for r in recs)
        currency = clean(recs[0].get("WAEHRUNG"))

        cur.execute(
            """INSERT INTO commission_statements
                 (supplier_id, statement_number, period_from, period_to, statement_date,
                  status, total_amount, total_provision, currency)
               VALUES (%s, %s, %s, %s, %s, 'issued', %s, %s, %s)
               ON CONFLICT (statement_number) DO NOTHING
               RETURNING id""",
            (supplier_id, nummer or None, datum, datum, datum,
             total_amount, total_prov, currency),
        )
        result = cur.fetchone()
        if result is None:
            # statement_number war NULL oder Duplikat -> trotzdem ohne Nummer anlegen
            cur.execute(
                """INSERT INTO commission_statements
                     (supplier_id, statement_number, period_from, period_to, statement_date,
                      status, total_amount, total_provision, currency)
                   VALUES (%s, NULL, %s, %s, %s, 'issued', %s, %s, %s)
                   RETURNING id""",
                (supplier_id, datum, datum, datum, total_amount, total_prov, currency),
            )
            result = cur.fetchone()
        statement_id = result[0]
        n_statements += 1

        item_rows = []
        for r in recs:
            customer_code = clean(r.get("CODE"))
            item_rows.append((
                statement_id,
                customer_map.get(customer_code),
                num(r.get("PROVISION")),
                num(r.get("TOTAL_S")) or 0,
                num(r.get("TOTAL_P")) or 0,
                clean(r.get("WAEHRUNG")),
                clean(r.get("WAEHRUNG1")),
                num(r.get("TOTAL_S1")),
                num(r.get("TOTAL_P1")),
                num(r.get("KURS"), default=1),
                clean(r.get("REP")),
                clean(r.get("PROVART")),
            ))
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO commission_statement_items
                 (statement_id, customer_id, provision_rate, total_amount, provision_amount,
                  currency, currency2, total_amount2, provision_amount2, exchange_rate,
                  rep_code, provision_type)
               VALUES %s""",
            item_rows,
        )
        n_items += len(item_rows)

    print(f"   {n_statements} Abrechnungen, {n_items} Positionen (historisch, aus hdprovBH)")
    if skipped_bh:
        print(f"   {skipped_bh} Zeilen mit F_CODE='BH' uebersprungen (kein Lieferant in HDFIRMA)")
    if n_unknown:
        print(f"   {n_unknown} Zeilen mit unbekanntem F_CODE uebersprungen")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="Verzeichnis mit .dbf-Dateien")
    parser.add_argument("--dsn", required=True, help="PostgreSQL DSN, z.B. postgresql://localhost/winagent")
    parser.add_argument("--encoding", default="latin1")
    args = parser.parse_args()

    if not args.source.is_dir():
        sys.exit(f"Quellverzeichnis nicht gefunden: {args.source}")

    conn = psycopg2.connect(args.dsn)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        migrate_countries(cur, args.source, args.encoding)
        migrate_representatives(cur, args.source, args.encoding)
        migrate_suppliers(cur, args.source, args.encoding)
        migrate_customers(cur, args.source, args.encoding)
        migrate_exchange_rates(cur, args.source, args.encoding)
        migrate_users(cur, args.source, args.encoding)
        migrate_yearly_data(cur, args.source, args.encoding)
        migrate_commission_history(cur, args.source, args.encoding)
        conn.commit()
        print("\nMigration erfolgreich abgeschlossen.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
