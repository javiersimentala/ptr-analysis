"""Dashboard Streamlit — PTR Analysis (Fase 7).

Lee directamente la base SQLite generada por el backend (members / positions /
transactions) y muestra ranking, portafolio por congresista y operaciones
ganadoras.

Ejecutar:  streamlit run frontend/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from backend.db import database  # noqa: E402
from backend.portfolio import queries  # noqa: E402

st.set_page_config(page_title="PTR Analysis", page_icon="📊", layout="wide")


def _df(rows) -> pd.DataFrame:
    return pd.DataFrame([dict(r) for r in rows])


def _money(x) -> str:
    return "—" if x is None else f"${x:,.0f}"


@st.cache_data(ttl=300)
def _load():
    """Lee todo lo necesario en DataFrames (cacheado 5 min)."""
    conn = database.get_connection()
    queries.ensure_built(conn)
    data = {
        "overview": queries.overview(conn),
        "members": _df(queries.list_members(conn, limit=2000)),
        "winners": _df(queries.top_operations(conn, winners=True, limit=25)),
        "losers": _df(queries.top_operations(conn, winners=False, limit=25)),
    }
    conn.close()
    return data


def _member_detail(member_key: str):
    conn = database.get_connection()
    out = (
        queries.member(conn, member_key),
        _df(queries.positions(conn, member_key)),
        _df(queries.member_transactions(conn, member_key, limit=1000)),
    )
    conn.close()
    return out


st.title("📊 PTR Analysis — Trading del Congreso de EE.UU.")
st.caption(
    "Datos públicos del House Clerk (Periodic Transaction Reports). "
    "El P/L es una **estimación por rango**. No es asesoría de inversión."
)

data = _load()
ov = data["overview"]

if ov["transactions"] == 0:
    st.warning(
        "No hay transacciones en la base. Corre el pipeline:\n\n"
        "`python scripts/run_ingest.py all` → `run_download.py all` → "
        "`run_parse.py all` → `run_enrich.py` → `run_portfolio.py`"
    )
    st.stop()

tab_resumen, tab_miembro, tab_ops = st.tabs(
    ["🏆 Ranking", "👤 Congresista", "📈 Operaciones ganadoras"]
)

# ----------------------------------------------------------------- Ranking ---
with tab_resumen:
    c = st.columns(4)
    c[0].metric("Congresistas", f"{ov['members']:,}")
    c[1].metric("Transacciones", f"{ov['transactions']:,}")
    c[2].metric("Tickers", f"{ov['tickers']:,}")
    c[3].metric("P/L estimado (máx)", _money(ov["gain_max"]))

    st.subheader("Ranking por P/L estimado")
    df = data["members"].copy()
    if not df.empty:
        df["congresista"] = (
            df["first_name"].fillna("").str.strip() + " " + df["last_name"].fillna("")
        ).str.strip()
        df["win_rate"] = (df["win_rate"] * 100).round(0)
        cols = {
            "congresista": "Congresista", "state_dst": "Distrito", "n_tx": "Ops",
            "n_buys": "Compras", "n_sells": "Ventas", "invested_max": "Invertido ≤ ($)",
            "est_gain_max": "P/L est. ≤ ($)", "win_rate": "Win %",
        }
        st.dataframe(
            df[list(cols)].rename(columns=cols),
            use_container_width=True, hide_index=True,
            column_config={
                "Invertido ≤ ($)": st.column_config.NumberColumn(format="$%d"),
                "P/L est. ≤ ($)": st.column_config.NumberColumn(format="$%d"),
            },
        )

# -------------------------------------------------------------- Congresista ---
with tab_miembro:
    members_df = data["members"]
    labels = {
        f"{(r['first_name'] or '').strip()} {r['last_name']} ({r['state_dst'] or '?'})".strip():
        r["member_key"]
        for _, r in members_df.iterrows()
    }
    pick = st.selectbox("Elige un congresista", sorted(labels))
    if pick:
        m, pos, txs = _member_detail(labels[pick])
        if m:
            c = st.columns(4)
            c[0].metric("Operaciones", m["n_tx"])
            c[1].metric("Tickers", m["n_tickers"])
            c[2].metric("Invertido (rango)", f"{_money(m['invested_min'])}–{_money(m['invested_max'])}")
            wr = "—" if m["win_rate"] is None else f"{m['win_rate'] * 100:.0f}%"
            c[3].metric("Win-rate", wr)

        st.subheader("Posición neta estimada por ticker")
        if not pos.empty:
            pcols = {
                "ticker": "Ticker", "n_buys": "Compras", "n_sells": "Ventas",
                "net_value": "Neto est. ($)", "est_gain_max": "P/L est. ≤ ($)",
                "return_pct": "Var. %", "price_current": "Precio actual",
            }
            show = pos.copy()
            show["return_pct"] = (show["return_pct"] * 100).round(1)
            st.dataframe(
                show[list(pcols)].rename(columns=pcols),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("Sin posiciones con ticker (p. ej. sólo bonos/fondos).")

        st.subheader("Operaciones")
        if not txs.empty:
            tcols = {
                "tx_date": "Fecha", "tx_type": "Tipo", "ticker": "Ticker",
                "asset_name": "Activo", "raw_amount": "Monto", "return_pct": "Var. %",
            }
            show = txs.copy()
            show["return_pct"] = (show["return_pct"] * 100).round(1)
            st.dataframe(
                show[list(tcols)].rename(columns=tcols),
                use_container_width=True, hide_index=True,
            )

# --------------------------------------------------------------- Operaciones ---
with tab_ops:
    st.caption("Compras valuadas (con ticker y precio), ordenadas por la variación del activo.")
    col_a, col_b = st.columns(2)

    def _ops_table(df: pd.DataFrame, container):
        if df.empty:
            container.info("Aún no hay operaciones valuadas. Corre `run_enrich.py`.")
            return
        d = df.copy()
        d["congresista"] = (
            d["first_name"].fillna("").str.strip() + " " + d["last_name"].fillna("")
        ).str.strip()
        d["return_pct"] = (d["return_pct"] * 100).round(1)
        cols = {
            "congresista": "Congresista", "ticker": "Ticker", "tx_date": "Fecha",
            "return_pct": "Var. %", "raw_amount": "Monto", "est_gain_max": "P/L est. ≤ ($)",
        }
        container.dataframe(
            d[list(cols)].rename(columns=cols), use_container_width=True, hide_index=True
        )

    col_a.markdown("#### 🟢 Mejores")
    _ops_table(data["winners"], col_a)
    col_b.markdown("#### 🔴 Peores")
    _ops_table(data["losers"], col_b)
