"""Pruebas de la capa de consultas del frontend (Fase 7), en memoria."""
import sqlite3

from backend.db import database
from backend.portfolio import builder, queries


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    database.init_db(conn)
    conn.execute(
        "INSERT INTO filings (doc_id, last_name, first_name, state_dst, filing_type, year) "
        "VALUES ('D1', 'Doe', 'Jane', 'CA01', 'P', 2026)"
    )
    for ticker, ret, gmin, gmax, date in [
        ("AAPL", 0.2, 200, 600, "2025-02-01"),
        ("MSFT", -0.1, -100, -300, "2025-03-01"),
    ]:
        conn.execute(
            "INSERT INTO transactions (doc_id, ticker, tx_type, amount_min, amount_max, "
            "return_pct, est_gain_min, est_gain_max, price_status, price_current, tx_date) "
            "VALUES ('D1', ?, 'P', 1000, 3000, ?, ?, ?, 'ok', 150, ?)",
            (ticker, ret, gmin, gmax, date),
        )
    conn.commit()
    builder.build(conn)
    return conn


def test_overview():
    ov = queries.overview(_conn())
    assert ov["members"] == 1
    assert ov["transactions"] == 2
    assert ov["tickers"] == 2


def test_list_members_y_posiciones():
    conn = _conn()
    members = queries.list_members(conn)
    assert len(members) == 1
    key = members[0]["member_key"]
    assert queries.member(conn, key)["last_name"] == "Doe"
    assert len(queries.positions(conn, key)) == 2


def test_member_transactions_ordenadas():
    conn = _conn()
    key = queries.list_members(conn)[0]["member_key"]
    txs = queries.member_transactions(conn, key)
    assert len(txs) == 2
    assert txs[0]["tx_date"] >= txs[1]["tx_date"]   # descendente


def test_top_operations():
    conn = _conn()
    assert queries.top_operations(conn, winners=True)[0]["ticker"] == "AAPL"   # +20%
    assert queries.top_operations(conn, winners=False)[0]["ticker"] == "MSFT"  # -10%


def test_ensure_built_sin_transacciones():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    database.init_db(conn)
    queries.ensure_built(conn)   # no debe fallar ni crear miembros
    assert queries.overview(conn)["members"] == 0
