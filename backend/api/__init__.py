"""Capa de presentacion web y API JSON del proyecto PTR Analysis.

Este paquete expone, mediante FastAPI, dos cosas sobre la misma base de datos
SQLite que produce el backend de datos (tablas ``filings``, ``transactions``,
``members`` y ``positions``):

1. Paginas HTML renderizadas en el servidor con plantillas Jinja2 (carpeta
   ``frontend/templates``) y estilos Tailwind cargados por CDN. No hay ningun
   paso de compilacion de JavaScript: el proyecto sigue siendo 100% Python.

2. Endpoints JSON bajo ``/api/...`` para consumir los mismos datos desde otras
   herramientas o un futuro cliente.

Modulos:
    main.py     Define la aplicacion FastAPI, los filtros de plantilla y todas
                las rutas (Filings, Congresistas, Portafolio, Comparar, Optimo).

La logica de consulta vive en ``backend/portfolio/queries.py`` para mantener el
acceso a datos separado de las rutas y poder probarlo de forma aislada.
"""
