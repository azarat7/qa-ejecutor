"""Pruebas del guardado de los .feature que entrega xray-proxy."""
import pytest

from qa_ejecutor import gherkin
from tests.apoyo import RESPUESTA


def test_guarda_los_feature_y_el_modulo_que_los_carga(tmp_path):
    rutas = gherkin.guardar(RESPUESTA, tmp_path)
    assert [r.name for r in rutas] == ["DEMO-3.feature"]
    assert (tmp_path / "DEMO-3.feature").read_text(encoding="utf-8").startswith("@REQ_DEMO-3\n")
    assert "scenarios(\".\")" in (tmp_path / "test_xray.py").read_text(encoding="utf-8")


def test_sin_features_no_escribe_nada(tmp_path):
    assert gherkin.guardar({"features": []}, tmp_path) == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("nombre", ["../fuera.feature", "DEMO-3.py", "demo-3.feature", ""])
def test_rechaza_nombres_de_archivo_no_permitidos(tmp_path, nombre):
    with pytest.raises(gherkin.GherkinInvalido):
        gherkin.guardar({"features": [{"archivo": nombre, "contenido": "x"}]}, tmp_path)


def test_identificador():
    assert gherkin.identificador("TC-AUT-SES-02 Cierre de sesión") == "TC-AUT-SES-02"
    assert gherkin.identificador("  ") == ""
