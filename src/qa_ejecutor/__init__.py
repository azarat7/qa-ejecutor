"""
qa-ejecutor: ejecuta en GitHub Actions las pruebas Cucumber que QA programó en Xray (flujo BDD nativo, ADR-008).

1. Pide a xray-proxy el .feature de la Sub Test Execution abierta de la historia (gherkin.py).
2. Lo ejecuta con pytest-bdd y Playwright, con los pasos que escribe cada proyecto (plugin.py, navegador.py).
3. Prepara las pruebas Manual que el proyecto haya automatizado (manual.py): QA decide su estado.
4. Arma el ZIP de resultados con el formato que ya recibe xray-proxy (paquete.py) y lo envía (envio.py).
"""

__version__ = "0.1.1"
