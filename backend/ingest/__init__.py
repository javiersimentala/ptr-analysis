"""Ingesta del indice de Financial Disclosures (Fase 1).

`index_ingest.py` descarga el ZIP anual del House Clerk, extrae el archivo
`{ano}FD.txt` (separado por tabuladores) y carga/actualiza la tabla `filings`. Es
la unica fase que funciona solo con la libreria estandar de Python.
"""
