# Bitácora del proyecto — PTR Analysis

Registro cronológico de decisiones, cambios y aprendizajes. La entrada más
reciente va arriba.

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
