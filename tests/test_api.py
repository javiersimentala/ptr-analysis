"""Pruebas de la web/API (FastAPI) con el TestClient.

Funcionan con base vacia o poblada: las paginas deben responder 200 sin lanzar
excepciones y la API debe devolver JSON valido.
"""
from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_home_redirige_a_filings():
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)
    assert "/filings" in r.headers["location"]


def test_pagina_filings():
    r = client.get("/filings")
    assert r.status_code == 200
    assert "Filings" in r.text


def test_pagina_congresistas():
    r = client.get("/politicians")
    assert r.status_code == 200
    assert "Congresistas" in r.text


def test_pagina_congresista_desconocido_no_rompe():
    r = client.get("/politician", params={"key": "Nadie|Sin Nombre|XX99"})
    assert r.status_code == 200   # muestra "no encontrado", no error


def test_stubs_compare_y_optimal():
    assert client.get("/compare").status_code == 200
    assert client.get("/optimal").status_code == 200


def test_api_politicians_devuelve_lista():
    r = client.get("/api/politicians")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_api_politician_estructura():
    r = client.get("/api/politician", params={"key": "Nadie|Sin Nombre|XX99"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"member", "summary", "positions"}
