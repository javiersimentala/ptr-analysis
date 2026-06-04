# PTR Analysis — Periodic Transaction Reports del Congreso de EE.UU.

Pipeline de **scraping y análisis** de los *Periodic Transaction Reports* (PTR)
que los congresistas de la Cámara de Representantes de EE.UU. están obligados a
publicar a través del [House Clerk](https://disclosures-clerk.house.gov/FinancialDisclosure).

El objetivo es, por cada congresista, **listar y almacenar todas sus operaciones**
(compra/venta de activos), estimar el **precio al momento de la operación** y el
**precio actual**, calcular la **ganancia/pérdida** y reconstruir su **portafolio**.

> ⚖️ **Aviso:** toda la información proviene de divulgaciones públicas oficiales.
> Este proyecto es con fines de investigación y educativos. **No es asesoría de
> inversión.**

---

## 📐 Realidad de los datos (leer antes de usar)

Un PTR **no** declara precios ni cantidades exactas. Sólo declara, por operación:
activo, *ticker* (a veces), tipo (compra `P` / venta `S` / intercambio `E`),
fecha y un **rango de monto** (p. ej. `$1,001 – $15,000`). Por lo tanto:

- El **precio de compra** y el **precio actual** se **derivan** de un proveedor de
  mercado (ticker + fecha histórica), no salen del reporte.
- La **ganancia/pérdida** es una **estimación por rango**, no un número exacto.
- Activos sin ticker (bonos, fondos privados, opciones, inmuebles) se marcan como
  **no valuables** automáticamente.

**Fuentes oficiales** (sin necesidad de scrapear el formulario "Search"):

| Recurso | URL |
|---|---|
| Índice anual (ZIP con `{year}FD.txt`) | `…/public_disc/financial-pdfs/{year}FD.zip` |
| PDF de cada PTR (e-filed) | `…/public_disc/ptr-pdfs/{year}/{DocID}.pdf` |

---

## 🗂️ Estructura del proyecto

```
ptr-analysis/
├── backend/
│   ├── config.py          # rutas, URLs y constantes
│   ├── db/                # esquema SQLite + acceso a datos
│   └── ingest/            # Fase 1 — ingesta del índice (FD.txt)
├── scripts/               # entradas de línea de comandos
├── notebooks/             # exploración (parsing de PDFs, validación)
├── tests/                 # pruebas con pytest
├── data/                  # raw/ y processed/  (ignorado por git)
├── frontend/              # dashboard Streamlit  (Fase 7)
├── requirements.txt
└── pyproject.toml
```

---

## 🚀 Puesta en marcha

```bash
# 1. Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell

# 2. Instalar dependencias (necesarias a partir de la Fase 2)
pip install -r requirements.txt

# 3. Ejecutar la Fase 1 — ingesta del índice (un año, un rango o 'all')
python scripts/run_ingest.py 2026          # un año
python scripts/run_ingest.py 2013-2026     # un rango
python scripts/run_ingest.py all           # todos los años disponibles (2008+)

# 4. Ejecutar la Fase 2 — descargar los PDFs de los PTR
python scripts/run_download.py 2026 --limit 10   # quita --limit para todos

# 5. Ejecutar la Fase 3 — parsear los PDFs a la tabla `transactions`
python scripts/run_parse.py 2026

# 6. Ejecutar la Fase 4 — precios de mercado y P/L estimado (yfinance)
python scripts/run_enrich.py            # usa --limit N para acotar

# 7. Ejecutar la Fase 5 — portafolio y P/L por congresista
python scripts/run_portfolio.py

# 8. Correr las pruebas
pytest
```

La Fase 1 descarga el índice del año, lo carga en `data/processed/ptr.db`
(SQLite) e imprime el conteo por tipo de filing. La Fase 2 baja los PDFs de
cada PTR a `data/raw/ptr/{año}/` con caché y rate-limiting. La Fase 3 parsea
cada PDF y carga la tabla `transactions` (activo, ticker, tipo, fecha y rango
de monto). La Fase 4 añade, vía yfinance, el precio en la fecha de la operación
y el actual, y estima la ganancia/pérdida por rango. La Fase 5 agrega todo por
congresista en `members` (resumen, P/L, win-rate) y `positions` (posición neta
estimada por ticker, con el punto medio del rango).

---

## 🗺️ Hoja de ruta

| Fase | Descripción | Estado |
|---|---|---|
| **0** | Setup: repo, estructura, CI/git, docs | ✅ |
| **1** | Ingesta del índice (`FD.txt` → tabla `filings`) | ✅ |
| **2** | Descarga de los PDFs de cada PTR (con caché y rate-limit) | ✅ |
| **3** | Parsing de PDFs → tabla `transactions` | ✅ |
| **4** | Enriquecimiento con precios de mercado (yfinance) | ✅ |
| **5** | Portafolio y P/L estimado por congresista | ✅ |
| **6** | API (FastAPI) | ⏳ |
| **7** | Frontend (Streamlit) | ⏳ |

> **Cobertura histórica:** el índice existe desde **2008**, pero los PTR
> (operaciones) sólo desde **2013** (STOCK Act): ~8,200 PTR en 2013–2026
> (≈450–830/año). Los e-filed se parsean como texto; los **escaneados** (sobre
> todo 2013 e inicios de 2014) requieren OCR (pendiente). Carga histórica completa:
> `python scripts/run_ingest.py all && python scripts/run_download.py all && python scripts/run_parse.py all`.

---

## 🌳 Estrategia de ramas

- `main` — estable / publicable.
- `develop` — integración de las fases.
- `feature/*` — una rama por unidad de trabajo (p. ej. `feature/pdf-download`,
  `feature/pdf-parser`). Se integran a `develop` vía Pull Request.

---

## 📓 Bitácora

El historial de decisiones y cambios del proyecto se documenta en
[`MEMORY.md`](MEMORY.md).
