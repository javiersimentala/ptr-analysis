"""Pruebas del portafolio optimo (media-varianza) con precios simulados, sin red."""
import datetime as dt
import sqlite3

import numpy as np

from backend.db import database
from backend.portfolio import optimize


def _fake_fetcher(ticker, start, end):
    """Genera precios sinteticos: AAA con buen Sharpe, BBB con peor Sharpe."""
    rng = np.random.default_rng(1 if ticker == "AAA" else 2)
    n = 300
    # AAA: retorno claramente positivo y baja volatilidad (Sharpe alto).
    # BBB: sin deriva y mas volatil (Sharpe bajo) -> debe recibir menos peso.
    drift, vol = (0.003, 0.008) if ticker == "AAA" else (0.0, 0.02)
    rets = rng.normal(drift, vol, n)
    px = 100 * np.cumprod(1 + rets)
    base = dt.date(2024, 1, 1)
    days = [(base + dt.timedelta(days=i)).isoformat() for i in range(n)]
    return list(zip(days, [float(p) for p in px]))


def test_build_returns_alinea_columnas():
    r = optimize.build_returns(["AAA", "BBB"], "2024-01-01", fetcher=_fake_fetcher, today="2024-12-31")
    assert list(r.columns) == ["AAA", "BBB"]
    assert len(r) > 100


def test_optimize_pesos_validos_y_prefiere_el_mejor():
    r = optimize.build_returns(["AAA", "BBB"], "2024-01-01", fetcher=_fake_fetcher, today="2024-12-31")
    res = optimize.optimize_max_sharpe(r)
    w = res["weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-6      # totalmente invertido
    assert all(v >= -1e-9 for v in w.values())    # solo largos
    assert w["AAA"] > w["BBB"]                     # el de mejor Sharpe pesa mas
    assert res["sharpe"] > 0


def _conn_con_posiciones() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    database.init_db(conn)
    conn.execute("INSERT INTO positions (member_key, ticker, net_value) VALUES ('m', 'AAA', 1000)")
    conn.execute("INSERT INTO positions (member_key, ticker, net_value) VALUES ('m', 'BBB', 500)")
    conn.commit()
    return conn


def test_run_completo_guarda_resultado():
    conn = _conn_con_posiciones()
    out = optimize.run(conn=conn, fetcher=_fake_fetcher, today="2024-12-31", lookback_days=400)
    assert out["status"] == "ok"
    assert out["n_assets"] == 2
    assert conn.execute("SELECT COUNT(*) FROM optimal_weights").fetchone()[0] == 2
    assert conn.execute("SELECT * FROM optimal_meta WHERE id = 1").fetchone() is not None


def test_run_sin_universo_no_rompe():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    database.init_db(conn)
    out = optimize.run(conn=conn, fetcher=_fake_fetcher, today="2024-12-31")
    assert out["status"] == "sin_datos"
