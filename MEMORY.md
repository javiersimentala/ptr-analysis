# Bitácora del proyecto — PTR Analysis

Registro cronológico de decisiones, cambios y aprendizajes. La entrada más
reciente va arriba.

---

## 2026-06-03 — Soporte histórico multi-año (2008→2026)

- Ingesta multi-año: `index_ingest.ingest_years` + CLI `run_ingest.py` acepta año,
  rango (`2013-2026`) o `all`. `run_download.py` y `run_parse.py` aceptan `all`.
- **Parser tolerante al formato antiguo (~2014-2016):** tipo/owner en minúscula
  (`s`→S, `sP`→SP), ticker sin código `[ST]` (último paréntesis), terminadores de
  tabla case-insensitive (IPO / certificación) además del pie de asteriscos.
- **Validación:** índice histórico completo cargado = **40,775 filings (2008-2026),
  8,213 PTR**. End-to-end en años viejos: 2014 → 131 tx (121 con ticker) tras el fix.
- **Límites:** los PTR (operaciones) existen desde **2013** (antes, 0). Los
  **escaneados** (DocID corto, frecuentes en 2013/inicios 2014) dan 0 tx y necesitan
  **OCR** (pendiente). Descargar los ~8,200 PDFs es un lote largo (~1 req/s).
- Rama `feature/multi-year`.

---

## 2026-06-03 — Fase 4 (precios de mercado y P/L estimado)

- `backend/market/prices.py`: para cada transacción con ticker obtiene vía
  **yfinance** el cierre en/antes de `tx_date` (`price_at_tx`) y el último cierre
  (`price_current`); calcula `return_pct` y, para compras, `est_gain_min/max`
  (rango de monto × variación). Cachea cierres en la tabla `prices`. El proveedor
  de datos es **inyectable** (`fetcher`) para probar sin red.
- Nuevas columnas en `transactions`: `price_at_tx, price_current, return_pct,
  est_gain_min, est_gain_max, price_status` (ok / no_ticker / no_price) + migración.
- CLI `scripts/run_enrich.py`; tests herméticos en `tests/test_market_prices.py`.
- **Validado con yfinance real** (8 tickers, 22 tx): p. ej. AA +93.1% (compra
  2024-10-23 a $41.88, actual $80.86), AAPL +34.5%. Precios coherentes.
- Recordatorio: P/L es **estimación por rango** (los PTR no declaran cantidades);
  activos sin ticker (bonos, fondos, notas) se marcan `no_ticker`.
- Construido en `feature/market-data` → PR a `develop`.

---

## 2026-06-03 — Fase 3 (parsing de PDFs → transacciones)

- `backend/parse/ptr_parser.py`: extrae las transacciones del texto del PDF
  (`pdfplumber`). Parser line-based anclado en `<Tipo> <Fecha> <Notif> <Monto>`;
  maneja nombres de activo partidos en varias líneas, monto máximo en línea
  siguiente, owner (JT/SP/DC), ticker (paréntesis en activos `[ST]/[OP]`) y código
  de tipo de activo (`[XX]`). Normaliza los NUL (`\x00`) de las etiquetas.
- Nueva columna `transactions.asset_type` + migración idempotente en `init_db`.
- CLI `scripts/run_parse.py`; tests herméticos en `tests/test_ptr_parser.py`.
- **Validación sobre datos reales:** 28 PDFs → **350 transacciones** (P=257, S=92,
  E=1), 283 con ticker (185 distintos), 0 montos invertidos, 0 sin fecha, 0 fallos.
  2 PDFs sin transacciones (probables escaneados → OCR a futuro).
- Construido en `feature/pdf-parser` → PR a `develop`.

---

## 2026-06-03 — Fase 2 (descarga de PDFs)

- `backend/download/pdf_downloader.py`: descarga los PDFs de los PTR pendientes
  (`filings.filing_type='P'`, `downloaded=0`) a `data/raw/ptr/{año}/{DocID}.pdf`.
- **Caché** (no re-descarga), **rate-limiting** (`RATE_LIMIT_SECONDS`), **reintentos**
  con backoff (429/5xx) vía `urllib3 Retry`, `User-Agent` propio. Marca `downloaded=1`.
- CLI `scripts/run_download.py [año] [--limit N] [--delay S]`. Tests en
  `tests/test_pdf_downloader.py` (sesión HTTP falsa, sin red).
- Verificado en vivo: 3 PDFs reales descargados del House Clerk (~68 KB c/u).
- Construido en la rama `feature/pdf-download` → PR a `develop`.

---

## 2026-06-03 — Infra: GitHub CLI + CI

- Instalado **GitHub CLI (gh 2.93)** y `gh auth setup-git`: ahora `git push`/`pull`
  funcionan desde la máquina sin el conector MCP (cuenta `javiersimentala`).
- Añadido workflow de **CI** (`.github/workflows/ci.yml`) que corre `pytest` en
  cada push/PR a `main` y `develop`.
- **Seguridad:** `.gitignore` reforzado para bloquear claves privadas y archivos
  de secretos (`*.pem`, `*.key`, `id_rsa`, `credentials.json`, `.env.*`, etc.) y
  job de **gitleaks** en CI que falla si se intenta subir algún secreto.
  Auditoría inicial: 0 secretos en el historial.

---

## 2026-06-03 — Fase 0 (setup) + Fase 1 (ingesta del índice)

**Decisiones de arranque**
- Repositorio en carpeta **local** (`C:\Users\javie\Proyectos\ptr-analysis`),
  no dentro de Google Drive (Drive sincroniza `.git` y puede corromper el repo).
  Los datos pesados pueden respaldarse a Drive por separado.
- GitHub **público**, conectado vía el conector MCP de GitHub.
- Orden de construcción: **backend / scraping primero**, frontend después.
- Stack: Python 3.14 · SQLite · `pdfplumber` (parsing) · `yfinance` (mercado) ·
  FastAPI (API) · Streamlit (frontend).

**Hallazgos sobre los datos**
- La fuente oficial publica un **ZIP anual** (`{year}FD.zip`) con `{year}FD.txt`
  (tab-delimited). No hace falta scrapear el formulario "Search".
- Cada PTR e-filed tiene un PDF en una URL predecible:
  `…/ptr-pdfs/{year}/{DocID}.pdf` (verificado: responde `application/pdf`).
- Tipos de filing relevantes: sólo **`P` = Periodic Transaction Report** tiene
  operaciones bursátiles. En el índice 2026 hay ~227 PTR.
- ⚠️ Un PTR declara **rangos de monto**, no precios/cantidades exactas. El precio
  de compra y el actual deben derivarse de datos de mercado por ticker+fecha.

**Implementado**
- Estructura del repo, `.gitignore`, `.gitattributes`, `requirements.txt`,
  `pyproject.toml`, `LICENSE` (MIT), `README.md`.
- Esquema SQLite (`filings`, `transactions`, `prices`).
- **Fase 1** — `backend/ingest/index_ingest.py`: descarga el ZIP, parsea el
  `FD.txt` y carga la tabla `filings` (sólo librería estándar). CLI en
  `scripts/run_ingest.py`. Pruebas en `tests/test_index_ingest.py`.

**Siguiente**
- Fase 2: descargar los PDFs de los PTR con caché y rate-limiting.
