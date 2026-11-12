"""
Fixtures de Playwright para los pasos de cada proyecto: un navegador por corrida y una página limpia por ejemplo.

    def mi_paso(pagina, url_app): pagina.goto(f"{url_app}/login")

APP_URL es la dirección de la aplicación que se prueba. QA_VISIBLE=1 muestra el navegador (solo en local).
"""
import contextlib
import os

import pytest

VIEWPORT = {"width": 1280, "height": 900}
LOCALE = "es-GT"
TIMEOUT_MS = 20000


@contextlib.contextmanager
def navegador_de_la_corrida():
    """Abre Chromium (sin ventana, salvo QA_VISIBLE=1) y lo cierra al terminar."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(headless=os.environ.get("QA_VISIBLE") != "1")
        try:
            yield navegador
        finally:
            navegador.close()


@contextlib.contextmanager
def pagina_limpia(navegador):
    """Una página en un contexto nuevo (sin cookies ni sesión de otra prueba)."""
    contexto = navegador.new_context(viewport=VIEWPORT, locale=LOCALE)
    contexto.set_default_timeout(TIMEOUT_MS)
    try:
        yield contexto.new_page()
    finally:
        contexto.close()


@pytest.fixture(scope="session")
def url_app():
    url = os.environ.get("APP_URL", "").rstrip("/")
    if not url:
        pytest.fail("Falta APP_URL: la dirección de la aplicación que se prueba")
    return url


@pytest.fixture(scope="session")
def navegador():
    with navegador_de_la_corrida() as n:
        yield n


@pytest.fixture
def pagina(navegador):
    with pagina_limpia(navegador) as p:
        yield p
