"""Pruebas del ZIP de resultados (mismo formato que recibe hoy xray-proxy)."""
import json
import zipfile

from qa_ejecutor import paquete


def test_zip_con_manifest_resultados_y_evidencias(tmp_path):
    (tmp_path / "a.png").write_bytes(b"png")
    (tmp_path / "grande.png").write_bytes(b"0" * (paquete.MAX_EVIDENCIA + 1))
    resultados = [{"identificador": "TC-A-01", "evidencias": ["a.png", "no-existe.png"]},
                  {"identificador": "TC-M-01", "evidencias": [], "steps": [{"evidencias": ["grande.png"]}]}]
    ruta, avisos = paquete.empaquetar("DEMO-3", "bdd-20261112-1000", resultados, tmp_path, tmp_path / "salida")
    assert ruta.name == "resultados_DEMO-3_bdd-20261112-1000.zip"
    assert len(avisos) == 2
    with zipfile.ZipFile(ruta) as zf:
        assert sorted(zf.namelist()) == ["evidencias/a.png", "manifest.json", "resultados.json"]
        m = json.loads(zf.read("manifest.json"))
        assert (m["tipo"], m["historia"], m["proyecto"], m["run_id"]) == ("resultados", "DEMO-3", "DEMO", "bdd-20261112-1000-demo3")
        assert m["version_prompt"] == "qa-ejecutor@0.1.1"
        tests = json.loads(zf.read("resultados.json"))["tests"]
        assert tests[0]["evidencias"] == ["a.png"]
        assert tests[1]["steps"][0]["evidencias"] == []
