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
    price_at_tx       REAL,             -- cierre en/antes de tx_date (precio "de compra")
    price_current     REAL,             -- ultimo cierre conocido
    return_pct        REAL,             -- variacion: price_current/price_at_tx - 1
    est_gain_min      REAL,             -- ganancia/perdida estimada (extremo bajo del rango)
    est_gain_max      REAL,             -- ganancia/perdida estimada (extremo alto del rango)
    price_status      TEXT,             -- ok / no_ticker / no_price
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

-- Resumen por congresista (derivado; se reconstruye en la Fase 5).
CREATE TABLE IF NOT EXISTS members (
    member_key   TEXT PRIMARY KEY,
    last_name    TEXT,
    first_name   TEXT,
    state_dst    TEXT,
    n_tx         INTEGER,
    n_buys       INTEGER,
    n_sells      INTEGER,
    n_tickers    INTEGER,
    invested_min REAL,                  -- suma de rangos de compra (extremo bajo)
    invested_max REAL,
    est_gain_min REAL,                  -- P/L estimado total (compras valuadas)
    est_gain_max REAL,
    win_rate     REAL,                  -- fraccion de compras valuadas con retorno > 0
    built_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Posicion neta estimada por congresista y ticker (derivado).
CREATE TABLE IF NOT EXISTS positions (
    member_key    TEXT,
    ticker        TEXT,
    last_name     TEXT,
    first_name    TEXT,
    state_dst     TEXT,
    n_buys        INTEGER,
    n_sells       INTEGER,
    buy_value     REAL,                 -- suma de puntos medios de compras ($)
    sell_value    REAL,                 -- suma de puntos medios de ventas ($)
    net_value     REAL,                 -- buy_value - sell_value (posicion neta est. $)
    est_gain_min  REAL,
    est_gain_max  REAL,
    return_pct    REAL,                 -- variacion media del activo desde las operaciones
    price_current REAL,
    PRIMARY KEY (member_key, ticker)
);
CREATE INDEX IF NOT EXISTS idx_positions_member ON positions(member_key);

-- Pesos del portafolio optimo (media-varianza) calculado por scripts/run_optimal.py.
CREATE TABLE IF NOT EXISTS optimal_weights (
    ticker      TEXT PRIMARY KEY,
    weight      REAL,                   -- fraccion del portafolio (0..1)
    exp_return  REAL,                   -- retorno anualizado esperado del activo
    volatility  REAL,                   -- volatilidad anualizada del activo
    computed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Una sola fila (id=1) con las metricas del portafolio optimo agregado.
CREATE TABLE IF NOT EXISTS optimal_meta (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    exp_return   REAL,                  -- retorno anualizado del portafolio
    volatility   REAL,                  -- volatilidad anualizada del portafolio
    sharpe       REAL,                  -- ratio de Sharpe (rf = 0)
    n_assets     INTEGER,               -- activos en el universo optimizado
    lookback_days INTEGER,              -- ventana de historial usada
    computed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
