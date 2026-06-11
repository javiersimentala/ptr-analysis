"""Descarga de los PDFs de los PTR (Fase 2).

`pdf_downloader.py` recorre la tabla `filings` buscando PTR aun no descargados y
baja cada PDF a `data/raw/ptr/{ano}/{DocID}.pdf`. Incluye cache en disco (no
re-descarga lo existente), pausa entre peticiones (cortesia con el servidor) y
reintentos con backoff; al terminar marca `downloaded = 1` en la base.
"""
