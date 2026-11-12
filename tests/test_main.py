"""Pruebas de la línea de comandos: de la respuesta de xray-proxy al ZIP enviado."""
import json
import zipfile

import pytest

from qa_ejecutor import __main__ as cli
from qa_ejecutor import manual
from qa_ejecutor.xray_proxy import ErrorDeXrayProxy
from tests.apoyo import PASOS, RESPUESTA

MANUAL = '''
from qa_ejecutor.manual import manual

@manual("TC-AUT-MSG-01", pasos=1)
def redaccion(t):
    t.verificar(True, "sin página", paso=1)
'''


class ProxyFalso:
    enviados = []

    def __init__(self, base, api_key, respuesta=RESPUESTA, falla=None):
        self.respuesta, self.falla = respuesta, falla

    def despertar(self):
        if self.falla == "despertar":
            raise ErrorDeXrayProxy("xray-proxy no respondió")
        return True

    def gherkin(self, historia):
        return self.respuesta

    def enviar(self, ruta):
        if self.falla == "enviar":
            raise ErrorDeXrayProxy("HTTP 400")
        ProxyFalso.enviados.append(ruta)
        return {"testExecution": "DEMO-9"}


@pytest.fixture
def proyecto(pytester, monkeypatch):
    """Un proyecto ficticio con su paquete de pasos (proyecto_demo.pasos) y una prueba Manual registrada."""
    monkeypatch.setattr(manual, "REGISTRO", {})
    pytester.mkpydir("proyecto_demo")
    pasos = pytester.mkpydir("proyecto_demo/pasos")
    (pasos / "inicio.py").write_text(PASOS, encoding="utf-8")
    (pasos / "mensajes.py").write_text(MANUAL, encoding="utf-8")
    monkeypatch.setenv("XRAY_PROXY_API_KEY", "clave")
    monkeypatch.setattr(cli, "navegador_de_la_corrida", lambda: __import__("contextlib").nullcontext(None))
    monkeypatch.setattr(cli, "pagina_limpia", lambda navegador: __import__("contextlib").nullcontext(None))
    ProxyFalso.enviados = []
    return pytester


def ejecutar(monkeypatch, *extra, **proxy):
    monkeypatch.setattr(cli, "XrayProxy", lambda base, clave: ProxyFalso(base, clave, **proxy))
    return cli.main(["--historia", "DEMO-3", "--pasos", "proyecto_demo.pasos", "--url", "https://app",
                     "--xray-proxy", "https://proxy", *extra])


def test_ejecuta_arma_el_zip_y_lo_envia(proyecto, monkeypatch, capsys):
    assert ejecutar(monkeypatch) == 0
    [ruta] = ProxyFalso.enviados
    with zipfile.ZipFile(ruta) as zf:
        tests = {t["identificador"]: t for t in json.loads(zf.read("resultados.json"))["tests"]}
    assert {i: t["status"] for i, t in tests.items()} == {
        "TC-AUT-SES-02": "PASSED", "TC-AUT-LOG-02": "FAILED", "TC-AUT-SES-01": "TODO", "TC-AUT-LOG-01": "PASSED", "TC-AUT-MSG-01": "TODO"}
    salida = capsys.readouterr().out
    assert "DEMO-3 · Sub Test Execution DEMO-9: 4 pruebas Cucumber, 1 Manual, 0 Cucumber sin Gherkin" in salida
    assert "Totales: FAILED: 1, PASSED: 2, TODO: 2" in salida


def test_sin_enviar_y_sin_gherkin(proyecto, monkeypatch):
    respuesta = {**RESPUESTA, "features": [], "cucumber": 0, "manual": ["TC-OTRA-01 Sin función"], "sin_gherkin": ["TC-AUT-BLO-09 Vacía"]}
    assert ejecutar(monkeypatch, "--sin-enviar", respuesta=respuesta) == 0
    assert ProxyFalso.enviados == []
    [zip_] = list(proyecto.path.glob("resultados_e2e/*/resultados_DEMO-3_*.zip"))
    with zipfile.ZipFile(zip_) as zf:
        [t] = json.loads(zf.read("resultados.json"))["tests"]
    assert (t["identificador"], t["status"]) == ("TC-AUT-BLO-09", "TODO")


def test_nada_que_ejecutar(proyecto, monkeypatch, capsys):
    respuesta = {**RESPUESTA, "features": [], "manual": ["TC-OTRA-01 Sin función"]}
    assert ejecutar(monkeypatch, respuesta=respuesta) == 1
    assert "TC-OTRA-01: prueba Manual sin preparación automática" in capsys.readouterr().out


@pytest.mark.parametrize("falla", ["despertar", "enviar"])
def test_errores_de_xray_proxy(proyecto, monkeypatch, falla):
    assert ejecutar(monkeypatch, falla=falla) == 1


@pytest.mark.parametrize("args", [["--historia", "demo"], ["--historia", "DEMO-3", "--url", ""]])
def test_argumentos_invalidos(monkeypatch, args):
    monkeypatch.delenv("APP_URL", raising=False)
    assert cli.main(args) == 2
