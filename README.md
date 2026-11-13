# qa-ejecutor

Ejecutor compartido de pruebas automatizadas con el flujo BDD nativo de Xray (ADR-008 del proyecto Calidad
Preventiva con IA). Contenido de demostración, sin datos ni secretos. Todos los derechos reservados.

## Qué hace

1. Pide a xray-proxy (`GET /ejecucion/gherkin?historia=...`) el `.feature` de las pruebas Cucumber de la Sub Test
   Execution abierta de la historia: **se ejecuta exactamente lo que QA programó en Xray**.
2. Lo ejecuta con pytest-bdd y Playwright, con los **pasos que escribe cada proyecto**.
3. Prepara las pruebas Manual que el proyecto haya automatizado: el agente deja lo observado y las capturas en cada
   paso, en TODO; QA decide el estado (D-40).
4. Arma el ZIP de resultados con el formato que ya recibe xray-proxy y lo envía a `/resultados/recibir`. QA lo revisa
   y confirma en xray-proxy, como siempre.

| Situación | Estado que se envía |
|---|---|
| Todas las filas de Examples pasan | PASSED |
| Alguna fila falla | FAILED, con la fila, el paso y el motivo en el comentario |
| Algún paso sin código | TODO, con el texto del paso que falta (no es un defecto del producto) |
| Prueba Manual con preparación automática | TODO, con lo observado y las capturas en cada paso |
| Prueba Cucumber sin Gherkin en Xray | TODO |

Capturas: al final de cada ejemplo y en el momento de cada falla.

### Comentario de cada prueba

xray-proxy lee el comentario para proponer los Errores y para sugerir qué fallas tienen la misma causa. Cada ejemplo va
en su línea, entre corchetes, y debajo un renglón por paso ejecutado, sin la palabra clave de Gherkin:

```
[Auditoría Interna]
  OK    un usuario activo con rol "Auditoría Interna"
  OK    ingresa usuario y contraseña válidos
  FALLA accede al portal -> sigue en la pantalla de inicio de sesión
```

Después de `->` va lo obtenido, en un solo renglón: el mensaje de la verificación (`assert`) o, en otro error, su tipo
y su mensaje. **Dos pruebas que obtienen lo mismo tienen el mismo síntoma** y xray-proxy las sugiere en un solo Error.

## Cómo lo usa un proyecto

1. **Pasos:** un paquete de Python (por defecto `e2e/pasos/`) con un módulo por tema. Cada frase del catálogo es un
   paso; las fixtures `pagina` (Playwright) y `url_app` las da qa-ejecutor:

   ```python
   from pytest_bdd import given, parsers

   @given(parsers.re(r'^un operador de "(?P<banco>[^"]+)" con sesión iniciada$'))
   def operador_con_sesion(pagina, url_app, banco):
       pagina.goto(f"{url_app}/login")
       ...
   ```

   Reglas del catálogo: frase fija y el ejemplo solo cambia un valor; los valores entre comillas no llevan comillas;
   expresiones exactas (`^...$`) para que dos frases no se confundan.

   **Un paso que prepara un estado verifica que lo logró**, con el mismo mensaje que usa el paso que comprueba ese
   estado. Si el producto no deja preparar la precondición, la prueba falla en ese paso (no pasa ni falla más adelante
   por otra razón) y queda con el mismo síntoma que la prueba que detecta el defecto:

   ```python
   @given(parsers.re(r"^un operador bloqueado hace (?P<minutos>\d+) minutos$"), converters={"minutos": int})
   def operador_bloqueado(esc, minutos):
       mensaje = fallar(esc.pagina, esc.url, 5, esc.usuario)
       assert "bloqueada" in mensaje, f"Mensaje: {mensaje!r}"   # el mismo mensaje del paso "la cuenta queda bloqueada"
       esc.portal.reloj(minutos)
   ```

2. **Pruebas Manual** que el agente puede adelantar:

   ```python
   from qa_ejecutor.manual import manual

   @manual("TC-AUT-MSG-01", pasos=2)
   def redaccion_del_mensaje(t):
       with t.ejemplo("mensaje de bloqueo", paso=2):
           t.verificar(condicion, "lo que se verifica", detalle, paso=1)
           t.nota("lo observado")
   ```

3. **Flujo** `.github/workflows/pruebas-e2e.yml` (xray-proxy lo lanza con la historia):

   ```yaml
   name: Pruebas E2E
   on:
     workflow_dispatch:
       inputs:
         historia: {description: "Historia de Jira", required: true, type: string}
   concurrency:            # una ejecución a la vez contra el mismo ambiente
     group: pruebas-e2e
     queue: max
   permissions:
     contents: read
   jobs:
     pruebas:
       uses: azarat7/qa-ejecutor/.github/workflows/ejecutar.yml@v0.1.1
       with:
         historia: ${{ inputs.historia }}
         version: v0.1.1
         url: ${{ vars.APP_URL }}
         xray-proxy-url: ${{ vars.XRAY_PROXY_URL }}
       secrets: inherit
   ```

4. **Secretos del repositorio:** `XRAY_PROXY_API_KEY` y los que usen los pasos (por ejemplo, las credenciales de los
   usuarios de prueba). El flujo los entrega como variables de entorno solo durante la ejecución.

## En local

```bash
pip install "qa-ejecutor @ https://github.com/azarat7/qa-ejecutor/archive/v0.1.1.tar.gz"
python -m playwright install chromium
export XRAY_PROXY_API_KEY=...   # nunca en archivos
python -m qa_ejecutor --historia QAPEC-3 --url https://mi-aplicacion --xray-proxy https://xray-proxy --sin-enviar
```

`QA_VISIBLE=1` muestra el navegador. Con `--sin-enviar` el ZIP queda en `resultados_e2e/` para revisarlo.

## Desarrollo

```bash
pip install -e ".[dev]"
ruff check
pytest
```

Versiones con etiquetas (`v0.1.1`); cada proyecto fija la suya y Dependabot avisa de las nuevas. La versión de
Playwright de `pyproject.toml` debe coincidir con la imagen del flujo (`mcr.microsoft.com/playwright/python`).
