"""Lanza el servidor web (FastAPI + uvicorn) que sirve las paginas y la API.

Uso:
    python scripts/run_web.py                 # http://127.0.0.1:8000
    python scripts/run_web.py --port 8080
    python scripts/run_web.py --reload        # recarga en caliente (desarrollo)

La web lee la base SQLite generada por el resto del pipeline; conviene haber
corrido al menos run_ingest -> run_download -> run_parse (y run_enrich +
run_portfolio para ver P/L y portafolios).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor web de PTR Analysis.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="recarga en caliente (desarrollo)")
    args = parser.parse_args()

    print(f"Servidor web en http://{args.host}:{args.port}  (Ctrl+C para detener)")
    uvicorn.run("backend.api.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
