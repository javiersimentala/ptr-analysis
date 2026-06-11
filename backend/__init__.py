"""PTR Analysis: pipeline de extraccion y analisis de los Periodic Transaction
Reports (PTR) que publica la Camara de Representantes de los Estados Unidos.

El backend se organiza por fases, cada una en su propio subpaquete:

    config      Rutas, URLs y parametros centrales (un solo lugar para constantes).
    db          Esquema SQLite y conexion (modo WAL; crea/migra tablas idempotente).
    ingest      Fase 1: descarga e ingesta del indice anual -> tabla `filings`.
    download    Fase 2: descarga de los PDFs de cada PTR (cache + rate-limit).
    parse       Fase 3: parsing de los PDFs -> tabla `transactions`.
    market      Fase 4: precios de mercado (yfinance) y P/L estimado.
    portfolio   Fase 5+: agregacion (`members`, `positions`), consultas y optimizacion.
    api         Aplicacion FastAPI: paginas HTML (Jinja2) y API JSON.

Cada fase tiene un script de entrada en `scripts/` (ver el README para el detalle
de cada uno y el orden de ejecucion).
"""

__version__ = "0.1.0"
