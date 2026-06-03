"""Pruebas de la Fase 1 (parsing del indice) sin tocar la red."""
import io
import zipfile

from backend.ingest import index_ingest

SAMPLE = (
    "Prefix\tLast\tFirst\tSuffix\tFilingType\tStateDst\tYear\tFilingDate\tDocID\n"
    "Hon.\tPelosi\tNancy\t\tP\tCA11\t2026\t1/23/2026\t20033725\n"
    "\tAdair\tPatti\t\tC\tOR05\t2026\t5/5/2026\t10076351\n"
)


def _zip_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2026FD.txt", text)
    return buf.getvalue()


def test_parse_index_txt_basic():
    rows = index_ingest.parse_index_txt(_zip_bytes(SAMPLE))
    assert len(rows) == 2

    pelosi = rows[0]
    assert pelosi["last_name"] == "Pelosi"
    assert pelosi["filing_type"] == "P"
    assert pelosi["filing_date"] == "2026-01-23"
    assert pelosi["pdf_url"].endswith("/ptr-pdfs/2026/20033725.pdf")


def test_non_ptr_has_no_pdf_url():
    rows = index_ingest.parse_index_txt(_zip_bytes(SAMPLE))
    adair = rows[1]
    assert adair["filing_type"] == "C"
    assert adair["pdf_url"] is None
