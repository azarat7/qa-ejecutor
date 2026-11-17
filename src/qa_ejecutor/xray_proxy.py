"""Llamadas a xray-proxy: despertarlo, pedir el Gherkin de la ejecución y enviar el paquete de resultados."""
import os
import time

import requests

TIMEOUT = 60
TIMEOUT_ENVIO = 180
SIN_EJECUCION = 409   # xray-proxy: la historia no tiene una Sub Test Execution abierta


class ErrorDeXrayProxy(Exception):
    """xray-proxy no respondió o rechazó la petición."""


class XrayProxy:
    """Cliente de xray-proxy. La clave (X-API-Key) llega por variable de entorno y nunca se escribe."""

    def __init__(self, base, api_key, sesion=None):
        if not base or not api_key:
            raise ErrorDeXrayProxy("Faltan la dirección de xray-proxy o XRAY_PROXY_API_KEY")
        self.base = base.rstrip("/")
        self.sesion = sesion or requests.Session()
        self.sesion.headers["X-API-Key"] = api_key

    def despertar(self, intentos=7, espera_s=10):
        """Render Free apaga el servicio tras 15 minutos sin tráfico: se espera a que /health responda."""
        for intento in range(intentos):
            try:
                if self.sesion.get(f"{self.base}/health", timeout=TIMEOUT).ok:
                    return True
            except requests.RequestException:
                pass
            if intento < intentos - 1:
                time.sleep(espera_s)
        raise ErrorDeXrayProxy(f"xray-proxy no respondió en {self.base}/health")

    def gherkin(self, historia, intentos=8, espera_s=15):
        """
        El .feature de la Sub Test Execution abierta de la historia (GET /ejecucion/gherkin).

        xray-proxy encuentra la Sub Test Execution con la búsqueda de Jira, que tarda en mostrar lo recién creado o
        modificado: si la ejecución se lanzó apenas se creó, la primera respuesta puede ser 409 aunque exista. Por eso
        el 409 se reintenta (por omisión, hasta unos 2 minutos); cualquier otro error falla de inmediato.
        """
        for intento in range(1, intentos + 1):
            r = self.sesion.get(f"{self.base}/ejecucion/gherkin", params={"historia": historia}, timeout=TIMEOUT)
            if r.ok:
                return r.json()
            if r.status_code != SIN_EJECUCION or intento == intentos:
                raise ErrorDeXrayProxy(f"/ejecucion/gherkin respondió HTTP {r.status_code}: {r.text[:300]}")
            print(f"La Sub Test Execution de {historia} aún no aparece en la búsqueda de Jira; reintento en {espera_s} s "
                  f"({intento + 1} de {intentos}).", flush=True)
            time.sleep(espera_s)
        raise ErrorDeXrayProxy("intentos debe ser 1 o más")

    def enviar(self, ruta_zip):
        """Envía el paquete a /resultados/recibir. Devuelve la respuesta de xray-proxy (testExecution y enlace)."""
        with open(ruta_zip, "rb") as archivo:
            r = self.sesion.post(f"{self.base}/resultados/recibir", timeout=TIMEOUT_ENVIO,
                                 files={"paquete": (os.path.basename(ruta_zip), archivo, "application/zip")})
        if not r.ok:
            raise ErrorDeXrayProxy(f"/resultados/recibir respondió HTTP {r.status_code}: {r.text[:300]}")
        return r.json()
