He terminado la contextualización y he medido las dos cosas que faltaban para poder planificar la tarea 3. Aquí está el plan.

---

# Estado real y los cuatro hechos que fijan el plan

**Lo que ya está hecho y no hay que rehacer:**
- `delete_solution_one/solution_task_one_using_experts_final/` — tarea 1 cerrada: **0,8390** sin juez, **0,8368 / rationale 0,8012** con juez, 195/195 entregados. Cuatro expertos entrenados, 15 intervenciones, protocolo determinista, guardias.
- `delete_expert_modelate/task_two/` — **cinco expertos ya entrenados y medidos** (LOO, informes en `train/artifacts/*.json`). No hay que entrenarlos; hay que revisarlos y empaquetarlos.
- `delete_expert_modelate/task_three/` — **un README de una línea**. Todo por diseñar.
- `delete_final_versions_task/task_{1,2,3}/` — **los tres directorios están vacíos**.

**Cuatro hechos medidos que condicionan el diseño:**

1. **`variable_weight_score` recorre sólo las claves del ground truth** (`evaluate.py:736`), pero `important_decisive_factor_score` es un **F1 de conjuntos** sobre las claves que *tú* emites. Marcar `important` de más es gratis en el componente de 0,25 y caro en el de 0,15. Eso convierte la selección de variables importantes en un problema de **maximización de F1 esperado sobre un conjunto**, no de umbralizar once casillas por separado. Nadie lo está explotando.

2. **En la tarea 3, `ranking_score` es sólo el c-index**, y el c-index sólo compara `preds[i] < preds[j]`: es **invariante a cualquier transformación monótona creciente**. `time_score` sí depende de la magnitud. Son **separables**: se ajusta primero el orden (c-index) y después un mapa monótono riesgo→meses (time_score), y el segundo **no puede dañar al primero**. Es la palanca de diseño más importante de la tarea 3 y no está en ningún documento tuyo.

3. **CAPRA-S es calculable en 75/75 casos de la tarea 3** con expresiones regulares sobre `surgical_pathology_report` + el PSA del `structured-prompt`. Sus seis variables (PSA, Gleason patológico, márgenes, EPE, invasión de vesículas, ganglios) están **todas presentes**. Medido hoy sobre los 75:

   | | c-index |
   |---|---|
   | baseline actual | 0,6636 |
   | CAPRA-S crudo, sin ajustar nada | **0,7372** |
   | CAPRA-S + 8 PCs del embedding de prostatectomía, OOF, PCA dentro del pliegue | **0,8319 ± 0,0055** |
   | embedding de prostatectomía solo | 0,7359 |
   | embedding de RM solo | 0,5124 |
   | constante 60 meses | 0,5000 |

   Es el mismo patrón que en las otras dos tareas: **existe un suelo de guía que el baseline no alcanza**. Aviso honesto: el nº de componentes (4/8/16) se eligió mirando estos mismos 75 casos y el riesgo se modela como P(evento) con logística, ignorando la censura. Hay que rehacerlo con Cox y anidado antes de publicarlo.

4. `dev/score_with_judge.py` está **cableado a la tarea 1** (`task1/`, `CLINICAL` constante, `evaluate_case`). La tarea 3 necesita `evaluate_recurrence_case` + `aggregate_recurrence_metrics`, que son funciones distintas del evaluador.

---

# La metodología de incertidumbre, confianza y pesos — [PLAN]

Esto es lo que me pediste diseñar y es el núcleo del README de `task_1`. Lo dejo cerrado aquí para que los pasos de ejecución lo implementen sin inventar.

## Principio rector

> **Cada número del formulario tiene un estimador distinto, un objetivo distinto y una validación distinta. Confundirlos es lo que hace que el baseline escriba «prior positive biopsy» mientras marca `bx: not_used`.**

## A. La confianza no la produce el modelo: la produce el peldaño que decidió

El sistema actual saca `confidence` de una política de acuerdo entre expertos. Es razonable pero no está fundamentado. La propuesta:

**A.1 — Descomposición de la varianza.** Tres términos ya existen en `chimera_experts/uncertainty.py`:

- `σ²_model` — dispersión entre miembros del ensemble (Lakshminarayanan 2017)
- `σ²_missing` — varianza *entre imputaciones*, término *between* de las reglas de Rubin (1987)
- `H` — entropía normalizada, aleatoria (Depeweg 2018)

Falta un cuarto que el sistema ya usa sin nombrarlo:

- `σ²_panel` — **varianza entre expertos**. La junta es un conjunto de modelos de la misma cantidad; la dispersión entre ellos es epistémica legítima y se suma en cuadratura con las otras dos.

$$\sigma^2_{\text{epist}} = \sigma^2_{\text{model}} + \sigma^2_{\text{missing}} + \sigma^2_{\text{panel}} \qquad H \text{ se reporta aparte, nunca se suma}$$

**A.2 — La confianza es función del peldaño, no de la probabilidad.** Cada peldaño de la cascada tiene un acierto medido y escrito (24/24, 16/18, 7/8, 3/4, voto ponderado ≈0,64 en el cubo duro). Regla:

$$\texttt{confidence} = f(\text{peldaño que disparó},\ \sigma_{\text{epist}})$$

con un **techo por peldaño**: un peldaño cuyo acierto out-of-fold está por debajo de 0,75 **no puede emitir `clear` nunca**, por mucho que los clasificadores estén de acuerdo. Un peldaño 24/24 emite `clear` aunque el panel discrepe. Esto es Chow (1970) aplicado al camino de decisión en vez de a la probabilidad: la decisión de cubrirse es función del riesgo medido *en el punto de operación*, y el punto de operación aquí es el peldaño.

**A.3 — Se valida con dos números, no con uno.**
- `confidence_score` contra el urólogo (lo que puntúa el reto).
- **La escalera de fiabilidad**: acierto dentro de cada tramo declarado, out-of-fold. Una etiqueta de confianza que no estratifica el acierto es decoración. Si no es monótona, se publica igualmente y se dice.

En la tarea 2 esto tiene una respuesta ya medida e incómoda: la **constante `clear` puntúa 0,9028 y ningún modelo la bate**. La metodología obliga a publicar la constante y a decir por qué — no a inventar variación que no existe.

## B. Tres nociones de «importancia», y sólo una se entrega

El README de la tarea 1 ya detectó el conflicto sin nombrarlo. Nombrarlo:

| noción | qué mide | de dónde sale | papel |
|---|---|---|---|
| **atributiva** | cuánto movió *la predicción de este modelo* en *este caso* | importancia de permutación OOF, atribución local | lo que declara cada experto en `vocab.py` |
| **normativa** | qué dice la guía que debe decidir | EAU/NCCN: PI-RADS en T1, ISUP en T2, componentes de CAPRA-S en T3 | determinista, del peldaño que disparó |
| **conductual** | qué marcó *el urólogo* | EXPERT-TRACE / `reasoning_task2`, entrenados contra las trazas | **lo único que el evaluador puntúa** |

**Regla de entrega: se entrega la conductual. Las otras dos son la auditoría.** Está medido: promover pesos por acuerdo del panel *baja* la nota (0,8390 → 0,8365). La divergencia entre las tres se publica en la tabla de variables de la sala y alimenta el razonamiento, no el formulario.

**B.2 — Arbitraje por casilla contra la moda, out-of-fold.** El informe `reasoning_task2_report.json` ya tiene exactamente la forma correcta: por cada casilla, `loo` vs `moda` y una bandera `aprendido`. Con 72-91 casos y 11 casillas × 4 niveles, **la moda gana en 10 de 12 casillas**. La metodología es: *aprende la casilla sólo donde aprender bate a la constante fuera de muestra; publica qué casillas son aprendidas y cuáles constantes.* Es selección de modelo por casilla, y es honesta porque se declara.

**B.3 — El conjunto importante se elige por F1 esperado, no casilla a casilla.** `important_decisive_factor_score` es un F1 de conjuntos. Dada la posterior por casilla $p_v = P(v \in \text{importante})$, el conjunto $S$ que maximiza el F1 esperado **no** es $\{v : p_v > 0{,}5\}$: para F1 el umbral óptimo depende de la cardinalidad esperada del conjunto verdadero. Se resuelve ordenando por $p_v$ y evaluando los $|V|+1$ conjuntos anidados bajo la posterior (Ye et al. 2012). Coste: once evaluaciones por caso. Es la palanca de 0,15 que hoy nadie toca.

## C. Las dos restricciones duras y la dual

- **Aterrizaje (duro).** Variable cuya sección no se reveló → no puede superar `not_used`. Ya implementado en `decide.enforce_grounding`; se formaliza como proyección sobre el conjunto factible.
- **Coherencia (duro).** Variable nombrada en el texto libre → mínimo `noted`. Variable en `decisive` → tiene que ser la que usó el peldaño que disparó. Mata la familia de fallo del baseline.
- **La dual.** El plan de revelación y los pesos son **el mismo problema**: revela exactamente las secciones que aterrizan las variables que vas a pesar. Se resuelven juntos, no en secuencia.

**Aviso medido que la metodología debe respetar** ([[chimera-task2-trampa-scoring]]): silenciar casillas para subir el grounding gana **sin** juez (0,7896 vs 0,7347) y **pierde con juez** (0,7340 vs 0,7696), porque apagar el juez redistribuye el grounding de 0,05 a 0,175. **La política se elige con el juez encendido, que es como puntúa el leaderboard.**

---

# El andamiaje de `delete_final_versions_task/`

```
delete_final_versions_task/
├── README.md                    el mapa: tres tareas, qué comparten, cómo se fusionan
├── common/                      ← el núcleo COPIADO (nada importa de fuera del directorio)
│   ├── board.py  roster.py  telemetry.py  sampling.py  guards.py
│   ├── vocab.py                 vocabulario del formulario, por tarea
│   ├── uncertainty_forms.py     ← LA METODOLOGÍA (A/B/C de arriba)
│   ├── chimera_experts/         copia del paquete de features y modelos
│   └── gc_entry.py              despacho por tarea = el agente único del futuro
├── task_1/  README.md  experts_1/  agent/  analysis/  runs/{labeled,unlabeled,judge}/
├── task_2/  ídem
└── task_3/  ídem
```

`common/` es la costura del agente único: **un** acta, **un** roster, **un** juego de guardias, **una** metodología de incertidumbre; y tres `protocol.py` + tres `prompts.py`. `gc_entry.dispatch(task, ...)` es el punto de entrada que después llaman los tres `interfN_handler` de `inference.py`.

---

# Los pasos

## FASE 0 — Andamiaje y herramienta de medida

### 0.1 [EJECUCIÓN] Crear `common/` autocontenido

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

OBJETIVO
Crear delete_final_versions_task/common/ como un paquete Python autocontenido y
borrable: nada dentro de delete_final_versions_task/ puede importar de
delete_solution_one/ ni de delete_expert_modelate/. Sí puede importar de
src/chimera_agent_baseline/ (el baseline upstream), que no se toca.

