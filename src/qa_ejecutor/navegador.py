"""
Fixtures de Playwright para los pasos de cada proyecto: un navegador por corrida y una página limpia por ejemplo.

    def mi_paso(pagina, url_app): pagina.goto(f"{url_app}/login")

APP_URL es la dirección de la aplicación que se prueba. QA_NAVEGADOR elige el navegador (msedge, chrome o chromium; por
omisión Edge en Windows, que ya viene instalado, y Chromium en los demás sistemas). QA_VISIBLE=1 muestra el navegador
(solo en local).
"""
import contextlib
import os

import pytest

VIEWPORT = {"width": 1280, "height": 900}
LOCALE = "es-GT"
TIMEOUT_MS = 20000
# Navegador: canal de Playwright. Edge y Chrome usan el que ya está instalado; Chromium requiere
# "python -m playwright install chromium" (en el flujo de GitHub Actions ya viene en la imagen).
NAVEGADORES = {"msedge": "msedge", "chrome": "chrome", "chromium": None}


def navegador_por_omision(sistema=None):
    """Edge en Windows (ya viene instalado: no hay que descargar Chromium); Chromium en los demás sistemas."""
    return "msedge" if (sistema or os.name) == "nt" else "chromium"


def opciones_de_lanzamiento():
    """Opciones de Playwright para abrir el navegador elegido (QA_NAVEGADOR), sin ventana salvo QA_VISIBLE=1."""
    nombre = os.environ.get("QA_NAVEGADOR") or navegador_por_omision()
    if nombre not in NAVEGADORES:
        raise ValueError(f"Navegador no soportado: {nombre!r} (usa {', '.join(NAVEGADORES)})")
    opciones = {"headless": os.environ.get("QA_VISIBLE") != "1"}
    if NAVEGADORES[nombre]:
        opciones["channel"] = NAVEGADORES[nombre]
    return opciones


@contextlib.contextmanager
def navegador_de_la_corrida():
    """Abre el navegador de la corrida (ver opciones_de_lanzamiento) y lo cierra al terminar."""
    from playwright.sync_api import sync_playwright
    opciones = opciones_de_lanzamiento()
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(**opciones)
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
