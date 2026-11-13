"""
Plugin de pytest que recoge el resultado de cada prueba Cucumber para el paquete de Xray.

- Cada escenario trae la etiqueta @TEST_<clave> (la pone xray-proxy) y su nombre empieza con el identificador TC-...
- En un Scenario Outline, cada fila de Examples es un ejemplo con su propio estado, en el orden de Examples.
- Un paso que falla deja el ejemplo en FAILED, con el paso y el motivo en el comentario.
- Un paso sin código deja la prueba en TODO, con el texto del paso que falta: no es un defecto del producto.
- Captura de pantalla al final de cada ejemplo y en el momento de cada falla, si el escenario usó la página.

Comentario de cada prueba: el formato que lee xray-proxy para proponer los Errores y las fallas con la misma causa.
Cada ejemplo en su línea, entre corchetes, y debajo un renglón por paso ejecutado, sin la palabra clave de Gherkin:

    [Auditoría Interna]
      OK    un usuario activo con rol "Auditoría Interna"
      OK    ingresa usuario y contraseña válidos
      FALLA accede al portal -> sigue en la pantalla de inicio de sesión

Lo que va después de "->" es lo obtenido, en un solo renglón: dos pruebas que obtienen lo mismo tienen el mismo síntoma.
"""
import datetime as dt
import logging
import re
from pathlib import Path

import pytest

from qa_ejecutor import __version__
from qa_ejecutor.gherkin import identificador

logger = logging.getLogger(__name__)
FORMATO_HORA = "%Y-%m-%dT%H:%M:%S+00:00"
ESCENARIO = "escenario"
MAX_MOTIVO = 300


def ahora():
    """Hora actual en UTC, en el formato que espera Xray."""
    return dt.datetime.now(dt.timezone.utc).strftime(FORMATO_HORA)


def clave_de(etiquetas):
    """La clave de Xray de la etiqueta TEST_<clave>, o una cadena vacía."""
    return next((e[len("TEST_"):] for e in etiquetas if e.startswith("TEST_")), "")


def fila_de(item):
    """Los valores de la fila de Examples que se ejecuta ("" si el escenario no es un esquema)."""
    callspec = getattr(item, "callspec", None)
    ejemplo = (callspec.params.get("_pytest_bdd_example") if callspec else None) or {}
    return " | ".join(str(v) for v in ejemplo.values())


def motivo_de(excepcion):
    """
    Lo obtenido en una falla, en un solo renglón. De una verificación (assert) queda su mensaje, sin el nombre de la
    excepción ni la explicación que agrega pytest: así dos pasos que obtienen lo mismo dejan el mismo texto. De cualquier
    otro error queda también su tipo (por ejemplo, TimeoutError), que ayuda a reconocerlo.
    """
    lineas = [x.strip() for x in str(excepcion).splitlines() if x.strip()]
    if isinstance(excepcion, AssertionError) and lineas:
        # Después del mensaje de la verificación, pytest agrega su explicación ("assert ..."): no es lo obtenido.
        corte = next((i for i, x in enumerate(lineas) if i and x.startswith("assert ")), len(lineas))
        return " ".join(lineas[:corte])[:MAX_MOTIVO]
    tipo = type(excepcion).__name__
    return (f"{tipo}: {' '.join(lineas)}" if lineas else tipo)[:MAX_MOTIVO]


def renglon(ok, paso, obtenido=""):
    """Un renglón del comentario: "OK    paso" o "FALLA paso -> lo obtenido" (las mismas marcas de las pruebas Manual)."""
    return f"  {'OK   ' if ok else 'FALLA'} {paso}" + (f" -> {obtenido}" if obtenido and not ok else "")