QUÉ COPIAR (copia literal, luego reescribe imports)
  delete_solution_one/solution_task_one_using_experts_final/board.py      -> common/board.py
  .../roster.py       -> common/roster.py
  .../telemetry.py    -> common/telemetry.py
  .../sampling.py     -> common/sampling.py
  .../experts/vocab.py-> common/vocab.py
  delete_expert_modelate/chimera_experts/  -> common/chimera_experts/   (paquete entero)

QUÉ EXTRAER (no copiar entero)
  De .../decide.py, mover a common/guards.py SÓLO las funciones agnósticas de tarea:
  process_language, unsourced_values, unsourced_grades, enforce_grounding,
  validate_output. Lo que dependa de las variables de la tarea 1 (VARIABLES,
  _SECTION_OF) se parametriza por argumento, no se hardcodea. Deja en
  task_1/agent/decide.py lo específico de la tarea 1 (documented_grade, el parser
  de Gleason, la nota determinista).

CONTRATOS
- common/vocab.py debe pasar de una lista global VARIABLES a un dict
  VARIABLES_BY_TASK = {1: [...], 2: [...], 3: []}, tomando las listas EXACTAS de
  src/chimera_agent_baseline/output/schema.py (TASK1_VARIABLES, TASK2_VARIABLES).
  Task 3 no tiene variable_weights: la lista es vacía y las funciones deben
  tolerarlo sin ramificar.
- common/guards.py: firma pública estable
    enforce_grounding(weights: dict, opened: list[str], section_of: dict) -> tuple[dict, list[str]]
    validate_output(task: int, payload: dict) -> tuple[bool, str]
  validate_output importa Task1Output/Task2Output/Task3Output de
  chimera_agent_baseline.output.schema. Ese fichero es INTOCABLE.
- Añade delete_final_versions_task/__init__.py y common/__init__.py.

ACEPTACIÓN
1. `grep -rn "delete_solution_one\|delete_expert_modelate" delete_final_versions_task/`
   no devuelve nada.
2. `PYTHONPATH=src:. .venv/bin/python -c "from delete_final_versions_task.common import board, roster, guards, vocab, telemetry, sampling; from delete_final_versions_task.common import chimera_experts"`
   funciona.
3. `PYTHONPATH=src:. .venv/bin/python -m pytest tests/ -q` sigue en verde
   (no has tocado nada de src/).

NO HAGAS
- No modifiques src/, configs/, templates/, ni delete_solution_one/, ni
  delete_expert_modelate/. Este paso es sólo copiar y desenganchar imports.
- No reescribas la lógica de ninguna función copiada. Copia y ajusta imports.
```

### 0.2 [EJECUCIÓN] Generalizar `dev/score_with_judge.py` a las tres tareas

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline
Fichero: dev/score_with_judge.py  (hoy cableado a la tarea 1)

OBJETIVO
Que acepte --task {1,2,3} manteniendo el comportamiento actual EXACTO para --task 1
(hoy es el default implícito y hay resultados publicados contra él: ranking 0.8368,
rationale 0.8012 — tienen que reproducirse bit a bit).

CAMBIOS
1. Añade --task (int, default 1). Deriva de él:
   - data_root  = REPO/"data"/f"task{task}"        (si no se pasa --data-root)
   - output_dir = Path(output_root)/f"task{task}"
   - CLINICAL: {1:"prostate-biopsy-decision-clinical-data.json",
                2:"prostate-treatment-decision-clinical-data.json",
                3:"prostate-time-to-recurrence-or-last-follow-up-clinical-data.json"}
   - DECISION / REASONING: los nombres de fichero del reto por tarea; míralos en
     src/chimera_agent_baseline/run.py::_write_task_outputs (líneas 110-152).
2. load_predictions: parametrizar por tarea.
   - task 1: rec["biopsy_decision"] = json del fichero de decisión (bool/"yes"/"no")
   - task 2: rec["action"] = la cadena del fichero de decisión
   - task 3: el fichero de decisión es {"event": int, "months_to_recurrence": float};
     vuélcalo con rec.update(...). El -reasoning.json de la tarea 3 es UNA CADENA
     SUELTA, no un objeto: ponla en rec["free_text"].
3. Agregación: la tarea 3 NO usa evaluate_case ni compute_aggregate_metrics.
   Usa ev.evaluate_recurrence_case(gt, pred, judge) y
   ev.aggregate_recurrence_metrics(rows). Verifícalo en
   ~/PycharmProjects/CHIMERA-agent-eval/evaluation/evaluate.py (líneas 1391 y 1595).
4. El bloque de impresión de componentes es de tareas 1/2. Para la tarea 3 imprime:
   ranking_score (= concordance_index), mean_case_score, mean_event_score,
   mean_time_score, event1_time_mae_months, time_dependent_auc, mean_rationale_score.
5. ev.load_ground_truth_records(data_root/"ground_truth", f"task{task}") ya soporta
   las tres; no lo reimplementes.

ACEPTACIÓN
  .venv-eval/bin/python dev/score_with_judge.py --task 1 \
    --output-root delete_solution_one/solution_task_one_using_experts_final/runs/final/output
reproduce ranking_score 0.8368 y mean rationale_score 0.8012 (±0.01 por la varianza
del juez). --task 2 y --task 3 corren sin excepción sobre un directorio de salida vacío
y reportan 0 casos.

NO HAGAS
- No toques dev/score_local.py.
- No cambies el default del juez ni las variables de entorno del módulo.
```

---

## FASE 1 — La metodología, implementada y medida

### 1.1 [EJECUCIÓN] `common/uncertainty_forms.py`

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline
Fichero nuevo: delete_final_versions_task/common/uncertainty_forms.py

CONTEXTO
Implementa una metodología ya diseñada para rellenar los campos del formulario de
CHIMERA (confidence, variable_weights, reveal_sequence) con fundamento medible.
El módulo NO decide la clase; sólo produce los campos que la acompañan.
Lee antes delete_final_versions_task/common/chimera_experts/uncertainty.py, que ya
tiene rubin_pool, ladder, completeness_score, brier_score,
expected_calibration_error, ladder_table, y REUTILÍZALO en vez de reimplementarlo.

API PÚBLICA (exacta)

  @dataclass
  class VarianceBudget:
      model: float        # sigma^2 entre miembros del ensemble
      missing: float      # sigma^2 entre imputaciones (termino between de Rubin)
      panel: float        # sigma^2 entre expertos del panel
      aleatoric: float    # entropia normalizada; NO se suma a las otras tres
      @property
      def epistemic(self) -> float:   # sqrt(model + missing + panel)

  def pool_variance(expert_verdicts: list[dict]) -> VarianceBudget
      # Cada verdict trae p, epistemic_model, epistemic_missing, aleatoric
      # (formato de chimera_experts.uncertainty.Verdict.to_dict()).
      # panel = varianza muestral de las p disponibles. Expertos ausentes o
      # abstenidos no cuentan y reducen n; con n<2, panel = 0.0.

  RUNG_CEILING: dict[str, str]      # peldaño -> confianza maxima que puede emitir
  def confidence_from_rung(rung: str, budget: VarianceBudget,
                           rung_accuracy: dict[str, float],
                           *, clear_min_acc: float = 0.75) -> tuple[str, str]
      # Devuelve (confidence, motivo en una frase). Regla:
      #   1. techo por peldaño: rung_accuracy[rung] < clear_min_acc  ->  nunca 'clear'
      #   2. dentro del techo, baja un escalon si budget.epistemic supera el
      #      cuantil 0.66 de la cohorte (parametro cohort_sigma_q66)
      # El motivo es texto para el acta, en palabras clinicas, sin nombrar el mecanismo.

  def arbitrate_cells(learned: dict[str,str], mode: dict[str,str],
                      cell_report: dict[str,dict]) -> tuple[dict[str,str], dict[str,bool]]
      # Por casilla: usa 'learned' solo si cell_report[var]["loo"] > cell_report[var]["moda"];
      # si no, la moda. Devuelve (pesos, mapa var->aprendida). El formato de
      # cell_report es el de delete_expert_modelate/task_two/train/artifacts/
      # reasoning_task2_report.json ("cells": [{campo, loo, moda, moda_valor, aprendido}]).

  def expected_f1_set(posterior: dict[str, float]) -> set[str]
      # Maximiza el F1 ESPERADO del conjunto important/decisive bajo la posterior
      # por casilla, asumiendo independencia. Ordena por p descendente y evalua los
      # |V|+1 conjuntos anidados; devuelve el argmax. Referencia: Ye et al. 2012,
      # "Optimizing F-measure: A Tale of Two Approaches", ICML.
      # IMPORTANTE, verificado en el evaluador:
      #   - variable_weight_score recorre SOLO las claves del ground truth
      #     (evaluate.py:736) -> emitir claves de mas es gratis ahi;
      #   - important_decisive_factor_score es un F1 de CONJUNTOS sobre las claves
      #     que emites (evaluate.py:772) -> emitir 'important' de mas SI cuesta.
      #   Esa asimetria es justo lo que esta funcion explota.

  def project_feasible(weights: dict[str,str], opened: list[str],
                       section_of: dict[str,str], named_in_text: set[str],
                       decisive_var: str | None) -> tuple[dict[str,str], list[str]]
      # Las dos restricciones duras, aplicadas como proyeccion:
      #   aterrizaje: seccion no abierta -> not_used
      #   coherencia: variable nombrada en el texto libre -> minimo 'noted';
      #               si decisive_var no es None, es la UNICA que puede ser 'decisive'
      # Devuelve (pesos corregidos, lista de correcciones en texto para el acta).

REQUISITOS
- Sin dependencias nuevas: numpy y stdlib. Nada de scipy si se puede evitar.
- Docstring de modulo en castellano explicando por que las tres varianzas
  epistemicas se suman en cuadratura y la aleatoria no (el argumento ya esta en
  chimera_experts/uncertainty.py; cita a Rubin 1987 y Depeweg 2018).
- Todas las funciones puras y deterministas.

TESTS (fichero nuevo delete_final_versions_task/common/tests/test_uncertainty_forms.py)
- pool_variance con 1 experto -> panel == 0.0
- confidence_from_rung: un peldaño con acierto 1.0 devuelve 'clear' aunque
  budget.epistemic sea alto; uno con acierto 0.64 nunca devuelve 'clear'
- expected_f1_set: con posterior {a:0.9,b:0.8,c:0.1} devuelve {a,b}; con todas a
  0.3 devuelve el conjunto que maximiza el F1 esperado (comprueba a mano que no es
  el conjunto vacio cuando la cardinalidad esperada es >=1)
- project_feasible: pirads='decisive' con radiology_report sin abrir -> 'not_used'
  y una linea de correccion

ACEPTACIÓN
  PYTHONPATH=src:. .venv/bin/python -m pytest delete_final_versions_task/common/tests -q
