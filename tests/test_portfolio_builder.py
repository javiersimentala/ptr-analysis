"""Pruebas de la Fase 5 (agregación de portafolio) en memoria."""
import sqlite3

from backend.db import database
from backend.portfolio import builder

KEY = "Doe|Jane|CA01"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    database.init_db(conn)
    conn.execute(
        "INSERT INTO filings (doc_id, last_name, first_name, state_dst, filing_type, year) "
        "VALUES ('D1', 'Doe', 'Jane', 'CA01', 'P', 2026)"
    )
    conn.commit()
    return conn


def _tx(conn, ticker, tx_type, amin, amax, ret, gmin, gmax, status="ok"):
    conn.execute(
        "INSERT INTO transactions (doc_id, ticker, tx_type, amount_min, amount_max, "
        "return_pct, est_gain_min, est_gain_max, price_status, price_current) "
        "VALUES ('D1', ?, ?, ?, ?, ?, ?, ?, ?, 150)",
        (ticker, tx_type, amin, amax, ret, gmin, gmax, status),
    )
    conn.commit()


def _build():
    conn = _conn()
    _tx(conn, "AAPL", "P", 1000, 3000, 0.1, 100, 300)     # compra ganadora
    _tx(conn, "AAPL", "P", 1000, 3000, 0.1, 100, 300)     # compra ganadora
    _tx(conn, "AAPL", "S", 1000, 3000, 0.1, None, None)   # venta
    _tx(conn, "MSFT", "P", 5000, 25000, -0.05, -250, -1250)  # compra perdedora
    builder.build(conn)
    return conn


def test_posicion_neta_estimada():
    conn = _build()
    aapl = conn.execute("SELECT * FROM positions WHERE ticker='AAPL'").fetchone()
    assert aapl["n_buys"] == 2 and aapl["n_sells"] == 1
    assert aapl["buy_value"] == 4000      # 2 x medio(2000)
    assert aapl["sell_value"] == 2000
    assert aapl["net_value"] == 2000      # 4000 - 2000
    assert aapl["est_gain_min"] == 200 and aapl["est_gain_max"] == 600

    msft = conn.execute("SELECT * FROM positions WHERE ticker='MSFT'").fetchone()
    assert msft["net_value"] == 15000     # medio(5000,25000)


def test_resumen_miembro_y_winrate():
    conn = _build()
    m = conn.execute("SELECT * FROM members WHERE member_key=?", (KEY,)).fetchone()
    assert m["n_tx"] == 4
    assert m["n_buys"] == 3 and m["n_sells"] == 1
    assert m["n_tickers"] == 2
    assert m["invested_min"] == 7000      # 1000+1000+5000
    assert m["invested_max"] == 31000     # 3000+3000+25000
    # win-rate = compras valuadas con retorno>0 / compras valuadas = 2/3
    assert abs(m["win_rate"] - 2 / 3) < 1e-9


def test_build_idempotente():
    conn = _build()
    builder.build(conn)  # segunda corrida no debe duplicar
    assert conn.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 2
