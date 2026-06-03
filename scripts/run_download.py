"""CLI de la Fase 2: descarga los PDFs de los PTR pendientes.

Uso:
    python scripts/run_download.py                 # anio por defecto, todos
    python scripts/run_download.py 2026 --limit 10 # solo 10 (prueba)
    python scripts/run_download.py 2026 --delay 0.5

Requiere que la Fase 1 (ingesta del indice) se haya corrido antes.
"""
import argparse
import sys
from pathlib import Path

# Salida en UTF-8 (la consola de Windows usa cp1252 por defecto).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402
from backend.download import pdf_downloader  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga PDFs de PTR del House Clerk.")
    parser.add_argument(
        "year", nargs="?", default=str(config.DEFAULT_YEAR),
        help="año (p. ej. 2025) o 'all' para todos los años",
    )
    parser.add_argument("--limit", type=int, default=None, help="maximo de PDFs a bajar")
    parser.add_argument(
        "--delay", type=float, default=config.RATE_LIMIT_SECONDS,
        help="pausa en segundos entre descargas",
    )
    args = parser.parse_args()

    year = None if str(args.year).lower() == "all" else int(args.year)
    label = "todos los años" if year is None else f"año {year}"
    print(f"Descargando PDFs de PTR ({label}, limit={args.limit}, delay={args.delay}s)...\n")

    def progress(doc_id: str, result: str) -> None:
        icon = {"downloaded": "[+]", "cached": "[=]"}.get(result, "[!]")
        print(f"  {icon} {doc_id}  {result}")

    stats = pdf_downloader.download_year(
        year, limit=args.limit, delay=args.delay, on_event=progress
    )

    print(
        f"\nResumen: {stats['downloaded']} descargados, "
        f"{stats['cached']} en cache, {stats['failed']} fallidos "
        f"(de {stats['total']} pendientes)."
    )
    print(f"PDFs en: {config.RAW_DIR / 'ptr'}")


if __name__ == "__main__":
    main()
