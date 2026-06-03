"""Acceso a la base de datos SQLite (solo libreria estandar)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from backend import config

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Abre (creando si hace falta) la conexion a SQLite."""
    db_path = db_path or config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Crea las tablas (schema.sql) y aplica migraciones (idempotente)."""
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate(conn)
    conn.commit()


# Columnas añadidas a `transactions` después del esquema inicial (nombre -> tipo).
_TX_ADDED_COLUMNS = {
    "asset_type": "TEXT",
    "price_at_tx": "REAL",
    "price_current": "REAL",
    "return_pct": "REAL",
    "est_gain_min": "REAL",
    "est_gain_max": "REAL",
    "price_status": "TEXT",
}


def _migrate(conn: sqlite3.Connection) -> None:
    """Migra bases creadas con un esquema anterior (añade columnas nuevas)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
    for name, col_type in _TX_ADDED_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE transactions ADD COLUMN {name} {col_type}")
