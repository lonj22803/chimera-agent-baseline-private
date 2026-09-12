# Estructura del repositorio tras la limpieza

**12 de septiembre de 2026.** El repositorio acumulaba seis versiones del agente
y sus árboles de experimentos. En `main` queda sólo lo que hace falta; todo lo
retirado vive íntegro en la rama **`pre-limpieza`**.

## Qué hay y por qué

| Ruta | Qué es | Por qué se queda |
|---|---|---|
| `version_final_reto/` | **La entrega.** Agente de las tres tareas, expertos, entrenamientos, análisis, prompts, pizarras, perfil de 16 GB e investigación | Es lo que se ejecuta y lo que se defiende |
| `result_v2/` | 423 salidas y 423 pizarras de la cobertura completa, con su comparativa | La evidencia de que funciona sobre toda la base |
| `delete/` | Exploración temprana y el notebook de análisis | Pedido explícitamente: puede hacer falta |
| `delete_test/` | Banco de pruebas | Pedido explícitamente |
| `src/`, `inference.py`, `configs/`, `templates/`, `resources/`, `scripts/`, `tests/`, `test/`, `input/`, `output/`, `docs/`, `dev/` | El repositorio base del reto, sin tocar | Es el marco que el reto exige; `inference.py` es el entrypoint oficial |
| `data/`, `model/` | Datos bajo acuerdo de uso y pesos (19 GB) | Nunca estuvieron en git (`.gitignore`) |
| `Dockerfile_final`, `do_build_final.sh`, `do_save_final.sh` | Construcción y empaquetado de la entrega | — |

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
