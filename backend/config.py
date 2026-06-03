"""Configuracion central del proyecto PTR Analysis.

Todas las rutas y URLs viven aqui para que el resto del backend no tenga
constantes "magicas" repartidas por el codigo.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Rutas del proyecto (este archivo esta en backend/) -------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = PROCESSED_DIR / "ptr.db"

# --- Fuente oficial: House Clerk Financial Disclosure ---------------------
HOUSE_BASE = "https://disclosures-clerk.house.gov/public_disc"
# Indice anual (ZIP que contiene {year}FD.txt y {year}FD.xml)
INDEX_ZIP_URL = HOUSE_BASE + "/financial-pdfs/{year}FD.zip"
# PDF e-filed de cada Periodic Transaction Report
PTR_PDF_URL = HOUSE_BASE + "/ptr-pdfs/{year}/{doc_id}.pdf"

# User-Agent cortes para identificar el scraper y no ser bloqueados.
USER_AGENT = "ptr-analysis/0.1 (research project; contact via GitHub)"

# Mapa de la columna FilingType del indice -> descripcion legible.
FILING_TYPES = {
    "P": "Periodic Transaction Report",
    "A": "Enmienda",
    "C": "Candidato",
    "D": "Borrador",
    "O": "Original",
    "W": "Candidato Write-in",
    "X": "Candidato Retirado",
    "T": "Terminacion",
}

# Ano por defecto a ingestar (configurable por variable de entorno).
DEFAULT_YEAR = int(os.environ.get("PTR_DEFAULT_YEAR", "2026"))
