"""Fase 1 - Ingesta del indice de Financial Disclosures.

Descarga el ZIP anual publicado por el House Clerk, extrae el archivo
``{year}FD.txt`` (tab-delimited) y carga/actualiza la tabla ``filings``.

Solo usa la libreria estandar (urllib, zipfile, csv) para que la Fase 1
sea ejecutable sin instalar dependencias.
"""
from __future__ import annotations

import csv
import io
import sqlite3
import urllib.request
import zipfile
from datetime import datetime

from backend import config
from backend.db import database


def download_index_zip(year: int) -> bytes:
    """Descarga el ZIP del indice anual y devuelve sus bytes."""
    url = config.INDEX_ZIP_URL.format(year=year)
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def parse_index_txt(raw_zip: bytes) -> list[dict]:
    """Parsea el ``{year}FD.txt`` contenido en el ZIP a una lista de dicts."""
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        text = zf.read(txt_name).decode("utf-8-sig", errors="replace")

    rows: list[dict] = []
    for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
        doc_id = (r.get("DocID") or "").strip()
        if not doc_id:
            continue
        filing_type = (r.get("FilingType") or "").strip()
        year = int((r.get("Year") or "0").strip() or 0)
        rows.append(
            {
                "doc_id": doc_id,
                "prefix": (r.get("Prefix") or "").strip(),
                "last_name": (r.get("Last") or "").strip(),
                "first_name": (r.get("First") or "").strip(),
                "suffix": (r.get("Suffix") or "").strip(),
                "filing_type": filing_type,
                "state_dst": (r.get("StateDst") or "").strip(),
                "year": year,
                "filing_date": _to_iso_date(r.get("FilingDate")),
                "pdf_url": _ptr_pdf_url(filing_type, year, doc_id),
            }
        )
    return rows


def _to_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value  # se conserva el texto original si no se reconoce el formato


def _ptr_pdf_url(filing_type: str, year: int, doc_id: str) -> str | None:
    """Solo los PTR (tipo P) tienen PDF en ptr-pdfs/."""
    if filing_type.upper() == "P":
        return config.PTR_PDF_URL.format(year=year, doc_id=doc_id)
    return None


def upsert_filings(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Inserta o actualiza filings por doc_id. Devuelve cuantos se procesaron."""
    sql = """
        INSERT INTO filings
            (doc_id, prefix, last_name, first_name, suffix,
             filing_type, state_dst, year, filing_date, pdf_url)
        VALUES
            (:doc_id, :prefix, :last_name, :first_name, :suffix,
             :filing_type, :state_dst, :year, :filing_date, :pdf_url)
        ON CONFLICT(doc_id) DO UPDATE SET
            prefix=excluded.prefix, last_name=excluded.last_name,
            first_name=excluded.first_name, suffix=excluded.suffix,
            filing_type=excluded.filing_type, state_dst=excluded.state_dst,
            year=excluded.year, filing_date=excluded.filing_date,
            pdf_url=excluded.pdf_url
    """
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def ingest_year(year: int = config.DEFAULT_YEAR) -> dict:
    """Pipeline completo de la Fase 1 para un ano.

    Devuelve un resumen con el total cargado y el conteo por tipo de filing.
    """
    raw = download_index_zip(year)
    rows = parse_index_txt(raw)

    conn = database.get_connection()
    database.init_db(conn)
    total = upsert_filings(conn, rows)
    cur = conn.execute(
        "SELECT filing_type, COUNT(*) FROM filings WHERE year=? GROUP BY filing_type",
        (year,),
    )
    by_type = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()

    return {"year": year, "total": total, "by_type": by_type}
