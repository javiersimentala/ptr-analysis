"""Fase 2 - Descargador de PDFs de los Periodic Transaction Reports.

Recorre la tabla ``filings`` buscando PTR (tipo P) aun no descargados y baja
cada PDF a ``data/raw/ptr/{year}/{doc_id}.pdf``. Caracteristicas:

- **Cache en disco:** no vuelve a descargar un PDF que ya existe.
- **Rate-limiting:** pausa entre descargas para ser cortes con el House Clerk.
- **Reintentos** con backoff ante errores transitorios (429 / 5xx).
- Marca ``downloaded=1`` en la base al terminar cada archivo.

Separa la peticion HTTP (``download_pdf``) de la orquestacion (``download_year``)
para poder probar la logica de cache/estado sin tocar la red.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend import config
from backend.db import database


def build_session() -> requests.Session:
    """Crea una sesion HTTP con User-Agent propio y reintentos con backoff."""
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})
    retry = Retry(
        total=config.DOWNLOAD_RETRIES,
        backoff_factor=1.0,  # espera 0s, 1s, 2s, 4s... entre reintentos
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def local_pdf_path(year: int, doc_id: str) -> Path:
    """Ruta local destino del PDF de un PTR."""
    return config.RAW_DIR / "ptr" / str(year) / f"{doc_id}.pdf"


def pending_ptrs(
    conn: sqlite3.Connection, year: int | None = None, limit: int | None = None
) -> list[sqlite3.Row]:
    """Devuelve los PTR (tipo P) con PDF aun no descargado."""
    sql = (
        "SELECT doc_id, year, pdf_url FROM filings "
        "WHERE filing_type = 'P' AND downloaded = 0 AND pdf_url IS NOT NULL"
    )
    params: list = []
    if year is not None:
        sql += " AND year = ?"
        params.append(year)
    sql += " ORDER BY filing_date"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def download_pdf(
    session: requests.Session, url: str, dest: Path, *, overwrite: bool = False
) -> str:
    """Descarga un PDF a ``dest``. Devuelve 'cached' o 'downloaded'.

    Si el archivo ya existe (y no esta vacio) no se vuelve a descargar.
    """
    if dest.exists() and dest.stat().st_size > 0 and not overwrite:
        return "cached"
    resp = session.get(url, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return "downloaded"


def mark_downloaded(conn: sqlite3.Connection, doc_id: str) -> None:
    conn.execute("UPDATE filings SET downloaded = 1 WHERE doc_id = ?", (doc_id,))
    conn.commit()


def download_year(
    year: int = config.DEFAULT_YEAR,
    *,
    limit: int | None = None,
    delay: float = config.RATE_LIMIT_SECONDS,
    conn: sqlite3.Connection | None = None,
    session: requests.Session | None = None,
    on_event=None,
) -> dict:
    """Descarga los PDFs pendientes de un anio.

    Args:
        limit: maximo de PDFs a bajar en esta corrida (None = todos).
        delay: segundos de pausa tras cada descarga real (no aplica a cache).
        conn/session: inyectables para pruebas; si no, se crean por defecto.
        on_event: callback opcional ``fn(doc_id, result)`` para mostrar progreso.

    Returns:
        dict con conteos: total, downloaded, cached, failed.
    """
    close_conn = conn is None
    conn = conn or database.get_connection()
    if close_conn:
        database.init_db(conn)
    session = session or build_session()

    rows = pending_ptrs(conn, year=year, limit=limit)
    stats = {"total": len(rows), "downloaded": 0, "cached": 0, "failed": 0}

    try:
        for row in rows:
            dest = local_pdf_path(row["year"], row["doc_id"])
            try:
                result = download_pdf(session, row["pdf_url"], dest)
            except Exception as exc:  # red, 404, timeout, etc.
                stats["failed"] += 1
                if on_event:
                    on_event(row["doc_id"], f"failed: {type(exc).__name__}")
                continue

            mark_downloaded(conn, row["doc_id"])
            stats[result] += 1
            if on_event:
                on_event(row["doc_id"], result)
            if result == "downloaded" and delay:
                time.sleep(delay)
    finally:
        if close_conn:
            conn.close()

    return stats
