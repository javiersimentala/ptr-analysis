"""CLI de la Fase 5: construye los portafolios por congresista y muestra un top.

Uso:
    python scripts/run_portfolio.py            # reconstruye y muestra top 15
    python scripts/run_portfolio.py --top 30

Requiere haber corrido la Fase 3 (parsing) y, para el P/L, la Fase 4 (precios).
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

from backend.db import database  # noqa: E402
from backend.portfolio import builder  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye portafolios por congresista.")
    parser.add_argument("--top", type=int, default=15, help="cuántos congresistas mostrar")
    args = parser.parse_args()

    print("Construyendo portafolios por congresista...\n")
    conn = database.get_connection()
    database.init_db(conn)
    stats = builder.build(conn)
    print(f"{stats['members']} congresistas · {stats['positions']} posiciones (ticker × congresista).\n")

    rows = builder.top_members_by_gain(conn, limit=args.top)
    if rows:
        print("Top por P/L estimado (extremo alto del rango):")
        print(f"  {'congresista':26} {'edo':5} {'#tx':>4} {'invertido≤':>13} {'P/L est≤':>12} {'win':>5}")
        for r in rows:
            name = f"{(r['first_name'] or '').strip()} {r['last_name']}".strip()[:26]
            wr = "  -  " if r["win_rate"] is None else f"{r['win_rate'] * 100:4.0f}%"
            print(
                f"  {name:26} {r['state_dst'] or '':5} {r['n_tx']:>4} "
                f"{r['invested_max'] or 0:>13,.0f} {r['est_gain_max'] or 0:>12,.0f} {wr:>5}"
            )
    conn.close()


if __name__ == "__main__":
    main()
