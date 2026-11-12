"""Pruebas del recolector: estado por prueba y por fila, pasos sin código, fallas y capturas."""
from qa_ejecutor import gherkin
from qa_ejecutor.plugin import Recolector, clave_de
from tests.apoyo import PASOS, RESPUESTA

ARGS = ("-p", "pasos_demo", "-W", "ignore::pytest.PytestUnknownMarkWarning")


def correr(pytester, pasos=PASOS, respuesta=RESPUESTA):
    pytester.makepyfile(pasos_demo=pasos)
    pytester.syspathinsert()
    gherkin.guardar(respuesta, pytester.path)
    recolector = Recolector(pytester.path)
    pytester.runpytest_inprocess(*ARGS, plugins=[recolector])
    return {r["identificador"]: r for r in recolector.como_xray("https://app", "bdd-1")}


def test_clave_de_la_etiqueta():
    assert clave_de(["REQ_DEMO-3", "TEST_DEMO-11"]) == "DEMO-11"
    assert clave_de(["qa-ia"]) == ""


def test_estados_por_prueba_y_por_fila(pytester):
    r = correr(pytester)
    assert list(r) == ["TC-AUT-SES-02", "TC-AUT-LOG-02", "TC-AUT-SES-01", "TC-AUT-LOG-01"]
    assert r["TC-AUT-SES-02"]["status"] == "PASSED"
    assert "ejemplos" not in r["TC-AUT-SES-02"]
    assert r["TC-AUT-LOG-02"]["status"] == "FAILED"
    assert r["TC-AUT-LOG-02"]["ejemplos"] == [{"nombre": "Administrador ICG", "status": "PASSED"},
                                             {"nombre": "Auditoría Interna", "status": "FAILED"}]
    assert ("[Auditoría Interna] FALLA Then accede al portal -> AssertionError: sigue en la pantalla de inicio de sesión"
            in r["TC-AUT-LOG-02"]["comment"])
    assert r["TC-AUT-LOG-01"]["status"] == "PASSED"


def test_paso_sin_codigo_deja_la_prueba_en_todo(pytester):
    r = correr(pytester)["TC-AUT-SES-01"]
    assert r["status"] == "TODO"
    assert "PASOS SIN CÓDIGO (la prueba queda en TODO hasta que se programen): When pasan 15 minutos sin actividad" in r["comment"]
    assert "ejemplos" not in r
    assert r["tipo"] == "Cucumber"
    assert r["comment"].endswith("Ejecutado contra https://app con qa-ejecutor 0.1.0 (pytest-bdd y Playwright). run bdd-1.")


def test_un_esquema_con_un_paso_sin_codigo_no_envia_filas(pytester):
    sin_accede = PASOS.replace('@then("accede al portal")', '@then("accede al portal y ve su banco")')
    r = correr(pytester, pasos=sin_accede)["TC-AUT-LOG-02"]
    assert r["status"] == "TODO"
    assert "ejemplos" not in r


def test_falla_antes_del_primer_paso(pytester):
    pasos = PASOS + '''
import pytest

@pytest.fixture(autouse=True)
def entorno_roto(request):
    if "Cierre" in (request.node.function.__doc__ or ""):
        raise RuntimeError("el portal no respondió")
'''
    r = correr(pytester, pasos=pasos)["TC-AUT-SES-02"]
    assert r["status"] == "FAILED"
    assert "FALLA fuera de los pasos (setup): RuntimeError: el portal no respondió" in r["comment"]


def test_captura_al_final_y_en_cada_falla(pytester):
    pasos = PASOS + '''
import pytest

class PaginaFalsa:
    def screenshot(self, path, full_page):
        open(path, "wb").write(b"png")

@pytest.fixture
def pagina():
    return PaginaFalsa()

@pytest.fixture(autouse=True)
def usa_pagina(pagina):
    return pagina
'''
    r = correr(pytester, pasos=pasos)
    assert r["TC-AUT-SES-02"]["evidencias"] == ["TC-AUT-SES-02_01_escenario.png"]
    assert r["TC-AUT-LOG-02"]["evidencias"] == ["TC-AUT-LOG-02_01_Administrador-ICG.png", "TC-AUT-LOG-02_02_falla.png",
                                                "TC-AUT-LOG-02_03_Auditor-a-Interna.png"]
    assert (pytester.path / "TC-AUT-LOG-02_02_falla.png").read_bytes() == b"png"


def test_captura_que_falla_no_pierde_el_resultado(pytester):
    pasos = PASOS + '''
import pytest

class PaginaRota:
    def screenshot(self, path, full_page):
        raise OSError("sin pantalla")

@pytest.fixture(autouse=True)
def pagina():
    return PaginaRota()
'''
    r = correr(pytester, pasos=pasos)["TC-AUT-SES-02"]
    assert (r["status"], r["evidencias"]) == ("PASSED", [])
