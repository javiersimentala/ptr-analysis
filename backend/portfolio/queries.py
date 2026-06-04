"""Consultas de lectura para el frontend (Fase 7).

Funciones puras sobre la base SQLite (members / positions / transactions),
separadas de Streamlit para poder probarlas sin la UI.
"""
from __future__ import annotations

import sqlite3

from backend.db import database
from backend.portfolio import builder

# Expresión de la clave de congresista (igual que en builder).
_KEY = "(f.last_name || '|' || COALESCE(f.first_name, '') || '|' || COALESCE(f.state_dst, ''))"


def ensure_built(conn: sqlite3.Connection) -> None:
    """Crea el esquema (si falta) y construye members/positions si están vacíos."""
    database.init_db(conn)  # idempotente: garantiza que existan las tablas
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
    conn: sqlite3.Connection, member_key: str, year: int | None = None, limit: int = 1000
) -> list[sqlite3.Row]:
    """Operaciones de un congresista, opcionalmente filtradas por año."""
    sql = (
        f"SELECT t.tx_date, t.tx_type, t.ticker, t.asset_name, t.raw_amount, "
        f"t.return_pct, t.est_gain_min, t.est_gain_max, t.price_status "
        f"FROM transactions t JOIN filings f ON f.doc_id = t.doc_id WHERE {_KEY} = ?"
    )
    params: list = [member_key]
    if year:
        sql += " AND f.year = ?"
        params.append(int(year))
    sql += " ORDER BY t.tx_date DESC LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


# Punto medio del rango de monto de una transacción (para valores en dólares).
_MID = "(t.amount_min + COALESCE(t.amount_max, t.amount_min)) / 2.0"


def available_years(conn: sqlite3.Connection) -> list[int]:
    """Años con PTR disponibles, de más reciente a más antiguo (para el selector)."""
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT year FROM filings WHERE filing_type = 'P' ORDER BY year DESC"
    )]


def list_filings(
    conn: sqlite3.Connection, member_key: str | None = None, year: int | None = None,
    limit: int = 50, offset: int = 0,
) -> list[sqlite3.Row]:
    """Lista de PTR (con conteo de transacciones), filtrable por congresista y año."""
    sql = (
        f"SELECT f.doc_id, f.last_name, f.first_name, f.state_dst, f.filing_date, "
        f"{_KEY} AS member_key, "
        f"(SELECT COUNT(*) FROM transactions t WHERE t.doc_id = f.doc_id) AS n_tx "
        f"FROM filings f WHERE f.filing_type = 'P'"
    )
    params: list = []
    if member_key:
        sql += f" AND {_KEY} = ?"
        params.append(member_key)
    if year:
        sql += " AND f.year = ?"
        params.append(int(year))
    sql += " ORDER BY f.filing_date DESC, f.doc_id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return conn.execute(sql, params).fetchall()


def count_filings(
    conn: sqlite3.Connection, member_key: str | None = None, year: int | None = None
) -> int:
    sql = "SELECT COUNT(*) FROM filings f WHERE f.filing_type = 'P'"
    params: list = []
    if member_key:
        sql += f" AND {_KEY} = ?"
        params.append(member_key)
    if year:
        sql += " AND f.year = ?"
        params.append(int(year))
    return conn.execute(sql, params).fetchone()[0]


def member_portfolio(
    conn: sqlite3.Connection, member_key: str, year: int | None = None
) -> list[sqlite3.Row]:
    """Posición neta estimada por ticker de un congresista (opcional: un año)."""
    sql = (
        f"SELECT t.ticker, "
        f"SUM(CASE WHEN t.tx_type='P' THEN 1 ELSE 0 END) AS n_buys, "
        f"SUM(CASE WHEN t.tx_type='S' THEN 1 ELSE 0 END) AS n_sells, "
        f"SUM(CASE WHEN t.tx_type='P' THEN {_MID} ELSE 0 END) AS buy_value, "
        f"SUM(CASE WHEN t.tx_type='P' THEN {_MID} "
        f"         WHEN t.tx_type='S' THEN -{_MID} ELSE 0 END) AS net_value, "
        f"SUM(t.est_gain_min) AS est_gain_min, SUM(t.est_gain_max) AS est_gain_max, "
        f"AVG(t.return_pct) AS return_pct, MAX(t.price_current) AS price_current "
        f"FROM transactions t JOIN filings f ON f.doc_id = t.doc_id "
        f"WHERE {_KEY} = ? AND t.ticker IS NOT NULL"
    )
    params: list = [member_key]
    if year:
        sql += " AND f.year = ?"
        params.append(int(year))
    sql += " GROUP BY t.ticker ORDER BY net_value DESC"
    return conn.execute(sql, params).fetchall()


def members_by_keys(conn: sqlite3.Connection, keys: list[str]) -> list[sqlite3.Row]:
    """Resumen de varios congresistas (preservando el orden de ``keys``)."""
    if not keys:
        return []
    placeholders = ",".join("?" * len(keys))
    rows = conn.execute(
        f"SELECT * FROM members WHERE member_key IN ({placeholders})", keys
    ).fetchall()
    by_key = {r["member_key"]: r for r in rows}
    return [by_key[k] for k in keys if k in by_key]


def optimal_portfolio(conn: sqlite3.Connection):
    """Devuelve (meta, pesos) del portafolio optimo guardado, o (None, [])."""
    meta = conn.execute("SELECT * FROM optimal_meta WHERE id = 1").fetchone()
    weights = conn.execute(
        "SELECT * FROM optimal_weights ORDER BY weight DESC"
    ).fetchall()
    return meta, weights


def member_period_summary(
    conn: sqlite3.Connection, member_key: str, year: int | None = None
) -> sqlite3.Row:
    """Totales de un congresista para el periodo (todo o un año)."""
    sql = (
        f"SELECT COUNT(*) AS n_tx, "
        f"SUM(CASE WHEN t.tx_type='P' THEN 1 ELSE 0 END) AS n_buys, "
        f"SUM(CASE WHEN t.tx_type='S' THEN 1 ELSE 0 END) AS n_sells, "
        f"COUNT(DISTINCT t.ticker) AS n_tickers, "
        f"SUM(CASE WHEN t.tx_type='P' THEN t.amount_min ELSE 0 END) AS invested_min, "
        f"SUM(CASE WHEN t.tx_type='P' THEN COALESCE(t.amount_max,t.amount_min) ELSE 0 END) AS invested_max, "
        f"SUM(t.est_gain_min) AS est_gain_min, SUM(t.est_gain_max) AS est_gain_max, "
        f"CAST(SUM(CASE WHEN t.tx_type='P' AND t.price_status='ok' AND t.return_pct>0 "
        f"             THEN 1 ELSE 0 END) AS REAL) "
        f"  / NULLIF(SUM(CASE WHEN t.tx_type='P' AND t.price_status='ok' "
        f"                    THEN 1 ELSE 0 END), 0) AS win_rate "
        f"FROM transactions t JOIN filings f ON f.doc_id = t.doc_id WHERE {_KEY} = ?"
    )
    params: list = [member_key]
    if year:
        sql += " AND f.year = ?"
        params.append(int(year))
    return conn.execute(sql, params).fetchone()


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
