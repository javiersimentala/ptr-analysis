"""Aplicacion FastAPI: paginas web (Jinja2 + Tailwind) y API JSON.

Arranque local:
    python scripts/run_web.py
    # o, de forma equivalente:
    uvicorn backend.api.main:app --reload

Cada peticion abre una conexion SQLite de solo lectura logica (la base la
generan los scripts del pipeline) y se asegura de que existan las tablas
derivadas (members/positions) llamando a ``queries.ensure_built``.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend import config
from backend.db import database
from backend.portfolio import queries

# Carpeta del frontend (plantillas + estaticos), relativa a la raiz del proyecto.
_FRONTEND = config.PROJECT_ROOT / "frontend"

templates = Jinja2Templates(directory=str(_FRONTEND / "templates"))

app = FastAPI(
    title="PTR Analysis",
    description="Operaciones, portafolios y P/L estimado de los congresistas de EE.UU.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=str(_FRONTEND / "static")), name="static")


# --------------------------------------------------------------------------- #
# Filtros y utilidades de plantilla                                           #
# --------------------------------------------------------------------------- #
def _money(value, dash: str = "—") -> str:
    """Formatea un numero como dolares sin decimales; '—' si es None."""
    return dash if value is None else f"${value:,.0f}"


def _pct(value, dash: str = "—") -> str:
    """Formatea una fraccion (0.12) como porcentaje (12.0%); '—' si es None."""
    return dash if value is None else f"{value * 100:,.1f}%"


def _display_name(last, first) -> str:
    """Nombre legible 'Nombre Apellido' a partir de las columnas del filing."""
    return f"{(first or '').strip()} {last or ''}".strip()


templates.env.filters["money"] = _money
templates.env.filters["pct"] = _pct
templates.env.globals["display_name"] = _display_name


def _conn():
    """Abre la conexion y garantiza que existan las tablas derivadas."""
    conn = database.get_connection()
    queries.ensure_built(conn)
    return conn


# --------------------------------------------------------------------------- #
# Paginas HTML                                                                #
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    """La raiz redirige a la lista de filings."""
    return RedirectResponse(url="/filings")


@app.get("/filings", response_class=HTMLResponse)
def filings_page(
    request: Request, key: str | None = None, year: int | None = None, page: int = 1
):
    """Tabla paginada de PTR, filtrable por congresista y año."""
    per_page = 50
    page = max(1, page)
    conn = _conn()
    try:
        total = queries.count_filings(conn, member_key=key, year=year)
        rows = queries.list_filings(
            conn, member_key=key, year=year, limit=per_page, offset=(page - 1) * per_page
        )
        members = queries.list_members(conn, limit=2000)
        years = queries.available_years(conn)
    finally:
        conn.close()
    pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        request,
        "filings.html",
        {
            "active": "filings", "rows": rows, "members": members,
            "years": years, "sel_key": key, "sel_year": year, "page": page,
            "pages": pages, "total": total,
        },
    )


@app.get("/politicians", response_class=HTMLResponse)
def politicians_page(request: Request, q: str = ""):
    """Lista de congresistas con buscador por nombre/apellido."""
    conn = _conn()
    try:
        members = queries.list_members(conn, search=q, limit=2000)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request,
        "politicians.html",
        {"active": "politicians", "members": members, "q": q},
    )


@app.get("/politician", response_class=HTMLResponse)
def politician_page(request: Request, key: str, year: int | None = None):
    """Portafolio de un congresista: resumen, posiciones y operaciones del periodo."""
    conn = _conn()
    try:
        member = queries.member(conn, key)
        summary = queries.member_period_summary(conn, key, year=year)
        positions = queries.member_portfolio(conn, key, year=year)
        txs = queries.member_transactions(conn, key, year=year, limit=500)
        years = queries.available_years(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request,
        "politician.html",
        {
            "active": "politicians", "member_key": key,
            "m": member, "summary": summary, "positions": positions, "txs": txs,
            "years": years, "sel_year": year,
        },
    )


@app.get("/compare", response_class=HTMLResponse)
def compare_page(request: Request):
    """Comparacion de portafolios (se implementa en el siguiente entregable)."""
    return templates.TemplateResponse(
        request,
        "placeholder.html",
        {
            "active": "compare", "title": "Comparar portafolios",
            "msg": "Comparacion lado a lado entre congresistas. En construccion.",
        },
    )


@app.get("/optimal", response_class=HTMLResponse)
def optimal_page(request: Request):
    """Portafolio optimo (se implementa en el siguiente entregable)."""
    return templates.TemplateResponse(
        request,
        "placeholder.html",
        {
            "active": "optimal", "title": "Portafolio optimo",
            "msg": "Optimizacion media-varianza sobre el universo del Congreso. En construccion.",
        },
    )


# --------------------------------------------------------------------------- #
# API JSON                                                                    #
# --------------------------------------------------------------------------- #
@app.get("/api/politicians")
def api_politicians(q: str = ""):
    """Lista de congresistas (resumen) en JSON."""
    conn = _conn()
    try:
        return [dict(r) for r in queries.list_members(conn, search=q, limit=2000)]
    finally:
        conn.close()


@app.get("/api/politician")
def api_politician(key: str, year: int | None = None):
    """Resumen, posiciones y P/L de un congresista en JSON."""
    conn = _conn()
    try:
        member = queries.member(conn, key)
        summary = queries.member_period_summary(conn, key, year=year)
        return {
            "member": dict(member) if member else None,
            "summary": dict(summary) if summary else None,
            "positions": [dict(r) for r in queries.member_portfolio(conn, key, year=year)],
        }
    finally:
        conn.close()
