"""
Ejecuta las pruebas de la Sub Test Execution abierta de una historia y envía los resultados a xray-proxy.

    python -m qa_ejecutor --historia QAPEC-3 --pasos e2e.pasos --url https://mi-aplicacion --xray-proxy https://xray-proxy

Variables de entorno: XRAY_PROXY_API_KEY (obligatoria; nunca se escribe en archivos), APP_URL y XRAY_PROXY_URL
(si no se pasan --url y --xray-proxy) y los secretos que usen los pasos del proyecto.
"""
import argparse
import datetime as dt
import importlib
import os
import pkgutil
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from qa_ejecutor import gherkin, manual
from qa_ejecutor.navegador import navegador_de_la_corrida, pagina_limpia
from qa_ejecutor.paquete import empaquetar
from qa_ejecutor.plugin import Recolector, ahora
from qa_ejecutor.xray_proxy import ErrorDeXrayProxy, XrayProxy

HISTORIA_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")


def argumentos(argv=None):
    a = argparse.ArgumentParser(prog="python -m qa_ejecutor", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--historia", required=True, help="clave de la historia en Jira, por ejemplo QAPEC-3")
    a.add_argument("--pasos", default="e2e.pasos", help="paquete de Python con los pasos del proyecto (por defecto e2e.pasos)")
    a.add_argument("--url", default=os.environ.get("APP_URL", ""), help="dirección de la aplicación que se prueba (o APP_URL)")
    a.add_argument("--xray-proxy", default=os.environ.get("XRAY_PROXY_URL", ""), help="dirección de xray-proxy (o XRAY_PROXY_URL)")
    a.add_argument("--salida", default="resultados_e2e", help="carpeta donde queda el ZIP de resultados")
    a.add_argument("--sin-enviar", action="store_true", help="arma el ZIP y no lo envía (para revisar en local)")
    return a.parse_args(argv)


def modulos_de_pasos(paquete):
    """Importa el paquete de pasos y sus módulos (también registran las pruebas Manual). Devuelve sus nombres."""
    sys.path.insert(0, os.getcwd())
    raiz = importlib.import_module(paquete)
    nombres = [paquete] + [f"{paquete}.{m.name}" for m in pkgutil.iter_modules(getattr(raiz, "__path__", []))]
    for nombre in nombres:
        importlib.import_module(nombre)
    return nombres


def ejecutar_cucumber(respuesta, carpeta, evidencias, modulos, url, run_id):
    """Corre los .feature con pytest-bdd y los pasos del proyecto. Devuelve los resultados para el paquete."""
    if not gherkin.guardar(respuesta, carpeta):
        return []
    recolector = Recolector(evidencias)
    # Las etiquetas de Xray (@TEST_..., @REQ_...) no son marcas registradas de pytest: se ignora ese aviso.
    args = [str(carpeta), "-q", "--tb=short", "-p", "no:cacheprovider", "-W", "ignore::pytest.PytestUnknownMarkWarning",
            "-W", "ignore::pytest.PytestAssertRewriteWarning", "-p", "qa_ejecutor.navegador"]
    for m in modulos:
        args += ["-p", m]
    pytest.main(args, plugins=[recolector])
    return recolector.como_xray(url, run_id)


def sin_gherkin(resumenes):
    """Las pruebas Cucumber sin Gherkin en Xray quedan en TODO: no se dan por buenas sin ejecutar nada."""
    hora = ahora()
    return [{"identificador": gherkin.identificador(s), "tipo": "Cucumber", "status": "TODO", "start": hora, "finish": hora,
             "comment": "La prueba Cucumber no tiene Gherkin en Xray: QA debe completarla antes de ejecutarla.", "evidencias": []}
            for s in resumenes]


def preparar_manual(resumenes, evidencias, url, run_id):
    """Prepara las pruebas Manual que el proyecto registró (D-40). Devuelve (resultados, sin función registrada)."""
    identificadores = [gherkin.identificador(s) for s in resumenes]
    if not any(i in manual.REGISTRO for i in identificadores):
        return [], identificadores
    with navegador_de_la_corrida() as navegador:
        return manual.preparar(identificadores, evidencias, url, run_id, lambda: pagina_limpia(navegador))


def correr(args, respuesta, run_id):
    """Ejecuta todo y arma el ZIP. Devuelve (ruta del ZIP o None, resultados, avisos)."""
    modulos = modulos_de_pasos(args.pasos)
    with tempfile.TemporaryDirectory(prefix="qa-ejecutor-") as temporal:
        carpeta, evidencias = Path(temporal, "features"), Path(temporal, "evidencias")
        carpeta.mkdir()
        evidencias.mkdir()
        resultados = ejecutar_cucumber(respuesta, carpeta, evidencias, modulos, args.url, run_id)
        resultados += sin_gherkin(respuesta.get("sin_gherkin") or [])
        de_manual, sin_funcion = preparar_manual(respuesta.get("manual") or [], evidencias, args.url, run_id)
        resultados += de_manual
        avisos = [f"{i}: prueba Manual sin preparación automática; QA la hace desde cero" for i in sin_funcion]
        if not resultados:
            return None, [], avisos
        ruta, mas = empaquetar(args.historia, run_id, resultados, evidencias, Path(args.salida) / run_id)
    return ruta, resultados, avisos + mas


def main(argv=None):
    args = argumentos(argv)
    if not HISTORIA_RE.match(args.historia):
        print(f"Historia inválida: {args.historia!r} (debe ser una clave de Jira, por ejemplo QAPEC-3)", file=sys.stderr)
        return 2
    if not args.url:
        print("Falta la dirección de la aplicación (--url o APP_URL)", file=sys.stderr)
        return 2
    os.environ["APP_URL"] = args.url
    try:
        proxy = XrayProxy(args.xray_proxy, os.environ.get("XRAY_PROXY_API_KEY", ""))
        proxy.despertar()
        respuesta = proxy.gherkin(args.historia)
    except ErrorDeXrayProxy as e:
        print(f"No se pudo obtener el Gherkin: {e}", file=sys.stderr)
        return 1
    print(f"{args.historia} · Sub Test Execution {respuesta.get('testExecution')}: {respuesta.get('cucumber', 0)} pruebas Cucumber, "
          f"{len(respuesta.get('manual') or [])} Manual, {len(respuesta.get('sin_gherkin') or [])} Cucumber sin Gherkin", flush=True)
    run_id = "bdd-" + dt.datetime.now().strftime("%Y%m%d-%H%M")
    ruta, resultados, avisos = correr(args, respuesta, run_id)
    for aviso in avisos:
        print(f"Aviso: {aviso}")
    if not ruta:
        print("La Sub Test Execution no tiene pruebas para ejecutar ni preparar.", file=sys.stderr)
        return 1
    totales = Counter(r["status"] for r in resultados)
    print("Totales: " + ", ".join(f"{k}: {v}" for k, v in sorted(totales.items())) + f" · paquete {ruta}", flush=True)
    if args.sin_enviar:
        return 0
    try:
        print(f"Enviado a xray-proxy: {proxy.enviar(ruta)}")
    except ErrorDeXrayProxy as e:
        print(f"No se pudo enviar el paquete: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