```

### 1.2 [EJECUCIÓN] Medir la metodología antes de adoptarla

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline
Fichero nuevo: delete_final_versions_task/common/analysis/measure_forms.py

OBJETIVO
Decidir CON DATOS si cada pieza de uncertainty_forms.py entra o no. Nada se adopta
sin batir lo que ya hay. Escribe delete_final_versions_task/common/analysis/
forms_report.json y una tabla por stdout.

QUÉ MEDIR, out-of-fold (leave-one-out), sobre los 91 etiquetados de task1 y los 72
de task2, usando el evaluador oficial de ~/PycharmProjects/CHIMERA-agent-eval/evaluation:

 A. confidence
    - constante 'clear'                                    (linea base task2: 0.9028)
    - politica actual de task1 ('agreement' en protocol.py) (linea base task1: 0.7651)
    - confidence_from_rung con los aciertos por peldaño reales
    Metricas: confidence_score del evaluador + escalera de fiabilidad (acierto de
    decision dentro de cada tramo declarado). Publica las dos.

 B. variable_weights
    - moda por casilla
    - modelo aprendido entero (EXPERT-TRACE en task1, reasoning_task2 en task2)
    - arbitrate_cells (por casilla, el que gane OOF)
    Metricas: variable_weight_score y important_decisive_factor_score, por separado.

 C. conjunto important/decisive
    - umbral 0.5 por casilla
    - expected_f1_set sobre la misma posterior
    Metrica: important_decisive_factor_score. Este es el contraste clave del paso.

REGLAS DE MEDIDA (no negociables)
- LOO: la posterior de un caso no puede haberse ajustado con ese caso.
- Prueba de signos por caso para cada comparacion, y publica n_sube/n_baja/p.
- Publica el suelo (la constante) en cada tabla. Un metodo que no bate a la
  constante se reporta como no adoptado, no se esconde.

SALIDA
forms_report.json con, por tarea y por politica: la metrica, el delta contra la
linea base, n_sube/n_baja/p, y un campo "adoptar": true/false con el motivo en una
frase. Ese fichero es la fuente del README; que sea legible.

NO HAGAS
- No cambies ninguna solucion existente todavia. Este paso solo mide.
```

---

## FASE 2 — Tarea 1 a versión final

### 2.1 [EJECUCIÓN] Trasplante a `task_1/`

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

OBJETIVO
Llevar delete_solution_one/solution_task_one_using_experts_final/ a
delete_final_versions_task/task_1/ dejandola INDEPENDIENTE: si se borra
delete_solution_one/ y delete_expert_modelate/, task_1 sigue corriendo.

DESTINO
  task_1/agent/{graph.py, prompts.py, protocol.py, decide.py, run_task1.py}
  task_1/experts_1/{cohort.py, fusion.py, image.py, library.py, panel.py, psa.py,
                    structured.py, trace.py}
  task_1/experts_1/model/   <- los .joblib de delete_expert_modelate/task_one/
                               expert_{one,two,three}/model/ y el reasoning_model
  task_1/artifacts/panel_cache.json
  task_1/analysis/{report.py, simulate.py, _build_notebook.py, _build_anatomia.py,
                   _run_notebook.py, *.ipynb}
  task_1/PROMPTS.md
  task_1/runs/launch.sh

REESCRITURA DE IMPORTS
- experts/vocab.py YA ESTA en common/vocab.py (paso 0.1): borra la copia local y
  importa de ahi. Ojo: common/vocab.py usa VARIABLES_BY_TASK[1], no VARIABLES.
- Las guardias agnosticas viven en common/guards.py: task_1/agent/decide.py se queda
  solo con lo especifico de la tarea 1 (documented_grade, el parser Gleason->ISUP,
  la nota determinista, process_language con su lista curada de patrones).
- board/roster/telemetry/sampling: importar de common/.
- panel.py deserializa joblib que fueron guardados con clases de chimera_experts:
  esas clases estan ahora en common/chimera_experts/. Comprueba que joblib.load
  funciona; si el pickle guarda la ruta de modulo antigua, arreglalo con un alias
  en common/chimera_experts/__init__.py (sys.modules["chimera_experts"] = este
  paquete) ANTES de cargar. Documenta el alias con un comentario.

RUTAS DE DATOS
Todas las rutas a data/ y a artefactos deben salir de una constante unica en
task_1/agent/paths.py, no dispersas por el codigo. La biblioteca de precedentes lee
los 91 etiquetados en runtime: deja esa ruta tambien ahi.

ACEPTACIÓN
1. grep -rn "delete_solution_one\|delete_expert_modelate" delete_final_versions_task/
   sigue sin devolver nada.
2. PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.task_1.analysis.simulate
   reproduce ranking_score 0.8390 EXACTO (la simulacion es determinista y sin LLM;
   si sale otro numero, algo se rompio en el trasplante — no lo justifiques,
   arreglalo).
3. --self-match reproduce 0.9469 y la configuracion honesta 0.7607.

NO HAGAS
- No mejores nada. Este paso es un trasplante que tiene que reproducir tres numeros
  publicados. Cualquier cambio de comportamiento es un fallo del paso.
```

### 2.2 [EJECUCIÓN] Corrida etiquetados / no etiquetados por separado + puntuación

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

OBJETIVO
Correr la tarea 1 trasplantada sobre los 195 casos, con los etiquetados y los no
etiquetados en carpetas separadas, y puntuar con el evaluador oficial en los dos
modos (sin juez y con juez).

CORRIDA
- task_1/agent/run_task1.py necesita una opcion --split {labeled,unlabeled,all}
  que lea data/task1/ground_truth/ para saber cuales son cuales (91 etiquetados,
  104 sin etiqueta).
- Salidas:
    task_1/runs/labeled/output/task1/<case>/    (91)
    task_1/runs/unlabeled/output/task1/<case>/  (104)
  Mismo formato que runs/final actual: los dos JSON del reto + acta JSON + acta MD
  + summary.jsonl + telemetry.jsonl.
- Lanzalo con task_1/runs/launch.sh en tmux. Son ~30 s/caso: 195 casos ~100 min.
  Temperatura 0.

PUNTUACIÓN (los cuatro numeros)
  .venv/bin/python dev/score_local.py --tasks 1 --count-missing \
    --output-root delete_final_versions_task/task_1/runs/labeled/output \
    --json-out delete_final_versions_task/task_1/runs/score_no_judge.json

  .venv-eval/bin/python dev/score_with_judge.py --task 1 \
    --output-root delete_final_versions_task/task_1/runs/labeled/output \
    --json-out delete_final_versions_task/task_1/runs/judge/entrega.json
  (necesita Ollama con gemma4:e4b levantado; ~8 s/caso, 12 min los 91)

ACEPTACIÓN
- 195/195 casos con salida, 195/195 validan contra Task1Output.
- sin juez: ranking_score 0.8390 +- 0.01
- con juez: ranking_score 0.8368 +- 0.01 y rationale_score 0.8012 +- 0.02
- 0 notas que nombren un participante de la junta (comprueba con
  decide.process_language sobre los 195 free_text entregados)
- 0 grados de biopsia sin documento (decide.unsourced_grades sobre los 195)
Si alguno de estos cinco falla, PARA y reporta cual y en que casos. No ajustes
parametros para que salga el numero.
```

### 2.3 [EJECUCIÓN] El README de `task_1`

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline
Fichero nuevo: delete_final_versions_task/task_1/README.md

CONTEXTO
Es el documento de referencia de la tarea 1 en la version de entrega. Toma como
base delete_solution_one/solution_task_one_using_experts_final/README.md (495
lineas, en castellano, con tablas de resultados y bibliografia) y CONSERVA su
estructura, su tono y sus cifras. No lo reescribas: extiendelo.

QUÉ AÑADIR — dos secciones nuevas que hoy no existen

  ## La votacion, paso a paso
  Hoy el README dice "cascada ordenada por acierto medido" y lista los peldaños,
  pero no explica el mecanismo del peldaño 4. Escribelo entero:
   - que aporta cada experto al voto (p, tramo, y el peso tier_weight que le
     corresponde: firm 3 / supports 2 / discuss 1)
   - por que el Experto 3 lleva multiplicador 1.5 (AUC 0.794 vs 0.758 del Experto 1)
   - por que la biblioteca vale 0.0 (acierto 0.47 en el cubo positivo = azar;
     darle medio voto costaba 0.033 de ranking)
   - la formula del voto ponderado y el umbral 0.45, con la rejilla que ya esta
     en la seccion 5 del README fuente
   - un ejemplo trabajado END TO END con un caso real de
     task_1/runs/labeled/output: los cinco numeros que entran, la aritmetica, y
     la decision que sale
   - QUE NO ES: no es un promedio, no es una mayoria, y el LLM no tiene voto.
     Las tres cifras que lo justifican (registrador 0.47, verificador 0.49,
     presidente 0.59) van aqui.

  ## Incertidumbre, confianza y peso de las variables
  Esta es la seccion que falta y la razon principal de este documento. Contenido
  exacto, con estas subsecciones:

  ### Tres nociones de importancia, y solo una se entrega
    tabla: atributiva (permutacion OOF, lo que declara cada experto) /
    normativa (lo que exige la guia, del peldaño que disparo) /
    conductual (lo que marco el urologo, EXPERT-TRACE — lo unico que se puntua).
    Y el hecho medido: promover pesos por acuerdo del panel BAJA la nota
    0.8390 -> 0.8365. Se entrega la conductual; las otras dos son la auditoria y
    alimentan el razonamiento.

  ### El presupuesto de varianza
    sigma^2_epist = sigma^2_model + sigma^2_missing + sigma^2_panel, en cuadratura
    porque son varianzas de la misma cantidad bajo fuentes independientes (reglas
    de Rubin). La aleatoria H se reporta aparte y NO se suma: mezclar una varianza
    de Bernoulli con un error tipico da una barra de anchura casi constante que no
    discrimina. Di de donde sale cada termino en el codigo.

  ### La confianza la produce el peldaño que decidio, no la probabilidad
    Cada peldaño tiene acierto medido (24/24, 16/18, 7/8, 3/4, voto ~0.64) y un
    techo de confianza. Un peldaño por debajo de 0.75 no emite 'clear' nunca.
    Es Chow (1970) aplicado al camino de decision. Publica la escalera de
    fiabilidad: acierto dentro de cada tramo declarado, out-of-fold. Si no es
    monotona, dilo.

  ### El conjunto important/decisive se elige por F1 esperado
    Explica la asimetria del evaluador, con las lineas exactas:
      variable_weight_score recorre solo las claves del ground truth (evaluate.py:736)
      important_decisive_factor_score es un F1 de conjuntos sobre las tuyas (evaluate.py:772)
    y por que eso hace que umbralizar cada casilla a 0.5 no sea optimo.

  ### Las dos restricciones duras y su dual
    aterrizaje, coherencia, y por que el plan de revelacion y los pesos son el
    mismo problema resuelto a la vez.

  ### Que se adopto y que no
    Tabla directa de common/analysis/forms_report.json: politica, metrica, delta,
    n_sube/n_baja/p, adoptada si/no. Incluye las NO adoptadas con su motivo. En
    particular, si la constante gana, se publica la constante.

