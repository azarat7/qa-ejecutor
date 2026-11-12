"""Datos de ejemplo para las pruebas: un .feature como el que entrega xray-proxy y pasos de un proyecto ficticio."""

FEATURE = """@REQ_DEMO-3
Feature: DEMO-3 · DEMO-9

  @TEST_DEMO-11
  Scenario: TC-AUT-SES-02 Cierre de sesión
    # Given = Dado · When = Cuando · Then = Entonces · And = Y · Examples = Ejemplos
    Given un operador de "Banco Demo" con sesión iniciada
    When cierra la sesión
    Then vuelve a la pantalla de inicio de sesión

  @TEST_DEMO-12
  Scenario Outline: TC-AUT-LOG-02 Inicio de sesión de los otros roles
    Given un usuario activo con rol "<rol>"
    When ingresa usuario y contraseña válidos
    Then accede al portal
    Examples:
    | rol               |
    | Administrador ICG |
    | Auditoría Interna |

  @TEST_DEMO-13
  Scenario: TC-AUT-SES-01 Expiración de la sesión
    Given un operador de "Banco Demo" con sesión iniciada
    When pasan 15 minutos sin actividad
    Then la sesión expira

  @TEST_DEMO-14
  Scenario: TC-AUT-LOG-01 Inicio de sesión correcto
    Given un operador de "Banco Demo" con sesión iniciada
    Then accede al portal
"""

# Pasos de un proyecto ficticio: "Auditoría Interna" no accede (falla), "pasan ... minutos" no tiene código.
PASOS = '''
from pytest_bdd import given, when, then, parsers

@given(parsers.re(r'^un operador de "(?P<banco>[^"]+)" con sesión iniciada$'), target_fixture="rol")
def operador(banco):
    return "Operador"

@given(parsers.re(r'^un usuario activo con rol "(?P<nombre>[^"]+)"$'), target_fixture="rol")
def usuario(nombre):
    return nombre

@when("ingresa usuario y contraseña válidos")
def ingresa():
    pass

@when("cierra la sesión")
def cierra():
    pass

@then("vuelve a la pantalla de inicio de sesión")
def vuelve():
    pass

@then("accede al portal")
def accede(rol):
    assert rol != "Auditoría Interna", "sigue en la pantalla de inicio de sesión"
'''

RESPUESTA = {"historia": "DEMO-3", "testExecution": "DEMO-9", "cucumber": 4, "manual": ["TC-AUT-MSG-01 Redacción"],
             "sin_gherkin": [], "features": [{"archivo": "DEMO-3.feature", "contenido": FEATURE}]}
