"""Smoke test del dashboard Streamlit: corre el app headless y verifica que no
lanza excepción (funciona con base vacía o poblada)."""
from pathlib import Path

import pytest

# streamlit es dependencia de runtime; si no está, se omite (no rompe la suite).
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

_APP = str(Path(__file__).resolve().parent.parent / "frontend" / "app.py")


def test_app_corre_sin_excepcion():
    at = AppTest.from_file(_APP, default_timeout=60).run()
    assert not at.exception