REQUISITOS
- Castellano, mismo registro que el README fuente (sobrio, cifras primero,
  advertencias explicitas donde hay sesgo de seleccion).
- Toda cifra que escribas tiene que salir de un fichero del repo: cita el fichero.
  Si un numero no lo tienes, escribe "pendiente de medir", no lo inventes.
- Bibliografia: conserva la del README fuente y añade, en la seccion nueva:
    Chow (1970) On Optimum Recognition Error and Reject Tradeoff, IEEE Trans. Inf. Theory 16(1).
    Rubin (1987) Multiple Imputation for Nonresponse in Surveys, Wiley.
    Depeweg et al. (2018) Decomposition of Uncertainty in Bayesian Deep Learning, ICML.
    Lakshminarayanan et al. (2017) Simple and Scalable Predictive Uncertainty Estimation, NeurIPS.
    Guo et al. (2017) On Calibration of Modern Neural Networks, ICML.
    Ye et al. (2012) Optimizing F-measure: A Tale of Two Approaches, ICML.
    Barber et al. (2021) Predictive inference with the jackknife+, Ann. Statist. 49(1).
```

---

## FASE 3 — Expertos de la tarea 2: revisión y empaquetado

### 3.1 [PLAN] Qué hay que verificarles

Los cinco están entrenados y medidos. Lo que la revisión tiene que **comprobar**, no rehacer:

1. **Los expertos 1, 2 y 4 emiten las 72 decisiones idénticas.** Verificado en el README. Consecuencia de diseño: **sentarlos como tres voces en la junta es una ficción**; en la sala entra **uno** (el 1, mejor calibrado: ECE 0,0425) y los otros dos se declaran como *réplicas confirmatorias*, no como votos.
2. **La escalera del Experto 5 se midió con CV 4×2, no LOO** (5.400 ajustes, >2 h sin terminar). No son la misma medida que las otras cuatro. Debe seguir declarándolo en `ladder_protocol`.
3. **El Experto 3 es portavoz en 3 casos, dentro de muestra.** Ilustra el mecanismo de escalera, no demuestra que generalice. Se documenta así.
4. **Falta el bloque de aterrizaje.** `reasoning_task2_report.json` da `section_grounding: 0.215` — es el componente más flojo con diferencia. Con `reveal_sequence` vacío (que es lo correcto: los 72 GT lo traen vacío y `compute_tool_score` premia precisión) sólo `psa` y `age` quedan anclados. **Y aquí está la trampa medida: silenciar las otras nueve gana sin juez y pierde con juez.** La política se decide con juez.

### 3.2 [EJECUCIÓN] `task_2/experts_2/`

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

OBJETIVO
Empaquetar los cinco expertos ya entrenados de la tarea 2 en
delete_final_versions_task/task_2/experts_2/, independiente, y VERIFICAR que sus
cifras publicadas se reproducen. No los reentrenes.

COPIAR
  delete_expert_modelate/task_two/expert_{one..five}/model/*.joblib
    -> task_2/experts_2/model/
  delete_expert_modelate/task_two/reasoning_model/model/reasoning_task2.joblib
    -> task_2/experts_2/model/
  delete_expert_modelate/task_two/run_experts.py
    -> task_2/experts_2/panel.py   (adaptado, ver abajo)
  Los informes train/artifacts/expert_*_report.json y reasoning_task2_report.json
    -> task_2/experts_2/reports/

ADAPTAR panel.py
- Toma como modelo delete_solution_one/solution_task_one_using_experts_final/
  experts/panel.py, que ya resuelve los dos problemas de integracion que costaron
  una corrida en la tarea 1:
    (a) Panel.ensure() puntua EN VIVO un caso no cacheado, en vez de dejar a los
        expertos abstenidos en silencio. Todo caso de test es no cacheado.
    (b) precalculo en lote a artifacts/panel_cache.json.
  Replica las dos.
- La funcion align() de run_experts.py es correcta y hay que conservarla tal cual:
  construye el vector sin podar y reordena por feature_names, y de ahi sale la
  incertidumbre por datos ausentes en vez de un error. No la simplifiques.
- Cada experto debe cerrar su turno con el bloque de variables de
  common/vocab.py::variable_block, en el vocabulario del formulario de la TAREA 2
  (11 variables: ct, fh, age, psa, psad, cspca, pirads, bx_isup, bx_gl_sec,
  bx_gl_prim, comorbidity — de schema.py::TASK2_VARIABLES).

VERIFICACIÓN (script task_2/experts_2/verify.py)
Reproduce sobre los 72 etiquetados y falla ruidosamente si no cuadra:
  1. acierto LOO por experto: 1=0.8611, 2=0.8611, 3=0.6389, 4=0.8611, 5=0.8611
  2. Brier: 1=0.2619, 2=0.2733, 3=0.4865, 4=0.2652, 5=0.2842
  3. ECE:   1=0.0425, 2=0.0627, 3=0.1069, 4=0.0760, 5=0.0857
  4. la matriz de acuerdo caso a caso: expertos 1, 2 y 4 coinciden 72/72; el 3
     coincide 44/72 con cada uno de ellos
  5. la regla ISUP sola (mapa bx_isup -> conducta reajustado en cada pliegue LOO)
     acierta 62/72 = 0.8611
Vuelca task_2/experts_2/reports/verify.json con lo medido vs lo publicado.

ACEPTACIÓN
  PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.task_2.experts_2.verify
pasa los cinco checks. Si alguno falla, reporta el delta; no ajustes el umbral
para que pase.

NO HAGAS
- No reentrenes. No cambies hiperparametros. No "mejores" ningun experto.
```

---

## FASE 4 — La junta de la tarea 2

### 4.1 [PLAN] El criterio de diseño, y en qué se diferencia de la tarea 1

La tarea 2 **no es la tarea 1 con otras etiquetas**. La diferencia es estructural y hay que escribirla:

| | tarea 1 | tarea 2 |
|---|---|---|
| dónde está la dificultad | el cubo `bx=Positive`, 49/91 casos, que **ninguna variable del panel determina** | en ningún sitio: la etiqueta es casi función de `bx_isup` (0,8611) y el techo de consistencia es 0,931 |
| qué aporta el LLM | **recupera el grado documentado** de las notas previas, y eso decide el caso | casi nada de decisión: el grado ya viene estructurado |
| a qué dedica la sala su tiempo | **encontrar evidencia** | **justificar y calibrar** — dónde la regla está en su límite |
| el margen que queda | la puerta (0,68 → 0,91) | el 82,5 % del `case_score` que **no** es la decisión |

De ahí el protocolo:

```
1. cascada de guía (Experto 5)   ¿hay cáncer?  AUC 0,940
                                 ¿tratar?      AUC 0,881
                                 ¿se beneficia? AUC 0,500  ← declarado, no disimulado
2. portavoz por fiabilidad       Experto 1 (ECE 0,0425), no votación
3. escalón de excepción          si 1/2/4/5 están todos en `discuss` → habla el Experto 3
4. techo de consistencia         5 casos comparten perfil exacto con etiqueta contraria:
                                 la sala lo dice y la confianza lo refleja
```

Y las tres cosas que **no** hay que hacer, todas medidas: voto blando (0,7639, p<0,001 peor), apilado (0,8472 con siete modelos para empatar), y la política de silenciar casillas para subir el grounding (gana sin juez, pierde con juez).

### 4.2 [EJECUCIÓN] Construir la junta

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

OBJETIVO
La junta clinica de la tarea 2 en delete_final_versions_task/task_2/agent/,
reusando common/ y con la misma anatomia que la tarea 1.

REFERENCIA OBLIGATORIA
Lee entero delete_final_versions_task/task_1/agent/graph.py y prompts.py, y
delete_final_versions_task/task_1/PROMPTS.md. La tarea 2 es una VARIACION de esa
arquitectura, no un diseño nuevo. Todo lo que aprendio la tarea 1 sobre prompts
aplica aqui y esta en PROMPTS.md; leelo antes de escribir un solo prompt.

FICHEROS
  task_2/agent/graph.py      el grafo LangGraph
  task_2/agent/prompts.py    los prompts + el parte clinico del presidente
  task_2/agent/protocol.py   la cascada de guia + consolidacion
  task_2/agent/decide.py     guardias especificas de la tarea 2
  task_2/agent/run_task2.py  runner por lotes con --split {labeled,unlabeled,all}
  task_2/PROMPTS.md          el analisis de los prompts, uno por uno

LA SESIÓN (intervenciones; numeracion global y monotona como en la tarea 1)
   1 INTAKE            structured-prompt.json campo por campo
   2 EXPERT-GRADE      Experto 1 (bloque G, 28 vars) — el ancla, mejor calibrado
   3 EXPERT-PATHOLOGY  Experto 2 — segunda lectura del grado, riesgo de upgrade
   4 EXPERT-CASCADE    Experto 5 — el veredicto abierto en sus tres preguntas
   5 EXPERT-TRACE      reasoning_task2 — que documentos y que pesos → FIJA EL PLAN
   6 EXPERT-EAU        LLM + RAG sobre la guia; critica a los expertos
   7 MODERATOR         preguntas abiertas, una por documento del plan
   8 REGISTRAR         abre exactamente el plan (LLM + MCP)
   9 EXPERT-FUSION     Experto 4 — solo sobre lo abierto
  10 EXPERT-FITNESS    Experto 3 — SOLO si 1/2/4/5 estan todos en `discuss`
  11 PANEL-PROTOCOL    la cascada; DECIDE
  12 VERIFIER          ¿decidible? ¿falta un documento del plan?
  13 CHAIR             la nota clinica y el formulario

REGLAS DE DISEÑO (medidas, no negociables)
- El LLM NO vota. Portavoz por fiabilidad medida, no por votacion: los expertos
  1, 2 y 4 emiten las MISMAS 72 decisiones caso a caso, asi que una votacion entre
  ellos tiene resultado conocido de antemano. Se sientan como replicas
  confirmatorias, no como voces independientes, y el acta lo dice.
- El nodo de aptitud publica su AUC 0.500 (watchful_waiting: 2 casos de 72, no es
  aprendible). Que la junta lo declare es lo que impide que trate como informado un
  veredicto que no lo es.
- reveal_sequence ENTREGADO = lista vacia. Los 72 GT la traen vacia y
  compute_tool_score premia precision (|agente ∩ patron| / |agente|): declarar
  cualquier seccion la pone a 0. Ojo: la lista vacia es lo que se ENTREGA; el
  registrador SI abre documentos internamente, porque sin el informe de patologia
  el Experto 2 no puede hablar.
- confidence: usa common/uncertainty_forms.confidence_from_rung, pero la constante
  'clear' puntua 0.9028 y ningun modelo la bate bajo LOO. Si la politica por peldaño
  no la bate en common/analysis/forms_report.json, ENTREGA LA CONSTANTE y escribelo
  en el README.
