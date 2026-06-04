"""Fase 5 - Construcción del portafolio y P/L estimado por congresista.

Agrega las ``transactions`` por congresista (identificado por
``apellido|nombre|estado-distrito``) en dos tablas derivadas:

- ``members``   : resumen por congresista (nº de operaciones, monto invertido,
  P/L estimado total, win-rate de las compras valuadas).
- ``positions`` : posición neta estimada por congresista y ticker.

Como los PTR declaran **rangos**, la "posición neta" se estima con el **punto
medio** del rango de cada operación: ``net_value = Σ medios(compras) − Σ medios(ventas)``.
Es una **estimación direccional en dólares**, no una cantidad de acciones.
"""
from __future__ import annotations

import sqlite3

from backend.db import database

# Clave de congresista y punto medio del rango de una transacción.
_KEY = "f.last_name || '|' || COALESCE(f.first_name, '') || '|' || COALESCE(f.state_dst, '')"
_MID = "(t.amount_min + COALESCE(t.amount_max, t.amount_min)) / 2.0"

_POSITIONS_SQL = f"""
INSERT INTO positions
    (member_key, ticker, last_name, first_name, state_dst,
     n_buys, n_sells, buy_value, sell_value, net_value,
     est_gain_min, est_gain_max, return_pct, price_current)
SELECT
    {_KEY} AS member_key, t.ticker, f.last_name, f.first_name, f.state_dst,
    SUM(CASE WHEN t.tx_type = 'P' THEN 1 ELSE 0 END),
    SUM(CASE WHEN t.tx_type = 'S' THEN 1 ELSE 0 END),
    SUM(CASE WHEN t.tx_type = 'P' THEN {_MID} ELSE 0 END),
    SUM(CASE WHEN t.tx_type = 'S' THEN {_MID} ELSE 0 END),
    SUM(CASE WHEN t.tx_type = 'P' THEN {_MID}
             WHEN t.tx_type = 'S' THEN -{_MID} ELSE 0 END),
    SUM(t.est_gain_min), SUM(t.est_gain_max),
    AVG(t.return_pct), MAX(t.price_current)
FROM transactions t JOIN filings f ON f.doc_id = t.doc_id
WHERE t.ticker IS NOT NULL
GROUP BY member_key, t.ticker
"""

_MEMBERS_SQL = f"""
INSERT INTO members
    (member_key, last_name, first_name, state_dst,
     n_tx, n_buys, n_sells, n_tickers,
     invested_min, invested_max, est_gain_min, est_gain_max, win_rate)
SELECT
    {_KEY} AS member_key, f.last_name, f.first_name, f.state_dst,
    COUNT(*),
    SUM(CASE WHEN t.tx_type = 'P' THEN 1 ELSE 0 END),
    SUM(CASE WHEN t.tx_type = 'S' THEN 1 ELSE 0 END),
    COUNT(DISTINCT t.ticker),
    SUM(CASE WHEN t.tx_type = 'P' THEN t.amount_min ELSE 0 END),
    SUM(CASE WHEN t.tx_type = 'P' THEN COALESCE(t.amount_max, t.amount_min) ELSE 0 END),
    SUM(t.est_gain_min), SUM(t.est_gain_max),
    CAST(SUM(CASE WHEN t.tx_type = 'P' AND t.price_status = 'ok' AND t.return_pct > 0
                  THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(CASE WHEN t.tx_type = 'P' AND t.price_status = 'ok'
                          THEN 1 ELSE 0 END), 0)
FROM transactions t JOIN filings f ON f.doc_id = t.doc_id
GROUP BY member_key
"""


def build(conn: sqlite3.Connection | None = None) -> dict:
    """Reconstruye las tablas ``members`` y ``positions`` desde ``transactions``."""
    close_conn = conn is None
    conn = conn or database.get_connection()
    if close_conn:
        database.init_db(conn)
    try:
        conn.execute("DELETE FROM positions")
        conn.execute("DELETE FROM members")
        conn.execute(_POSITIONS_SQL)
        conn.execute(_MEMBERS_SQL)
        conn.commit()
        return {
            "members": conn.execute("SELECT COUNT(*) FROM members").fetchone()[0],
            "positions": conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0],
        }
    finally:
        if close_conn:
            conn.close()


def top_members_by_gain(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    """Congresistas ordenados por P/L estimado (extremo alto del rango)."""
    return conn.execute(
        "SELECT * FROM members WHERE est_gain_max IS NOT NULL "
        "ORDER BY est_gain_max DESC LIMIT ?",
        (limit,),
    ).fetchall()


def member_positions(conn: sqlite3.Connection, member_key: str) -> list[sqlite3.Row]:
    """Posiciones de un congresista, de mayor a menor valor neto estimado."""
    return conn.execute(
        "SELECT * FROM positions WHERE member_key = ? ORDER BY net_value DESC",
        (member_key,),
    ).fetchall()
