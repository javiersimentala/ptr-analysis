"""Fase 3 - Parser de los PDFs de PTR a transacciones estructuradas.

Los PTR e-filed tienen una tabla con columnas:
    ID | Owner | Asset | Transaction Type | Date | Notification Date | Amount | Cap. Gains

El texto extraído (``pdfplumber``) resulta más fiable que la detección de tablas.
Cada transacción se ancla en el patrón ``<Tipo> <Fecha> <Notificación> <Monto>``;
el nombre del activo puede partirse en varias líneas (antes y después del ancla).
Las sub-líneas (``Filing Status:``, ``Subholding Of:``, ``Description:``) llevan
``:`` y se usan como delimitador.

Limitaciones conocidas:
- Sólo PDFs e-filed (con texto). Los escaneados (imagen) darían 0 transacciones y
  requerirían OCR (fase futura).
- Los montos son rangos: se guardan ``amount_min``, ``amount_max`` y el texto crudo.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pdfplumber

from backend import config
from backend.db import database

# Ancla de transacción: Tipo (P/S/E) + fecha + notificación + monto mín [- máx].
# El tipo puede venir en minúscula en los PTR antiguos (~2014-2016).
_ANCHOR = re.compile(
    r"\b([PSEpse])\s+"
    r"(\d{1,2}/\d{1,2}/\d{4})\s+"        # fecha de la operación (año 4 dígitos)
    r"(\d{1,2}/\d{1,2}/\d{4})\s+"        # fecha de notificación
    r"\$([\d,]+)"                         # monto mínimo
    r"(?:\s*-\s*\$?([\d,]+))?"            # monto máximo (puede caer en la línea sig.)
)
_OWNER = re.compile(r"^(JT|SP|DC)\b", re.IGNORECASE)
_TICKER = re.compile(r"\(([A-Za-z][A-Za-z0-9.\-]{0,5})\)")   # moderno (activo con [ST])
_TICKER_STRICT = re.compile(r"\(([A-Za-z]{1,5})\)")          # respaldo formato antiguo
_ASSET_TYPE = re.compile(r"\[([A-Z]{2})\]")
_AMOUNT_TOKEN = re.compile(r"\$([\d,]+)")
# Sub-línea de metadatos: etiqueta corta seguida de ':'.
_META = re.compile(r"^[A-Za-z][\w .,&/()-]{0,30}:")

# Prefijos de líneas a ignorar (cabeceras repetidas, cabecera del PDF). En minúscula.
_NOISE_PREFIXES = (
    "id owner asset", "type date", "$200?", "filing id #", "clerk of the house",
    "digitally signed", "yes no",
)
# Marcadores (case-insensitive) que indican el fin de la tabla de transacciones.
_TERMINATORS = (
    "* for the complete list", "initial public offering",
    "certification and signature", "i certify that",
)

# Tipos de activo cuyo paréntesis SÍ contiene un ticker (acciones / opciones).
_TICKERED_TYPES = {"ST", "OP", "OL"}


def extract_text(pdf_path: str | Path) -> str:
    """Texto concatenado de todas las páginas del PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _iso(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return date_str


def _num(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _is_noise(line: str) -> bool:
    s = line.strip().lower()
    return not s or any(s.startswith(p) for p in _NOISE_PREFIXES)


def _is_terminator(line: str) -> bool:
    s = line.strip().lower()
    return any(t in s for t in _TERMINATORS)


def parse_transactions(text: str) -> list[dict]:
    """Extrae la lista de transacciones del texto de un PTR."""
    # Las etiquetas del PDF (Filing Status, etc.) usan glifos que se extraen como
    # NUL (\x00); se normalizan a espacios para poder detectarlas como metadatos.
    text = text.replace("\x00", " ")

    txs: list[dict] = []
    cur: dict | None = None

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            txs.append(_finalize(cur))
            cur = None

    for raw in text.splitlines():
        line = raw.rstrip()

        if _is_terminator(line):
            flush()
            continue
        if _is_noise(line):
            continue

        m = _ANCHOR.search(line)
        if m:
            flush()
            prefix = line[: m.start()].strip()
            cur = {
                "asset_parts": [prefix] if prefix else [],
                "tx_type": m.group(1).upper(),
                "tx_date": _iso(m.group(2)),
                "notification_date": _iso(m.group(3)),
                "amount_min": _num(m.group(4)),
                "amount_max": _num(m.group(5)),
                "needs_max": m.group(5) is None,
                "seen_meta": False,
            }
            continue

        if cur is None:
            continue

        stripped = line.strip()
        if _META.match(stripped):
            cur["seen_meta"] = True
            continue

        # Línea de continuación: puede traer el monto máximo y/o más nombre.
        if cur["needs_max"]:
            mm = _AMOUNT_TOKEN.search(stripped)
            if mm:
                cur["amount_max"] = _num(mm.group(1))
                cur["needs_max"] = False
                stripped = _AMOUNT_TOKEN.sub("", stripped).strip()
        if stripped and not cur["seen_meta"]:
            cur["asset_parts"].append(stripped)

    flush()
    return txs


def _finalize(cur: dict) -> dict:
    asset = re.sub(r"\s+", " ", " ".join(p for p in cur["asset_parts"] if p)).strip()

    owner = None
    mo = _OWNER.match(asset)
    if mo:
        owner = mo.group(1).upper()
        asset = asset[mo.end():].strip()

    mt = _ASSET_TYPE.search(asset)
    asset_type = mt.group(1) if mt else None

    ticker = None
    if asset_type in _TICKERED_TYPES:
        mk = _TICKER.search(asset)
        if mk:
            ticker = mk.group(1).upper()
    elif asset_type is None:
        # Formato antiguo sin código [XX]: el último paréntesis suele ser el ticker.
        cands = _TICKER_STRICT.findall(asset)
        if cands:
            ticker = cands[-1].upper()

    amin, amax = cur["amount_min"], cur["amount_max"]
    if amin is not None and amax is not None:
        raw_amount = f"${amin:,.0f} - ${amax:,.0f}"
    elif amin is not None:
        raw_amount = f"${amin:,.0f}+"
    else:
        raw_amount = None

    return {
        "owner": owner,
        "asset_name": asset or None,
        "ticker": ticker,
        "asset_type": asset_type,
        "tx_type": cur["tx_type"],
        "tx_date": cur["tx_date"],
        "notification_date": cur["notification_date"],
        "amount_min": amin,
        "amount_max": amax,
        "raw_amount": raw_amount,
    }


def parse_pdf(pdf_path: str | Path) -> list[dict]:
    """Parsea un PDF de PTR y devuelve sus transacciones."""
    return parse_transactions(extract_text(pdf_path))


def insert_transactions(conn: sqlite3.Connection, doc_id: str, txs: list[dict]) -> None:
    conn.execute("DELETE FROM transactions WHERE doc_id = ?", (doc_id,))  # idempotente
    conn.executemany(
        """
        INSERT INTO transactions
            (doc_id, owner, asset_name, ticker, asset_type, tx_type, tx_date,
             notification_date, amount_min, amount_max, raw_amount)
        VALUES
            (:doc_id, :owner, :asset_name, :ticker, :asset_type, :tx_type, :tx_date,
             :notification_date, :amount_min, :amount_max, :raw_amount)
        """,
        [{**t, "doc_id": doc_id} for t in txs],
    )
    conn.commit()


def parse_all(
    year: int | None = None,
    *,
    limit: int | None = None,
    conn: sqlite3.Connection | None = None,
    on_event=None,
) -> dict:
    """Parsea los PTR descargados aún sin procesar y carga ``transactions``.

    Returns:
        dict con conteos: files, transactions, empty, failed.
    """
    close_conn = conn is None
    conn = conn or database.get_connection()
    if close_conn:
        database.init_db(conn)

    sql = (
        "SELECT doc_id, year FROM filings "
        "WHERE filing_type = 'P' AND downloaded = 1 AND parsed = 0"
    )
    params: list = []
    if year is not None:
        sql += " AND year = ?"
        params.append(year)
    sql += " ORDER BY filing_date"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()

    stats = {"files": 0, "transactions": 0, "empty": 0, "failed": 0}
    try:
        for row in rows:
            path = config.RAW_DIR / "ptr" / str(row["year"]) / f"{row['doc_id']}.pdf"
            if not path.exists():
                continue
            try:
                txs = parse_pdf(path)
            except Exception as exc:
                stats["failed"] += 1
                if on_event:
                    on_event(row["doc_id"], f"failed: {type(exc).__name__}")
                continue

            insert_transactions(conn, row["doc_id"], txs)
            conn.execute("UPDATE filings SET parsed = 1 WHERE doc_id = ?", (row["doc_id"],))
            conn.commit()
            stats["files"] += 1
            stats["transactions"] += len(txs)
            if not txs:
                stats["empty"] += 1
            if on_event:
                on_event(row["doc_id"], f"{len(txs)} tx")
    finally:
        if close_conn:
            conn.close()
    return stats
