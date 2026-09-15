# Estructura del repositorio tras la limpieza

**12 de septiembre de 2026.** El repositorio acumulaba seis versiones del agente
y sus árboles de experimentos. En `main` queda sólo lo que hace falta; todo lo
retirado vive íntegro en la rama **`pre-limpieza`**.

## Qué hay y por qué

| Ruta | Qué es | Por qué se queda |
|---|---|---|
| `version_final_reto_send/` | **La entrega (V3, 15-sep).** Agente de las tres tareas, expertos, entrenamientos, análisis, prompts, pizarras, perfil de 16 GB, investigación, y el supervisor con la sombra que garantiza los 15 minutos | Es lo que se ejecuta y lo que se defiende |
| `version_final_reto_before/` | El mismo paquete **antes** del supervisor (commit `fb4b6ff`), y en `imagen_v2_enviada/` el kit exacto de la imagen enviada a Test | Volver atrás y reconstruir los tarballs sin guardarlos |
| `version_final_reto` → `version_final_reto_send` | Enlace simbólico | Las pruebas, el perfilador y los imports usan este nombre |
| `result_v2/` | 423 salidas y 423 pizarras de la cobertura completa, con su comparativa | La evidencia de que funciona sobre toda la base |
| `delete/` | Exploración temprana y el notebook de análisis | Pedido explícitamente: puede hacer falta |
| `delete_test/` | Banco de pruebas | Pedido explícitamente |
| `src/`, `inference.py`, `configs/`, `templates/`, `resources/`, `scripts/`, `tests/`, `test/`, `input/`, `output/`, `docs/`, `dev/` | El repositorio base del reto, sin tocar | Es el marco que el reto exige; `inference.py` es el entrypoint oficial |
| `data/`, `model/` | Datos bajo acuerdo de uso y pesos (19 GB) | Nunca estuvieron en git (`.gitignore`) |
| `Dockerfile_final`, `do_build_final.sh`, `do_save_final.sh`, `do_fijar_dependencias.sh` | Construcción y empaquetado de la entrega; `CODE_DIR` elige la versión | ver «Versiones e imágenes» |

## Qué se retiró de `main`

| Ruta | Ficheros | Dónde está ahora |
|---|---:|---|
| `delete_solution_one/` | 8 463 | rama `pre-limpieza` |
| `delete_final_versions_task/` | 2 888 | rama `pre-limpieza`; sus salidas y pizarras, congeladas en `version_final_reto/investigacion/referencias_historicas/` |
| `delete_final_versions_task_V1/` | 2 139 | rama `pre-limpieza`; su `t3_adoptado` congelado como `H0_task3` |
| `delete_expert_modelate/` | 99 | rama `pre-limpieza` |
| `delete_PLAN/` | 5 | rama `pre-limpieza` |
| `delete_final_versions_task_V1_1/` | — | **renombrado** a `version_final_reto/` |
| `delete_final_versions_task_V2/` | — | **fusionado** en `version_final_reto/runtime_16gb/` |
| `delete_final_versions_task_V2_2/` | — | **fusionado** en `version_final_reto/investigacion/` |

## Volver atrás

```bash
git checkout pre-limpieza          # el repositorio entero, como estaba
git checkout pre-limpieza -- <ruta>  # recuperar sólo una parte a main
```

Nada se ha perdido. `pre-limpieza` es un commit completo del árbol de trabajo,
incluidos los ficheros que nunca estuvieron trackeados.

## Una trampa que costó tiempo, por si se repite

Al crear `pre-limpieza` con `git add -A` y volver a `main`, los ficheros que sólo
existían en la rama **desaparecen del árbol de trabajo** — `result_v2` pasó de
40 MB a 2,6 MB sin avisar. No se perdió nada (estaban en el commit), pero la
recuperación es explícita:

```bash
git checkout pre-limpieza -- result_v2
```

## Lo que el renombrado rompió, y cómo se cazó

**Los pickles de los expertos no se rompieron.** Guardan la ruta del paquete donde
se entrenaron, y renombrar el paquete es lo que tumbó la tarea 3 en la V1.1. Aquí
aguantó porque siguen en pie las dos defensas de entonces: `find_class` compara
por el final de la ruta, y `chimera_experts` se registra bajo su nombre histórico.

**El entrypoint sí se rompió**, y ninguna prueba lo vio. El original importaba

    from delete_final_versions_task_V2.verification import inference_v2

con el módulo separado por ` import `. La regla específica de sustitución no casó
y la general lo convirtió en `version_final_reto.runtime_16gb.verification`, que
no existe. **Las 221 pruebas pasaron**, porque ninguna importaba el entrypoint.

Lo cazó la compuerta sin montar código: los tres casos salían con **exit 1 y cero
ficheros en 3–5 segundos**. En Grand Challenge habría sido un envío con todos los
casos a cero. Se buscaron entonces todos los imports del paquete que no resuelven
y aparecieron cuatro; los cuatro están corregidos.

Quedan dos pruebas para que no vuelva a pasar
(`common/tests/test_entrypoint_final.py`): una importa el entrypoint en un
subproceso y comprueba que aplica sus dos sustituciones, y otra recorre todo el
paquete y falla si algún import apunta a un módulo inexistente o a un árbol
retirado.

