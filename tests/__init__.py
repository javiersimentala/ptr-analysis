"""Paquete de pruebas (pytest).

Las pruebas son hermeticas: no tocan la red ni la base de produccion. Los
proveedores de descarga y de precios se inyectan o se simulan, y la web se prueba
con el TestClient de FastAPI sobre una base temporal (vacia o poblada).
"""
