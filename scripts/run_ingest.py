"""CLI de la Fase 1: descarga y carga el indice de un ano.

Uso:
    python scripts/run_ingest.py            # usa el ano por defecto (config)
    python scripts/run_ingest.py 2025       # un ano especifico
"""
import sys
from pathlib import Path

# La consola de Windows usa cp1252 por defecto y no puede imprimir algunos
# caracteres (p. ej. flechas). Forzamos UTF-8 en la salida.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Permite ejecutar el script directamente anadiendo la raiz al sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402
from backend.ingest import index_ingest  # noqa: E402


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else config.DEFAULT_YEAR
    print(f"Ingestando indice de Financial Disclosures del ano {year}...\n")

    result = index_ingest.ingest_year(year)

    print(f"Filings cargados: {result['total']}")
    print("Por tipo:")
    for ftype, count in sorted(result["by_type"].items(), key=lambda kv: -kv[1]):
        label = config.FILING_TYPES.get(ftype, "?")
        print(f"  {ftype:>2}  {count:>4}  {label}")

    ptr = result["by_type"].get("P", 0)
    print(f"\n-> {ptr} reportes PTR (con operaciones) listos para la Fase 2 (descarga).")


if __name__ == "__main__":
    main()