- section_grounding: NO adoptes la politica de silenciar casillas. Gana sin juez
  (0.7896 vs 0.7347) y PIERDE con juez (0.7340 vs 0.7696), porque apagar el juez
  redistribuye el grounding de 0.05 a 0.175. El leaderboard puntua con juez.
- Las claves bx_isup/bx_gl_prim/bx_gl_sec solo aparecen en 52 de las 72 trazas,
  exactamente cuando bx_isup > 0. Emitirlas de mas no daña variable_weight_score
  (recorre las claves del patron) pero si el F1 de factores.

GUARDIAS (reusa common/guards.py; añade las especificas)
- process_language: la nota describe al paciente, no el procedimiento. La lista
  curada de la tarea 1 es un punto de partida, pero VERIFICALA contra los 72
  free_text reales del urologo de la tarea 2 y exige 0 falsos positivos antes de
  activarla. No la copies a ciegas.
- unsourced_values, enforce_grounding, validate_output(task=2): de common/.
- respaldo determinista si el presidente no entrega JSON valido: ningun caso se
  pierde.

ACEPTACIÓN
- La simulacion sin LLM (task_2/analysis/simulate.py, replica de la de la tarea 1)
  corre en segundos y da un ranking_score sobre los 72.
- El grafo compila y un caso corre end to end.
```

### 4.3 [EJECUCIÓN] Corrida, puntuación y README de la tarea 2

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

OBJETIVO
Correr la junta de la tarea 2 sobre los 153 casos, puntuarla contra el baseline y
escribir delete_final_versions_task/task_2/README.md.

CORRIDA
  task_2/runs/labeled/output/task2/    (72 etiquetados)
  task_2/runs/unlabeled/output/task2/  (81 sin etiqueta)
  Temperatura 0. Acta completa JSON+MD, summary.jsonl, telemetry.jsonl por caso.

PUNTUACIÓN — los dos modos, y el baseline al lado
  .venv/bin/python dev/score_local.py --tasks 2 --count-missing \
    --output-root delete_final_versions_task/task_2/runs/labeled/output \
    --json-out delete_final_versions_task/task_2/runs/score_no_judge.json
  .venv-eval/bin/python dev/score_with_judge.py --task 2 \
    --output-root delete_final_versions_task/task_2/runs/labeled/output \
    --json-out delete_final_versions_task/task_2/runs/judge/entrega.json

Linea base a batir (dev/baseline_reference.json): task2 ranking 0.4457,
puerta 56.9%, weighted_f1 0.5224. AVISO: su tool_score de 0.0000 es artefacto de
los datos (los 72 GT traen reveal_sequence vacio), no del agente; el task 2 real
del baseline ronda 0.47. No presentes el 0.4457 sin esa nota.
Compara tambien contra el SUELO real: la regla ISUP acierta 0.8611 y el techo de
consistencia es 0.931. Un agente que no bate 0.8611 en decision no es un resultado.

README (castellano, misma estructura que task_1/README.md)
Secciones obligatorias:
  - Resultado: tabla baseline / regla ISUP / junta, en los dos modos de juez, con
    prueba de signos por caso. Y el techo de consistencia 0.931 al lado.
  - La sesion, intervencion por intervencion (el diagrama ASCII y la tabla
    "quien es quien", como en la tarea 1)
  - ## En que se diferencia de la tarea 1  <- SECCION EXIGIDA. Contenido:
      * en T1 la dificultad es el cubo bx=Positive (49/91) que ninguna variable
        determina; en T2 la etiqueta es casi funcion de bx_isup
      * en T1 el LLM decide el caso porque RECUPERA el grado documentado de las
        notas; en T2 el grado ya viene estructurado y el LLM no decide casi nada
      * por eso el margen de T2 esta en el 82.5% del case_score que no es la
        decision, no en la puerta
      * los tres expertos identicos: por que se sientan como replicas y no como
        votos, y por que eso NO es una debilidad del panel sino un hallazgo sobre
        los datos
      * el nodo de aptitud con AUC 0.500 y por que se publica
  - Incertidumbre, confianza y pesos: la misma metodologia que task_1, con los
    numeros de la tarea 2. Si la constante 'clear' gana, dilo y publica el 0.9028.
  - Bibliografia: la de task_1 mas
      Cooperberg et al. (2011) The CAPRA-S score, Cancer 117(22).   [para el paralelo con T3]
      EAU-EANM-ESTRO-ESUR-ISUP-SIOG Guidelines on Prostate Cancer (2024)
      NCCN Clinical Practice Guidelines in Oncology: Prostate Cancer (2024)
      Kweldam et al. (2015) Cribriform growth is highly predictive..., Mod Pathol 28(3).
      van Leenders et al. (2020) ISUP consensus on grading, Am J Surg Pathol 44(8).
      Barry et al. (1992) The American Urological Association symptom index (IPSS), J Urol 148(5).
      Chapman et al. (2001) A simple algorithm for identifying negated findings (NegEx), J Biomed Inform 34(5).
```

---

## FASE 5 — Los expertos de la tarea 3 (nuevos)

### 5.1 [PLAN] El diseño

**La separación orden/magnitud.** Es el resultado que ordena toda la tarea:

- `ranking_score = c_index`, y el c-index sólo compara `preds[i] < preds[j]` → **invariante a toda transformación monótona creciente**.
- `time_score` sí depende de la magnitud, y para los censurados (75 % de los casos) vale **1,0 si predices ≥ el tiempo de seguimiento**.

Por tanto: **primero se ajusta el orden del riesgo (maximiza c-index), después un mapa monótono riesgo→meses (maximiza time_score), y el segundo no puede dañar al primero.** Isotónica. Nadie tiene que elegir entre las dos métricas.

**El suelo de guía es CAPRA-S** (Cooperberg 2011): PSA prequirúrgico (0-3), Gleason patológico (0-3), márgenes (0/2), extensión extraprostática (0/1), invasión de vesículas (0/2), ganglios (0/1) → 0-12 puntos. Sus seis variables están todas en el caso. c-index original 0,77, validaciones externas >0,80. Medido hoy sobre los 75 casos: **0,7372 crudo**, contra 0,6636 del baseline.

**Los cinco expertos:**

| # | experto | qué lee | qué aporta |
|---|---|---|---|
| 1 | **CAPRA-S / ancla de guía** | los 6 campos, por regex | el score, el grupo de riesgo y su c-index; determinista y auditable |
| 2 | **patología quirúrgica ampliada** | `surgical_pathology_report` + `pathology_report` | pT, patrón terciario, cribiforme, LVI, y el **upgrade/downgrade biopsia→pieza** |
| 3 | **patología digital** | embedding de prostatectomía (960-d, 1-3 láminas) | la única fuente que añade orden sobre CAPRA-S (medido) |
| 4 | **fusión** | 1+2+3 + RM | el candidato de 0,83; control de si alguna fuente añade algo compitiendo |
| 5 | **calibrador de horizonte** | el riesgo de los anteriores | **no vota**: convierte riesgo→meses por mapa monótono y decide el bit `event`. Es el análogo del Experto 5 de la tarea 2: descompone, no añade voto |

**Dos avisos honestos que el diseño debe llevar dentro:**
- **Ganglios ausentes en 43/75** ("no lymph nodes were removed"). CAPRA-S los puntúa 0 por convención (pNx = pN0), pero eso **no es lo mismo** que un pN0 confirmado. Bandera `ln_unknown` separada, y la incertidumbre por datos ausentes tiene que crecer ahí — es exactamente el caso de uso del término *between-imputation*.
- **19 eventos.** Cualquier número con más de ~5 parámetros libres está sobreajustado. Regularización fuerte, CV anidada para elegir el número de componentes, y el intervalo bootstrap publicado al lado de cada c-index.

**Y una simetría que conviene decir:** en la tarea 3 el juez de razonamiento pesa **0,30** del `case_score` (frente a 0,20 en las otras dos) y **no hay puerta de decisión**. Es la tarea donde la prosa del LLM vale más y su decisión menos. Además, los dos abortos sistemáticos del baseline (T3-038, T3-063) **desaparecen por construcción**: el número no lo produce el LLM.

### 5.2 [EJECUCIÓN] Features y cabeza de supervivencia

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline
Directorio: delete_final_versions_task/common/chimera_experts/

OBJETIVO
Los tres modulos que la tarea 3 necesita y que no existen. Mismo estilo, mismas
convenciones y mismo nivel de docstring que los modulos hermanos que ya estan ahi
(features_grading.py, features_pathology.py, uncertainty.py): docstring en
castellano explicando el porque, no el que.

FICHERO 1 — features_surgical.py  (bloque S)
Parsea data/task3/agent_input/<case>/prostate-time-to-recurrence-or-last-follow-up-
clinical-data.json::surgical_pathology_report. El corpus es plantillado; estas
expresiones estan verificadas hoy sobre los 75 casos y funcionan 75/75 salvo
ganglios:
    Gleason (\d)\s*\+\s*(\d)                       -> prim, sec        (75/75)
    ISUP grade group (\d)                          -> isup_rp          (75/75)
    pathological stage (pT\w+)                     -> pt               (75/75)
    "Extraprostatic extension was present" / "no extraprostatic extension"  -> epe
    "surgical margins were positive" / "...negative"                       -> margins
    "seminal vesicles were invaded" / "...were not invaded"                 -> svi
    "lymphovascular invasion was present" / "...was absent"                 -> lvi
    "lymph node metastasis was present" / "no lymph node metastasis"        -> ln
    "no lymph nodes were removed"  -> ln = NaN  y  ln_unknown = 1   (43 de 75 casos)
    "with tertiary pattern (\d)"   -> tertiary
Reglas del bloque:
- Cada concepto es TERNARIO: 1.0 afirmado, 0.0 negado, NaN no mencionado. "Negado"
  y "no mencionado" son evidencias distintas (mismo criterio que features_pathology.py).
- capra_s(): implementa la tabla de Cooperberg 2011 EXACTA
    PSA:      <=6 -> 0 | 6.1-10 -> 1 | 10.1-20 -> 2 | >20 -> 3
    Gleason:  <=6 -> 0 | 3+4 -> 1 | 4+3 -> 2 | 8-10 -> 3
    EPE 0/1 · SVI 0/2 · margenes 0/2 · ganglios 0/1        total 0-12
    grupos: bajo 0-2 · intermedio 3-5 · alto >=6
  Con ln_unknown=1 se puntua 0 POR CONVENCION (pNx = pN0) pero se devuelve la
  bandera aparte, y el llamador ensancha la incertidumbre. Documentalo: no es lo
  mismo un pN0 confirmado que un pNx.
- Extra fuera de CAPRA-S: pt_ge_t3 (pT3a/pT3b/pT4), tertiary_pattern_5,
  upgrade_bx_to_rp = isup_rp - isup_bx (del pathology_report de biopsia; NaN si el
  informe dice "Gleason pattern and ISUP report missing" — pasa en varios casos).

