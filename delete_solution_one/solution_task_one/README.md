# Pizarra en blanco — tarea 1 (decisión de biopsia)

> **Resultado medido** (evaluador oficial, juez desactivado, 91 casos
> etiquetados, temperatura 0, casos sin salida contados como fallo):
>
> | | referencia repo (T=1.0) | control (T=0) | corrida 1 | **corrida 2** |
> |---|---|---|---|---|
> | `ranking_score` | 0.6351 | 0.6428 | 0.6500 | **0.6749** |
> | sólo split `val` | — | 0.6585 | 0.6480 | **0.7126** |
>
> Prueba de signos por caso frente al control: 54 suben · 11 bajan · 26
> empatan · **p = 0.000**. 91/91 casos entregados, 0 respaldos, 0 números
> inventados en el texto libre. Detalle en
> [`runs/CORRECCIONES.md`](runs/CORRECCIONES.md) y en
> [`analysis/analysis_task1.ipynb`](analysis/analysis_task1.ipynb).

Solución alternativa al bucle ReAct del baseline. En lugar de **un** agente que
llama herramientas y rellena un formulario, aquí hay **una conversación entre
seis participantes** sobre una pizarra compartida: cada uno ve lo escrito hasta
su turno, aporta lo que su mandato le permite aportar, y sólo el último decide.

Todo vive en `delete_solution_one/solution_task_one/`. No modifica ni un byte
del upstream: importa `chimera_agent_baseline` (plantilla Jinja, cargador de
modelo, servidor MCP, `FeatureStore`, `run_predictor` y el esquema de salida) y
añade encima. Borrar `delete_solution_one/` deja el repositorio intacto.

---

## 1. El diseño

```
 START
   │
   ▼
 [1] INTAKE ─────────── el structured-prompt.json renderizado con la plantilla
   │                    upstream (templates/prompts/agent_prompt.j2), tal cual
   ▼
 [2] EXPERT-PRIOR ───── recomendador kNN sobre las 8 variables del prompt:
   │                    sugerencia A ± ΔA + el tramo operativo medido
   ▼
 [3] EXPERT-PROTOCOL ── el criterio EAU del cubo clínico de ESTE paciente, con
   │                    su acierto medido; se abstiene cuando el panel no decide
   ▼
 [4] LLM-1 GAP-ANALYST ─ sólo duda. Qué no puede ver el clasificador, por qué
   │   ⇅ search_guidelines  podría fallar, y qué documento resolvería qué duda
   ▼
 [5] LLM-2 EVIDENCE ──── el único que abre documentos. Recupera, cita valores
   │   ⇅ herramientas MCP  literales, y dice hacia dónde apunta la evidencia
   ▼
 [6] EXPERT-IMAGE ────── FeatureStore + run_predictor sobre los embeddings
   │                     congelados; declara explícitamente qué aporta (hoy: nada)
   ▼
 [7] LLM-3 CHAIR ─────── lee toda la pizarra, decide, y emite el formulario
   │                     validado contra Task1Output
   ▼
  END
```

Grafo LangGraph (`graph.py`) con dos sub-bucles ReAct independientes, cada uno
con su propia lista de mensajes y su propio presupuesto de rondas. **Lo que
viaja entre participantes es la pizarra, no el historial**: L2 no hereda la
conversación de L1, sólo su conclusión escrita. Es lo que hace que aporten
cosas distintas en vez de reforzarse mutuamente.

### Por qué cada participante existe

| Participante | Aporta algo que el resto no puede | Coste en la métrica |
|---|---|---|
| EXPERT-PRIOR | probabilidad calibrada out-of-fold (AUC 0.75, ECE 0.095) **con barra de error separada en aleatoria y epistémica** | 0 — no revela ninguna sección |
| EXPERT-PROTOCOL | el criterio clínico del cubo del paciente y su acierto medido; y, cuando el panel no determina el caso, lo dice en vez de callarse — ver [CRITERIO_DIAGNOSTICO.md](CRITERIO_DIAGNOSTICO.md) | 0 |
| LLM-1 | fuerza a nombrar lo que falta antes de recuperar nada; convierte "buscar todo" en "buscar esto por esta razón" | 0 — sólo `search_guidelines`, que no es una sección del formulario |
| LLM-2 | la evidencia real, con valores literales | lo que revele: `tool_score` es **precisión** |
| EXPERT-IMAGE | cierra la vía de imagen de forma explícita, para que el presidente no invente un apoyo que no existe | 0 |
| LLM-3 | la decisión, la confianza, los pesos y el texto libre | es lo único evaluado |

---

## 2. Reglas del reto que el diseño respeta

* **El esquema de salida es intocable.** `chimera_agent_baseline.output.schema`
  (`Task1Output`) es lo único bloqueado por el reglamento y es exactamente lo
  que valida la salida de L3, incluido el modelo dinámico por caso
  (`build_dynamic_model`) y la normalización a la forma completa.
* **Las dos entradas originales se mantienen.** `structured-prompt.json` entra
  íntegro por dos caminos: renderizado con la plantilla upstream para los LLM, y
  crudo al recomendador inicial. `prostate-...-clinical-data.json` sólo llega
  por herramientas MCP.
* **`reveal_sequence` no la escribe ningún LLM**: se deriva de los
  `ToolMessage` realmente ejecutados (`decide.reveal_sequence_from_messages`).
  Es honesta por construcción.
