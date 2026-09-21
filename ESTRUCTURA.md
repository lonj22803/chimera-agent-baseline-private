# Estructura de la rama `ablation_study_final_version`

**21 de septiembre de 2026.** Esta rama parte de `main` (commit `8b3cb70`) y
conserva **sólo la versión final** —`version_final_reto_send_v4`— con los datos y
todo lo que la hace funcionar. Lo demás se retiró; sigue íntegro en `main` y en
`pre-limpieza`.

## Qué hay y por qué

| Ruta | Qué es | Por qué se queda |
|---|---|---|
| `version_final_reto_send_v4/` | **La versión final (V4).** Agente de las tres tareas, expertos, entrenamientos, prompts, pizarras, perfil de 16 GB, supervisor con reloj duro, investigación | Es lo que se ejecuta y lo que se defiende |
| `version_final_reto` → `version_final_reto_send_v4` | Enlace simbólico | Las pruebas, el perfilador y los imports usan este nombre; dentro de la imagen el paquete se llama siempre así |
| `result_v2/` | 423 salidas y 423 pizarras de la cobertura completa | Referencia contra la que comparan `comparativa.py`, `cierre.py` y `cobertura_completa.py` |
| `dev/` | Splits fijos (`dev/splits/`), puntuación local y con juez | Los usan los experimentos de la V4 y `test_paired_judge_protocol.py` |
| `src/`, `inference.py`, `configs/`, `templates/`, `resources/`, `scripts/`, `tests/`, `test/`, `input/`, `output/`, `docs/`, `Makefile`, `pyproject.toml`, `requirements.txt`, `README.md` | El repositorio base del reto | Es el marco que el reto exige; `inference.py` es el entrypoint oficial y `inference_final.py` lo envuelve |
| `Dockerfile_Baseline`, `Dockerfile` (enlace), `Dockerfile_template`, `do_build.sh`, `do_save.sh`, `do_save_existing.sh`, `do_test_run.sh` | Plantilla del reto | Sin tocar |
| `Dockerfile_final`, `do_build_final.sh`, `do_save_final.sh`, `do_fijar_dependencias.sh` | Construcción y empaquetado de la entrega | `CODE_DIR` vale `version_final_reto_send_v4` por defecto |
| `data/`, `model/` | Datos bajo acuerdo de uso y pesos | Están en el árbol de trabajo pero **nunca en git** (`.gitignore`) |

Los 17 expertos entrenados (`.joblib`) viven en `version_final_reto_send_v4/task_*/experts_*/model/`
y tampoco están en git: la regla `model/` los ignora. Sin ellos ni el run local
ni la imagen funcionan.

## Qué se retiró

| Ruta | Ficheros rastreados | Motivo |
|---|---:|---|
| `version_final_reto_before/` | 1 735 | V2 enviada a Test (rechazada por tiempo); su kit de imagen |
| `version_final_reto_send/` | 1 586 | V3; superada por la V4 |
| `delete/` | 37 | Exploración temprana, notebook, orquestador de Codex; la V4 sólo lo cita en documentación |
| `delete_test/` | 1 495 | Banco de pruebas; la V4 no lo usa |
| `ESTRUCTURA.md` (anterior) | — | Describía un árbol que ya no existe |

Lo que sólo existía sin rastrear dentro de esas carpetas eran logs, cachés y
copias exactas de los pesos de la V4 y de `data/task1` (comparadas por hash y
byte a byte); se borraron con ellas.

**Referencias que apuntan a lo retirado.** Los ficheros de evidencia de la V4
`verification/plan_v4_f1_f4_evidence/sha256_outputs.txt` y
`compare_f3_sim300_t3_vs_v3.json`, y dos párrafos de `PLAN_V4.md`, citan salidas
de la V3 en `version_final_reto_send/verification/gc_profile_20260915_*`. Esas
rutas ya no existen en esta rama. Para reverificar la comparación V3↔V4:

```bash
git checkout main -- version_final_reto_send/verification
```

## Volver atrás

```bash
git checkout main                          # el repositorio completo
git checkout main -- <ruta>                # recuperar sólo una parte
```

Ojo, por si se repite: al cambiar de rama, los ficheros que sólo existen en una
rama **desaparecen del árbol de trabajo** (le pasó a `result_v2` con
`pre-limpieza`). Lo ignorado por git (`data/`, `model/`, los `.joblib`) no se
toca al cambiar de rama.

## Construir la imagen

```bash
DOCKER_IMAGE_TAG=chimera_agent_baseline_v4 ./do_build_final.sh
DOCKER_IMAGE_TAG=chimera_agent_baseline_v4 ./do_save_final.sh
```

Dentro de la imagen el paquete se llama **siempre** `version_final_reto`, porque
el código importa ese nombre y los pickles de los expertos guardan su ruta.
Sin `model.tar.gz` no hay entrega, sea cual sea la imagen.
