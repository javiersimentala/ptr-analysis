"""Datos de mercado y P/L estimado (Fase 4).

`prices.py` obtiene, via yfinance, el cierre en (o antes de) la fecha de la
operacion y el ultimo cierre de cada ticker, cachea los cierres en la tabla
`prices` y calcula la variacion y la ganancia/perdida estimada por rango. El
proveedor de precios es inyectable para poder probar sin acceso a la red.
"""