* **`tool_score` es precisión**, así que revelar de menos es gratis y revelar de
  más penaliza: L2 lleva la política de recuperación en su prompt.
* **`section_grounding_score`** exige que toda variable pesada por encima de
  `not_used` tenga su sección revelada: L3 sabe qué variable depende de qué
  documento.
* **Los embeddings no entran al contexto.** `FeatureStore` +`run_predictor`
  devuelven un escalar y una nota; los 1024 floats nunca se muestran.
* **Ningún caso se queda sin salida.** `decide.fallback_response` construye un
  registro válido de forma determinista si L3 no consigue emitir JSON válido.
  Un caso perdido cuesta doble en Grand Challenge: `case_score` 0 **y** recall
  en el F1 de su clase.
* **Sin red en tiempo de ejecución.** Todo (pesos, DB de guías, artefacto del
  recomendador) está en disco.

### Dos cosas que el diseño original pedía y no se pueden hacer en la tarea 1

1. **`get_pathology_report` no existe en la tarea 1.** El registro MCP
   `TASK1_TOOLS` no lo expone y
   `prostate-biopsy-decision-clinical-data.json` no tiene el campo: en esta
   tarea no hay informe de patología que recuperar. Además,
   `Task1Output.reveal_sequence` **no admite** el valor `"pathology_report"`,
   así que emitirlo invalidaría la salida. El estado de biopsia previa (`bx`)
   que sí está en el panel es toda la información de patología del caso, y se
   le dice explícitamente a la mesa en la entrada [1].
2. **`get_family_history` existe pero cuesta.** En los 91 casos etiquetados los
   urólogos revelaron la anamnesis familiar **cero veces**; cualquier llamada es
   una revelación "extra" que baja la precisión. El prompt de L2 se lo prohíbe
   explícitamente. La contrapartida es que `fh` deja de ser puntuable y se
   normaliza a `not_used`, lo que cuesta ~0.009 de `case_score` frente a los
   ~0.03 que costaría la llamada.

---

## 3. Cómo se corre

```bash
source .venv/bin/activate

# corrida completa sobre los 91 casos etiquetados
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one.run_task1 \
    --out-root delete_solution_one/solution_task_one/runs/run2 --prompts v2

# lo mismo pero en tmux, para que no se caiga si se pierde la sesión
delete_solution_one/solution_task_one/runs/launch_run2.sh
tmux attach -t chimera-run2        # Ctrl-b d para salir sin matarla

# sólo el split de desarrollo, o unos pocos casos
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one.run_task1 \
    --out-root .../runs/dev --split dev
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one.run_task1 \
    --out-root .../runs/probe --limit 3
```

Puntuar con el evaluador **oficial** (juez desactivado, casos sin salida
contados como fallo, que es lo que hace Grand Challenge):

```bash
python dev/score_local.py --tasks 1 --count-missing \
    --output-root delete_solution_one/solution_task_one/runs/run1/output
```

### Qué escribe

```
runs/<nombre>/
├── run_config.json              # modelo, temperatura, presupuestos, nº de casos
├── summary.jsonl                # una línea por caso: decisión, confianza,
│                                #   revelaciones, pesos, avisos, segundos
├── output/task1/<case_id>/      # ← lo que puntúa el evaluador
│   ├── prostate-biopsy-decision.json
│   └── prostate-biopsy-decision-reasoning.json
└── blackboards/<case_id>.json   # la pizarra completa, con payloads
    blackboards/<case_id>.md      #   y la versión legible
```

Las pizarras son el motivo por el que este diseño se puede depurar: cada
entrada dice quién habló, con qué mandato y qué escribió.

---

## 4. Mapa de ficheros

| Fichero | Qué contiene |
|---|---|
| `blackboard.py` | la pizarra: entradas tipadas, render para el prompt, volcado a disco |
| `prompts.py` | los tres prompts (L1/L2/L3), el marco de decisión por cubo y el esqueleto JSON |
| `prompts_v1.py` | los prompts de la corrida 1, congelados para poder reproducirla (`--prompts v1`) |
| `graph.py` | el grafo LangGraph con los dos sub-bucles ReAct |
| `decide.py` | derivación de `reveal_sequence`, parseo del JSON y respaldo determinista |
| `experts/initial_recommender.py` | adaptador del kNN A ± ΔA de `../recomendador_inicial` |
| `experts/protocol.py` | el criterio EAU por cubo clínico y su acierto medido |
| `experts/image_predictor.py` | `FeatureStore` + `run_predictor` |
| `run_task1.py` | runner: MCP, modelo, cola de casos, salidas y pizarras |
| `analysis/analysis_task1.ipynb` | comparación contra el baseline con el evaluador oficial |
| `analysis/diagnose.py` | comportamiento de una corrida: decisión por cubo, revelaciones, confianza, pesos, defectos de prompt |
| `analysis/criterio.py` | reproduce las medidas de `CRITERIO_DIAGNOSTICO.md` |
| `analysis/scoring.py` | envoltura del evaluador oficial (juez apagado) |
| `runs/CORRECCIONES.md` | qué se midió en la corrida 1 y qué se cambió para la 2 |
| `CRITERIO_DIAGNOSTICO.md` | los tres cubos clínicos y por qué uno de ellos es irreducible |
| `runs/launch_run2.sh` | lanza una corrida completa en tmux (sobrevive a desconexiones) |
