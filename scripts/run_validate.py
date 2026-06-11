"""Auditoria de cobertura del parser: compara cada PDF contra la base de datos.

Para cada PTR descargado vuelve a extraer el texto del PDF y cuenta las lineas
"candidatas a transaccion" (patron laxo: dos fechas seguidas de un monto, que es
la forma de toda fila de transaccion en ambos formatos del formulario). Luego
compara ese conteo con las transacciones guardadas en la tabla `transactions`.

Clasificacion por documento:
    OK          candidatas == guardadas (cobertura completa).
    UNDER       candidatas >  guardadas (el parser dejo filas sin capturar).
    OVER        candidatas <  guardadas (posibles falsos positivos del parser).
    SCANNED     el PDF no tiene texto (escaneado; requiere OCR, fuera de alcance).
    NOT_PARSED  el PDF esta descargado pero aun no se ha parseado.

Uso:
    python scripts/run_validate.py                  # todos los anos
    python scripts/run_validate.py 2026             # un ano
    python scripts/run_validate.py --sample 200     # muestra aleatoria de N PDFs
    python scripts/run_validate.py --show-under 20  # detalle de los peores UNDER

El patron laxo es una heuristica: puede contar lineas de cabecera raras como
candidatas, por eso OVER/UNDER pequenos se reportan pero no son necesariamente
errores. UNDER sistematico si indica un hueco del parser.
"""
import argparse
import random
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402
from backend.db import database  # noqa: E402
from backend.parse import ptr_parser  # noqa: E402

# Toda fila de transaccion (formato moderno o antiguo) lleva en una misma linea:
# fecha de operacion + fecha de notificacion + monto. Se usa como patron laxo.
_CANDIDATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}/\d{1,2}/\d{4}\s+\$[\d,]+")


def count_candidates(pdf_path: Path) -> int | None:
    """Lineas candidatas a transaccion en el PDF; None si no tiene texto."""
    text = ptr_parser.extract_text(pdf_path).replace("\x00", " ")
    if not text.strip():
        return None
    return sum(1 for line in text.splitlines() if _CANDIDATE.search(line))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audita la cobertura del parser de PTR.")
    parser.add_argument("year", nargs="?", default=None, help="ano a auditar (omitir = todos)")
    parser.add_argument("--sample", type=int, default=None, help="muestra aleatoria de N PDFs")
    parser.add_argument("--show-under", type=int, default=10,
                        help="cuantos documentos UNDER detallar (por brecha)")
    args = parser.parse_args()

    conn = database.get_connection()
    sql = "SELECT doc_id, year, parsed FROM filings WHERE filing_type='P' AND downloaded=1"
    params: list = []
    if args.year:
        sql += " AND year = ?"
        params.append(int(args.year))
    rows = conn.execute(sql, params).fetchall()
    if args.sample and args.sample < len(rows):
        rows = random.sample(rows, args.sample)

    stats = {"OK": 0, "UNDER": 0, "OVER": 0, "SCANNED": 0, "NOT_PARSED": 0, "MISSING_PDF": 0}
    gap_total = 0
    unders: list[tuple[str, int, int, int]] = []  # (doc, year, candidatas, guardadas)

    for r in rows:
        path = config.RAW_DIR / "ptr" / str(r["year"]) / f"{r['doc_id']}.pdf"
        if not path.exists():
            stats["MISSING_PDF"] += 1
            continue
        if not r["parsed"]:
            stats["NOT_PARSED"] += 1
            continue
        candidates = count_candidates(path)
        if candidates is None:
            stats["SCANNED"] += 1
            continue
        stored = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE doc_id = ?", (r["doc_id"],)
        ).fetchone()[0]
        if candidates == stored:
            stats["OK"] += 1
        elif candidates > stored:
            stats["UNDER"] += 1
            gap_total += candidates - stored
            unders.append((r["doc_id"], r["year"], candidates, stored))
        else:
            stats["OVER"] += 1
    conn.close()

    total = sum(stats.values())
    print(f"Documentos auditados: {total}")
    for k in ("OK", "UNDER", "OVER", "SCANNED", "NOT_PARSED", "MISSING_PDF"):
        print(f"  {k:<12} {stats[k]:>6}")
    if stats["UNDER"]:
        print(f"\nTransacciones potencialmente perdidas (suma de brechas): {gap_total}")
        print(f"Peores {min(args.show_under, len(unders))} documentos UNDER:")
        unders.sort(key=lambda u: -(u[2] - u[3]))
        for doc, year, cand, stored in unders[: args.show_under]:
            print(f"  {doc} ({year}): candidatas={cand} guardadas={stored} brecha={cand - stored}")
    parsed_docs = stats["OK"] + stats["UNDER"] + stats["OVER"]
    if parsed_docs:
        print(f"\nCobertura exacta: {stats['OK']}/{parsed_docs} "
              f"({100 * stats['OK'] / parsed_docs:.1f}% de los parseados con texto)")


if __name__ == "__main__":
    main()
