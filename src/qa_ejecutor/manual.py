"""
Preparación de las pruebas Manual por el agente (D-40, D-44): el estado final lo decide QA.

El proyecto registra una función por prueba Manual que pueda adelantar:

    @manual("TC-AUT-MSG-01", pasos=2)
    def redaccion_del_mensaje(t):
        with t.ejemplo("mensaje de bloqueo", paso=2):
            ...
            t.verificar(condicion, "lo que se verifica", detalle, paso=1)
            t.nota("lo observado")

Cada paso de Xray recibe TODO, la sugerencia del agente, lo observado y sus capturas: una al verificar el paso por
primera vez y otra en su primera falla. Las pruebas Manual sin función registrada no se envían: QA las hace desde cero.
"""
import contextlib
import datetime as dt
import logging
import re
from pathlib import Path

from qa_ejecutor import __version__
from qa_ejecutor.plugin import FORMATO_HORA, ahora

logger = logging.getLogger(__name__)
REGISTRO = {}   # identificador TC-... -> (función, número de pasos en Xray)


def manual(identificador, pasos):
    """Registra la función que prepara una prueba Manual de Xray con `pasos` pasos."""
    def decorador(funcion):
        REGISTRO[identificador] = (funcion, pasos)
        return funcion
    return decorador


class PruebaManual:
    """Lo que el agente observa en una prueba Manual, agrupado por paso de Xray."""

    def __init__(self, identificador, pasos, carpeta, url, abrir_pagina):
        self.identificador, self.pasos, self.carpeta, self.url = identificador, pasos, Path(carpeta), url
        self._abrir_pagina = abrir_pagina
        self.verificaciones, self.notas, self.evidencias = [], [], []
        self.pagina, self.paso_actual = None, None
        self.inicio, self.fin = ahora(), None

    @contextlib.contextmanager
    def ejemplo(self, nombre="escenario", paso=None):
        """Una parte de la prueba con una página limpia. Un error queda como verificación fallida y no detiene la prueba."""
        self.paso_actual = paso
        with self._abrir_pagina() as pagina:
            self.pagina = pagina
            try:
                yield self
            except Exception as e:  # noqa: BLE001 - el error queda en lo observado
                self.verificar(False, "La preparación terminó con un error", f"{type(e).__name__}: {str(e)[:300]}")
            finally:
                if not self._capturas_del_paso(self.paso_actual):
                    self.captura(nombre)
                self.pagina = None

    def verificar(self, condicion, descripcion, detalle="", paso=None):
        ok, paso = bool(condicion), paso or self.paso_actual
        self.verificaciones.append({"descripcion": descripcion, "ok": ok, "detalle": str(detalle)[:400], "paso": paso})
        capturas = self._capturas_del_paso(paso)
        if paso and (not capturas or (not ok and not any(e["falla"] for e in capturas))):
            self.captura(f"paso{paso}-{'falla-' if not ok else ''}{descripcion}", paso=paso, falla=not ok)
        return ok

    def nota(self, texto, paso=None):
        self.notas.append({"texto": texto, "paso": paso or self.paso_actual, "hora": dt.datetime.now().strftime("%H:%M:%S")})

    def captura(self, nombre, paso=None, falla=False):
        if not self.pagina:
            return
        limpio = re.sub(r"[^A-Za-z0-9_-]+", "-", nombre)[:40].strip("-") or "captura"
        archivo = f"{self.identificador}_{len(self.evidencias) + 1:02d}_{limpio}.png"
        try:
            self.pagina.screenshot(path=str(self.carpeta / archivo), full_page=True)
            self.evidencias.append({"archivo": archivo, "paso": paso or self.paso_actual, "falla": falla})
        except Exception as e:  # noqa: BLE001 - sin captura no se pierde lo observado
            logger.warning("No se pudo tomar la captura %s: %s", archivo, e)

    def _capturas_del_paso(self, paso):
        return [e for e in self.evidencias if paso and e["paso"] == paso]

    # --- Resultado para el paquete -------------------------------------------------------
    @staticmethod
    def _sugerencia(verificaciones):
        if not verificaciones:
            return "sin verificación automática"
        return "PASSED" if all(v["ok"] for v in verificaciones) else "FAILED"

    @staticmethod
    def _linea(v):
        return f"{'OK   ' if v['ok'] else 'FALLA'} {v['descripcion']}" + (f" -> {v['detalle']}" if v["detalle"] and not v["ok"] else "")

    def como_xray(self, run_id):
        pasos = []
        for n in range(1, self.pasos + 1):
            verifs = [v for v in self.verificaciones if v["paso"] == n]
            lineas = [f"Sugerencia del agente: {self._sugerencia(verifs)}."] + [self._linea(v) for v in verifs]
            lineas += [f"Nota ({x['hora']}): {x['texto']}" for x in self.notas if x["paso"] == n]
            pasos.append({"status": "TODO", "actualResult": "\n".join(lineas),
                          "evidencias": [e["archivo"] for e in self.evidencias if e["paso"] == n]})
        en_pasos = {a for s in pasos for a in s["evidencias"]}
        comentario = [f"PRUEBA MANUAL PREPARADA POR EL AGENTE. Sugerencia: {self._sugerencia(self.verificaciones)}. "
                      "QA debe revisar lo observado y las evidencias de cada paso y decidir el estado final."]
        comentario += [self._linea(v) for v in self.verificaciones if not v["paso"]]
        comentario += [f"Nota: {x['texto']}" for x in self.notas if not x["paso"]]
        comentario.append(f"Preparada contra {self.url} con qa-ejecutor {__version__} (Playwright). run {run_id}.")
        return {"identificador": self.identificador, "tipo": "Manual", "status": "TODO", "comment": "\n".join(comentario),
                "start": self.inicio, "finish": self.fin or self.inicio, "steps": pasos,
                "evidencias": [e["archivo"] for e in self.evidencias if e["archivo"] not in en_pasos]}


def preparar(identificadores, carpeta, url, run_id, abrir_pagina):
    """Prepara las pruebas Manual registradas. Devuelve (resultados, identificadores sin función registrada)."""
    resultados, sin_funcion = [], []
    for ident in identificadores:
        if ident not in REGISTRO:
            sin_funcion.append(ident)
            continue
        funcion, pasos = REGISTRO[ident]
        t = PruebaManual(ident, pasos, carpeta, url, abrir_pagina)
        try:
            funcion(t)
        except Exception as e:  # noqa: BLE001 - un error de una prueba no detiene a las demás
            t.verificar(False, "La preparación no pudo terminar", f"{type(e).__name__}: {str(e)[:300]}")
        t.fin = dt.datetime.now(dt.timezone.utc).strftime(FORMATO_HORA)
        resultados.append(t.como_xray(run_id))
    return resultados, sin_funcion