## Verificación final

| comprobación | resultado |
|---|---|
| Pruebas | **230 pasan** |
| E00 desde las referencias congeladas | reproduce H0: **0,82360** |
| Imports internos que no resuelven | **0** |
| Compuerta, imagen tal cual, sin montar, 4 núcleos | **3/3 exit 0**, 2 ficheros cada una, `fallback: false` |
| Tiempos | 138,8 · 119,4 · 68,5 s de 900 |
| T1 y T2 frente a antes de limpiar (mismo `case_id`) | **idénticos byte a byte** |
| T3 frente a antes de limpiar | mismo evento; meses 29,8388 → 30,8723, que es exactamente el exportador nuevo |

La lección es la misma que la de la V1.1, y conviene tenerla escrita dos veces:
**montar código sobre una imagen comprueba el código, no la entrega.** Sólo la
imagen tal cual encontró el fallo.

## Versiones e imágenes (15 de septiembre de 2026)

Los tarballs pesan 10 GB cada uno y se pueden borrar: los dos se reconstruyen
desde este repositorio. Dentro de cualquier imagen el paquete se llama
**siempre** `version_final_reto`, porque el código importa ese nombre y los
pickles de los expertos guardan su ruta. Lo que cambia es la carpeta de la que
se copia.

| tarball | qué es | se reconstruye con |
|---|---|---|
| `chimera_agent_baseline_v2_2026-09-12_21-45-57.tar.gz` | la **enviada a Test** (rechazada por tiempo) | `version_final_reto_before/imagen_v2_enviada/construir.sh --save` |
| `chimera_agent_baseline_v3_2026-09-15_20-10-54.tar.gz` | V3: supervisor + sombra | ver abajo |
| *(sin tarball)* `chimera_agent_baseline_final` | `version_final_reto` del commit `fb4b6ff`, nunca enviada | ver abajo |

```bash
# V3, la que se envía
CODE_DIR=version_final_reto_send DOCKER_IMAGE_TAG=chimera_agent_baseline_v3 ./do_build_final.sh
./do_fijar_dependencias.sh chimera_agent_baseline_v3 version_final_reto_send/imagen/pip_freeze_imagen_v3.txt
DOCKER_IMAGE_TAG=chimera_agent_baseline_v3 TARBALL_NAME=chimera_agent_baseline_v3_2026-09-15_20-10-54.tar.gz ./do_save_final.sh

# El paquete antes del supervisor
CODE_DIR=version_final_reto_before DOCKER_IMAGE_TAG=chimera_agent_baseline_final ./do_build_final.sh
./do_fijar_dependencias.sh chimera_agent_baseline_final version_final_reto_before/imagen/pip_freeze_imagen_final.txt
```

### Tres cosas que no son obvias

**La v2 enviada no es `version_final_reto_before`.** Se construyó con
`Dockerfile_V2` desde el árbol de antes de la limpieza
(`delete_final_versions_task_V1_1` + `delete_final_versions_task_V2`, entrypoint
`inference_v2.py`). Por eso su kit lleva el `/opt/app` extraído de la propia
imagen, con los `.joblib` que git no guarda, y no depende del resto del repo.
Funcionalmente, `version_final_reto` es ese código renombrado **más el
exportador de T3 de V2_2**: T1 y T2 dan lo mismo, y en T3 cambian los meses
(`UNSEEN-2`: 29,8388 en v2 → 30,8723 en v3, mismo evento).

**vLLM resuelve sus dependencias el día que se construye.** `requirements.txt`
está fijado, pero la imagen del 12-sep y la del 15-sep difieren en 10 versiones
menores (anthropic, openai, grpcio, httpx2, uvicorn, sentry-sdk, uv,
cuda-bindings, httpcore2). `do_fijar_dependencias.sh` compara el `pip freeze` con
el registrado y, si difiere, añade una capa que instala las versiones de aquel día.

**Los datos y los pesos siguen fuera.** `data/task1/` y `model/` (con
`model.tar.gz`) no están en git; el kit v2 lleva su propia copia de `data/task1/`.
Sin `model.tar.gz` no hay entrega, sea cual sea la imagen.

### Cómo se comprobó (15-sep-2026)

Cada imagen reconstruida, frente a su original: hash de cada fichero de
`/opt/app`, `pip freeze` y `Entrypoint`/`Env`.

| reconstrucción | original | `/opt/app` | dependencias | configuración |
|---|---|---|---|---|
| kit v2 | tarball v2 cargado | **650/650 iguales** | iguales tras fijar | igual |
| `CODE_DIR=before` | `chimera_agent_baseline_final` (`33d7d7a648ab`) | **639/639** | iguales tras fijar | igual |
| `CODE_DIR=send` | `chimera_agent_baseline_v3` (`4e725e4fafd0`) | **642/642** | iguales sin fijar | igual |

Y en ejecución, v2 original frente a v2 reconstruida con el mismo `case_id`
(T3): **los dos ficheros byte a byte iguales**
(`verification/gc_profile_20260915_213033_rb_*` y `..._213157_rb_*_rebuild`).
