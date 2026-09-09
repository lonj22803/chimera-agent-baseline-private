# Tres juntas clínicas y un punto de entrada

Este paquete reúne la decisión de biopsia (T1), la decisión de tratamiento (T2)
y el pronóstico posoperatorio (T3). El despacho está implementado; **faltan la
puntuación con juez de T3 y la aceptación del despacho con GPU real**. No se
ha integrado todavía en `inference.py` ni construido el contenedor final.

## Mapa

| Componente | Compartido | Específico |
|---|---|---|
| `common/` | Acta `Board`, guardias, telemetría, metodología de incertidumbre y carga de casos | `gc_entry.py` despacha 1/2/3 |
| [task_1](task_1/README.md) | Anatomía de junta, fuentes y nota clínica | Cuatro expertos, criterio de biopsia previa, grado documentado, biblioteca |
| [task_2](task_2/README.md) | Misma separación entre protocolo, lectura y prosa | Cinco expertos, cascada, réplicas confirmatorias, formulario modal y `clear` |
| [task_3](task_3/README.md) | Acta y guardias sobre la nota | CAPRA-S fija el orden; EXPERT-HORIZON produce meses; censura explícita |

Cada tarea conserva `agent/protocol.py`, `agent/prompts.py`, `agent/decide.py`,
`agent/graph.py`, `agent/run_taskN.py` y sus expertos. No se mezclan los votos
ni se traslada una política de confianza de una tarea a otra.

## Resultados

| Tarea | Cobertura | Baseline sin juez | Entrega sin juez | Baseline con juez | Entrega con juez |
|---|---:|---:|---:|---:|---:|
| 1 | 195/195; 91 etiquetados | 0,6428 | **0,8390** | 0,6378 histórico | **0,8256** trasplante; 0,8368 histórico |
| 2 | 153/153; 72 etiquetados | 0,4457 | **0,7784** | no disponible | **0,8031 / 0,8150** |
| 3 | 75/75 etiquetados | 0,6636 | **0,7372** | 0,7637 | **0,7372** (el ranking de T3 es sólo el c-index; el juez no lo toca — mean_case con juez es 0,6898) |
| OVERALL 2:2:1 | 423/423 salidas | **0,5651** histórico | **0,7944** | no disponible | **0,799 – 0,808** |

Los rankings sin juez se leen de los tres `task_N/runs/score_no_judge.json`:
`(2·0,8390295553 + 2·0,7783863062 + 0,7371681416)/5 = 0,7943999729`.
El 0,5651 es la referencia inicial del plan, no una nueva corrida conjunta.

**El OVERALL con juez es un RANGO, no un número**, porque el juez no es
determinista ni dentro de una misma carga del modelo (medido: dos corridas
consecutivas de task2 sin recargar dieron 0,8031 y 0,8150; task1 dio 0,8368 en
su primera medición y 0,8256 al repetirla horas después). Combinando las
cuatro combinaciones posibles de esos dos valores con el `ranking_score` fijo
de task3 (0,7372, no afectado por el juez) el OVERALL con juez cae entre
**0,799 y 0,808**. Publicar un solo decimal aquí sería falsa precisión.
T2 conserva la anomalía histórica `tool_score=0` del baseline (su referencia
práctica rondaba 0,47); no se omite esta limitación.

En T3 se publican **juntos** ranking 0,7371681416 y `mean_case_score` sin juez
0,7636741685 (event 0,7733333333; time 0,7540150037). El juez pesa 0,30 en
la media por caso y juzga los 75; no altera el ranking, que es sólo c-index.
La constante 60 meses obtiene media sin juez 0,7528 y ranking 0,5000.

Como cálculo descriptivo usando el ranking invariante de T3, el agregado de
los pases con juez disponibles sería **0,7989 / 0,8037** (T1=0,8256114202,
T2=0,8031 / 0,8150334260). No es una corrida conjunta ni prueba de que el
juez de T3 haya terminado. Los JSON persistidos de T1/T2 están en
`task_N/runs/judge/entrega.json`; el primer pase T2 se conserva en el HANDOFF.

El juez varía incluso sin recargar el modelo: los dos pases T2 consecutivos
son mediciones igualmente válidas. No se selecciona uno como «el correcto».
El trasplante T1 conserva sus componentes deterministas y 83/91 decisiones;
la variación con juez (0,8368 histórico frente a 0,8256) no demuestra regresión.
Los expertos T1/T2 de entrega se ajustaron sobre la cohorte etiquetada; T3
reproduce predicciones OOF. Ninguna de estas cifras es validación externa.

La compuerta honesta de confianza (`nested_stratified_cv_10x9`) adopta
`agreement` en T1: 0,7582 frente a 0,7363 constante. En T2 conserva `clear`
(0,9028 frente a 0,4306 agreement y 0,3611 por peldaño). El mecanismo
`confidence_from_rung` no gana en ninguna tarea y no se adopta.

## Cómo se fusionan en un agente

[common/gc_entry.py](common/gc_entry.py) proporciona:

