-- Esquema de la base de datos PTR Analysis (SQLite).
-- Se aplica de forma idempotente desde backend/db/database.py::init_db().

-- Indice de presentaciones (Financial Disclosure index, {year}FD.txt).
CREATE TABLE IF NOT EXISTS filings (
    doc_id        TEXT PRIMARY KEY,
    prefix        TEXT,
    last_name     TEXT NOT NULL,
    first_name    TEXT,
    suffix        TEXT,
    filing_type   TEXT NOT NULL,        -- P, C, A, D, O, W, X, T
    state_dst     TEXT,                 -- ej. CA11
    year          INTEGER NOT NULL,
    filing_date   TEXT,                 -- ISO YYYY-MM-DD
    pdf_url       TEXT,                 -- solo para PTR (tipo P)
    downloaded    INTEGER NOT NULL DEFAULT 0,
    parsed        INTEGER NOT NULL DEFAULT 0,
    ingested_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_filings_type ON filings(filing_type);
CREATE INDEX IF NOT EXISTS idx_filings_year ON filings(year);

-- Transacciones extraidas de cada PTR (se llena en la Fase 3 - parsing).
CREATE TABLE IF NOT EXISTS transactions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id            TEXT NOT NULL REFERENCES filings(doc_id),
    owner             TEXT,             -- SP / DC / JT (self/spouse/joint)
    asset_name        TEXT,
    ticker            TEXT,
    asset_type        TEXT,             -- codigo del activo: ST, GS, OP, VA, ...
    tx_type           TEXT,             -- P (purchase) / S (sale) / E (exchange)
    tx_date           TEXT,             -- ISO YYYY-MM-DD
    notification_date TEXT,
    amount_min        REAL,             -- limite inferior del rango declarado
    amount_max        REAL,             -- limite superior del rango declarado
    raw_amount        TEXT,             -- texto original del rango (auditoria)
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tx_doc ON transactions(doc_id);
CREATE INDEX IF NOT EXISTS idx_tx_ticker ON transactions(ticker);

-- Precios de mercado cacheados por ticker/fecha (Fase 4).
CREATE TABLE IF NOT EXISTS prices (
    ticker      TEXT NOT NULL,
    price_date  TEXT NOT NULL,          -- ISO YYYY-MM-DD
    close       REAL,
    source      TEXT,
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, price_date)
);
