"""Portafolio optimo (media-varianza / Markowitz).

Construye un portafolio optimo de maximo ratio de Sharpe (solo posiciones largas,
totalmente invertido) sobre el universo de tickers que el Congreso mantiene en
posicion neta agregada positiva.

Pasos:
    1. select_universe   -> tickers con mayor posicion neta agregada del Congreso.
    2. build_returns     -> historial de precios (yfinance) -> retornos diarios.
    3. optimize_max_sharpe -> pesos que maximizan retorno/riesgo (scipy SLSQP).
    4. store             -> guarda pesos y metricas en optimal_weights/optimal_meta.

El proveedor de precios (``fetcher``) es inyectable para poder probar sin red.
La parte pesada (red + optimizacion) la corre el CLI scripts/run_optimal.py y la
web solo lee el resultado ya guardado.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from backend.db import database
from backend.market import prices

# Dias bursatiles al año, para anualizar media y covarianza.
TRADING_DAYS = 252


def select_universe(conn: sqlite3.Connection, limit: int = 25) -> list[str]:
    """Tickers con posicion neta agregada positiva (top por valor) en el Congreso."""
    rows = conn.execute(
        "SELECT ticker, SUM(net_value) AS agg FROM positions "
        "WHERE ticker IS NOT NULL "
        "GROUP BY ticker HAVING agg > 0 "
        "ORDER BY agg DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [r[0] for r in rows]


def build_returns(
    tickers: list[str], start_iso: str, *,
    fetcher=prices._yf_fetch_history, today: str | None = None,
) -> pd.DataFrame:
    """Retornos diarios alineados (columnas = tickers) desde ``start_iso``."""
    today = today or dt.date.today().isoformat()
    series: dict[str, pd.Series] = {}
    for ticker in tickers:
        rows = fetcher(ticker, start_iso, today)
        if rows and len(rows) > 30:  # se exige un minimo de historia util
            series[ticker] = pd.Series({d: c for d, c in rows})
    if not series:
        return pd.DataFrame()
    prices_df = pd.DataFrame(series).sort_index()
    return prices_df.pct_change().dropna(how="any")


def optimize_max_sharpe(returns: pd.DataFrame, risk_free: float = 0.0) -> dict:
    """Pesos de maximo Sharpe (solo largos, suma de pesos = 1)."""
    mu = returns.mean() * TRADING_DAYS                 # retorno anualizado
    cov = returns.cov() * TRADING_DAYS                 # covarianza anualizada
    tickers = list(returns.columns)
    n = len(tickers)
    mu_v, cov_m = mu.values, cov.values

    def neg_sharpe(w: np.ndarray) -> float:
        ret = float(w @ mu_v)
        vol = float(np.sqrt(w @ cov_m @ w))
        return -(ret - risk_free) / vol if vol > 1e-12 else 0.0

    constraints = ({"type": "eq", "fun": lambda w: w.sum() - 1.0},)
    bounds = tuple((0.0, 1.0) for _ in range(n))
    w0 = np.repeat(1.0 / n, n)
    res = minimize(
        neg_sharpe, w0, method="SLSQP", bounds=bounds, constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-9},
    )

    w = np.clip(res.x, 0.0, None)
    w = w / w.sum() if w.sum() > 0 else w
    port_ret = float(w @ mu_v)
    port_vol = float(np.sqrt(w @ cov_m @ w))
    sharpe = (port_ret - risk_free) / port_vol if port_vol > 1e-12 else 0.0

    per_asset = {
        t: {"exp_return": float(mu[t]), "volatility": float(np.sqrt(cov.loc[t, t]))}
        for t in tickers
    }
    weights = {t: float(wi) for t, wi in zip(tickers, w)}
    return {
        "weights": weights, "exp_return": port_ret, "volatility": port_vol,
        "sharpe": sharpe, "per_asset": per_asset,
    }


def store(conn: sqlite3.Connection, result: dict, lookback_days: int) -> None:
    """Persiste pesos y metricas (reemplazando el resultado anterior)."""
    conn.execute("DELETE FROM optimal_weights")
    conn.execute("DELETE FROM optimal_meta")
    conn.executemany(
        "INSERT INTO optimal_weights (ticker, weight, exp_return, volatility) VALUES (?, ?, ?, ?)",
        [
            (t, w, result["per_asset"][t]["exp_return"], result["per_asset"][t]["volatility"])
            for t, w in result["weights"].items()
        ],
    )
    conn.execute(
        "INSERT INTO optimal_meta (id, exp_return, volatility, sharpe, n_assets, lookback_days) "
        "VALUES (1, ?, ?, ?, ?, ?)",
        (result["exp_return"], result["volatility"], result["sharpe"],
         len(result["weights"]), lookback_days),
    )
    conn.commit()


def run(
    conn: sqlite3.Connection | None = None, *, limit: int = 25, lookback_days: int = 504,
    fetcher=prices._yf_fetch_history, today: str | None = None, on_event=None,
) -> dict:
    """Pipeline completo: universo -> retornos -> optimizacion -> guardado."""
    close_conn = conn is None
    conn = conn or database.get_connection()
    if close_conn:
        database.init_db(conn)
    today = today or dt.date.today().isoformat()
    start = (dt.date.fromisoformat(today) - dt.timedelta(days=lookback_days)).isoformat()

    try:
        universe = select_universe(conn, limit=limit)
        if on_event:
            on_event(f"universo: {len(universe)} tickers")
        returns = build_returns(universe, start, fetcher=fetcher, today=today)
        if returns.empty or returns.shape[1] < 2:
            return {"status": "sin_datos", "n_assets": int(returns.shape[1]) if not returns.empty else 0}
        result = optimize_max_sharpe(returns)
        store(conn, result, lookback_days)
        return {
            "status": "ok", "n_assets": len(result["weights"]),
            "exp_return": result["exp_return"], "volatility": result["volatility"],
            "sharpe": result["sharpe"],
        }
    finally:
        if close_conn:
            conn.close()
