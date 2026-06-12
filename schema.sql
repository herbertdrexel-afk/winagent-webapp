-- ============================================================
-- WinAgent → Webapp – PostgreSQL Schema
-- Normalisierte Ablösung der dBase-Struktur (HDFIRMA, HDADR,
-- {CODE}YY_INV/BUD/ART, hdprovBH, HDSTAT, HDLAND, HDVERT, ...)
-- ============================================================

-- ---------- Stammdaten ----------

CREATE TABLE countries (
    code            VARCHAR(3) PRIMARY KEY,     -- HDLAND.FA_LAND
    name            VARCHAR(50) NOT NULL,
    language        CHAR(1),                    -- D/E/...
    vat_rate        NUMERIC(5,2),               -- HDLAND.MWSTEUER
    invoice_texts   JSONB                       -- diverse Sprach-/Textbausteine aus HDLAND
);

CREATE TABLE representatives (                  -- HDVERT.DBF
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(2) UNIQUE NOT NULL,
    name            VARCHAR(60),
    address         JSONB,                      -- FA_*, BA_* Felder
    bank_account    VARCHAR(40),
    bank_blz        VARCHAR(20),
    currency        VARCHAR(3),
    mail_to         VARCHAR(100),
    mail_cc         VARCHAR(100),
    mail_bcc        VARCHAR(100),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE suppliers (                        -- HDFIRMA.DBF (Lieferanten)
    id                  SERIAL PRIMARY KEY,
    code                VARCHAR(2) UNIQUE NOT NULL,   -- F_CODE
    name                VARCHAR(60) NOT NULL,         -- LIEFERANT
    address             VARCHAR(60),                  -- LI_STRASSE
    country_code        VARCHAR(3) REFERENCES countries(code),
    default_currency    VARCHAR(3),                   -- LISTE1
    -- Provisionssätze inkl. evtl. Aufteilungen auf mehrere Vertreter
    -- [{ "rate": 5.0, "rep_code": "NA" }, { "rate": 0, "rep_code": "" }, ...]
    provision_splits    JSONB,
    representative_code VARCHAR(2) REFERENCES representatives(code),
    contact_person      VARCHAR(60),
    -- Layout-/Bezeichnungs-Konfiguration für Artikel-Anzeige (BEZ_*, ME_*, etc.)
    display_config      JSONB,
    is_active           BOOLEAN DEFAULT TRUE,
    notes               TEXT
);

CREATE TABLE customers (                        -- HDADR.DBF (Kunden)
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(6) UNIQUE NOT NULL,  -- CODE (z.B. ALLSPO)
    ku_nr           VARCHAR(4),                  -- KU_NR
    name            VARCHAR(50) NOT NULL,        -- FA_NAME
    address_lines   JSONB,                       -- FA_ADR1..4
    country_code    VARCHAR(3) REFERENCES countries(code),
    zip             VARCHAR(8),
    city            VARCHAR(50),
    phone           VARCHAR(20),
    fax             VARCHAR(20),
    email           VARCHAR(40),
    url             VARCHAR(40),
    branche         VARCHAR(20),
    language        CHAR(1),
    tax_number      VARCHAR(20),
    contact_name    VARCHAR(24),
    contact_title   VARCHAR(3),
    contact_position VARCHAR(15),
    priority        CHAR(1),
    notes           TEXT
);

CREATE TABLE articles (                         -- {CODE}YY_art.DBF
    id              SERIAL PRIMARY KEY,
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),
    art_nr          VARCHAR(20) NOT NULL,
    name            VARCHAR(50),
    notes           VARCHAR(30),
    color           VARCHAR(15),
    composition     VARCHAR(20),
    weight          VARCHAR(7),
    width           VARCHAR(7),
    season          VARCHAR(8),
    category        SMALLINT,
    valid_from      DATE,
    prices          JSONB,      -- PREIS1-5, PREIS11-15, CURR1, CURR11
    provision_splits JSONB,     -- PROVISION, PROV2-6, REP1-6
    UNIQUE (supplier_id, art_nr)
);

CREATE TABLE exchange_rates (                   -- HDKURSE.DBF
    id              SERIAL PRIMARY KEY,
    currency        VARCHAR(3) NOT NULL,
    valid_date      DATE NOT NULL,
    rate            NUMERIC(12,5) NOT NULL,
    UNIQUE (currency, valid_date)
);

CREATE TABLE users (                            -- HDMITARB.DBF
    id              SERIAL PRIMARY KEY,
    login_name      VARCHAR(20) UNIQUE NOT NULL,
    full_name       VARCHAR(60),
    password_hash   VARCHAR(255),               -- ACHTUNG: alte Passwörter neu setzen!
    rep_code        VARCHAR(2),
    is_enabled      BOOLEAN DEFAULT TRUE,
    last_login      TIMESTAMP
);

-- ---------- Bewegungsdaten ----------