FICHERO 2 — survival.py
Cox de riesgos proporcionales en numpy+scipy puro. NO añadas lifelines ni
scikit-survival: el venv de entrega tiene mcp y vLLM fijados y cada dependencia
nueva es un riesgo en el contenedor.
    class CoxPH:
        def __init__(self, alpha: float = 1.0, l1_ratio: float = 0.0)
        def fit(self, X, t, e)      # verosimilitud parcial de Breslow para empates,
                                    # penalizacion elastic-net, scipy.optimize.minimize L-BFGS-B
        def risk(self, X) -> np.ndarray          # exp(X @ beta), el orden
        def baseline_survival(self) -> tuple     # Breslow, para poder dar meses
    def c_index(t, risk, e) -> float
        # IDENTICO al del evaluador oficial: solo cuentan pares donde events[i]==1
        # y times[i] < times[j]; empates de prediccion valen 0.5.
        # Copia la semantica de ~/PycharmProjects/CHIMERA-agent-eval/evaluation/
        # evaluate.py::concordance_index y comprueba que coincide en un caso de test.
    def monotone_calibrate(risk_train, t_train, e_train) -> Callable[[np.ndarray], np.ndarray]
        # EL PUNTO CLAVE DEL DISEÑO. Devuelve un mapa ESTRICTAMENTE DECRECIENTE
        # riesgo -> meses ajustado por isotonica para maximizar el recurrence_time_score
        # del evaluador. Como el c-index solo compara ordenes, este mapa NO PUEDE
        # cambiarlo: el orden se fija primero y la magnitud despues.
        # recurrence_time_score (evaluate.py:792): para event=1 penaliza |pred - t|/max(t,1);
        # para event=0 vale 1.0 si pred >= t. Es decir: pasarse de largo es GRATIS en el
        # 75% de los casos. La isotonica tiene que aprender eso, no promediarlo.
    def bootstrap_ci(fn, *args, n: int = 1000, seed: int = 0) -> tuple[float,float]

FICHERO 3 — dataset_task3.py
Modelado sobre dataset_task2.py, que ya existe: mismo build_matrix(cases, blocks,
drop_constant), mismo completeness_vector, misma poda. Bloques:
    A structured   (reutiliza features_structured; task 3 solo trae age/psa/dre/
                    active_treatment_prior_to_surgery, con dre nulo en 23 casos y
                    active_treatment nulo en 73 — no lo fuerces)
    S surgical     (features_surgical, nuevo)
    G grading      (features_grading sobre el informe de BIOPSIA)
    D radiology    (features_radiology: volumen, PSAD, PI-RADS, csPCa)
    E embeddings   (media por fuente: MRI 1024-d en 75/75, Prostatectomy 960-d en
                    75/75, Biopsy 960-d en 51/75. La reduccion de dimension va
                    DENTRO del pipeline, nunca ajustada sobre la cohorte entera)
io.py::Case ya conoce el layout de la tarea 3 (CLINICAL_FILENAME[3],
DECISION_FILENAME[3]) pero Case.label asume una cadena: la etiqueta de la tarea 3
es {"months_to_recurrence": float, "event": int}. Extiende io.py de forma
retrocompatible (las tareas 1 y 2 no pueden cambiar de comportamiento).

TESTS  delete_final_versions_task/common/tests/test_task3.py
- capra_s reproduce a mano el T3-001: PSA 86 -> 3, Gleason 4+3 -> 2, EPE -> 1,
  SVI -> 2, margenes -> 2, ganglios positivos -> 1  =  11
- features_surgical parsea 75/75 sin excepcion y ln_unknown == 43
- c_index coincide con evaluate.concordance_index sobre un vector aleatorio fijo
- monotone_calibrate devuelve una funcion decreciente y no cambia el c-index
  (comprueba: c_index antes == c_index despues, exactamente)
```

### 5.3 [EJECUCIÓN] Entrenar y medir los cinco expertos

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline
Directorio: delete_final_versions_task/task_3/experts_3/

OBJETIVO
Entrenar y medir los cinco expertos de la tarea 3 sobre los 75 casos etiquetados.
Estructura y estilo identicos a delete_expert_modelate/task_two/ (un directorio por
experto, train_expert_N.py, model/*.joblib, README.md, y un informe JSON en
train/artifacts/).

LOS CINCO
 1 expert_one   CAPRA-S — regla de guia determinista. Bloque S. Publica el score,
                el grupo de riesgo y su c-index. Es el ANCLA y el SUELO: cualquier
                experto que no lo bate se reporta como no aportando.
 2 expert_two   patologia quirurgica ampliada. Bloques S+G. CoxPH regularizado.
 3 expert_three patologia digital. Bloque E, SOLO prostatectomia. Reduccion de
                dimension DENTRO del pipeline.
 4 expert_four  fusion. A+S+G+D+E.
 5 expert_five  calibrador de horizonte. NO produce orden propio: toma el riesgo del
                portavoz y produce (months, event). Es quien posee time_score y el bit
                event. Publica por separado su efecto sobre c-index (debe ser 0.0000)
                y sobre time_score.

PROTOCOLO DE MEDIDA — leelo entero antes de empezar
- 19 eventos de 75. Cualquier cosa con mas de ~5 parametros libres esta
  sobreajustada. Regularizacion fuerte y CV ANIDADA para elegir hiperparametros
  (numero de componentes incluido). Un c-index elegido mirando los mismos 75 casos
  no es un resultado; si lo haces, declaralo como tal.
- Metrica que ordena: c-index de Harrell, con la MISMA semantica que el evaluador
  oficial. Reporta ademas time-dependent AUC a 12/24/36/60 meses (el evaluador la
  calcula: TD_AUC_HORIZONS_MONTHS) e intervalo bootstrap de 1000 al lado de cada
  c-index.
- Suelos obligatorios en TODAS las tablas: baseline actual 0.6636 · CAPRA-S crudo
  0.7372 · constante 60 meses 0.5000. Un modelo que no los bate no es un resultado.
- Ablacion por bloque con bootstrap pareado, como en la tarea 2: un bloque que no
  mueve la metrica se documenta como redundante, no se queda "porque no hace daño".
- Escalera de fiabilidad: c-index dentro de cada tramo declarado, fuera de muestra.
  Si no es monotona, se publica igual y se dice.

CIFRAS DE PARTIDA (sonda ya hecha, PCA dentro del pliegue, 5-fold x 5 semillas,
riesgo = P(evento) con logistica; TIENES QUE REHACERLAS CON COX Y CV ANIDADA)
    CAPRA-S crudo                          0.7372
    CAPRA-S solo, logistica OOF            0.7159 +- 0.0088
    emb prostatectomia solo, 4 PCs         0.7487 +- 0.0078
    emb RM solo                            0.5124 +- 0.0105
    emb biopsia solo (n=51)                0.6657 +- 0.0130
    CAPRA-S + 8 PCs prostatectomia         0.8319 +- 0.0055   <- el candidato
Sesgo conocido y que hay que corregir: el numero de componentes (4/8/16) se eligio
mirando los mismos 75 casos, y la logistica sobre P(evento) IGNORA LA CENSURA.
Si con Cox y CV anidada la cifra baja, LA CIFRA BAJA. Reportala.

EL BIT `event`
Task3Output no tiene campo event, pero run.py lo escribe con
structured.get("event", 0) (linea 142) y vale 0.35 del case_score. Hoy es constante
0 = 0.7467, que es la tasa base de censura. Medido en muestra: CAPRA>=7 da 0.7733 y
CAPRA>=9 da 0.7867. Son ganancias pequeñas y DENTRO de muestra: mide el umbral
out-of-fold y si no bate a la constante 0, entrega la constante 0 y escribelo.

SALIDA
  task_3/experts_3/train/artifacts/expert_{one..five}_report.json
  task_3/experts_3/README.md con la tabla comparativa de los cinco, la ablacion por
  bloque, las escaleras, y los suelos. Estilo: delete_expert_modelate/task_two/README.md.
```

---

## FASE 6 — La junta de la tarea 3

### 6.1 [PLAN] Criterio de diseño y diferencias

```
   1 INTAKE               age, psa, dre, active_treatment_prior_to_surgery
   2 EXPERT-CAPRA         el ancla de guía: score 0-12, grupo, c-index publicado
   3 EXPERT-SURGICAL      pT, terciario, cribiforme, LVI, upgrade biopsia→pieza
   4 EXPERT-DIGITAL       la lámina de prostatectomía; declara nº de láminas
   5 MODERATOR            preguntas abiertas; una por documento
   6 REGISTRAR            abre el plan (informe quirúrgico, biopsia, RM, notas)
   7 EXPERT-FUSION        sobre lo abierto
   8 PANEL-PROTOCOL       fija el ORDEN de riesgo → c-index
   9 EXPERT-HORIZON       el mapa monótono riesgo→meses y el bit `event` → time_score
  10 VERIFIER             ¿el expediente está en condiciones?
  11 CHAIR                la nota clínica (vale 0,30 aquí, no 0,20)
```

Tres diferencias que el README debe explicar:

1. **No hay puerta.** En T1/T2 fallar la clase pone el caso a cero. Aquí no: `event` 0,35 + `time` 0,35 + razonamiento 0,30. Pero el **leaderboard** es sólo el c-index. Son dos objetivos distintos y hay que optimizar los dos, no confundirlos.
2. **No hay `variable_weights` ni `confidence`.** `Task3Output` sólo tiene `months_to_recurrence` y `reasoning`. Toda la metodología de la sección B no aplica; la de la sección A **sí**, y se expresa en la prosa: la nota tiene que decir de qué depende el pronóstico y qué le falta al expediente.
3. **El LLM no produce el número, y por eso los dos abortos sistemáticos del baseline desaparecen.** T3-038 y T3-063 resisten 8 intentos con el mismo centinela porque el prompt nunca explica la censura: en el 74,7 % de los casos `months_to_recurrence` no es «cuándo recurre» sino «cuánto seguimiento sin evento». Aquí el número lo pone el Experto 5 y el prompt del presidente **explica la semántica de censura explícitamente**.

### 6.2 [EJECUCIÓN] Construir, correr y documentar

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

OBJETIVO
La junta de la tarea 3 en delete_final_versions_task/task_3/agent/, corrida sobre
los 75 casos, puntuada, y su README.

FICHEROS
  task_3/agent/{graph.py, prompts.py, protocol.py, decide.py, run_task3.py}
  task_3/PROMPTS.md
  task_3/README.md

REFERENCIA
delete_final_versions_task/task_1/agent/ y task_2/agent/. Misma anatomia, mismo
acta numerada, mismas guardias de common/. Las 11 intervenciones estan en el plan
que acompaña a este prompt.

LO QUE CAMBIA RESPECTO A LAS OTRAS DOS
1. No hay puerta de decision ni variable_weights ni confidence. Task3Output solo
   tiene case_id, task, months_to_recurrence (float >= 0.0) y reasoning
   (min_length=40). Comprueba src/chimera_agent_baseline/output/schema.py, que es
   INTOCABLE.
