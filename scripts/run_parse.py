"""CLI de la Fase 3: parsea los PDFs descargados y carga `transactions`.

Uso:
    python scripts/run_parse.py                 # todos los descargados sin parsear
    python scripts/run_parse.py 2026 --limit 20

Requiere haber corrido antes las Fases 1 (índice) y 2 (descarga).
"""
import argparse
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402
from backend.parse import ptr_parser  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Parsea PDFs de PTR a transacciones.")
    parser.add_argument("year", nargs="?", type=int, default=config.DEFAULT_YEAR)
    parser.add_argument("--limit", type=int, default=None, help="máximo de PDFs a parsear")
    parser.add_argument("--quiet", action="store_true", help="no mostrar por archivo")
    args = parser.parse_args()

    print(f"Parseando PDFs de PTR del año {args.year} (limit={args.limit})...\n")

    def progress(doc_id: str, result: str) -> None:
        if not args.quiet:
            print(f"  {doc_id}: {result}")

    stats = ptr_parser.parse_all(args.year, limit=args.limit, on_event=progress)

    print(
        f"\nResumen: {stats['files']} PDFs parseados, "
        f"{stats['transactions']} transacciones cargadas, "
        f"{stats['empty']} sin transacciones, {stats['failed']} fallidos."
    )


if __name__ == "__main__":
    main()
