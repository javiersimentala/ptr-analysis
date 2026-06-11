"""Acceso a la base de datos SQLite.

Contiene el esquema (`schema.sql`) y la capa de conexion (`database.py`). La
conexion se abre en modo WAL para permitir lectura y escritura concurrentes (por
ejemplo, una descarga en segundo plano mientras la web consulta), y crea o migra
las tablas de forma idempotente. Todo el proyecto comparte una unica base en
`data/processed/ptr.db`.
"""