```python
from delete_final_versions_task.common.gc_entry import dispatch

status = dispatch(
    task=2,
    structured_prompt="/input/structured-prompt.json",
    clinical_data="/input/prostate-treatment-decision-clinical-data.json",
    neural_representations="/input/prostate-modality-level-neural-representations.json",
    output_path="/output",
    embedding_model_dir="/opt/ml/model/embedding_model",
)
```

También acepta diccionarios ya leídos. `run_task1_case`, `run_task2_case` y
`run_task3_case` son envoltorios de dispatch. El adaptador monta
`/tmp/chimera-*/taskN/agent_input/<case_id>/`, conserva `/input` sin escribir,
y llama a `run_case` del runner de la tarea. Esa función invoca el grafo existente
y sus expertos, sin una segunda implementación de la lógica clínica.

T1/T2 arrancan MCP con el registro `task1`/`task2`. Upstream ya define los tres
registros `TASK1_TOOLS`, `TASK2_TOOLS`, `TASK3_TOOLS`. T3 mantiene la lectura
directa de `Case.clinical` de su runner: no se inventa una dependencia MCP.
Para T3 en el contenedor el presidente usa el modelo local; el runner de la
cohorte usa Ollama. Esta adaptación de backend exige validación real con GPU.

Los modelos son rutas locales absolutas. Fijar
`CHIMERA_MODEL_DIR=/opt/ml/model/gemma-4-E2B-it`; las bibliotecas Hugging Face
se ponen en modo offline y no se admite sustituir pesos ausentes por descargas.
El servicio de embeddings se detiene en `finally`. La vida del modelo queda
ligada al proceso: **un caso, un arranque de contenedor**, no un servidor para
varios pacientes en este adaptador.

El contrato se valida contra Task1Output/Task2Output/Task3Output y se escriben
los dos JSON del reto. Los fallos del backend activan el respaldo del runner:
T1 criterio estructurado, T2 regla por grado y T3 horizonte del experto con nota
determinista. Si incluso faltan los artefactos T3, el último recurso son 60 meses,
event=0 y una nota que declara que no es una predicción individual. Se registra
el fallo en stderr; retorno 0 significa archivos escritos, no éxito del LLM.
Una tarea desconocida o un destino no escribible se consideran errores del llamador.

**Integración documentada, todavía no aplicada:** en `inference.py`, los cuerpos
de `interf0_handler`, `interf1_handler` e `interf2_handler` deben llamar a
`dispatch(task=1/2/3, ...)` con los tres sockets de entrada y OUTPUT_PATH.
Conservar el arranque por paciente y pasar las rutas locales de los modelos.
No hay cambios upstream en esta entrega.

## Lista de empaquetado pendiente

- Copiar `delete_final_versions_task/` en el Dockerfile e incluir su raíz en
  PYTHONPATH, junto con `src/`. El Dockerfile actual no copia el paquete ni sus expertos.
- Empaquetar todos los `.joblib` de T1/T2/T3 y proyectores, cachés e informes que
  sus lectores consultan. Preservar el layout de cada tarea; los informes T3
  también contienen nombres y bloques necesarios para alinear variables.
- Fijar **scikit-learn==1.9.0**, y versiones compatibles de `scipy` y `joblib`
  con el entorno que serializó los artefactos. Validar carga en la imagen final.
- Incluir en el tarball del modelo los pesos del LLM y embeddings, artefactos
  entrenados y casos etiquetados que la biblioteca T1 consulta en runtime.
  Dar acceso en el layout esperado `data/task1`; excluir los casos del paciente
  actual de la biblioteca. No incluir al evaluador oficial como dependencia runtime.
- Copiar templates, recursos de guías y sus índices locales. Revisar rutas
  absolutas y recursos escribibles del servicio antes de bloquear la red.
- Integrar los tres handlers según el apartado anterior.
- Ejecutar **`./do_test_run.sh` con la GPU entera libre**, un caso de cada tarea
  desde sockets hasta ambos JSON, y un fallo forzado. Medir tiempo y memoria.

## Tiempo por caso y aceptación

Presupuesto histórico orientativo: carga del modelo ~90 s, embeddings ~30 s,
junta ~25–30 s: **2–3 minutos**; añadir **30–80 s** si el panel no está cacheado
(como ocurre en test). Es una estimación de la arquitectura previa, no una
medición del nuevo dispatch. Contrastar con el límite real del reto; T3 tiene
otro recorrido y tampoco debe heredar ese tiempo como si estuviera medido.

```bash
./delete/run_tests.sh
PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.task_2.analysis.accept_run
PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.task_3.analysis.accept_run
```

Las pruebas de `common/tests/test_gc_entry.py` validan staging, lectura por los
stores reales, serialización, limpieza temporal y fallos forzados. Sustituyen
explícitamente el backend GPU: **no satisfacen la aceptación end-to-end con LLM
real de 7.1**. Las auditorías de corrida verifican los artefactos e incluyen hashes.
El estado detallado y los pendientes se conservan en [HANDOFF](../delete/HANDOFF.md).

Última verificación: **202 passed**, siete suites (92+62+22+4+4+7+11),
registrada en [verification_final_suites.log](../delete/verification_final_suites.log).
