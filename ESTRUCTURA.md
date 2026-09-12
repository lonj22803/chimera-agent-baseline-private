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

## Lo que el renombrado podía romper, y no rompió

Los expertos viajan como pickles que guardan la **ruta del paquete** donde se
entrenaron. Renombrar el paquete es exactamente lo que tumbó la tarea 3 en la
V1.1. Aquí no pasó porque las dos defensas que se añadieron entonces siguen en
pie y se comprobaron después del renombrado:

- `ModelReader.find_class` compara **por el final de la ruta**, no por el nombre
  exacto del paquete.
- `common/chimera_experts/__init__.py` registra el nombre histórico en
  `sys.modules`.

Las 221 pruebas pasan, E00 reproduce H0 (0,82360) desde las referencias
congeladas, y la imagen se reconstruye y pasa su compuerta.
