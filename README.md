# PTR Analysis

Pipeline de extraccion y analisis de los *Periodic Transaction Reports* (PTR) que
los representantes de la Camara de Representantes de los Estados Unidos estan
obligados a publicar a traves del
[House Clerk](https://disclosures-clerk.house.gov/FinancialDisclosure).

Por cada congresista, el proyecto lista y almacena todas sus operaciones de
compra/venta de activos, estima el precio en la fecha de la operacion y el precio
actual, calcula una ganancia/perdida estimada y reconstruye un portafolio. Sobre
esos datos ofrece una interfaz web (FastAPI) con ranking, busqueda, comparacion
de portafolios y un portafolio optimo (media-varianza).

> **Aviso.** Toda la informacion proviene de divulgaciones publicas oficiales.
> Este proyecto es para investigacion y educacion. No constituye asesoria de
> inversion. El P/L es una estimacion por rango (ver "Realidad de los datos").

---

## Tabla de contenido

1. [Realidad de los datos](#realidad-de-los-datos)
2. [Arquitectura y estructura](#arquitectura-y-estructura)
3. [Modelo de datos](#modelo-de-datos)
4. [Instalacion](#instalacion)
5. [Pipeline de datos paso a paso](#pipeline-de-datos-paso-a-paso)
6. [Referencia de scripts](#referencia-de-scripts)
7. [Interfaz web y API](#interfaz-web-y-api)
8. [Pruebas](#pruebas)
9. [Estrategia de ramas](#estrategia-de-ramas)

---

## Realidad de los datos

Un PTR no declara precios ni cantidades exactas. Por cada operacion declara:
activo, ticker (a veces), tipo (compra `P` / venta `S` / intercambio `E`), fecha y
un rango de monto (por ejemplo `$1,001 - $15,000`). En consecuencia:

- El precio de compra y el precio actual se derivan de un proveedor de mercado
  (yfinance) por ticker y fecha; no salen del reporte.
- La ganancia/perdida es una estimacion por rango, no un numero exacto.
- Activos sin ticker (bonos, fondos, notas estructuradas) se marcan como no
  valuables (`price_status = 'no_ticker'`).

Fuentes oficiales (no hace falta scrapear el formulario "Search"):

| Recurso | URL |
|---|---|
| Indice anual (ZIP con `{ano}FD.txt`) | `.../public_disc/financial-pdfs/{ano}FD.zip` |
| PDF de cada PTR (e-filed) | `.../public_disc/ptr-pdfs/{ano}/{DocID}.pdf` |

Cobertura historica: el indice existe desde 2008, pero los PTR (operaciones)
existen desde 2013 (STOCK Act): aproximadamente 8,200 PTR entre 2013 y 2026
(unos 450 a 830 por ano). Los PDFs e-filed se parsean como texto; los escaneados
(sobre todo 2013 e inicios de 2014, con DocID corto) no tienen texto y dan cero
transacciones: requeririan OCR (pendiente).

---

## Arquitectura y estructura

```
ptr-analysis/
|-- backend/
|   |-- config.py            Rutas, URLs y parametros centrales.
|   |-- db/
|   |   |-- schema.sql       Esquema SQLite (todas las tablas).
|   |   |-- database.py      Conexion (WAL) + creacion/migracion de tablas.
|   |-- ingest/
|   |   |-- index_ingest.py  Fase 1: descarga el ZIP del indice y carga `filings`.
|   |-- download/
|   |   |-- pdf_downloader.py Fase 2: descarga los PDFs de los PTR (cache + rate-limit).
|   |-- parse/
|   |   |-- ptr_parser.py     Fase 3: PDF -> transacciones (formato moderno y antiguo).
|   |-- market/
|   |   |-- prices.py         Fase 4: precios (yfinance) y P/L estimado.
|   |-- portfolio/
|   |   |-- builder.py        Fase 5: agrega `members` y `positions`.
|   |   |-- queries.py        Consultas de lectura para la web.
|   |   |-- optimize.py       Portafolio optimo (media-varianza / Markowitz).
|   |-- api/
|       |-- main.py           Aplicacion FastAPI: paginas HTML + API JSON.
|-- frontend/
|   |-- templates/           Plantillas Jinja2 (base, filings, politician, ...).
|   |-- static/styles.css    Estilos propios minimos (Tailwind se carga por CDN).
|-- scripts/                 Puntos de entrada de linea de comandos (ver referencia).
|-- notebooks/               Exploracion (parsing de PDFs).
|-- tests/                   Pruebas con pytest.
|-- data/                    raw/ (PDFs, ZIPs) y processed/ (SQLite). Ignorado por git.
|-- requirements.txt
|-- pyproject.toml
```

El proyecto es 100% Python. La web usa FastAPI + Jinja2 con Tailwind cargado por
CDN: no hay paso de compilacion de JavaScript.

---

## Modelo de datos

Base SQLite en `data/processed/ptr.db`. Tablas principales:

- `filings`      Indice de presentaciones (una fila por documento; `filing_type='P'`
                 son los PTR). Marca `downloaded` y `parsed`.
- `transactions` Operaciones extraidas de cada PTR (activo, ticker, tipo, fecha,
                 rango de monto y, tras la Fase 4, precios y P/L estimado).
- `prices`       Cache de cierres por ticker y fecha (yfinance).
- `members`      Resumen por congresista (operaciones, invertido, P/L, win-rate).
- `positions`    Posicion neta estimada por congresista y ticker.
- `optimal_weights` / `optimal_meta`  Resultado del portafolio optimo.

Las tablas `members`, `positions` y las `optimal_*` son derivadas: se reconstruyen
desde `transactions` y se pueden regenerar en cualquier momento.

---

## Instalacion

Requisitos: Python 3.11 o superior.

```bash
# 1. Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate           # Linux / macOS

# 2. Instalar dependencias
pip install -r requirements.txt
```

La Fase 1 (ingesta del indice) funciona solo con la libreria estandar; el resto de
las fases necesitan las dependencias de `requirements.txt`.

---

## Pipeline de datos paso a paso

Ejecutar en este orden desde la raiz del proyecto. Cada script es idempotente y
se puede repetir sin duplicar datos.

```bash
# 1. Indice de presentaciones -> tabla `filings`
python scripts/run_ingest.py all          # todos los anos (2008+)

# 2. Descargar los PDFs de los PTR -> data/raw/ptr/{ano}/
python scripts/run_download.py all        # lote largo (~8,200 PDFs, ~1 req/s)

# 3. Parsear los PDFs -> tabla `transactions`
python scripts/run_parse.py all

# 4. Precios de mercado y P/L estimado (yfinance) -> columnas de `transactions`
python scripts/run_enrich.py

# 5. Agregar portafolios -> tablas `members` y `positions`
python scripts/run_portfolio.py

# 6. Portafolio optimo (Markowitz) -> tablas `optimal_*`
python scripts/run_optimal.py

# 7. Levantar la web
python scripts/run_web.py                 # http://127.0.0.1:8000
```

Para una prueba rapida sin bajar todo el historico, usar un solo ano y limites:
`run_ingest.py 2026`, `run_download.py 2026 --limit 30`, `run_parse.py 2026`,
`run_enrich.py --limit 20`, `run_portfolio.py`, `run_web.py`.

---

## Referencia de scripts

Todos los scripts viven en `scripts/` y se ejecutan con
`python scripts/<archivo>.py [argumentos]`.

### run_ingest.py  (Fase 1)

Descarga el ZIP del indice anual publicado por el House Clerk, extrae el archivo
`{ano}FD.txt` (separado por tabuladores) y carga/actualiza la tabla `filings`. Solo
usa la libreria estandar.

| Argumento | Descripcion | Por defecto |
|---|---|---|
| `año` (posicional) | Un ano (`2026`), un rango (`2013-2026`) o `all` (2008+) | ano de `config.DEFAULT_YEAR` |

```bash
python scripts/run_ingest.py 2026
python scripts/run_ingest.py 2013-2026
python scripts/run_ingest.py all
```
Prerrequisitos: ninguno. Salida: cuantos filings se cargaron por tipo y cuantos PTR.

### run_download.py  (Fase 2)

Recorre la tabla `filings` buscando PTR aun no descargados y baja cada PDF a
`data/raw/ptr/{ano}/{DocID}.pdf`. Tiene cache en disco (no re-descarga lo
existente), pausa entre descargas (cortesia con el servidor) y reintentos con
backoff ante errores transitorios.

| Argumento | Descripcion | Por defecto |
|---|---|---|
| `año` (posicional) | Un ano (`2025`) o `all` (todos) | ano por defecto |
| `--limit N` | Maximo de PDFs a bajar en esta corrida | sin limite |
| `--delay S` | Pausa en segundos entre descargas | `1.0` |

```bash
python scripts/run_download.py 2026 --limit 30
python scripts/run_download.py all
```
Prerrequisitos: haber corrido `run_ingest.py`. Nota: bajar todo el historico tarda
alrededor de dos horas a 1 peticion/segundo; se puede correr por tramos.

### run_parse.py  (Fase 3)

Parsea los PDFs ya descargados y carga la tabla `transactions`. Extrae por
operacion: owner (JT/SP/DC), activo, ticker, tipo de activo, tipo de operacion,
fecha, fecha de notificacion y rango de monto. Maneja el formato moderno y el
antiguo (~2014, con minusculas y sin codigo de tipo de activo). Los PDFs
escaneados producen cero transacciones (se marcan como vacios, no fallan).

| Argumento | Descripcion | Por defecto |
|---|---|---|
| `año` (posicional) | Un ano o `all` | ano por defecto |
| `--limit N` | Maximo de PDFs a parsear | sin limite |
| `--quiet` | No imprimir el detalle por archivo | desactivado |

```bash
python scripts/run_parse.py all --quiet
```
Prerrequisitos: haber corrido `run_download.py`.

### run_enrich.py  (Fase 4)

Para cada transaccion con ticker obtiene, via yfinance, el cierre en (o antes de)
la fecha de la operacion (`price_at_tx`) y el ultimo cierre (`price_current`);
calcula `return_pct` y, para compras, `est_gain_min`/`est_gain_max` (rango de monto
por la variacion). Cachea los cierres en la tabla `prices`. Las transacciones sin
ticker se marcan como `no_ticker`.

| Argumento | Descripcion | Por defecto |
|---|---|---|
| `--limit N` | Maximo de tickers a procesar | sin limite |
| `--quiet` | No imprimir el detalle por ticker | desactivado |

```bash
python scripts/run_enrich.py --limit 50
python scripts/run_enrich.py
```
Prerrequisitos: haber corrido `run_parse.py`. Nota: yfinance es gratuito pero no
oficial; los tickers no encontrados o deslistados se marcan `no_price`.

### run_portfolio.py  (Fase 5)

Agrega las `transactions` por congresista (clave `apellido|nombre|estado-distrito`)
en dos tablas: `members` (resumen, P/L estimado y win-rate de compras valuadas) y
`positions` (posicion neta estimada por ticker = suma de puntos medios de compras
menos ventas). Reconstruye ambas tablas en cada corrida.

| Argumento | Descripcion | Por defecto |
|---|---|---|
| `--top N` | Cuantos congresistas mostrar en el resumen | `15` |

```bash
python scripts/run_portfolio.py --top 30
```
Prerrequisitos: haber corrido `run_parse.py` (y `run_enrich.py` para el P/L).

### run_optimal.py  (Portafolio optimo)

Toma el universo de tickers con mayor posicion neta agregada del Congreso (tabla
`positions`), descarga su historial de precios via yfinance, calcula el portafolio
de maximo ratio de Sharpe (solo posiciones largas, totalmente invertido) y guarda
los pesos en `optimal_weights` y las metricas en `optimal_meta`. La web solo lee el
resultado ya calculado.

| Argumento | Descripcion | Por defecto |
|---|---|---|
| `--limit N` | Numero de tickers del universo | `25` |
| `--lookback-days N` | Ventana de historial usada | `504` (~2 anos) |

```bash
python scripts/run_optimal.py --limit 25 --lookback-days 504
```
Prerrequisitos: haber corrido `run_portfolio.py`.

### run_web.py  (Interfaz web)

Levanta el servidor FastAPI (uvicorn) que sirve las paginas HTML y la API JSON.

| Argumento | Descripcion | Por defecto |
|---|---|---|
| `--host H` | Interfaz de red | `127.0.0.1` |
| `--port P` | Puerto | `8000` |
| `--reload` | Recarga en caliente (desarrollo) | desactivado |

```bash
python scripts/run_web.py
python scripts/run_web.py --port 8080 --reload
```
Prerrequisitos: haber corrido al menos `run_ingest.py`, `run_download.py` y
`run_parse.py` (y `run_enrich.py` + `run_portfolio.py` para ver P/L y portafolios).

---

## Interfaz web y API

`python scripts/run_web.py` y abrir `http://127.0.0.1:8000`.

Paginas:

- `/filings`    Tabla de PTR filtrable por congresista y ano, con paginacion.
- `/politicians` Listado de congresistas con buscador por nombre o apellido.
- `/politician?key=...` Portafolio de un congresista: resumen, posicion neta
  estimada por ticker y operaciones, con selector de ano/periodo.
- `/compare?keys=...&keys=...` Comparacion de portafolios lado a lado.
- `/optimal`    Portafolio optimo (media-varianza) ya calculado.

API JSON:

- `GET /api/politicians?q=...`     Lista de congresistas (resumen).
- `GET /api/politician?key=...&year=...`  Resumen, posiciones y P/L de uno.

---

## Pruebas

```bash
pytest
```

Las pruebas son hermeticas: no tocan la red (los proveedores de descarga, precios
y mercado se inyectan o se simulan) ni dependen de la base de produccion. La web se
prueba con el `TestClient` de FastAPI y funciona con base vacia o poblada.

---

## Estrategia de ramas

- `main`      Estable y publicable.
- `develop`   Integracion de los cambios.
- `feature/*` Una rama por unidad de trabajo; se integra a `develop` via Pull
  Request con CI (pruebas + escaneo de secretos) en verde, y `develop` se fusiona a
  `main` por hito.

El historial de decisiones y cambios se documenta en
[`MEMORY.md`](MEMORY.md).