-- Ersetzt ALLE {CODE}YY_INV.DBF Dateien (alle Lieferanten, alle Jahre)
CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),
    customer_id     INTEGER REFERENCES customers(id),
    year            SMALLINT NOT NULL,           -- aus Dateiname {CODE}YY_INV
    invoice_number  VARCHAR(10) NOT NULL,        -- NUMMER
    invoice_date    DATE NOT NULL,               -- DATUM
    art_nr          VARCHAR(20),
    color           VARCHAR(15),
    quantity        NUMERIC(11,2),               -- MENGE
    unit            VARCHAR(2),                  -- ME_MENGE
    discount        NUMERIC(8,2),                -- RABATT
    provision_rate  NUMERIC(8,2),                -- PROVISION
    provision_splits JSONB,                      -- PROV2-6 + REP1-6
    price           NUMERIC(10,3),               -- PREIS
    currency        VARCHAR(3),
    total_amount    NUMERIC(13,2) NOT NULL,      -- TOTAL_S
    exchange_rate   NUMERIC(12,5) DEFAULT 1,     -- KURS
    customer_order_no VARCHAR(20),               -- CUST_ORDNO
    notes           TEXT,                        -- NOTIZ1-3 zusammengefasst
    created_at      TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_transactions_supplier_year ON transactions(supplier_id, year);
CREATE INDEX idx_transactions_customer ON transactions(customer_id);
CREATE INDEX idx_transactions_date ON transactions(invoice_date);

-- Ersetzt ALLE {CODE}YY_BUD.DBF Dateien.
-- Die _BUD-Dateien enthalten das Budget des jeweiligen Jahres je
-- Kunde + Artikel (keine Monatsaufteilung wie HDFIRMA.BUD1-12).
CREATE TABLE budgets (
    id              SERIAL PRIMARY KEY,
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),
    year            SMALLINT NOT NULL,
    customer_id     INTEGER REFERENCES customers(id),
    art_nr          VARCHAR(20),
    category        SMALLINT,
    currency        VARCHAR(3),
    -- Vorjahreswerte (zum Vergleich, _LJ Felder)
    quantity_prev_year  NUMERIC(11,2),
    price_prev_year     NUMERIC(11,2),
    amount_prev_year    NUMERIC(13,2),
    -- Budget für das Jahr selbst (_BUD/_BKG/_BU/_B1 Felder)
    quantity_budget     NUMERIC(11,2),
    quantity_forecast   NUMERIC(11,2),  -- MENGE_BKG
    price_budget        NUMERIC(11,2),
    amount_budget       NUMERIC(13,2),  -- TOTAL_S_BU
    amount_budget_alt   NUMERIC(13,2),  -- TOTAL_S_B1
    UNIQUE (supplier_id, year, customer_id, art_nr)
);

-- ---------- Provisionsabrechnung ----------

-- Header: eine Zeile pro gedruckter Provisionsrechnung (PR-Nummer)
CREATE TABLE commission_statements (
    id              SERIAL PRIMARY KEY,
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),
    statement_number VARCHAR(15) UNIQUE,         -- z.B. PR26-0174 (NULL = noch nicht gedruckt = "draft")
    period_from     DATE NOT NULL,
    period_to       DATE NOT NULL,
    statement_date  DATE,                        -- Datum des Drucks
    status          VARCHAR(10) NOT NULL DEFAULT 'draft',  -- draft | issued
    total_amount    NUMERIC(13,2),               -- Summe TOTAL_S
    total_provision NUMERIC(13,2),               -- Summe Provisionsbetrag
    currency        VARCHAR(3),
    created_at      TIMESTAMP DEFAULT now()
);

-- Positionen: eine Zeile pro Kunde + Provisionssatz innerhalb einer Abrechnung
CREATE TABLE commission_statement_items (
    id              BIGSERIAL PRIMARY KEY,
    statement_id    INTEGER NOT NULL REFERENCES commission_statements(id) ON DELETE CASCADE,
    customer_id     INTEGER REFERENCES customers(id),
    provision_rate  NUMERIC(8,2),
    total_amount    NUMERIC(13,2) NOT NULL,      -- Umsatzbasis (TOTAL_S)
    provision_amount NUMERIC(13,2) NOT NULL,     -- TOTAL_P
    currency        VARCHAR(3),
    currency2       VARCHAR(3),                  -- WAEHRUNG1 / TOTAL_P1/TOTAL_S1
    total_amount2   NUMERIC(13,2),
    provision_amount2 NUMERIC(13,2),
    exchange_rate   NUMERIC(12,5) DEFAULT 1,
    rep_code        VARCHAR(2),
    provision_type  CHAR(1)                      -- PROVART
);

CREATE INDEX idx_csi_statement ON commission_statement_items(statement_id);
CREATE INDEX idx_cs_supplier ON commission_statements(supplier_id);

-- ---------- Konfiguration ----------

CREATE TABLE app_settings (
    key             VARCHAR(50) PRIMARY KEY,
    value           JSONB NOT NULL
);

-- Beispiel-Eintrag für den Rechnungsnummern-Zähler (ersetzt HDPARAM.UBW_NR):
-- INSERT INTO app_settings (key, value)
--   VALUES ('commission_statement_number', '{"prefix": "PR", "year": 26, "next_seq": 175}');
