"""Pruebas del cliente de xray-proxy, con una sesión HTTP falsa."""
import pytest
import requests

from qa_ejecutor import xray_proxy
from qa_ejecutor.xray_proxy import ErrorDeXrayProxy, XrayProxy


class Respuesta:
    def __init__(self, status=200, datos=None, texto=""):
        self.status_code, self._datos, self.text = status, datos or {}, texto
        self.ok = status < 400

    def json(self):
        return self._datos


class SesionFalsa:
    def __init__(self, respuestas):
        self.headers, self.respuestas, self.llamadas = {}, list(respuestas), []

    def _siguiente(self, metodo, url, **kwargs):
        self.llamadas.append((metodo, url, kwargs.get("params")))
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def get(self, url, **kwargs):
        return self._siguiente("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._siguiente("POST", url, **kwargs)


def test_necesita_direccion_y_clave():
    with pytest.raises(ErrorDeXrayProxy):
        XrayProxy("", "clave")
    with pytest.raises(ErrorDeXrayProxy):
        XrayProxy("https://proxy", "")


def test_despertar_reintenta_hasta_que_responde(monkeypatch):
    monkeypatch.setattr(xray_proxy.time, "sleep", lambda s: None)
    sesion = SesionFalsa([requests.ConnectionError("dormido"), Respuesta(503), Respuesta(200)])
    proxy = XrayProxy("https://proxy/", "clave", sesion)
    assert proxy.despertar() is True
    assert sesion.headers["X-API-Key"] == "clave"
    assert [u for _, u, _ in sesion.llamadas] == ["https://proxy/health"] * 3


def test_despertar_se_rinde(monkeypatch):
    monkeypatch.setattr(xray_proxy.time, "sleep", lambda s: None)
    with pytest.raises(ErrorDeXrayProxy, match="no respondió"):
        XrayProxy("https://proxy", "clave", SesionFalsa([Respuesta(503)] * 2)).despertar(intentos=2)


def test_gherkin_y_enviar(tmp_path):
    zip_ = tmp_path / "r.zip"
    zip_.write_bytes(b"zip")
    sesion = SesionFalsa([Respuesta(200, {"features": []}), Respuesta(201, {"testExecution": "DEMO-9"})])
    proxy = XrayProxy("https://proxy", "clave", sesion)
    assert proxy.gherkin("DEMO-3") == {"features": []}
    assert proxy.enviar(zip_) == {"testExecution": "DEMO-9"}
    assert sesion.llamadas == [("GET", "https://proxy/ejecucion/gherkin", {"historia": "DEMO-3"}),
                               ("POST", "https://proxy/resultados/recibir", None)]


def test_errores_de_xray_proxy(tmp_path):
    zip_ = tmp_path / "r.zip"
    zip_.write_bytes(b"zip")
    proxy = XrayProxy("https://proxy", "clave", SesionFalsa([Respuesta(409, texto="sin Sub Test Execution"), Respuesta(400, texto="inválido")]))
    with pytest.raises(ErrorDeXrayProxy, match="HTTP 409: sin Sub Test Execution"):
        proxy.gherkin("DEMO-3", intentos=1)
    with pytest.raises(ErrorDeXrayProxy, match="HTTP 400"):
        proxy.enviar(zip_)


def test_gherkin_reintenta_mientras_la_busqueda_de_jira_no_muestra_la_ejecucion(monkeypatch, capsys):
    esperas = []
    monkeypatch.setattr(xray_proxy.time, "sleep", esperas.append)
    sesion = SesionFalsa([Respuesta(409, texto="sin Sub Test Execution")] * 2 + [Respuesta(200, {"features": []})])
    assert XrayProxy("https://proxy", "clave", sesion).gherkin("DEMO-3") == {"features": []}
    assert (len(sesion.llamadas), esperas) == (3, [15, 15])
    salida = capsys.readouterr().out
    assert "La Sub Test Execution de DEMO-3 aún no aparece en la búsqueda de Jira; reintento en 15 s (2 de 8)." in salida
    assert "(3 de 8)" in salida


def test_gherkin_se_rinde_si_la_ejecucion_no_aparece(monkeypatch):
    monkeypatch.setattr(xray_proxy.time, "sleep", lambda s: None)
    sesion = SesionFalsa([Respuesta(409, texto="DEMO-3 no tiene una Sub Test Execution abierta")] * 3)
    with pytest.raises(ErrorDeXrayProxy, match="HTTP 409: DEMO-3 no tiene una Sub Test Execution abierta"):
        XrayProxy("https://proxy", "clave", sesion).gherkin("DEMO-3", intentos=3)
    assert len(sesion.llamadas) == 3


def test_gherkin_no_reintenta_otros_errores(monkeypatch):
    monkeypatch.setattr(xray_proxy.time, "sleep", lambda s: pytest.fail("no debe esperar"))
    sesion = SesionFalsa([Respuesta(502, texto="Jira no responde")])
    with pytest.raises(ErrorDeXrayProxy, match="HTTP 502"):
        XrayProxy("https://proxy", "clave", sesion).gherkin("DEMO-3")
    assert len(sesion.llamadas) == 1


def test_gherkin_sin_intentos():
    with pytest.raises(ErrorDeXrayProxy, match="intentos debe ser 1 o más"):
        XrayProxy("https://proxy", "clave", SesionFalsa([])).gherkin("DEMO-3", intentos=0)
