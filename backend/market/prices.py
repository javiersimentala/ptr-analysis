"""Fase 4 - Enriquecimiento de transacciones con precios de mercado.

Para cada transacción con ticker obtiene, vía ``yfinance``:
- ``price_at_tx``  : cierre en (o antes de) la fecha de la operación.
- ``price_current``: último cierre conocido.
y calcula:
- ``return_pct``   : ``price_current / price_at_tx - 1``.
- ``est_gain_min/max`` (sólo compras): rango de monto declarado × ``return_pct``.

Como los PTR declaran **rangos de monto** (no cantidades), la ganancia/pérdida
es una **estimación por rango** basada en la variación de precio del activo.

Los precios se cachean en la tabla ``prices``. El proveedor de datos
(``fetcher``) es inyectable para poder probar sin red.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

from backend.db import database

# Cierres que se cachean por (ticker, fecha). Sólo se piden datos una vez por
# ticker (ventana desde su primera operación hasta hoy).


def _yf_fetch_history(ticker: str, start: str, end: str) -> list[tuple[str, float]]:
    """Descarga el historial de cierres [(fecha_iso, close)] vía yfinance."""
    import yfinance as yf

    df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    out: list[tuple[str, float]] = []
    for idx, row in df.iterrows():
        close = row.get("Close")
        if close is None or close != close:  # descarta NaN
            continue
        out.append((idx.date().isoformat(), float(close)))
    return out


def _days(date_iso: str, delta: int) -> str:
    return (dt.date.fromisoformat(date_iso) + dt.timedelta(days=delta)).isoformat()


def _cache_put(conn: sqlite3.Connection, ticker: str, rows: list[tuple[str, float]]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO prices (ticker, price_date, close, source) VALUES (?, ?, ?, 'yfinance')",
        [(ticker, d, c) for d, c in rows],
    )
    conn.commit()


def _cached_series(conn: sqlite3.Connection, ticker: str) -> list[tuple[str, float]]:
    return [
        (r[0], r[1])
        for r in conn.execute(
            "SELECT price_date, close FROM prices WHERE ticker = ? ORDER BY price_date",
            (ticker,),
        )
    ]


def get_series(
    conn: sqlite3.Connection,
    ticker: str,
    start_iso: str,
    *,
    fetcher=_yf_fetch_history,
    today: str | None = None,
) -> list[tuple[str, float]]:
    """Serie de cierres del ticker desde ``start_iso`` hasta hoy (usa caché)."""
    today = today or dt.date.today().isoformat()
    cached = _cached_series(conn, ticker)
    if cached and cached[0][0] <= start_iso and cached[-1][0] >= _days(today, -4):
        return cached  # la caché cubre el rango y está fresca
    rows = fetcher(ticker, _days(start_iso, -7), _days(today, 1))
    if rows:
        _cache_put(conn, ticker, rows)
        return _cached_series(conn, ticker)
    return cached


def close_on_or_before(series: list[tuple[str, float]], date_iso: str) -> float | None:
    """Último cierre con fecha <= ``date_iso`` (la serie viene ordenada asc.)."""
    result = None
    for d, close in series:
        if d <= date_iso:
            result = close
        else:
            break
    return result


def enrich_all(
    conn: sqlite3.Connection | None = None,
    *,
    limit: int | None = None,
    fetcher=_yf_fetch_history,
    today: str | None = None,
    on_event=None,
) -> dict:
    """Calcula precios y P/L estimado para las transacciones sin enriquecer.

    Returns:
        dict con conteos: tickers, priced, no_price, no_ticker.
    """
    close_conn = conn is None
    conn = conn or database.get_connection()
    if close_conn:
        database.init_db(conn)
    today = today or dt.date.today().isoformat()

    # Las transacciones sin ticker no se pueden valuar automáticamente.
    no_ticker = conn.execute(
        "UPDATE transactions SET price_status = 'no_ticker' "
        "WHERE ticker IS NULL AND price_status IS NULL"
    ).rowcount
    conn.commit()

    tickers = conn.execute(
        "SELECT ticker, MIN(tx_date) FROM transactions "
        "WHERE ticker IS NOT NULL AND price_status IS NULL "
        "GROUP BY ticker ORDER BY ticker"
    ).fetchall()
    if limit is not None:
        tickers = tickers[:limit]

    stats = {"tickers": 0, "priced": 0, "no_price": 0, "no_ticker": no_ticker}
    try:
        for ticker, start in tickers:
            stats["tickers"] += 1
            try:
                series = get_series(conn, ticker, start, fetcher=fetcher, today=today)
            except Exception as exc:
                series = []
                if on_event:
                    on_event(ticker, f"error {type(exc).__name__}")
            current = series[-1][1] if series else None

            txs = conn.execute(
                "SELECT id, tx_type, tx_date, amount_min, amount_max "
                "FROM transactions WHERE ticker = ? AND price_status IS NULL",
                (ticker,),
            ).fetchall()
            for t in txs:
                p0 = close_on_or_before(series, t["tx_date"]) if series else None
                if p0 is None or current is None or p0 == 0:
                    conn.execute(
                        "UPDATE transactions SET price_status = 'no_price' WHERE id = ?",
                        (t["id"],),
                    )
                    stats["no_price"] += 1
                    continue
                ret = current / p0 - 1.0
                est_min = est_max = None
                if t["tx_type"] == "P":  # ganancia no realizada sólo aplica a compras
                    if t["amount_min"] is not None:
                        est_min = t["amount_min"] * ret
                    if t["amount_max"] is not None:
                        est_max = t["amount_max"] * ret
                conn.execute(
                    "UPDATE transactions SET price_at_tx = ?, price_current = ?, "
                    "return_pct = ?, est_gain_min = ?, est_gain_max = ?, price_status = 'ok' "
                    "WHERE id = ?",
                    (p0, current, ret, est_min, est_max, t["id"]),
                )
                stats["priced"] += 1
            conn.commit()
            if on_event:
                on_event(ticker, f"{len(txs)} tx, current={current}")
    finally:
        if close_conn:
            conn.close()
    return stats
