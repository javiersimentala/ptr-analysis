"""Orquestador: ejecuta las fases del pipeline de datos en orden.

Encadena, sobre la base ya ingestada y descargada:

    parse -> enrich -> portfolio -> optimal

Uso:
    python scripts/run_pipeline.py                 # solo lo pendiente
    python scripts/run_pipeline.py --reparse       # re-parsea TODO (tras cambiar
                                                   # el parser) y recalcula
    python scripts/run_pipeline.py --skip-enrich   # omite precios (rapido)

`--reparse` marca todos los PTR descargados como no parseados para que el parser
vigente reprocese cada PDF (la insercion es idempotente por documento). Es el
modo correcto despues de corregir o mejorar el parser.

Cada fase imprime su resumen; si una fase falla, el orquestador se detiene con
codigo de salida distinto de cero.
"""
import argparse
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db import database  # noqa: E402


def _run(label: str, args: list[str]) -> None:
    """Ejecuta un script hijo con el mismo interprete; aborta si falla."""
    print(f"\n=== {label} ===", flush=True)
    result = subprocess.run([sys.executable, *args], cwd=ROOT)
    if result.returncode != 0:
        print(f"FALLO en la fase '{label}' (codigo {result.returncode}); se detiene.")
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta el pipeline de datos completo.")
    parser.add_argument("--reparse", action="store_true",
                        help="re-parsear todos los PDFs descargados (tras cambiar el parser)")
    parser.add_argument("--skip-enrich", action="store_true",
                        help="omitir la fase de precios (mas rapido)")
    parser.add_argument("--skip-optimal", action="store_true",
                        help="omitir el portafolio optimo")
    args = parser.parse_args()

    if args.reparse:
        conn = database.get_connection()
        n = conn.execute(
            "UPDATE filings SET parsed = 0 WHERE filing_type = 'P' AND downloaded = 1"
        ).rowcount
        conn.commit()
        conn.close()
        print(f"Marcados {n} PTR para re-parseo con el parser vigente.")

    _run("Parse (PDF -> transacciones)", ["scripts/run_parse.py", "all", "--quiet"])
    if not args.skip_enrich:
        _run("Enrich (precios y P/L)", ["scripts/run_enrich.py", "--quiet"])
    _run("Portfolio (members/positions)", ["scripts/run_portfolio.py"])
    if not args.skip_optimal and not args.skip_enrich:
        _run("Optimal (Markowitz)", ["scripts/run_optimal.py"])

    print("\nPipeline completo.")


if __name__ == "__main__":
    main()
