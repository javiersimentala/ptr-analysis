"""Pruebas de la Fase 4 (precios y P/L) con un proveedor simulado, sin red."""
import sqlite3

from backend.db import database
from backend.market import prices

# Serie de cierres simulada: 2025-01-10 = 100, actual (2025-06-02) = 150 (+50%).
SERIES = [
    ("2025-01-09", 100.0),
    ("2025-01-10", 100.0),
    ("2025-01-13", 110.0),
    ("2025-06-02", 150.0),
]


def fake_fetcher(ticker, start, end):
    return [] if ticker == "NODATA" else list(SERIES)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    database.init_db(conn)
    conn.execute("INSERT INTO filings (doc_id, last_name, filing_type, year) VALUES ('D1','X','P',2026)")
    conn.commit()
    return conn


def _add_tx(conn, ticker, tx_type="P", tx_date="2025-01-10", amin=1001, amax=15000):
    conn.execute(
        "INSERT INTO transactions (doc_id, ticker, asset_type, tx_type, tx_date, amount_min, amount_max) "
        "VALUES ('D1', ?, 'ST', ?, ?, ?, ?)",
        (ticker, tx_type, tx_date, amin, amax),
    )
    conn.commit()


def test_compra_valuada():
    conn = _conn()
    _add_tx(conn, "AAPL")
    stats = prices.enrich_all(conn=conn, fetcher=fake_fetcher, today="2025-06-02")

    row = conn.execute("SELECT * FROM transactions").fetchone()
    assert row["price_at_tx"] == 100.0
    assert row["price_current"] == 150.0
    assert abs(row["return_pct"] - 0.5) < 1e-9
    assert abs(row["est_gain_min"] - 500.5) < 1e-6      # 1001 * 0.5
    assert abs(row["est_gain_max"] - 7500.0) < 1e-6     # 15000 * 0.5
    assert row["price_status"] == "ok"
    assert stats["priced"] == 1


def test_venta_sin_ganancia_estimada():
    conn = _conn()
    _add_tx(conn, "AAPL", tx_type="S")
    prices.enrich_all(conn=conn, fetcher=fake_fetcher, today="2025-06-02")

    row = conn.execute("SELECT * FROM transactions").fetchone()
    assert row["price_status"] == "ok"
    assert row["return_pct"] is not None          # variación informativa sí se calcula
    assert row["est_gain_min"] is None            # pero no hay ganancia no realizada
    assert row["est_gain_max"] is None


def test_sin_ticker():
    conn = _conn()
    conn.execute(
        "INSERT INTO transactions (doc_id, ticker, tx_type, tx_date, amount_min, amount_max) "
        "VALUES ('D1', NULL, 'P', '2025-01-10', 1001, 15000)"
    )
    conn.commit()
    stats = prices.enrich_all(conn=conn, fetcher=fake_fetcher, today="2025-06-02")
    assert conn.execute("SELECT price_status FROM transactions").fetchone()[0] == "no_ticker"
    assert stats["no_ticker"] == 1


def test_ticker_sin_datos():
    conn = _conn()
    _add_tx(conn, "NODATA")
    stats = prices.enrich_all(conn=conn, fetcher=fake_fetcher, today="2025-06-02")
    assert conn.execute("SELECT price_status FROM transactions").fetchone()[0] == "no_price"
    assert stats["no_price"] == 1


def test_close_on_or_before():
    assert prices.close_on_or_before(SERIES, "2025-01-11") == 100.0   # sábado -> viernes 10
    assert prices.close_on_or_before(SERIES, "2025-01-13") == 110.0   # fecha exacta
    assert prices.close_on_or_before(SERIES, "2025-01-08") is None    # antes de la serie