class Recolector:
    """Resultados de las pruebas Cucumber de una corrida, por clave de Xray y en el orden en que se ejecutaron."""

    def __init__(self, carpeta_evidencias):
        self.carpeta = Path(carpeta_evidencias)
        self.pruebas = {}
        self._actual = None   # (prueba, ejemplo) del escenario en curso

    # --- Ganchos de pytest-bdd -----------------------------------------------------
    def pytest_runtest_setup(self, item):
        self._actual = None

    def _empezar(self, clave, nombre, item):
        """Registra un ejemplo nuevo de la prueba (la crea si es su primer ejemplo) y lo deja como el actual."""
        fila = fila_de(item)
        prueba = self.pruebas.setdefault(clave, {
            "identificador": identificador(nombre), "esquema": bool(fila), "ejemplos": [],
            "faltantes": [], "evidencias": [], "start": ahora(), "finish": None})
        ejemplo = {"nombre": fila or ESCENARIO, "status": "PASSED", "renglones": []}
        prueba["ejemplos"].append(ejemplo)
        self._actual = (prueba, ejemplo)

    def pytest_bdd_before_scenario(self, request, feature, scenario):
        self._empezar(clave_de(scenario.tags), scenario.name, request.node)

    def pytest_bdd_after_step(self, request, feature, scenario, step, step_func, step_func_args):
        self._actual[1]["renglones"].append(renglon(True, step.name))

    def pytest_bdd_step_error(self, request, feature, scenario, step, step_func, step_func_args, exception):
        prueba, ejemplo = self._actual
        ejemplo["status"] = "FAILED"
        ejemplo["renglones"].append(renglon(False, step.name, motivo_de(exception)))
        self._captura(request, prueba, "falla")

    def pytest_bdd_step_func_lookup_error(self, request, feature, scenario, step, exception):
        prueba, ejemplo = self._actual
        ejemplo["status"] = "TODO"
        texto = f"{step.keyword} {step.name}"
        if texto not in prueba["faltantes"]:
            prueba["faltantes"].append(texto)

    def pytest_bdd_after_scenario(self, request, feature, scenario):
        prueba, ejemplo = self._actual
        prueba["finish"] = ahora()
        self._captura(request, prueba, ejemplo["nombre"])

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_makereport(self, item, call):
        """Una falla fuera de los pasos (por ejemplo, al preparar el navegador) también deja el ejemplo en FAILED."""
        reporte = yield
        if reporte.failed and self._actual is None:
            # Falló antes del primer paso: la prueba se identifica por su etiqueta (marca) y su nombre.
            nombre = (item.function.__doc__ or "").split(": ", 1)[-1]
            self._empezar(clave_de(m.name for m in item.iter_markers()), nombre, item)
        if reporte.failed and self._actual[1]["status"] == "PASSED":
            prueba, ejemplo = self._actual
            ejemplo["status"] = "FAILED"
            motivo = call.excinfo.exconly() if call.excinfo else reporte.longreprtext
            ejemplo["renglones"].append(renglon(False, f"fuera de los pasos ({reporte.when})", " ".join(motivo.split())[:MAX_MOTIVO]))
        return reporte

    # --- Evidencias -------------------------------------------------------------------
    def _captura(self, request, prueba, motivo):
        if "pagina" not in request.fixturenames:
            return
        limpio = re.sub(r"[^A-Za-z0-9_-]+", "-", motivo)[:40].strip("-") or ESCENARIO
        archivo = f"{prueba['identificador']}_{len(prueba['evidencias']) + 1:02d}_{limpio}.png"
        try:
            request.getfixturevalue("pagina").screenshot(path=str(self.carpeta / archivo), full_page=True)
            prueba["evidencias"].append(archivo)
        except Exception as e:  # noqa: BLE001 - sin captura no se pierde el resultado
            logger.warning("No se pudo tomar la captura %s: %s", archivo, e)

    # --- Resultado para el paquete -------------------------------------------------------
    @staticmethod
    def estado(prueba):
        estados = [e["status"] for e in prueba["ejemplos"]]
        if not estados or "TODO" in estados:
            return "TODO"
        return "FAILED" if "FAILED" in estados else "PASSED"

    def como_xray(self, url, run_id):
        """Una entrada por prueba para resultados.json, con el formato que valida xray-proxy."""
        return [self._resultado(p, url, run_id) for p in self.pruebas.values()]

    def _resultado(self, prueba, url, run_id):
        estado = self.estado(prueba)
        lineas = []
        if prueba["faltantes"]:
            lineas.append("PASOS SIN CÓDIGO (la prueba queda en TODO hasta que se programen): " + "; ".join(prueba["faltantes"]))
        for e in prueba["ejemplos"]:
            lineas += [f"[{e['nombre']}]", *e["renglones"]]
        lineas.append(f"Ejecutado contra {url} con qa-ejecutor {__version__} (pytest-bdd y Playwright). run {run_id}.")
        r = {"identificador": prueba["identificador"], "tipo": "Cucumber", "status": estado, "comment": "\n".join(lineas),
             "start": prueba["start"], "finish": prueba["finish"] or prueba["start"], "evidencias": list(prueba["evidencias"])}
        # Estado por fila solo en los esquemas y si todas las filas se ejecutaron (xray-proxy acepta PASSED o FAILED).
        if prueba["esquema"] and estado != "TODO":
            r["ejemplos"] = [{"nombre": e["nombre"], "status": e["status"]} for e in prueba["ejemplos"]]
        return r
