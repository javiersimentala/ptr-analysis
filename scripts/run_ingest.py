"""CLI de la Fase 1: descarga y carga el índice de uno o varios años.

Uso:
    python scripts/run_ingest.py              # año por defecto (config)
    python scripts/run_ingest.py 2025         # un año específico
    python scripts/run_ingest.py 2013-2026    # un rango de años
    python scripts/run_ingest.py all          # todos los años disponibles (2008+)

Los PTR (operaciones) existen desde 2013; antes el índice sólo trae otros tipos.
"""
import sys
from pathlib import Path

# La consola de Windows usa cp1252 por defecto; forzamos UTF-8 en la salida.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402
from backend.ingest import index_ingest  # noqa: E402


def parse_years(arg: str) -> list[int]:
    """Convierte 'all', 'A-B' o 'YYYY' en una lista de años."""
    arg = arg.strip().lower()
    if arg == "all":
        return list(range(index_ingest.FIRST_AVAILABLE_YEAR, config.DEFAULT_YEAR + 1))
    if "-" in arg:
        a, b = arg.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(arg)]


def _print_single(result: dict) -> None:
    print(f"Filings cargados: {result['total']}")
    print("Por tipo:")
    for ftype, count in sorted(result["by_type"].items(), key=lambda kv: -kv[1]):
        label = config.FILING_TYPES.get(ftype, "?")
        print(f"  {ftype:>2}  {count:>5}  {label}")
    ptr = result["by_type"].get("P", 0)
    print(f"\n-> {ptr} reportes PTR (con operaciones) listos para descargar (Fase 2).")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else str(config.DEFAULT_YEAR)
    years = parse_years(arg)

    if len(years) == 1:
        print(f"Ingestando índice de Financial Disclosures del año {years[0]}...\n")
        _print_single(index_ingest.ingest_year(years[0]))
        return

    print(f"Ingestando índices de {years[0]} a {years[-1]} ({len(years)} años)...\n")
    print(f"{'año':>5} {'total':>7} {'PTR (P)':>9}")
    grand_total = grand_ptr = 0

    def on_event(year: int, result: dict) -> None:
        nonlocal grand_total, grand_ptr
        if "error" in result:
            print(f"{year:>5}   ERROR  {result['error']}")
            return
        ptr = result["by_type"].get("P", 0)
        grand_total += result["total"]
        grand_ptr += ptr
        print(f"{year:>5} {result['total']:>7} {ptr:>9}")

    index_ingest.ingest_years(years, on_event=on_event)
    print(f"\nTotal: {grand_total} filings, {grand_ptr} PTR (operaciones) en {len(years)} años.")
    print("-> Descarga con:  python scripts/run_download.py all")


if __name__ == "__main__":
    main()
