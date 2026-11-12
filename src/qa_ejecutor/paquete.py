"""ZIP de resultados de una historia, con el formato que ya recibe xray-proxy (manifest.json, resultados.json, evidencias/)."""
import datetime as dt
import json
import zipfile
from pathlib import Path

from qa_ejecutor import __version__

MAX_EVIDENCIA = 5 * 1024 * 1024
MODELO = "playwright y pytest-bdd (ejecutor escrito por claude-opus-5-5)"


def manifest(historia, run_id):
    """Datos de la corrida. Sin claves de Jira: xray-proxy encuentra la Sub Test Execution abierta y cada prueba."""
    return {
        "tipo": "resultados",
        "run_id": f"{run_id}-{historia.lower().replace('-', '')}"[:64],
        "proyecto": historia.split("-")[0],
        "historia": historia,
        "version_prompt": f"qa-ejecutor@{__version__}",
        "modelo": MODELO,
        "generado": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _incluir_evidencias(zf, resultado, carpeta, avisos):
    """Agrega al ZIP las capturas de la prueba y de sus pasos; quita de la lista las que no existen o superan 5 MB."""
    for lista in [resultado["evidencias"]] + [s["evidencias"] for s in resultado.get("steps", [])]:
        for nombre in list(lista):
            archivo = Path(carpeta) / nombre
            if not archivo.is_file() or archivo.stat().st_size > MAX_EVIDENCIA:
                avisos.append(f"{resultado['identificador']}: la captura {nombre} no existe o supera 5 MB; no se incluye")
                lista.remove(nombre)
                continue
            zf.write(archivo, f"evidencias/{nombre}")


def empaquetar(historia, run_id, resultados, carpeta_evidencias, destino):
    """Escribe resultados_<historia>_<run_id>.zip en `destino`. Devuelve (ruta, avisos)."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    ruta, avisos = destino / f"resultados_{historia}_{run_id}.zip", []
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in resultados:
            _incluir_evidencias(zf, r, carpeta_evidencias, avisos)
        zf.writestr("manifest.json", json.dumps(manifest(historia, run_id), ensure_ascii=False, indent=2))
        zf.writestr("resultados.json", json.dumps({"tests": resultados}, ensure_ascii=False, indent=2))
    return ruta, avisos
