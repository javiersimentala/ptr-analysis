"""Pruebas de la Fase 2 (descargador de PDFs) sin tocar la red."""
import sqlite3

import pytest

from backend import config
from backend.db import database
from backend.download import pdf_downloader as dl


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    database.init_db(c)
    return c


def _insert(c, doc_id, ftype="P", downloaded=0, year=2026):
    url = f"https://example.test/{doc_id}.pdf" if ftype == "P" else None
    c.execute(
        "INSERT INTO filings (doc_id, last_name, filing_type, year, pdf_url, downloaded) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (doc_id, "Doe", ftype, year, url, downloaded),
    )
    c.commit()


class _FakeResp:
    def __init__(self, content=b"%PDF-1.4 contenido de prueba"):
        self.content = content

    def raise_for_status(self):
        pass


class _FakeSession:
    """Sesion HTTP falsa: registra las URLs pedidas y nunca toca la red."""

    def __init__(self):
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        return _FakeResp()


def test_pending_solo_ptr_no_descargados(conn):
    _insert(conn, "1", ftype="P", downloaded=0)
    _insert(conn, "2", ftype="P", downloaded=1)   # ya descargado
    _insert(conn, "3", ftype="C", downloaded=0)   # no es PTR
    rows = dl.pending_ptrs(conn, year=2026)
    assert [r["doc_id"] for r in rows] == ["1"]


def test_local_pdf_path(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    assert dl.local_pdf_path(2026, "20033725") == tmp_path / "ptr" / "2026" / "20033725.pdf"


def test_descarga_escribe_y_marca(conn, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    _insert(conn, "20033725", ftype="P", downloaded=0)
    session = _FakeSession()

    stats = dl.download_year(2026, conn=conn, session=session, delay=0)

    assert stats["downloaded"] == 1
    pdf = tmp_path / "ptr" / "2026" / "20033725.pdf"
    assert pdf.read_bytes().startswith(b"%PDF")
    assert conn.execute(
        "SELECT downloaded FROM filings WHERE doc_id='20033725'"
    ).fetchone()[0] == 1

    # Idempotencia: tras descargar, ya no quedan pendientes.
    stats2 = dl.download_year(2026, conn=conn, session=session, delay=0)
    assert stats2["total"] == 0


def test_cache_evita_segunda_descarga(conn, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    _insert(conn, "999", ftype="P", downloaded=0)
    # Pre-crea el archivo en cache.
    dest = dl.local_pdf_path(2026, "999")
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"%PDF cache previo")
    session = _FakeSession()

    stats = dl.download_year(2026, conn=conn, session=session, delay=0)

    assert session.calls == []          # nunca se llamo a la red
    assert stats["cached"] == 1
