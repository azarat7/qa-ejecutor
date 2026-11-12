"""Pruebas de las fixtures del navegador, sin abrir Chromium."""
from qa_ejecutor import navegador


class ContextoFalso:
    def __init__(self):
        self.cerrado, self.timeout = False, None

    def set_default_timeout(self, ms):
        self.timeout = ms

    def new_page(self):
        return "página"

    def close(self):
        self.cerrado = True


class NavegadorFalso:
    def __init__(self):
        self.contexto, self.opciones = ContextoFalso(), None

    def new_context(self, **opciones):
        self.opciones = opciones
        return self.contexto


def test_pagina_limpia_en_contexto_nuevo_y_se_cierra():
    n = NavegadorFalso()
    with navegador.pagina_limpia(n) as p:
        assert p == "página"
        assert n.opciones == {"viewport": navegador.VIEWPORT, "locale": "es-GT"}
        assert n.contexto.timeout == navegador.TIMEOUT_MS
    assert n.contexto.cerrado


def test_url_app(pytester, monkeypatch):
    pytester.makepyfile(test_url="""
def test_con_url(url_app):
    assert url_app == "https://app"
""")
    monkeypatch.setenv("APP_URL", "https://app/")
    pytester.runpytest_inprocess("-p", "qa_ejecutor.navegador").assert_outcomes(passed=1)
    monkeypatch.delenv("APP_URL")
    pytester.runpytest_inprocess("-p", "qa_ejecutor.navegador").assert_outcomes(errors=1)
