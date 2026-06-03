"""CLI de la Fase 4: enriquece las transacciones con precios de mercado.

Uso:
    python scripts/run_enrich.py               # todas las transacciones sin enriquecer
    python scripts/run_enrich.py --limit 20    # sólo los primeros 20 tickers

Requiere haber corrido la Fase 3 (parsing). Usa yfinance (sin clave).
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

from backend.market import prices  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Enriquece transacciones con precios.")
    parser.add_argument("--limit", type=int, default=None, help="máximo de tickers a procesar")
    parser.add_argument("--quiet", action="store_true", help="no mostrar por ticker")
    args = parser.parse_args()

    print("Enriqueciendo transacciones con precios de mercado (yfinance)...\n")

    def progress(ticker: str, msg: str) -> None:
        if not args.quiet:
            print(f"  {ticker}: {msg}")

    stats = prices.enrich_all(limit=args.limit, on_event=progress)

    print(
        f"\nResumen: {stats['tickers']} tickers procesados, "
        f"{stats['priced']} transacciones valuadas, "
        f"{stats['no_price']} sin precio, {stats['no_ticker']} sin ticker."
    )


if __name__ == "__main__":
    main()