2. El fichero de decision del reto es
   prostate-time-to-recurrence-or-last-follow-up.json con
   {"event": int, "months_to_recurrence": float}, y su gemelo -reasoning.json es
   UNA CADENA SUELTA, no un objeto. Ver run.py::_write_task_outputs lineas 138-152.
3. EL NUMERO NO LO PRODUCE EL LLM. Lo produce EXPERT-HORIZON (experto 5). Esto no
   es una preferencia: los casos T3-038 y T3-063 del baseline resisten 8 reintentos
   devolviendo "Cannot be determined", porque el prompt nunca explica la censura y
   el modelo se niega a decir cuando ocurrira algo que la pregunta mal planteada le
   hizo esperar. Sacandole el numero, la familia de fallo desaparece por
   construccion. Aun asi, el prompt del presidente DEBE explicar la semantica de
   censura ("si no hay evidencia de recurrencia, el numero es el seguimiento
   esperado sin evento") para que la prosa no contradiga al numero.
4. El juez de razonamiento pesa 0.30 aqui (frente a 0.20 en T1/T2) y no hay puerta
   que filtre. La nota clinica es proporcionalmente lo mas valioso de esta tarea:
   invierte en el prompt del presidente lo que en T1 invertiste en el protocolo.
5. Optimizacion en dos etapas, y el README tiene que explicarlo:
     - PANEL-PROTOCOL fija el ORDEN del riesgo -> mueve el c-index (= ranking_score)
     - EXPERT-HORIZON aplica el mapa monotono riesgo->meses -> mueve el time_score
     - el segundo NO PUEDE dañar al primero, porque el c-index solo compara ordenes.
   Verificalo en la corrida: c-index antes y despues del calibrado, identicos.

CORRIDA
  task_3/runs/labeled/output/task3/   (los 75; en la tarea 3 TODOS estan etiquetados)
  Temperatura 0. Acta JSON+MD, summary.jsonl, telemetry.jsonl.

PUNTUACIÓN
  .venv/bin/python dev/score_local.py --tasks 3 --count-missing \
    --output-root delete_final_versions_task/task_3/runs/labeled/output \
    --json-out delete_final_versions_task/task_3/runs/score_no_judge.json
  .venv-eval/bin/python dev/score_with_judge.py --task 3 \
    --output-root delete_final_versions_task/task_3/runs/labeled/output \
    --json-out delete_final_versions_task/task_3/runs/judge/entrega.json

Linea base: task3 ranking 0.6636 (= c-index), event 0.7397, time 0.3738.
AVISOS al presentarlo:
  - el ranking_score de la tarea 3 es SOLO el c-index; mean_case_score no rankea
    (verificado en evaluate.py:1644 "ranking_score": c_index)
  - el 0.7397 de event del baseline es la tasa base de censura, no una prediccion:
    escribe event=0 constante para los 75
  - predecir 60 meses a todo el mundo da mean_case_score 0.75 y c-index 0.50.
    Publica las dos metricas juntas SIEMPRE, o el numero engaña.

README (castellano, estructura de task_1/README.md)
Secciones obligatorias:
  - Resultado: c-index, TD-AUC a 12/24/36/60, event, time, mean_case_score, en los
    dos modos de juez, contra baseline / CAPRA-S crudo / constante 60m.
  - Los cinco expertos y sus suelos.
  - ## Orden y magnitud son dos problemas  <- SECCION EXIGIDA, con la demostracion
    de que el c-index es invariante a transformaciones monotonas y por que eso
    permite optimizar las dos metricas sin elegir.
  - ## En que se diferencia de las tareas 1 y 2  <- SECCION EXIGIDA: sin puerta,
    sin formulario, el juez pesa 0.30, el numero no lo produce el LLM, y el
    tratamiento explicito de la censura.
  - Incertidumbre: aqui NO hay campo confidence, asi que la incertidumbre se expresa
    en la prosa y en el ancho del intervalo. Explica la bandera ln_unknown (43 de 75
    casos sin ganglios extraidos: CAPRA-S los puntua 0 por convencion, pero pNx no
    es pN0) y como ensancha el termino de imputacion.
  - Bibliografia (verifica DOI y paginas antes de publicar):
      Cooperberg, Hilton, Carroll (2011). The CAPRA-S score: a straightforward tool
        for improved prediction of outcomes after radical prostatectomy. Cancer 117(22):5039-46.
      Punnen et al. (2014) / Tilki et al. (2015). Validaciones externas de CAPRA-S
        (c-index >0.77, hasta >0.80 en cohorte europea).
      Stephenson et al. (2005/2009). Nomogramas post-prostatectomia, MSKCC.
      Han, Partin, Pound, Epstein, Walsh (2001). Long-term biochemical disease-free
        survival following radical prostatectomy. Urol Clin North Am 28(3).
      Pound et al. (1999). Natural history of progression after PSA elevation
        following radical prostatectomy. JAMA 281(17).
      Freedland et al. (2005). Risk of prostate cancer-specific mortality following
        biochemical recurrence. JAMA 294(4).
      Cox (1972). Regression models and life-tables. JRSS-B 34(2).
      Harrell, Lee, Mark (1996). Multivariable prognostic models. Stat Med 15(4).
      Uno et al. (2007). Evaluating prediction rules for t-year survivors with
        censored regression models. JASA 102(478).       [la TD-AUC del evaluador]
      Breslow (1974). Covariance analysis of censored survival data. Biometrics 30(1).
      Y para la parte de patologia digital: al menos una referencia real y verificada
        de prediccion de BCR desde WSI con modelos fundacionales (2024-2025). Si no
        puedes verificar una, NO la inventes: escribe que la linea existe y deja el
        hueco marcado.
```

---

## FASE 7 — Convergencia hacia el agente único

### 7.1 [EJECUCIÓN] `common/gc_entry.py` — el despacho por tarea

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline
Fichero nuevo: delete_final_versions_task/common/gc_entry.py

OBJETIVO
El punto de entrada unico de un caso, que es el esqueleto del agente unico futuro.
Toma como base delete_solution_one/solution_task_one_using_experts_final/gc_entry.py
(177 lineas, ya escrito y verificado en sus partes) y generalizalo a tres tareas.

API
  def dispatch(task: int, *, structured_prompt, clinical_data,
               neural_representations, output_path, embedding_model_dir) -> int
      # monta el caso en un directorio temporal con el layout que espera el MCP,
      # arranca el servidor, construye el grafo de la tarea, valida contra
      # Task{N}Output y escribe los dos ficheros del reto.
      # Si algo falla, escribe IGUALMENTE una salida valida: en Grand Challenge un
      # caso sin salida no es un cero, es un caso perdido.

  run_task1_case / run_task2_case / run_task3_case  = envoltorios finos de dispatch.

REGLAS DEL ENTORNO DEL RETO (las tienes en la Anatomia de la solucion)
- SIN RED. Toda ruta a modelo, local y absoluta dentro del contenedor.
- /input es SOLO LECTURA. Todo lo temporal a /tmp.
- Un caso, un arranque: el modelo se recarga en cada paciente.

INTEGRACIÓN CON inference.py (documentala en el README, NO la apliques todavia)
Sustituir el cuerpo de interf0_handler / interf1_handler / interf2_handler por una
llamada a dispatch(task=N, ...). Es el unico cambio en codigo del upstream y es de
tres lineas por handler.

ACEPTACIÓN
Un caso de cada tarea, end to end, desde ficheros sueltos hasta los dos JSON, con
el schema validado. Y un caso forzado a fallar que produce salida valida igualmente.
```

### 7.2 [PLAN] El README raíz y la lista de empaquetado

Contenido de `delete_final_versions_task/README.md`:

- **El mapa**: qué comparten las tres tareas (`common/`) y qué es propio de cada una (`protocol.py`, `prompts.py`, los expertos).
- **La tabla de resultados de las tres**, contra el baseline, en los dos modos de juez, con el `OVERALL` ponderado 2:2:1 al lado del 0,5651 de partida.
- **Cómo se fusionan en un agente**: `dispatch(task)` en `common/gc_entry.py`, tres handlers en `inference.py`, tres registros de herramientas que ya existen (`TASK{1,2,3}_TOOLS`).
- **La lista de lo que falta para el contenedor** (de `solution_.../README.md` §7, ya escrita): el Dockerfile no copia el paquete ni los `.joblib`; hay que fijar `scikit-learn==1.9.0`, `scipy` y `joblib`; los artefactos y los casos etiquetados que la biblioteca lee en runtime van al tarball del modelo; y `./do_test_run.sh` con la GPU entera libre.
- **Un aviso de tiempo por caso** que hay que contrastar con el límite del reto: carga del modelo ~90 s + servicio de embeddings ~30 s + junta ~25-30 s ≈ **2-3 min**, más 30-80 s si el panel no está cacheado (todo caso de test).

---

# Orden de ejecución y camino crítico

```
0.1 ──┬── 1.1 ── 1.2 ──┐
0.2 ──┘                ├── 2.1 ── 2.2 ── 2.3   (tarea 1 cerrada)
                       │
                       ├── 3.2 ── 4.2 ── 4.3   (tarea 2)
                       │
              5.2 ── 5.3 ── 6.2                 (tarea 3)
                                     │
                                     └── 7.1 ── 7.2
```

- **0.1 y 0.2 son bloqueantes de todo.** Hazlos primero y en ese orden.
- **5.2 no depende de la fase 1**: los expertos de la tarea 3 se pueden entrenar en paralelo con el cierre de la tarea 1. Es el trabajo más largo (CV anidada con 19 eventos), así que conviene lanzarlo pronto.
- **2.2 y 4.3 son corridas de GPU largas** (100 min y ~80 min) y **no se pueden solapar**: vLLM pide el 90 % de la VRAM. Programa una de noche.
- El único paso que puede invalidar diseño posterior es **1.2**: si la metodología no bate a lo que ya hay, los READMEs publican las constantes y se ahorra la mitad de la fase 4.

**Riesgo que conviene mirar antes de invertir en la fase 6:** el `0,8319` de la tarea 3 sale de logística sobre P(evento) ignorando la censura y con el número de componentes elegido sobre los mismos 75 casos. Si con Cox y CV anidada cae a ~0,75, sigue siendo **+0,09 sobre el baseline** y el diseño no cambia; sólo cambian las cifras del README. No hay decisión que dependa de eso, pero hay que medirlo antes de escribir el documento.

---

Quedo a la espera. Si prefieres que ajuste algún paso —partir la fase 4, cambiar el reparto entre `common/` y las tareas, o llevar la fase 5 primero— dímelo antes de que empieces a pasarle prompts a Codex.

**Fuentes consultadas para la parte de la tarea 3:**
[CAPRA-S (Cooperberg 2011)](https://acsjournals.onlinelibrary.wiley.com/doi/full/10.1002/cncr.26169) · [validación externa europea](https://pubmed.ncbi.nlm.nih.gov/25498570/) · [validación multiinstitucional](https://pubmed.ncbi.nlm.nih.gov/23587869/) · [nomogramas post-RP MSKCC](https://www.sciencedirect.com/science/article/abs/pii/S0302283814009567) · [deep learning para BCR (2025)](https://bmccancer.biomedcentral.com/articles/10.1186/s12885-025-13628-9) · [modelo multimodal MRI+clínica vs CAPRA-S](https://pmc.ncbi.nlm.nih.gov/articles/PMC12415651/)
---

## FASE 1b — Cerrar la medición de confianza que 1.2 dejó incompleta (añadido 2026-09-09)

Decisión del usuario tras el veredicto de 1.2: diseñar la cascada de task2 desde cero
y luego remedir la confianza en las dos tareas. `forms_report.json` ya existe con 24
políticas medidas; esta fase sólo llena los tres huecos "n/d" de `confidence_score`.

### 1.3 [EJECUCIÓN] `RUNG_CEILING` para task2 + caché LOO honesto de task1

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

CONTEXTO — dos huecos distintos, no los mezcles

A) TASK2 no tiene cascada de peldaños. SÍ existe, ya medida, en
   delete_expert_modelate/task_two/expert_five/train_expert_five.py: una
   GuidelineCascade de tres nodos (chimera_experts/cascade_task2.py,
   node_targets). LOO ya medido, en
   delete_final_versions_task/task_2/experts_2/reports/expert_five_report.json:

     nodo    pregunta                          n   AUC     acierto  suelo_moda
     cancer  ¿hay cáncer confirmado?           72  0.9569  0.9722   0.8056
     treat   ¿indicado tratar?                 58  0.8739  0.8966   0.5690
     fit     ¿se beneficia del tratamiento?    33  0.5645  0.9394   0.9394   <- EN EL AZAR

   El nodo 'fit' tiene acierto == suelo_mayoritaria: cero información sobre la moda.
   Documentado así en el propio experto: "no es un fallo del modelo: es la medida de
   que la cohorte no contiene la evidencia para contestar esa pregunta".

   TAREA: en delete_final_versions_task/common/uncertainty_forms.py añade
   RUNG_CEILING_TASK2 siguiendo el MISMO patrON que RUNG_CEILING (task1), con
   tres peldaños (uno por nodo de la cascada) y techo derivado de estos AUC:
     - resuelto en 'cancer'  -> techo 'clear'      (AUC 0.957, muy por encima de clear_min_acc)
     - resuelto en 'treat'   -> techo 'borderline'  (AUC 0.874: sólido, pero un nivel de cascada
                                                      más abajo que 'cancer'; no lo iguales)
     - resuelto en 'fit'     -> techo 'uncertain'   (AUC en el azar, acierto == moda: no puede
                                                      salir 'clear' ni 'borderline' bajo ninguna
                                                      regla del modulo)
   Justifica por escrito en el docstring por qué 'treat' no llega a 'clear' aunque su
   acierto (0.8966) supere clear_min_acc=0.75: es la MISMA razón por la que task1 no
   iguala 'weighted_panel' a 'no_prior_biopsy' en RUNG_CEILING — un peldaño más abajo
   en la cascada hereda el error del peldaño anterior, y clear_min_acc solo mira su
   propio nodo, no la cadena.

B) TASK1: el caché llamado 'honest' usa 5 folds, no LOO, y la corrida final usa
   expertos ya ajustados con los etiquetados (hallazgo del propio Codex en el paso
   1.2, ver delete/plan_runs/run_1.2.log). measure_forms.py exige por
   --confidence-input un JSON con decision/rung/agreement/budget/training_case_ids/
   provenance/calibration por caso, LOO estricto y calibración interior sin fuga
   (docstring de measure_forms.py, líneas 1-19).

   TAREA: genera ese JSON para task1 recorriendo el protocolo real
   (delete_solution_one/solution_task_one_using_experts_final/protocol.py) en modo
   leave-one-out genuino: para cada caso exterior, entrena/ajusta sólo con los otros
   90, y dentro de esa calibración excluye también el caso interior que se está
   calibrando (LOO anidado, tal como exige el docstring). Es trabajo de cómputo, no
   de diseño: el protocolo y sus cuatro peldaños ya existen y están descritos arriba
   en la FASE 0 del plan original (líneas 122-177) y en protocol.py.

   Si el coste de un LOO anidado completo sobre 91 casos es excesivo (revisa antes de
   descartar: son 91 ajustes exteriores, cada uno con calibración sobre 90 casos —
   no 91²), repórtalo con el tiempo medido y decide con el usuario si se aproxima.
   No se publica una calibración con fuga etiquetada como 'honest'.

