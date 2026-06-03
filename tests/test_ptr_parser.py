"""Pruebas de la Fase 3 (parser de PTR) con fixtures de texto real, sin PDFs.

Los fixtures reproducen el texto tal cual lo extrae pdfplumber, incluidos los
caracteres NUL (``\\x00``) que aparecen en las etiquetas del formulario.
"""
from backend.parse import ptr_parser as P

# Etiqueta de metadatos como la entrega el PDF (con NUL en vez de espacios).
_FS = "F\x00\x00\x00\x00\x00 S\x00\x00\x00\x00\x00: New"
_SO = "S\x00\x00\x00\x00 O\x00: Stocks, Bonds, & Mutual Funds"

TEXT = (
    "Filing ID #20033713\n"
    "ID Owner Asset Transaction Date Notification Amount Cap.\n"
    "Type Date Gains >\n"
    "$200?\n"
    # 1) Acción, ticker en la misma línea.
    "Coca-Cola Company (KO) [ST] P 12/15/2025 01/02/2026 $1,001 - $15,000\n"
    f"{_FS}\n"
    "D\x00\x00\x00\x00: Automatic reinvestment of dividends earned.\n"
    # 2) Acción cuyo nombre + ticker se parten en líneas posteriores.
    "International Business Machines P 12/12/2025 01/02/2026 $1,001 - $15,000\n"
    "Corporation Common Stock (IBM)\n"
    "[ST]\n"
    f"{_FS}\n"
    # 3) Bono con owner JT y monto máximo en la línea siguiente.
    "JT King CNTY Wash Ltd 4.00% 12/1/32 S 12/18/2025 01/02/2026 $15,001 -\n"
    "[GS] $50,000\n"
    f"{_FS}\n"
    f"{_SO}\n"
    "* For the complete list of asset type abbreviations, please visit ...\n"
    "I CERTIFY that the statements ...\n"
)


def test_numero_de_transacciones():
    txs = P.parse_transactions(TEXT)
    assert len(txs) == 3


def test_accion_simple():
    ko = P.parse_transactions(TEXT)[0]
    assert ko["ticker"] == "KO"
    assert ko["asset_type"] == "ST"
    assert ko["tx_type"] == "P"
    assert ko["tx_date"] == "2025-12-15"
    assert ko["notification_date"] == "2026-01-02"
    assert ko["amount_min"] == 1001 and ko["amount_max"] == 15000
    assert ko["owner"] is None
    assert ko["asset_name"] == "Coca-Cola Company (KO) [ST]"
    # Los metadatos no deben colarse en el nombre del activo.
    assert "New" not in ko["asset_name"] and ":" not in ko["asset_name"]


def test_nombre_partido_en_varias_lineas():
    ibm = P.parse_transactions(TEXT)[1]
    assert ibm["ticker"] == "IBM"
    assert "International Business Machines" in ibm["asset_name"]
    assert ibm["asset_name"].endswith("[ST]")


def test_bono_con_owner_y_monto_partido():
    bond = P.parse_transactions(TEXT)[2]
    assert bond["owner"] == "JT"
    assert bond["tx_type"] == "S"
    assert bond["asset_type"] == "GS"
    assert bond["ticker"] is None                 # los bonos no llevan ticker
    assert bond["amount_min"] == 15001 and bond["amount_max"] == 50000
    assert bond["asset_name"].startswith("King CNTY")


def test_raw_amount_formato():
    ko = P.parse_transactions(TEXT)[0]
    assert ko["raw_amount"] == "$1,001 - $15,000"


# --- Formato antiguo (~2014): minúsculas, sin código [ST], sin pie de asteriscos ---
OLD_TEXT = (
    "Filing ID #20000077\n"
    "tranSactionS\n"
    "iD owner asset transaction Date notification amount\n"
    "type Date\n"
    "sP Hill International, Inc. (HIl) s 12/26/2013 12/30/2013 $15,001 - $50,000\n"
    "FIlINg sTATus: New\n"
    "initial Public offeringS\n"
    "nmlkj Yes nmlkji No\n"
    "certification anD Signature\n"
    "gfedcb I CERTIFY that the statements I have made ...\n"
)


def test_formato_antiguo_2014():
    txs = P.parse_transactions(OLD_TEXT)
    assert len(txs) == 1                       # el pie (IPO/certificación) no genera filas
    t = txs[0]
    assert t["owner"] == "SP"                  # 'sP' -> SP
    assert t["tx_type"] == "S"                 # 's' minúscula -> S
    assert t["ticker"] == "HIL"                # '(HIl)' -> HIL
    assert t["amount_min"] == 15001 and t["amount_max"] == 50000
    assert t["asset_name"].startswith("Hill International")
    assert "certify" not in (t["asset_name"] or "").lower()
