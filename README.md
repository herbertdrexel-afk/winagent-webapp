# WinAgent → Webapp Migration

Neuentwicklung des Provisions-/Lieferanten-Verwaltungssystems
(bisher: Delphi + dBase) als Web-App.

Dieses Projekt ist als **Startpunkt für Claude Code** gedacht – Konzept,
Datenbankschema, Migrationsskript und ein lauffähiges Backend-Skelett
sind enthalten. Vieles ist noch nicht fertig (s. "Offene Punkte" unten).

## 1. Architektur

- **Backend**: Python / FastAPI + SQLAlchemy
- **Datenbank**: PostgreSQL
- **Frontend**: React + TypeScript (noch nicht angelegt – Schritt 2)
- **Migration**: einmaliges Python-Skript (`migration/migrate.py`), liest
  alle `.dbf`-Dateien via `dbfread` und befüllt PostgreSQL

## 2. Mapping Alt → Neu (Kernidee)

Das alte System legt für **jeden Lieferanten pro Jahr** eigene Dateien an
(`AM25_INV.DBF`, `AM26_INV.DBF`, `SE25_INV.DBF`, ...). Das war eine
technische Notwendigkeit von dBase, fachlich aber unnötig.

**Neu**: eine zentrale Tabelle `transactions`, mit `supplier_id` + `year`
als normale Spalten. Filterung/Aggregation nach Lieferant, Jahr, Kunde,
Monat etc. wird dann zu ganz normalen SQL-Queries statt "welche Datei
muss ich öffnen".

| Alt (dBase)                          | Neu (PostgreSQL)                |
|---------------------------------------|----------------------------------|
| `HDFIRMA.DBF`                          | `suppliers`                      |
| `HDADR.DBF`                            | `customers`                      |
| `HDLAND.DBF`                           | `countries`                      |
| `HDVERT.DBF`                           | `representatives`                |
| `HDKURSE.DBF`                          | `exchange_rates`                 |
| `{CODE}YY_INV.DBF` (alle Lieferanten/Jahre) | `transactions`              |
| `{CODE}YY_BUD.DBF`                     | `budgets`                         |
| `{CODE}YY_art.DBF`                     | `articles`                        |
| `HDSTAT.DBF`                           | wird **berechnet** (View/Query), nicht mehr separat gespeichert |
| `hdprovBH.dbf`, `HDINVPRO.DBF`, `HDINVPEX.DBF` | `commission_statements` + `commission_statement_items` (historische Abrechnungen) |
| `HDPARAM.DBF` (Zähler, Pfade, Konfig)  | `app_settings` (Key/Value) + Sequenzen in Postgres |
| `HDMITARB.DBF`                         | `users`                           |

## 3. Provisionsabrechnung – Workflow (so wie im alten System beschrieben)

1. Lieferant + Zeitraum auswählen → System liest `transactions` für
   diesen Lieferanten/Zeitraum.
2. Aggregation pro Kunde + Provisionssatz → Vorschau "Aufstellung".
3. Bestätigen → Anlegen eines `commission_statements`-Datensatzes
   (Status `draft`).
4. Drucken → Rechnungsnummer (`PR{Jahr}-{laufende Nummer}`) und
   Rechnungsdatum vergeben, Status → `issued`. Nummernkreis kommt aus
   `app_settings` (ersetzt `HDPARAM.UBW_NR`).
5. Rechnung bleibt jederzeit erneut druckbar/einsehbar
   (`commission_statements` + `commission_statement_items`).

## 4. Setup (lokal, für Claude Code)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Datenbank anlegen
createdb winagent
psql winagent < ../schema.sql

# Migration ausführen (Pfad zu den .dbf-Dateien anpassen!)
python ../migration/migrate.py --source /pfad/zu/dbf-dateien --dsn postgresql://localhost/winagent

# Backend starten
uvicorn app.main:app --reload
```

## 5. Offene Punkte / Entscheidungen, die noch zu treffen sind

- **`hdprovBH.dbf`**: Zeilen mit `F_CODE = 'BH'` werden bei der Migration
  übersprungen (kein Lieferant in `HDFIRMA`, kein Pseudo-Lieferant mehr
  angelegt).
- **HDINVPRO.DBF / HDINVPEX.DBF**: laut Rückmeldung sind das
  **Reporting-Staging-Tabellen** – das alte System schreibt beim
  Generieren der Statistik/Abrechnung die relevanten Datensätze dort
  hinein, damit der R&R-Report sie ausliest. In der neuen Lösung
  übernimmt das der `/commission/{code}/statistic`-Endpoint **on the
  fly** per SQL-Aggregation (siehe `commission.py`) – eine
  Staging-Tabelle ist nicht mehr nötig. Beide Dateien werden daher
  **nicht migriert**.
- ~~Mehrfach-Provisionssätze...~~ (siehe oben, als JSON modelliert)
- **Budgets (`_BUD`-Dateien)**: enthalten das Budget des jeweiligen Jahres
  je Kunde/Artikel (Jahreswerte inkl. Vorjahresvergleich `_LJ`,
  Budget `_BUD/_BKG/_B1`) – **keine** Monatsaufteilung wie in
  `HDFIRMA.BUD1-12`. Ist entsprechend in `budgets` abgebildet (geklärt).
- **HDSTAT** (Monatsstatistik) wird in der neuen Lösung **on the fly**
  aus `transactions` berechnet statt gespeichert. Falls historische
  Stände (z.B. Stand zum Quartalsende, der sich später nicht mehr
  ändern darf) erhalten bleiben müssen, braucht es ein
  Snapshot-Konzept.
- **HDINVPRO / HDINVPEX**: Struktur ist nahezu identisch zu
  `hdprovBH` bzw. den `_INV`-Tabellen – im Migrationsskript aktuell
  als Platzhalter markiert, muss inhaltlich noch eingeordnet werden
  (offene Posten? Export-Snapshot?).
- **Encoding**: Die dBase-Dateien sind `latin1`/`cp850`-codiert
  (Umlaute!). Migration konvertiert nach UTF-8 – bitte nach der
  Migration stichprobenhaft auf kaputte Sonderzeichen prüfen.
- **Mehrwährung**: `transactions.amount` + `currency` +
  `exchange_rate` werden 1:1 übernommen. Ob Provisionsbeträge in
  Fremdwährung oder immer in EUR ausgewiesen werden sollen, ist im
  Frontend/Report noch zu definieren.
- **Frontend** existiert noch nicht – nur Backend-Grundgerüst
  (Health-Check + Supplier/Customer-Endpoints als Beispiel).

## 6. Nächste sinnvolle Schritte in Claude Code

1. Migrationsskript gegen die **echten, vollständigen** .dbf-Bestände
   laufen lassen (alle Jahre, alle Lieferanten) und Datenqualität
   prüfen (besonders die offenen Punkte oben).
2. Endpoints für Provisionsabrechnung (Statistik generieren, Abrechnung
   anlegen, Rechnungsnummer vergeben, PDF-Druck) implementieren.
3. React-Frontend: Lieferantenauswahl, Statistik-Ansicht,
   Rechnungsliste/-detail, Auswertungen über alle Lieferanten.
