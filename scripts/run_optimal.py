"""CLI: calcula el portafolio optimo (media-varianza / Markowitz) y lo guarda.

Uso:
    python scripts/run_optimal.py                       # 25 tickers, 2 años
    python scripts/run_optimal.py --limit 30 --lookback-days 756

Toma el universo de tickers con mayor posicion neta agregada del Congreso (tabla
positions), descarga su historial via yfinance, optimiza el Sharpe y guarda los
pesos en optimal_weights/optimal_meta. La web lee ese resultado ya calculado.

Requiere haber corrido antes run_portfolio (para tener la tabla positions).
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

from backend.portfolio import optimize  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcula el portafolio optimo (Markowitz).")
    parser.add_argument("--limit", type=int, default=25, help="numero de tickers del universo")
    parser.add_argument("--lookback-days", type=int, default=504, help="ventana de historial")
    args = parser.parse_args()

    print(f"Optimizando portafolio (universo={args.limit}, ventana={args.lookback_days} dias)...\n")
    result = optimize.run(
        limit=args.limit, lookback_days=args.lookback_days, on_event=lambda m: print(f"  {m}")
    )

    if result["status"] != "ok":
        print(f"\nNo se pudo optimizar (estado: {result['status']}). "
              f"Asegurate de haber corrido run_portfolio y run_enrich.")
        return
    print(
        f"\nPortafolio optimo con {result['n_assets']} activos:\n"
        f"  Retorno esperado anual: {result['exp_return'] * 100:.1f}%\n"
        f"  Volatilidad anual:      {result['volatility'] * 100:.1f}%\n"
        f"  Ratio de Sharpe:        {result['sharpe']:.2f}\n"
        f"-> Pesos guardados; revisalos en la web (/optimal)."
    )


if __name__ == "__main__":
    main()
