"""Pruebas de la preparación de las pruebas Manual por el agente (D-40, D-44)."""
import contextlib

import pytest

from qa_ejecutor import manual


class PaginaFalsa:
    def __init__(self, carpeta):
        self.carpeta = carpeta

    def screenshot(self, path, full_page):
        open(path, "wb").write(b"png")


@pytest.fixture
def abrir(tmp_path):
    return lambda: contextlib.nullcontext(PaginaFalsa(tmp_path))


@pytest.fixture(autouse=True)
def registro_limpio(monkeypatch):
    monkeypatch.setattr(manual, "REGISTRO", {})


def test_prepara_los_pasos_con_sugerencia_notas_y_capturas(tmp_path, abrir):
    @manual.manual("TC-AUT-MSG-01", pasos=2)
    def redaccion(t):
        with t.ejemplo("mensaje de bloqueo", paso=2):
            t.verificar(True, "La cuenta queda bloqueada", paso=1)
            t.nota('Texto mostrado: "Tu cuenta está bloqueada"')
            t.verificar(False, "Indica la acción sugerida", "sin acción sugerida")
    [r], sin = manual.preparar(["TC-AUT-MSG-01", "TC-OTRA-01"], tmp_path, "https://app", "bdd-1", abrir)
    assert sin == ["TC-OTRA-01"]
    assert (r["tipo"], r["status"]) == ("Manual", "TODO")
    assert r["comment"].startswith("PRUEBA MANUAL PREPARADA POR EL AGENTE. Sugerencia: FAILED.")
    paso1, paso2 = r["steps"]
    assert paso1 == {"status": "TODO", "actualResult": "Sugerencia del agente: PASSED.\nOK    La cuenta queda bloqueada",
                     "evidencias": ["TC-AUT-MSG-01_01_paso1-La-cuenta-queda-bloqueada.png"]}
    assert paso2["actualResult"].startswith("Sugerencia del agente: FAILED.\nFALLA Indica la acción sugerida -> sin acción sugerida\nNota (")
    assert paso2["evidencias"] == ["TC-AUT-MSG-01_02_paso2-falla-Indica-la-acci-n-sugerida.png"]
    assert r["evidencias"] == []


def test_un_error_queda_como_lo_observado(tmp_path, abrir):
    @manual.manual("TC-BAN-MSG-01", pasos=1)
    def con_error(t):
        with t.ejemplo("404"):
            raise RuntimeError("el banco simulado no respondió")

    @manual.manual("TC-BAN-DES-01", pasos=1)
    def sin_ejemplo(t):
        raise ValueError("faltan documentos")
    r, _ = manual.preparar(["TC-BAN-MSG-01", "TC-BAN-DES-01"], tmp_path, "https://app", "bdd-1", abrir)
    assert "FALLA La preparación terminó con un error -> RuntimeError: el banco simulado no respondió" in r[0]["comment"]
    assert r[0]["evidencias"] == ["TC-BAN-MSG-01_01_404.png"]
    assert "FALLA La preparación no pudo terminar -> ValueError: faltan documentos" in r[1]["comment"]
    assert r[1]["steps"][0]["actualResult"] == "Sugerencia del agente: sin verificación automática."


def test_captura_sin_pagina_no_hace_nada(tmp_path, abrir):
    t = manual.PruebaManual("TC-X-01", 1, tmp_path, "https://app", abrir)
    t.captura("antes de abrir")
    assert t.evidencias == []


def test_captura_que_falla_no_pierde_lo_observado(tmp_path):
    class PaginaRota:
        def screenshot(self, path, full_page):
            raise OSError("sin pantalla")
    t = manual.PruebaManual("TC-X-01", 1, tmp_path, "https://app", lambda: contextlib.nullcontext(PaginaRota()))
    with t.ejemplo("uno", paso=1):
        t.verificar(True, "algo")
    assert t.evidencias == []
    assert t.verificaciones[0]["ok"]
