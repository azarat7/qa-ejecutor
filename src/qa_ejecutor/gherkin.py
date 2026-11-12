"""Guarda en una carpeta los .feature que entrega xray-proxy, listos para pytest-bdd."""
import re
from pathlib import Path

ARCHIVO_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d+\.feature$")
MODULO_DE_PRUEBA = 'from pytest_bdd import scenarios\n\nscenarios(".")\n'


class GherkinInvalido(ValueError):
    """La respuesta de xray-proxy no trae un .feature válido."""


def guardar(respuesta, carpeta):
    """Escribe los .feature y el módulo que los carga (test_xray.py). Devuelve las rutas de los .feature."""
    carpeta = Path(carpeta)
    rutas = []
    for f in respuesta.get("features") or []:
        nombre = str(f.get("archivo", ""))
        if not ARCHIVO_RE.match(nombre):
            raise GherkinInvalido(f"Nombre de archivo no permitido: {nombre!r}")
        ruta = carpeta / nombre
        ruta.write_text(str(f.get("contenido", "")), encoding="utf-8")
        rutas.append(ruta)
    if rutas:
        (carpeta / "test_xray.py").write_text(MODULO_DE_PRUEBA, encoding="utf-8")
    return rutas


def identificador(nombre):
    """El identificador TC-... con que empieza el nombre del escenario (el resumen de la prueba en Xray)."""
    return nombre.split()[0] if nombre.strip() else ""
