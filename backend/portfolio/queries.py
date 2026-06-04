"""Consultas de lectura para el frontend (Fase 7).

Funciones puras sobre la base SQLite (members / positions / transactions),
separadas de Streamlit para poder probarlas sin la UI.
"""
from __future__ import annotations

import sqlite3

from backend.portfolio import builder

# Expresión de la clave de congresista (igual que en builder).
_KEY = "(f.last_name || '|' || COALESCE(f.first_name, '') || '|' || COALESCE(f.state_dst, ''))"


def ensure_built(conn: sqlite3.Connection) -> None:
    """Construye members/positions si están vacíos pero ya hay transacciones."""
    has_members = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    has_tx = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    if not has_members and has_tx:
        builder.build(conn)


def overview(conn: sqlite3.Connection) -> dict:
    members = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    positions = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    txs = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    tickers = conn.execute(
        "SELECT COUNT(DISTINCT ticker) FROM transactions WHERE ticker IS NOT NULL"
    ).fetchone()[0]
    gmin, gmax = conn.execute(
        "SELECT SUM(est_gain_min), SUM(est_gain_max) FROM members"
    ).fetchone()
    return {
        "members": members, "positions": positions, "transactions": txs,
        "tickers": tickers, "gain_min": gmin, "gain_max": gmax,
    }


def list_members(conn: sqlite3.Connection, search: str = "", limit: int = 1000) -> list[sqlite3.Row]:
    sql = "SELECT * FROM members"
    params: list = []
    if search:
        sql += " WHERE last_name LIKE ? OR first_name LIKE ?"
        params += [f"%{search}%", f"%{search}%"]
    # Los que tienen P/L estimado primero; luego por nº de operaciones.
    sql += " ORDER BY COALESCE(est_gain_max, -9e18) DESC, n_tx DESC LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def member(conn: sqlite3.Connection, member_key: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM members WHERE member_key = ?", (member_key,)).fetchone()


def positions(conn: sqlite3.Connection, member_key: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM positions WHERE member_key = ? ORDER BY net_value DESC",
        (member_key,),
    ).fetchall()


def member_transactions(
    conn: sqlite3.Connection, member_key: str, limit: int = 1000
) -> list[sqlite3.Row]:
    return conn.execute(
        f"SELECT t.tx_date, t.tx_type, t.ticker, t.asset_name, t.raw_amount, "
        f"t.return_pct, t.est_gain_min, t.est_gain_max, t.price_status "
        f"FROM transactions t JOIN filings f ON f.doc_id = t.doc_id "
        f"WHERE {_KEY} = ? ORDER BY t.tx_date DESC LIMIT ?",
        (member_key, limit),
    ).fetchall()


def top_operations(
    conn: sqlite3.Connection, *, winners: bool = True, limit: int = 20
) -> list[sqlite3.Row]:
    """Mejores (o peores) compras valuadas por variación del activo."""
    order = "DESC" if winners else "ASC"
    return conn.execute(
        f"SELECT f.last_name, f.first_name, f.state_dst, t.ticker, t.tx_date, "
        f"t.return_pct, t.est_gain_min, t.est_gain_max, t.raw_amount "
        f"FROM transactions t JOIN filings f ON f.doc_id = t.doc_id "
        f"WHERE t.price_status = 'ok' AND t.tx_type = 'P' AND t.return_pct IS NOT NULL "
        f"ORDER BY t.return_pct {order} LIMIT ?",
        (limit,),
    ).fetchall()
