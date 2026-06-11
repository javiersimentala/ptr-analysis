"""Agregacion de portafolios y analisis (Fase 5 y siguientes).

- `builder.py`:  agrega `transactions` por congresista en las tablas `members`
  (resumen, P/L estimado, win-rate) y `positions` (posicion neta por ticker).
- `queries.py`:  consultas de lectura que consume la interfaz web (filings,
  congresistas, portafolio por periodo, comparacion).
- `optimize.py`: portafolio optimo de media-varianza (maximo Sharpe, solo largos)
  sobre el universo de tickers que el Congreso mantiene en posicion neta positiva.
"""
