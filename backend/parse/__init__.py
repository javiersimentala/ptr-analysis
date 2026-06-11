"""Parsing de los PDFs de PTR a transacciones (Fase 3).

`ptr_parser.py` extrae las operaciones del texto de cada PDF (con pdfplumber):
owner, activo, ticker, tipo de activo, tipo de operacion, fecha y rango de monto.
Soporta el formato moderno (mayusculas, con codigo de tipo de activo) y el antiguo
(~2014, minusculas y sin codigo), y carga la tabla `transactions`. Los PDFs
escaneados no tienen texto y producen cero transacciones (no fallan).
"""
