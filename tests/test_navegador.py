"""Pruebas de las fixtures del navegador, sin abrir Chromium."""
import pytest

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


@pytest.mark.parametrize("sistema, esperado", [("nt", "msedge"), ("posix", "chromium")])
def test_navegador_por_omision(sistema, esperado):
    assert navegador.navegador_por_omision(sistema) == esperado


@pytest.mark.parametrize("elegido, visible, esperado", [
    ("msedge", None, {"headless": True, "channel": "msedge"}),
    ("chrome", None, {"headless": True, "channel": "chrome"}),
    ("chromium", "1", {"headless": False}),
])
def test_opciones_de_lanzamiento(monkeypatch, elegido, visible, esperado):
    monkeypatch.setenv("QA_NAVEGADOR", elegido)
    if visible:
        monkeypatch.setenv("QA_VISIBLE", visible)
    else:
        monkeypatch.delenv("QA_VISIBLE", raising=False)
    assert navegador.opciones_de_lanzamiento() == esperado


def test_sin_eleccion_usa_el_del_sistema(monkeypatch):
    monkeypatch.delenv("QA_NAVEGADOR", raising=False)
    monkeypatch.delenv("QA_VISIBLE", raising=False)
    monkeypatch.setattr(navegador, "navegador_por_omision", lambda: "msedge")
    assert navegador.opciones_de_lanzamiento() == {"headless": True, "channel": "msedge"}


def test_navegador_no_soportado(monkeypatch):
    monkeypatch.setenv("QA_NAVEGADOR", "firefox")
    with pytest.raises(ValueError, match="Navegador no soportado: 'firefox'"):
        navegador.opciones_de_lanzamiento()