VERIFICACIÓN
- RUNG_CEILING_TASK2 tiene exactamente 3 entradas, con las claves de nodo
  ('cancer','treat','fit') y valores en {'clear','borderline','uncertain'}.
- Test nuevo: confidence_from_rung('fit', budget_cualquiera, {'fit': 0.94}) nunca
  devuelve 'clear' aunque el acierto pasado sea alto, porque el techo del peldaño
  lo prohíbe (verifica el mecanismo de techo, no sólo el número).
- Tras generar ambos JSON, relanza measure_forms.py con --confidence-input y
  confirma que confidence_score dejó de estar 'n/d' en las dos tareas.
- .venv/bin/python -m pytest -q sigue en verde.

NO HAGAS
- No inventes un JSON de calibración sin el LOO anidado real: el propio módulo
  levanta ValueError si detecta fuga (case_id de calibración fuera del conjunto
  permitido) — no lo esquives.
- No subas el techo de 'fit' a 'borderline' aunque el acierto crudo (0.9394) parezca
  alto: ese acierto ES el suelo de la moda, no evidencia del modelo.
```

### 1.4 [EJECUCIÓN] Confianza por CV anidada DECLARADA (sustituye al LOO exacto de 1.3B)

```
/codex:rescue

Repo: /home/jjlondono/PycharmProjects/chimera-agent-baseline

DECISIÓN TOMADA — no vuelvas a preguntar esto
Mediste el LOO anidado exacto en 169,83 h en serie (sin traza ni task2) y paraste a
preguntar, que era lo correcto. El usuario decide: **CV estratificada anidada,
declarada explícitamente**. NO es una excusa para relajar el rigor: es un cambio de
protocolo que se nombra en voz alta en todos los sitios donde aparezca el número.

PRECEDENTE QUE DEBES SEGUIR (ya existe en este repo)
delete_expert_modelate/task_two/expert_five/train_expert_five.py hace exactamente
esto para su escalera de fiabilidad, y lo declara así:
  "La escalera se mide con validación cruzada estratificada repetida y no con
   leave-one-out. El motivo es de coste y está medido... Las dos estimaciones son
   fuera de muestra; ésta entrena con el 75 % de los casos en vez del 98.6 %, así que
   si difiere será por ser algo más PESIMISTA, no al revés. Se declara en el informe
   para que nadie compare esta fila con las de los demás como si fueran la misma medida."
Copia ese espíritu literalmente: mismo tono, misma honestidad sobre la dirección del
sesgo.

PROTOCOLO
- Exterior: StratifiedKFold(n_splits=10, shuffle=True, random_state=0) sobre los 91
  etiquetados de task1 y los 72 de task2.
- Interior (calibración por peldaño): StratifiedKFold(n_splits=9) SOBRE EL CONJUNTO DE
  ENTRENAMIENTO EXTERIOR únicamente. El caso exterior nunca entra en el interior.
- Nombre del protocolo, literal, en todos los artefactos:
    "nested_stratified_cv_10x9"
  Prohibido escribir "loo", "leave_one_out" u "honest" en provenance para estas filas.

EL VALIDADOR ACTUAL TE VA A RECHAZAR — extiéndelo, no lo desactives
measure_forms.py::confidence_measurement exige hoy
    set(r["training_case_ids"]) == ids - {r["case_id"]}
y lo mismo para la calibración interior. Con 10x9 eso es falso por construcción y
levanta ValueError. Lo que hay que hacer:
  1. Añadir a cada registro un campo obligatorio "protocol" ("loo_estricto" o
     "nested_stratified_cv_10x9"). Sin ese campo -> ValueError, como ahora.
  2. Para "nested_stratified_cv_10x9" la comprobación pasa a ser, y sigue siendo dura:
       - r["case_id"] NOT IN r["training_case_ids"]                 (no se ve a sí mismo)
       - para cada c en r["calibration"]:
             c["case_id"] != r["case_id"]
             r["case_id"] NOT IN c["training_case_ids"]             (no hay fuga del exterior)
             c["case_id"] NOT IN c["training_case_ids"]             (no se ve a sí mismo)
       - len(set(r["training_case_ids"])) >= 0.6 * (len(ids) - 1)   (el pliegue es real,
         no un subconjunto degenerado)
     Es decir: se relaja la IGUALDAD de conjuntos, NO la ausencia de fuga.
  3. Mantén intacta la rama "loo_estricto" con la validación actual, para que un futuro
     cálculo exacto siga siendo verificable con el mismo módulo.
  4. Propaga "protocol" a la salida: cada fila de confidence_score y cada fila de
     escalera_fiabilidad lleva su protocolo. En forms_report.json debe poder leerse
     sin ambigüedad con qué protocolo se midió cada número.

TAREA
- Genera los JSON de --confidence-input para task1 y task2 con ese protocolo, usando
  las recetas de experto que ya benchmarkeaste (delete_final_versions_task/common/
  analysis/benchmark_nested_confidence.py te da los tiempos reales por ajuste).
- Paraleliza: la máquina tiene 28 núcleos y está a carga 0,4. Usa ProcessPoolExecutor
  con ~20 workers (deja margen: hay pasos de GPU corriendo en paralelo). Reporta el
  tiempo de pared real que tardó.
- Para task2 usa RUNG_CEILING_TASK2 y los tres nodos de la GuidelineCascade
  ('cancer','treat','fit'), que ya implementaste en 1.3.
- Relanza measure_forms.py con ambos --confidence-input y actualiza forms_report.json.

ACEPTACIÓN
- forms_report.json: confidence_score de task1 y task2 ya NO es null en las filas
  'agreement' y 'confidence_from_rung'; cada una declara protocol="nested_stratified_cv_10x9".
- La regla de adopción no cambia: confidence_from_rung sólo se adopta si bate a 'clear'
  Y a 'agreement'. Si no las bate, "adoptar": false con el motivo, como con todo lo demás.
- El techo de 'fit' sigue vigente: ningún caso resuelto en ese nodo puede salir 'clear'.
- Test nuevo: un registro con protocol="nested_stratified_cv_10x9" cuyo calibration
  contenga el case_id exterior en training_case_ids DEBE levantar ValueError (la
  protección contra fuga sigue viva bajo el protocolo nuevo).
- .venv/bin/python -m pytest -q en verde.

NO HAGAS
- No escribas "honest" ni "loo" en provenance de filas medidas con 10x9.
- No compares en la misma tabla, sin nota, una fila 10x9 con una fila LOO estricta.
- No relajes la comprobación de fuga: relajas la igualdad de conjuntos y nada más.
```
