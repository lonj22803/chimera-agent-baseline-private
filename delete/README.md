# CHIMERA‑Agent — el reto explicado (para planear la solución)

> Documento de trabajo en `delete/`, fuera del árbol del upstream. Todo lo que
> se afirma aquí está leído del repositorio, de los datos de `data/`, del
> evaluador oficial (`~/PycharmProjects/CHIMERA-agent-eval/evaluation/evaluate.py`),
> del notebook [delete/exploratory_analysis.ipynb](delete/exploratory_analysis.ipynb)
> y de las páginas del reto. Cuando algo es una suposición, se dice.

---

## 0. Resumen en diez líneas

- El reto pide un **agente clínico**, no un clasificador: debe **decidir** y además **justificar** de forma auditable.
- Son **tres tareas** de cáncer de próstata sobre historia clínica sintética estilo EHR: biopsia sí/no, manejo terapéutico (4 clases), y tiempo hasta recurrencia bioquímica.
- Se entrega un **contenedor Docker** que Grand Challenge (GC) ejecuta **un caso por job**, sin internet, con los pesos dentro de la imagen.
- Cada caso entra como **3 JSON planos** en `/input` y debe salir como **2 JSON planos** en `/output` (predicción + razonamiento).
- La nota **no** es sólo acierto: en T1/T2 la decisión es una **puerta** (si fallas, el caso vale 0) y el resto de la nota mide la calidad del razonamiento estructurado.
- El uso de herramientas se puntúa como **precisión**: pedir de más penaliza, pedir de menos es gratis.
- T3 tiene **censura**: el 75 % de los casos no recurrió, y el ranking de T3 es el **c‑index** (ordenación), no el error absoluto en meses.
- El ranking global es la media ponderada **2 : 2 : 1** de los `ranking_score` de T1, T2 y T3.
- Lo único bloqueado por el reglamento es [src/chimera_agent_baseline/output/schema.py](src/chimera_agent_baseline/output/schema.py). Prompts, herramientas, grafo, modelo y hasta el entrypoint son libres.
- El baseline tal cual está hoy: **overall 0.5651** (T1 0.635 · T2 0.446 · T3 0.664) con el juez de razonamiento apagado.

---

## 1. En qué se basa el reto

### 1.1 Dos retos con nombre parecido — no confundirlos

| | CHIMERA (2025) | **CHIMERA‑Agent (este repo)** |
|---|---|---|
| URL | `chimera.grand-challenge.org` | `chimera-agent.grand-challenge.org` |
| Foco | Fusión multimodal (histología + radiología + transcriptómica), próstata y vejiga | **Razonamiento agéntico** sobre EHR de próstata |
| Tareas | T1 recurrencia próstata, T2 respuesta a BCG, T3 recurrencia vejiga | T1 biopsia, T2 tratamiento, T3 recurrencia post‑prostatectomía |
| Entrega | Predicción | **Predicción + traza de razonamiento estructurada** |
| Sede | MICCAI 2025 | MICCAI 2026 |

La URL que suele citarse (`chimera.grand-challenge.org`) describe el reto **anterior**. El que implementa este repositorio es **CHIMERA‑Agent**, y el baseline apunta explícitamente a `https://chimera-agent.grand-challenge.org/chimera-agent/`. Todo lo de abajo es de CHIMERA‑Agent.

### 1.2 La premisa clínica

La práctica real no es "un modelo, un dataset limpio, una predicción". Es **una secuencia de decisiones**, tomadas por especialistas distintos, en momentos distintos, **con la información que casualmente esté disponible**: modalidades ausentes, medidas longitudinales con espaciado irregular, y fuentes que a veces se contradicen.

De ahí las tres decisiones del pipeline urológico real, en orden temporal:

```
   PSA elevado / MRI                  Biopsia hecha                Prostatectomía hecha
          │                                 │                              │
          ▼                                 ▼                              ▼
   ┌─────────────┐                  ┌──────────────┐              ┌────────────────┐
   │  TAREA 1    │  ¿biopsiar?      │   TAREA 2    │  ¿qué manejo?│    TAREA 3     │ ¿cuándo recurre?
   │  pre‑biopsia│ ───────────────▶ │ post‑biopsia │ ───────────▶ │ post‑cirugía   │
   └─────────────┘   yes / no       └──────────────┘  1 de 4      └────────────────┘  meses + event
```

### 1.3 Lo que de verdad distingue a este reto

El agente tiene que **demostrar qué evidencia usó**, cómo manejó la información que falta o se contradice, y por qué llegó a esa decisión. El razonamiento se evalúa **contra los campos de entrada reales**: se penalizan hallazgos no soportados, contradictorios o alucinados. Un agente muy preciso que se invente la justificación **ranquea mal**.

El *ground truth* del razonamiento no es sintético: viene de **urólogos reales** que revisaron cada caso en un formulario estructurado (panel de datos clínicos visible + "Extended EHR view" enmascarada que se revelaba a demanda). Por eso el esquema de salida es tan raro: **reproduce el formulario del urólogo**, incluida la lista de secciones que fue destapando.

---

## 2. Las tres tareas

| | Tarea | Momento clínico | Entrada específica | Salida a evaluar | Peso |
|---|---|---|---|---|---|
| **T1** | Decisión de biopsia | Pre‑biopsia, sólo MRI | Informe mpMRI + variables clínicas (PSA, PI‑RADS, PSAD, DRE, csPCa…) | `"yes"` / `"no"` | **2** |
| **T2** | Estratificación / manejo | Post‑biopsia | T1 + patología de biopsia (Gleason/ISUP) + estadio cT | 1 de 4: `active_surveillance`, `continued_surveillance`, `watchful_waiting`, `active_treatment` | **2** |
| **T3** | Pronóstico de recurrencia | Post‑prostatectomía radical | Patología quirúrgica + biopsia + MRI + PSA | `months_to_recurrence` (float) + `event` (0/1) | **1** |

Notas clínicas que importan para el diseño:

- **T2 tiene cuatro clases, no dos.** `active_surveillance` (vigilancia activa: cáncer de bajo riesgo, seguimiento con intención curativa si progresa) vs `continued_surveillance` (continuar una vigilancia **ya iniciada**) es una distinción **de contexto temporal**, no de riesgo. El baseline no la hace nunca. `watchful_waiting` (esperar y ver, sin intención curativa, típico en comorbilidad alta / expectativa de vida corta) sólo tiene 2 casos etiquetados.
- **T3 no pregunta "cuándo recurre"** en el 75 % de los casos: pregunta *cuándo se le vio por última vez sin recurrencia*. Ver §4.3.

---

## 3. Los datos

### 3.1 Árbol local (el que usa `make run`)

```
data/
└── task<N>/
    ├── agent_input/<case_id>/
    │   ├── structured-prompt.json                                  # panel visible → prompt
    │   ├── <slug>-clinical-data.json                               # EHR enmascarado → herramientas MCP
    │   └── prostate-modality-level-neural-representations.json     # embeddings congelados
    └── ground_truth/<case_id>/                                     # etiquetas (sólo local; no va al contenedor)
```

Los `<slug>` por tarea:

| Tarea | Fichero clínico | Fichero de etiqueta |
|---|---|---|
| 1 | `prostate-biopsy-decision-clinical-data.json` | `prostate-biopsy-decision.json` + `…-reasoning.json` |
| 2 | `prostate-treatment-decision-clinical-data.json` | `prostate-treatment-decision.json` + `…-reasoning.json` |
| 3 | `prostate-time-to-recurrence-or-last-follow-up-clinical-data.json` | `prostate-time-to-recurrence-or-last-follow-up.json` |

### 3.2 Cuántos casos hay (medido en `data/`)

| Tarea | Casos con entrada | Casos **etiquetados** | Nota |
|---|---|---|---|
| T1 | 195 | **91** | ids `PT-pseudo_<hash>` |
| T2 | 153 | **72** | ids `T2-###` |
| T3 | 75 | **75** | ids `T3-###` |

238 casos etiquetados en total: eso es todo lo que hay para medir en local. Los ~204 casos sin etiqueta sirven para probar robustez y coste, no para puntuar.

### 3.3 Distribución de etiquetas (¡desbalanceo!)

| Tarea | Distribución |
|---|---|
| T1 | `yes` 56 · `no` 35 → predecir siempre "yes" da F1(yes) ≈ 0.76 y accuracy 0.62 |
| T2 | `active_treatment` 31 · `active_surveillance` 25 · `continued_surveillance` **14** · `watchful_waiting` **2** |
| T3 | `event=0` (censurado) **56** · `event=1` (recurrió) 19 → **74.7 % censura** |
| T3 | mediana de meses: 38.5 global, **6.2** en los que recurren (rango 1.3–110) |

La mediana de 6.2 meses en los recurrentes frente a 38.5 global es la asimetría clave de T3: los eventos ocurren **pronto**; los censurados aportan tiempos largos.

Confianza del urólogo en el ground truth: T1 `clear` 58 / `borderline` 18 / `uncertain` 15; T2 `clear` 58 / `borderline` 14 / `uncertain` 0.

### 3.4 `structured-prompt.json` — lo que el agente ve siempre

Registro plano, sin llamadas a herramientas. Tareas 1 y 2 comparten estructura (T2 añade los campos de biopsia); T3 es mucho más pobre.

**T1/T2** (`case_id`, `task`, `psa`, `age`, `months`, `pirads`, `psad`, `psav`, `psap`, `vol`, `cspca`, `dre`, `bx`, `medhx`, `meds`, `notes`, `pmhx`, `allergies`, `vitals{}`, `enc_*`, `note_sections[]`, social/admin; y en T2 además `ct`, `bx_isup`, `bx_gl_prim`, `bx_gl_sec`, `bx_gl_tert`).

**T3**: sólo `case_id`, `task`, `age`, `psa`, `dre`, `active_treatment_prior_to_surgery`. Ejemplo real:

```json
{"case_id": "T3-001", "task": 3, "age": 73, "psa": 86,
 "dre": "Digital rectal examination was abnormal on the right. The clinical T-stage … was cT2.",
 "active_treatment_prior_to_surgery": null}
```

**No hay campo `query`**: la pregunta la fija la plantilla [templates/prompts/agent_prompt.j2](templates/prompts/agent_prompt.j2), que es libre.

### 3.5 `*-clinical-data.json` — el EHR enmascarado (llega por herramientas)

Es el "Extended EHR view" del formulario: el agente **sólo lo ve si llama a la herramienta**. Un servidor **MCP** (stdio) lo sirve campo a campo.

| Herramienta | T1 | T2 | T3 | Devuelve |
|---|---|---|---|---|
| `get_psa_trend` | ✓ | ✓ | — | serie temporal de PSA |
| `get_lab_results` | ✓ | ✓ | — | panel de laboratorio completo |
| `get_mri_report` | ✓ | ✓ | ✓ | prosa del informe mpMRI |
| `get_pathology_report` | ✓ | ✓ | ✓ | prosa de la biopsia (T1: "no data" si no hay) |
| `get_surgical_pathology_report` | — | — | ✓ | prosa de la prostatectomía |
| `get_previous_notes` | ✓ | ✓ | ✓ | notas previas de MAP / urología |
| `get_family_history` | ✓ | ✓ | ✓ | antecedentes familiares de primer grado |
| `search_guidelines` | ✓ | ✓ | ✓ | RAG semántico sobre la guía EAU |

**Incompletitud medida** (sobre todos los casos con entrada): en T1 y T2 los cinco/seis campos están presentes y no vacíos en el 100 % de los casos. En **T3** faltan `previous_notes` en 30/75 y `family_history` en 23/75. Es decir: la "incompletitud" del reto está más en los valores centinela dentro del texto (`"Not reported"`, `"NA"`, `"Not done"`) y en la pobreza del prompt de T3 que en ficheros ausentes.

### 3.6 `prostate-modality-level-neural-representations.json` — los embeddings

Vectores congelados de modelos fundacionales, separados por origen. Las imágenes originales (mpMRI T2/ADC/DWI, WSI H&E) **no se distribuyen**: sólo estos vectores.

```jsonc
{
  "MRI image":           [[...1024 floats...]],       // 1 vector, las 3 tareas
  "Biopsy slide":        [[...960...], [...], [...]], // 1–3 vectores, T2 y T3
  "Prostatectomy slide": [[...960...], [...], [...]]  // 1–3 vectores, sólo T3
}
```

No deben entrar crudos al contexto del LLM. El camino previsto es construir un **predictor** encima y devolverle al agente un score compacto: [src/chimera_agent_baseline/features.py](src/chimera_agent_baseline/features.py) (`FeatureStore`) + [src/chimera_agent_baseline/tools/predictor.py](src/chimera_agent_baseline/tools/predictor.py) (`run_predictor`, hoy un *stub* apagado con `agent.predictor.enabled=false`).

El notebook ya sondeó la señal: **AUC ≈ 0.80** en validación cruzada para `active_treatment` vs resto en **T2**, ≈ 0.65 para el `event` de T3, y ≈ 0.41 (nada) en T1.

### 3.7 Dos artefactos de los datos locales que engañan

1. **Las 72 `reveal_sequence` del ground truth de T2 vienen vacías.** Por eso `tool_score` de T2 sale 0.0 en local: cualquier herramienta que llames es "extra". No optimices contra ese cero — en T1 la media es 3.13 revelaciones por caso y sólo 2/91 vacías.
2. **Casos sin etiqueta** (104 en T1, 81 en T2): si los cuentas, el denominador miente.

---

## 4. Cómo funciona la evaluación

Todo esto está leído de `evaluate.py` del repo de evaluación oficial. Es el mapa del tesoro: **la nota no es el acierto**.

### 4.1 T1 y T2 — la decisión es una PUERTA

```
   pred == None  ────────────────▶  gate = missing_candidate  →  case_score = 0
   schema inválido ──────────────▶  gate = schema_failed      →  case_score = 0
   decisión != ground truth ─────▶  gate = decision_failed    →  case_score = 0
   decisión correcta ────────────▶  se calculan los 5 componentes
```

Si la decisión falla, **no se calcula nada más**: confianza, pesos, factores, herramientas y grounding ni se miran. Acertar no es "una parte de la nota": es la **condición** para tener nota.

Si pasa la puerta, `case_score` es una combinación ponderada. **Los pesos cambian según esté el juez LLM activo o no**, y esto importa mucho:

| Componente | Con juez (`USE_RATIONALE_JUDGE=1`, **el default oficial**) | Sin juez (modo local determinista) |
|---|---|---|
| `variable_weight_score` | 0.25 | 0.275 |
| `confidence_score` | 0.20 | 0.225 |
| `rationale_score` (juez LLM) | **0.20** | — (redistribuido) |
| `important_decisive_factor_score` | 0.15 | 0.175 |
| `tool_score` | 0.15 | 0.150 |
| `section_grounding_score` | **0.05** | **0.175** |

> Consecuencia directa: un número medido en local (sin juez) **no es comparable** con el del leaderboard. Al apagar el juez, el grounding pasa de 0.05 a 0.175 — se multiplica por 3.5.

**Los seis componentes, uno a uno:**

- `confidence_score` = `1 − |conf_gt − conf_pred| / 2`, con `uncertain=0, borderline=1, clear=2`. Acertar la confianza vale 1.0, fallar por un escalón 0.5, por dos 0.0.
- `variable_weight_score` = `1 − media(|w_gt − w_pred|) / 3`, con `not_used=0, noted=1, important=2, decisive=3`, iterando **sobre las variables del ground truth**. Una variable que no predigas cuenta como `not_used`.
- `important_decisive_factor_score` = **F1 de conjuntos** entre `{variables con important|decisive}` del gt y las tuyas. Marcar de más y de menos penalizan igual.
- `tool_score` = **precisión** de las revelaciones: `|reveladas ∩ reveladas_por_el_urólogo| / |reveladas|`. **No revelar nada da 1.0.** Revelar de menos **no penaliza**. Se ignora el orden. Inventarse un nombre de sección cuenta como extra penalizado.
- `section_grounding_score` = `n_grounded / (n_grounded + n_ungrounded)` sobre las variables que pesaste por encima de `not_used`: una variable está "grounded" si su sección primaria aparece en tu `reveal_sequence`, o si es siempre disponible (`psa`, `age`). Las que no se pueden declarar (p. ej. `comorbidity`) se excluyen, no penalizan.
- `rationale_score` (juez): GEval con Ollama (`gemma4:e4b` por defecto) sobre tu `free_text`, comparado con el del urólogo. Puntúa alto si apoya la misma decisión, cita las mismas variables decisivas, no contradice los datos clínicos, **no inventa información** y expresa una incertidumbre coherente con la confianza declarada.

**El mapa exacto variable → sección → herramienta** (de `section_variable_mapping.json` del evaluador). Para poder pesar una variable por encima de `not_used` sin perder grounding, hay que haber llamado a la herramienta de su fila:

| Variable(s) | Sección primaria | Nombre en `reveal_sequence` | Herramienta que hay que llamar |
|---|---|---|---|
| `pirads`, `psad`, `cspca`, `vol`, `ct` | `section_s3-mri` | `radiology_report` | `get_mri_report` |
| `bx`, `bx_isup`, `bx_gl_prim`, `bx_gl_sec` | `section_s3-path` | `pathology_report` | `get_pathology_report` |
| `fh` | `section_s3-fh` | `family_history` | `get_family_history` |
| `dre` | `section_s3-labs` | `laboratory_results` | `get_lab_results` (sí, laboratorio: es lo que dice el mapa) |
| `psa` | `section_s3-psa` | `psa_trend` | ninguna — marcada `always_available` |
| `age` | — (sin secciones) | — | ninguna |
| `comorbidity` | `section_s3-comorb` | *no existe en el vocabulario* | **no puntuable**: se excluye del grounding |

Dos consecuencias finas:

- **`previous_notes` no aterriza ninguna variable.** Llamar a `get_previous_notes` sólo puede costar `tool_score`; nunca sube el grounding.
- **Trampa de T1**: `bx` se aterriza con `pathology_report`, pero `Task1Output.reveal_sequence` **no admite** ese valor y el mapeo herramienta→sección de T1 no lo incluye. Así que en T1, pesar `bx` por encima de `not_used` es un ungrounded garantizado. (El baseline lo hace en 1 de 194 casos, por eso su grounding sale 1.0.)

> **La tensión de diseño está aquí**: `tool_score` te dice "revela lo menos posible" y `section_grounding_score` te dice "no puntúes una variable cuya sección no revelaste". El óptimo no es llamar a todo ni a nada: es llamar **exactamente** a lo que vas a citar como importante.

**`ranking_score` de T1/T2** = `(mean_case_score + F1_de_la_tarea) / 2`, donde:
- T1 → F1 de la clase positiva `"yes"`.
- T2 → F1 ponderado por soporte sobre las cuatro clases.

`mean_case_score` se promedia **sobre todos los casos**, incluidos los que fallan la puerta (que valen 0) y los que no entregan (etiqueta centinela `__missing__`, que además cuesta recall a su clase verdadera en el F1). **Saltarse un caso difícil no es gratis.**

### 4.2 T3 — recurrencia bioquímica

```
   event_score  =  1.0 si event_pred == event_gt, si no 0.0
   time_score   =  censura‑aware (ver abajo)
   case_score   =  0.35·event + 0.35·time + 0.30·razonamiento   (con juez)
                =  0.50·event + 0.50·time                        (sin juez)
   ranking_score =  c‑index   ← SÓLO ESTO ranquea T3
```

`time_score`, con `scale = max(t_gt, 1)`:
- si `event_gt == 1`: `max(0, 1 − |t_pred − t_gt| / scale)` — hay que acertar el tiempo.
- si `event_gt == 0` (censurado): **si `t_pred ≥ t_gt` → 1.0**; si predices antes, `max(0, 1 − (t_gt − t_pred)/scale)`.

**El c‑index** usa los meses predichos como orden de riesgo (menos meses = más riesgo). Sólo son comparables los pares donde el sujeto que ocurre antes tiene `event=1`. Los empates suman 0.5 → **predecir una constante da exactamente 0.5**.

> La trampa de T3: predecir 60 meses a todo el mundo da `mean_case_score` ≈ 0.75 (frente a 0.54 del baseline), porque en los censurados basta con predecir tarde. Pero eso da **c‑index 0.5**, y el c‑index es lo único que ranquea. **Optimizar `mean_case_score` en T3 es optimizar el número equivocado.**

También se reporta AUC dependiente del tiempo a 12/24/36/60 meses, pero es diagnóstico: no entra en el ranking.

### 4.3 El número global

```
overall_ranking_score = (2·rank_T1 + 2·rank_T2 + 1·rank_T3) / 5
```

Está en el propio `evaluate.py` (`task_ranking_weights = {"task1": 2.0, "task2": 2.0, "task3": 1.0}`), no es una suposición del repo.

### 4.4 Las seis consecuencias prácticas

1. **La puerta domina.** En T1/T2, cada decisión fallada tira el caso entero. Es la palanca de mayor ganancia por unidad de esfuerzo.
2. **Un caso sin salida es peor que un caso mal contestado**: cuenta como fallo en el F1 *y* como `case_score` 0. Nunca abortar.
3. **Pedir de menos es gratis; pedir de más cuesta.** Herramienta que no vas a citar, herramienta que no llamas.
4. **T3 se ranquea por ordenación**, no por exactitud en meses.
5. **El `event` de T3 vale tanto como el tiempo** (0.35/0.35 con juez) y hoy el baseline lo tiene clavado a 0.
6. **El juez de razonamiento pesa 0.20 en T1/T2 y 0.30 en T3.** El texto libre no es decorativo: es el quinto y el tercer componente de la nota.

---

## 5. Qué recibe y qué debe entregar el Docker

### 5.1 Los dos modos de ejecución

| | Modo GC (el que cuenta) | Modo local / árbol completo |
|---|---|---|
| Invocación | GC lanza **un job por caso** | `make gc-test` monta todo `data/` |
| Entrada | `/input/` **plano** + `/input/inputs.json` | `/input/task<N>/agent_input/<case>/…` |
| Salida | `/output/` **plano**, 2 JSON | `/output/task<N>/<case>/…` |
| Quién adapta | [inference.py](inference.py) crea el árbol interno en un tmpdir y copia la salida de vuelta | `run.py` directamente |

### 5.2 Lo que recibe: contrato de entrada de GC

GC monta `/input` en **sólo lectura** y deja ahí `inputs.json`, que declara los *sockets*. El entrypoint identifica la tarea por la **tupla ordenada de slugs**:

| Interfaz | Slugs de entrada (ordenados) | Tarea |
|---|---|---|
| `interf0` | `prostate-biopsy-decision-clinical-data`, `prostate-modality-level-neural-representations`, `structured-prompt` | **1** |
| `interf1` | `prostate-modality-level-neural-representations`, `prostate-treatment-decision-clinical-data`, `structured-prompt` | **2** |
| `interf2` | `prostate-modality-level-neural-representations`, `prostate-time-to-recurrence-or-last-follow-up-clin`, `structured-prompt` | **3** |

Ejemplo real de `inputs.json` ([input/inputs.json](input/inputs.json)):

```json
[{"socket": {"slug": "structured-prompt",
             "relative_path": "structured-prompt.json",
             "is_json_kind": true, "is_file_kind": false},
  "file": null, "image": null, "value": null}, …]
```

Ojo: el **slug** de T3 está truncado a 50 caracteres (`…-follow-up-clin`) pero el **fichero en disco** se llama `prostate-time-to-recurrence-or-last-follow-up-clinical-data.json`. Los slugs y los nombres de fichero no son lo mismo.

Ejemplos de entrada listos para probar: [test/input/interf0/](test/input/interf0/), [test/input/interf1/](test/input/interf1/), [test/input/interf2/](test/input/interf2/).

### 5.3 Lo que debe entregar: contrato de salida

**Dos ficheros JSON planos en `/output`, por caso.** Uno con la predicción, otro con el razonamiento.

**Tarea 1** — `/output/prostate-biopsy-decision.json`:
```json
"yes"
```
(un string desnudo: `"yes"` o `"no"`)

`/output/prostate-biopsy-decision-reasoning.json`:
```jsonc
{
  "confidence": "clear",                       // clear | borderline | uncertain
  "variable_weights": {                        // not_used | noted | important | decisive
    "age": "important", "fh": "noted", "cspca": "not_used", "pirads": "important",
    "vol": "noted", "psa": "noted", "comorbidity": "noted", "psad": "not_used",
    "dre": "noted", "bx": "decisive"
  },
  "reveal_sequence": ["family_history", "previous_notes", "laboratory_results",
                      "psa_trend", "radiology_report"],   // el orden no importa
  "free_text": "…los 2‑4 factores que dirigen la decisión…"
}
```

**Tarea 2** — `/output/prostate-treatment-decision.json`:
```json
"active_surveillance"
```
(`active_surveillance` | `continued_surveillance` | `watchful_waiting` | `active_treatment`)

`/output/prostate-treatment-decision-reasoning.json`: misma forma, con las variables de T2 (`ct`, `fh`, `age`, `psa`, `psad`, `cspca`, `pirads`, `bx_isup`, `bx_gl_sec`, `bx_gl_prim`, `comorbidity`) y `reveal_sequence` que además admite `pathology_report`.

**Tarea 3** — `/output/prostate-time-to-recurrence-or-last-follow-up.json`:
```json
{"months_to_recurrence": 65.7, "event": 0}
```
`/output/prostate-time-to-recurrence-or-last-follow-up-reasoning.json`:
```json
"El tiempo estimado se basa en …"
```
(un string desnudo, no un objeto)

**Vocabulario de `reveal_sequence`** (los seis nombres planos que reconoce el evaluador; cualquier otro cuenta como revelación extra penalizada):
`previous_notes`, `laboratory_results`, `psa_trend`, `radiology_report`, `pathology_report`, `family_history`.

En el baseline, `reveal_sequence` **no la escribe el LLM**: se deriva automáticamente de las herramientas realmente llamadas ([src/chimera_agent_baseline/agent/form_fill.py:280](src/chimera_agent_baseline/agent/form_fill.py#L280)). Eso es bueno — es honesto por construcción — y hace que el `tool_score` dependa directamente del comportamiento del agente, no de lo que diga.

> **Punto a verificar antes de subir**: el evaluador acepta dos grafías para los slugs de salida de T1 (`prostate-biospy-decision` con la errata, y `prostate-biopsy-decision`) y dos para el de razonamiento de T3 (`…-reas` truncado y `…-reasoning`). El contenedor escribe hoy las grafías **correctas**. Hay que confirmar en la página del algoritmo en GC cuál es el slug exacto del socket de salida; si GC espera `prostate-biospy-decision.json`, el fichero tiene que llamarse así.

### 5.4 Restricciones del entorno de ejecución

| Restricción | Detalle |
|---|---|
| **Sin internet** | Todo (pesos, dependencias, DB vectorial) debe estar dentro de la imagen o del tarball del modelo. |
| **GPU** | NVIDIA **T4 16 GB** o **A10G 24 GB**; 16 o 32 GiB de RAM según instancia. Gemma‑4‑E2B (~10 GB bf16) cabe; algo mayor exige cuantización. |
| **`/input` es read‑only** | El contenedor no puede escribir ahí. Por eso `inference.py` usa un `tempfile.TemporaryDirectory`. |
| **Usuario no root** | El Dockerfile crea `user` y hace `USER user`. |
| **Plataforma** | `--platform=linux/amd64` obligatorio. |
| **Un caso por job** | ⚠️ **Se paga la carga del modelo en cada caso.** vLLM + Gemma + servicio de embeddings arrancan y mueren por caso. Es el mayor riesgo de coste/tiempo del diseño actual. |

### 5.5 Cómo se empaqueta y se prueba

```bash
make gc-build                 # docker build --platform=linux/amd64
make gc-test                  # monta data/ en /input:ro y test/output en /output
./do_test_run.sh              # el flujo GC de verdad: interf0/1/2, un caso plano cada uno
make gc-save                  # o ./do_save.sh → imagen .tar.gz + model.tar.gz
```

**El modelo va aparte.** `do_save.sh` empaqueta `model/` en `model.tar.gz` y hay que subirlo a GC como **Model** separado del algoritmo; GC lo extrae en `/opt/ml/model` en tiempo de ejecución. Rutas que el contenedor da por hechas ([inference.py](inference.py)):

| Ruta en el contenedor | Contenido |
|---|---|
| `/input`, `/output` | datos del caso |
| `/opt/app/configs/config.yaml` | config Hydra |
| `/opt/app/resources` | DB de guías EAU (ChromaDB) |
| `/opt/ml/model/gemma-4-E2B-it` | pesos del LLM |
| `/opt/ml/model/embedding_model` | `embeddinggemma-300m` para el RAG |

Si `resources/embedding_model/` no está en disco **antes** de `make gc-build`, `search_guidelines` devuelve resultados vacíos **en silencio**.

---

## 6. Reglas del reto que condicionan el diseño

- **No se entrena desde cero.** Se espera orquestar herramientas y modelos ya entrenados ("agent-level reasoning systems, not train models from scratch"). Entrenar una cabeza ligera sobre los embeddings congelados **sí** encaja: es justamente el punto de extensión que el baseline documenta.
- **Modelos y datos externos permitidos** si son públicos, con licencia abierta que permita su uso en la submission, y **declarados** en el nombre/página del algoritmo y en el paper.
- **Sin internet en el contenedor.**
- **Entregables**: contenedor Docker + **paper de 6 páginas** (plantilla MICCAI Springer LNCS, sin contar referencias) + repositorio GitHub con licencia permisiva. **Sin el paper no entras en el ranking final.**
- **Submissions**: hasta **5** en validación (cuenta la mejor), **1 sola** en test.
- **Equipos obligatorios** (aunque sean de una persona), sin cuentas duplicadas ni participación anónima en los leaderboards.
- **Guía EAU 2026**: se pueden usar recomendaciones seleccionadas y reglas de decisión derivadas, **sólo** para investigación no comercial dentro de CHIMERA‑Agent, **sin redistribuir** el documento original, y **citándola**. El `resources/guidelines_db` del repo ya es un uso licenciado.
- **Embargo de publicación** sobre resultados del training set hasta que salgan el paper del reto y el del baseline.
- **Premios sólo para submissions open‑source.**

---

## 7. Qué está bloqueado y qué es libre

| | Fichero / zona | Estado |
|---|---|---|
| 🔒 | [src/chimera_agent_baseline/output/schema.py](src/chimera_agent_baseline/output/schema.py) | **Lo único bloqueado.** La salida debe validar contra `Task1Output` / `Task2Output` / `Task3Output`. `extra="forbid"`, `reasoning` con `min_length=40`. |
| ✅ | prompt de sistema, [templates/prompts/agent_prompt.j2](templates/prompts/agent_prompt.j2) | libre |
| ✅ | herramientas ([src/chimera_agent_baseline/tools/definitions.py](src/chimera_agent_baseline/tools/definitions.py)) | libre: añadir `ToolSpec` a `TASK1_TOOLS`/`TASK2_TOOLS`/`TASK3_TOOLS` |
| ✅ | grafo LangGraph, `form_fill`, `run.py`, `inference.py` | libre |
| ✅ | modelo, `configs/`, overlays de experimento | libre |
| ✅ | `predictor.py` / `run_predictor` | libre — es **el** punto de extensión previsto para los embeddings |
| ⚠️ | Renombrar/quitar una herramienta que respalda una variable (`fh → get_family_history`) hace esa variable no puntuable | cuidado |

**Sólo se evalúa la salida estructurada final. El uso de herramientas no se puntúa como tal** — pero sí entra en la nota a través de `tool_score` y `section_grounding_score`, que se calculan sobre la `reveal_sequence` que las llamadas producen.

---

## 8. Dónde está el baseline hoy (línea base medida)

Baseline sin modificar (Gemma‑4‑E2B‑it en vLLM, `temperature 1.0`, `max_iterations 25`, predictor apagado), evaluador oficial, **juez desactivado**, casos etiquetados sin salida contados **como fallo** ([dev/baseline_reference.json](dev/baseline_reference.json)):

| | n | `mean_case_score` | Puerta | F1 | **`ranking_score`** |
|---|---|---|---|---|---|
| T1 | 91 | 0.4815 | 67.0 % | 0.789 (yes) | **0.6351** |
| T2 | 72 | 0.3691 | 56.9 % | 0.522 (ponderado) | **0.4458** |
| T3 | 75 | 0.5419 | — | c‑index 0.664 | **0.6636** |
| | | | | | **OVERALL 0.5651** |

**Patologías conocidas** (de la §6 del notebook):

| # | Síntoma | Causa | Dónde se arregla |
|---|---|---|---|
| 1 | T1 no descarta nunca: recall 1.00 en `yes`, **0.14** en `no` | prompt sin criterio de descarte | plantilla / prompt |
| 2 | T2 colapsa 4 clases en 2: nunca predice `continued_surveillance` (14 casos) ni `watchful_waiting` (2) | el prompt no define las cuatro clases | plantilla / prompt + RAG EAU |
| 3 | T3 `event` **constante 0** — el 0.74 de `event_score` es la tasa base de censura, no una predicción | `Task3Output` no tiene campo `event` y `run.py` usa `structured.get("event", 0)` | **`run.py`**, sin tocar el schema |
| 4 | El prompt de T3 nunca explica la censura (75 % de los casos) | plantilla Jinja | 3 frases en la plantilla |
| 5 | Dos casos de T3 sin salida (`T3-038`, `T3-063`) | `form_fill` prefiere lanzar excepción antes que entregar algo inválido; en GC eso es un caso perdido | valor de respaldo en `form_fill.py` + `try/except` en el bucle |
| 6 | Los embeddings no se abren nunca | `predictor.enabled=false`, `run_predictor` es un stub | `tools/predictor.py` |
| 7 | El agente pide más herramientas de las que pedía el urólogo | `tool_score` es precisión | prompt de sistema |
| 8 | `temperature = 1.0` → el mismo caso falla o no según la tirada | `configs/config.yaml` | bajar temperatura / fijar semilla |
| 9 | No hay trazabilidad persistida: mensajes, resultados de herramientas y reintentos se descartan | `run.py` sólo guarda los dos JSON | callback en `ainvoke` |

---

## 9. Palancas para planear la solución

Ordenadas por **puntos por unidad de esfuerzo**, según lo que dice la métrica:

**Nivel 0 — robustez (barato, no toca el razonamiento).**
Ningún caso sin entregar: valor de respaldo válido en `form_fill` y `try/except` en el bucle de `run.py`. Un caso sin salida cuesta doble (case_score 0 **y** recall en el F1). Verificar además el nombre exacto de los ficheros de salida contra los sockets de GC.

**Nivel 1 — la puerta de T1/T2 (aquí están los puntos).**
El 43 % de T2 y el 33 % de T1 se pierden ahí, y arrastran los cinco componentes de razonamiento con ellos. Trabajo: reglas EAU/NCCN explícitas para las cuatro clases de T2 en el prompt (con la distinción `active_surveillance` vs `continued_surveillance`, que hoy no existe), criterio de descarte en T1, y apoyarse en el RAG que ya está licenciado. Considerar además un router/clasificador determinista sobre las variables estructuradas como segunda opinión.

**Nivel 2 — T3: `event` y ordenación.**
(a) Derivar `event` en `run.py` sin tocar el schema — vale 0.35 de la nota del caso y hoy es constante. (b) Explicar la censura en la plantilla. (c) Recordar que **lo que ranquea es el c‑index**: lo que hay que producir es un **orden de riesgo** consistente, no un número de meses bonito.

**Nivel 3 — el predictor sobre embeddings.**
`run_predictor` devolviendo un score compacto como herramienta MCP. La sonda dice por dónde: **T2 primero** (AUC ≈ 0.80 justo en el corte que hoy falla), T3 después (≈ 0.65, y una cabeza de riesgo ataca directamente el c‑index), **T1 no** (≈ 0.41). Ojo con la regla: no se entrena desde cero, pero una cabeza ligera sobre embeddings congelados es exactamente lo que el baseline documenta como extensión — declararlo en el paper.

**Nivel 4 — economía de herramientas y grounding.**
Política explícita: llamar sólo a lo que se va a citar como `important`/`decisive`. Alinea `tool_score` (precisión) con `section_grounding_score` (lo que pesas debe estar revelado). Con el juez activo el grounding sólo vale 0.05, así que **la prioridad real es `tool_score` (0.15) y el `free_text` (0.20)**.

**Nivel 5 — calidad del `free_text`.**
Con el juez activo vale 0.20 en T1/T2 y 0.30 en T3. La rúbrica premia: apoyar la misma decisión, citar las mismas variables decisivas, no contradecir los datos, **no inventar**, y una incertidumbre coherente con `confidence`. Un texto genérico y agnóstico del caso puntúa bajo por definición.

**Nivel 6 — instrumentación.**
Persistir la traza (mensajes, tool calls, reintentos de `form_fill`) para poder medir **por qué** falla cada caso, no sólo cuánto. Un callback en `ainvoke` lo resuelve sin tocar el upstream.

**Transversal — coste por caso.** GC ejecuta un job por caso: la carga de vLLM + Gemma + el servicio de embeddings se paga entera cada vez. Cualquier diseño que añada pasos (auto‑consistencia, varias pasadas, ensemble) multiplica ese coste. Medir el tiempo por caso en `do_test_run.sh` antes de comprometerse.

---

## 10. Cómo medir sin engañarse

```bash
python dev/score_local.py                       # todo test/output/
python dev/score_local.py --split val           # sólo el split de validación
python dev/score_local.py --tasks 2 --count-missing
```

[dev/score_local.py](dev/score_local.py) **importa** el `evaluate.py` oficial en vez de reimplementarlo: si los organizadores cambian los pesos, el script cambia con ellos.

Cinco formas fáciles de medir mal:

1. **Excluir los casos sin salida** → número optimista. Usar siempre `--count-missing`: es lo que hace GC.
2. **Comparar un número con juez contra uno sin juez.** Apagar el juez **redistribuye** los pesos (grounding ×3.5). No son comparables.
3. **Optimizar `mean_case_score` en T3.** Lo que ranquea es el c‑index.
4. **Optimizar el `tool_score` de T2 en local.** Sale 0 por un artefacto (las 72 `reveal_sequence` del gt están vacías).
5. **Comparar corridas con `temperature = 1.0`.** El mismo caso falla o no según la tirada. Fijar temperatura/semilla o promediar varias corridas antes de declarar una mejora.

Usar los splits de [dev/splits/](dev/splits/) (`dev` para iterar, `val` para confirmar) y no mirar `val` hasta el final.

---

## 11. Checklist antes de subir

- [ ] El contenedor construye con `--platform=linux/amd64` y arranca como usuario no root.
- [ ] `./do_test_run.sh` produce las **dos** salidas correctas en `test/output/interf0`, `interf1` e `interf2`.
- [ ] Los **nombres de fichero de salida coinciden con los slugs de los sockets** de la página del algoritmo en GC (¡ojo a `biospy` y a `-reas`!).
- [ ] Ningún caso queda sin salida, ni siquiera con entradas degeneradas (campos `null`, textos vacíos).
- [ ] La salida valida contra `Task1Output`/`Task2Output`/`Task3Output`, `reasoning` ≥ 40 caracteres.
- [ ] `reveal_sequence` usa sólo los seis nombres del vocabulario.
- [ ] `resources/embedding_model/` estaba en disco **antes** del build (si no, el RAG está mudo).
- [ ] `model.tar.gz` subido como Model separado, y las rutas `/opt/ml/model/...` coinciden.
- [ ] Sin ninguna llamada de red en tiempo de ejecución.
- [ ] Tiempo y memoria por caso medidos en una GPU equivalente a T4 16 GB (el peor caso de la plataforma).
- [ ] Todo modelo/dato externo declarado en el nombre del algoritmo, su página y el paper.
- [ ] Paper de 6 páginas (LNCS) y repo con licencia permisiva preparados.

---

## 12. Las herramientas ya entrenadas que da el reto (y cómo usarlas)

El reto dice literalmente que entrega *"A set of pretrained, modality-specific tools including MRI prostate zone segmentation, automated Gleason grading for biopsy and prostatectomy specimens, and MRI-based csPCa detection"*, y que *"Participants may use these tools and variables as-is, replace them, or combine them with additional publicly available models"*.

Conviene separar **tres familias** que se confunden con facilidad, porque se usan de formas completamente distintas:

| Familia | Qué es | Cómo se usa |
|---|---|---|
| **A. Modelos de imagen preentrenados** | Los tres de la cita: segmentación zonal, Gleason automático, detección de csPCa — más los modelos fundacionales que produjeron los embeddings | **No se ejecutan**: sus salidas ya vienen precalculadas en los datos. Se consumen |
| **B. Herramientas clínicas del baseline (MCP)** | Las 7 `get_*` + `search_guidelines` | Se **llaman en tiempo de ejecución** por el agente |
| **C. Modelos y conocimiento dentro de la imagen** | Gemma‑4‑E2B‑it, embeddinggemma‑300m, la DB de guías EAU | Se **cargan** al arrancar el contenedor |

> ⚠️ **La confusión más cara**: la familia A **no es invocable**. Las imágenes originales (mpMRI T2/ADC/DWI y las WSI H&E) **no se distribuyen**. Nadie te va a dar un endpoint de segmentación al que mandarle un volumen. Lo que tienes son sus **resultados ya calculados**, en dos formas: **variables estructuradas** y **embeddings congelados**.

### 12.1 Familia A — los modelos de imagen preentrenados y dónde aterriza su salida

| Herramienta preentrenada | Qué hace clínicamente | Dónde llega su salida en los datos | Tareas |
|---|---|---|---|
| **Segmentación zonal de próstata en MRI** | Delimita próstata y zonas (periférica/transición) para medir el volumen | `vol` (mL) en `structured-prompt.json`; y de ahí `psad` — verificado: `4.7 / 33.46 = 0.14` | 1, 2 |
| **Detección de csPCa en MRI** | Probabilidad DL de cáncer clínicamente significativo (ISUP ≥ 2) | `cspca` (0–1) en `structured-prompt.json` | 1, 2 (**en T3 no existe**) |
| **Gleason automático en biopsia** | Grado de Gleason / ISUP sobre la WSI de biopsia | `bx_gl_prim`, `bx_gl_sec`, `bx_gl_tert`, `bx_isup` (T2) y la prosa de `pathology_report` | 2, 3 |
| **Gleason automático en prostatectomía** | Grado sobre la WSI de la pieza quirúrgica | prosa de `surgical_pathology_report` | 3 |
| **Modelos fundacionales de imagen** | Codifican MRI y WSI en vectores | `prostate-modality-level-neural-representations.json` (MRI 1024‑d; portaobjetos 960‑d) | 1, 2, 3 |

Matices que importan:

- **PI‑RADS no es DL**: es la lectura del radiólogo, sale del informe. `cspca` sí es "DL‑generated", y son señales **independientes** — cuando discrepan, ahí hay información.
- **`psad` ya viene calculado**, pero depende de `vol`, que viene de la segmentación. Si `vol` falta, `psad` es sospechoso.
- **La página oficial no publica los nombres, arquitecturas ni enlaces** de estos modelos. Si necesitas citarlos en el paper, hay que preguntarlo en el foro del reto o a `nadieh.khalili@radboudumc.nl`. No los inventes.

**Cobertura real de los embeddings** (medida sobre `data/`, no supuesta):

| Tarea | Fichero presente | `MRI image` | `Biopsy slide` | `Prostatectomy slide` |
|---|---|---|---|---|
| T1 | **191 / 195** | 191 (1 vector, 1024‑d) | — | — |
| T2 | 153 / 153 | **149** (1024‑d) | **147** (960‑d; 1 vec ×18, 2 ×46, 3 ×83) | — |
| T3 | 75 / 75 | 75 (1024‑d) | **51** (960‑d) | 75 (960‑d; 1 vec ×31, 2 ×29, 3 ×15) |

Es decir: **4 casos de T1 no tienen ni el fichero**, 4 casos de T2 no tienen MRI y 6 no tienen biopsia, y 24 casos de T3 no tienen biopsia. Cualquier predictor tiene que tolerar el vacío — `FeatureStore.get()` devuelve `{}` y `get_origin()` devuelve `[]`, así que el fallo es silencioso y hay que decidir explícitamente qué hacer.

### 12.2 Cómo usar la familia A

**Vía 1 — como variables (ya está hecho).** `cspca`, `vol`, `psad`, `bx_isup`, `bx_gl_*` ya se renderizan en el prompt vía [templates/prompts/agent_prompt.j2](templates/prompts/agent_prompt.j2). Lo que hay que decidir es **cómo pesarlas**, no cómo obtenerlas. Recuerda §4.1: para puntuar `cspca`, `pirads`, `psad`, `vol` o `ct` por encima de `not_used` sin perder grounding hay que haber llamado a `get_mri_report`; para los `bx_*`, a `get_pathology_report`.

**Vía 2 — como embeddings, detrás de un predictor.** Es el punto de extensión que el baseline documenta, y hoy está apagado.

```bash
make run RUN_ARGS="agent.predictor.enabled=true agent.tasks=[2]"
```

Eso registra un `get_image_predictor(case_id)` en el servidor MCP, que carga los vectores por `FeatureStore`, llama a `run_predictor` y devuelve **sólo** un dict compacto — nunca los vectores. Lo único que hay que escribir es la cabeza, en [src/chimera_agent_baseline/tools/predictor.py](src/chimera_agent_baseline/tools/predictor.py):

```python
# src/chimera_agent_baseline/tools/predictor.py
_MODEL = None

def run_predictor(features: dict[str, list[list[float]]]) -> dict:
    global _MODEL
    if _MODEL is None:                      # carga perezosa: una sola vez por proceso
        import joblib
        _MODEL = joblib.load("/opt/ml/model/heads/t2_active_treatment.joblib")

    # OJO: las claves son las del JSON, no 'mri' / 'biopsy' / 'prostatectomy'
    mri    = features.get("MRI image", [])
    biopsy = features.get("Biopsy slide", [])
    if not mri:
        return {"prediction": None, "detail": "sin embedding de MRI para este caso"}

    import numpy as np
    x = np.concatenate([
        np.asarray(mri[0]),                                   # 1024‑d
        np.mean(np.asarray(biopsy), axis=0) if biopsy else np.zeros(960),  # 960‑d agregado
    ])
    p = float(_MODEL.predict_proba(x.reshape(1, -1))[0, 1])
    return {"risk_active_treatment": round(p, 3),
            "interpretation": "alto" if p > 0.6 else "bajo" if p < 0.3 else "intermedio"}
```

> **Bug latente que te va a morder**: el docstring de `run_predictor` dice que las claves son `mri` / `biopsy` / `prostatectomy`, pero [features.py](src/chimera_agent_baseline/features.py) normaliza con `FEATURE_ORIGINS = ("MRI image", "Biopsy slide", "Prostatectomy slide")` — los nombres literales del JSON. Si escribes `features["mri"]` no falla ruidosamente: simplemente no encuentra nada.

Cuatro reglas al entrenar la cabeza:

1. **Offline y fuera del contenedor.** Entrena con los 238 casos etiquetados, guarda el artefacto en `model/` (va dentro de `model.tar.gz`) y cárgalo perezosamente. En el contenedor no hay red.
2. **Con los splits de [dev/splits/](dev/splits/)**, no con todo. Si entrenas sobre `val` y luego mides en `val`, el número es tuyo y de nadie más.
3. **Sin fuga**: el predictor devuelve un escalar o una etiqueta. Los vectores crudos no entran al contexto del LLM (además de que 1024 floats en el prompt son ~4k tokens de ruido).
4. **Declararlo en el paper.** La regla es "no entrenar desde cero"; una cabeza ligera sobre embeddings congelados es exactamente la extensión que el baseline documenta, pero hay que decirlo.

**Dónde apunta la evidencia** (sonda del notebook, §4.8): **T2 primero** — AUC ≈ 0.80 en CV para `active_treatment` vs resto, justo el corte que hoy falla el 43 % de las veces. **T3 después** — ≈ 0.65 sobre `event`, y ahí una cabeza de riesgo ataca directamente el c‑index, que es lo único que ranquea T3. **T1 no** — ≈ 0.41, es ruido.

**Vía 3 — leer los embeddings a mano**, para analizar o entrenar:

```python
from chimera_agent_baseline.features import FeatureStore, FEATURE_ORIGINS_BY_TASK

fs = FeatureStore("data/task2/agent_input")
fs.list_case_ids()                              # casos que SÍ tienen fichero
fs.get("T2-004")                                # {"MRI image": [[...]], "Biopsy slide": [[...], ...]}
fs.get_origin("T2-004", "Biopsy slide")         # [] si falta, sin excepción
FEATURE_ORIGINS_BY_TASK[3]                      # ("MRI image", "Biopsy slide", "Prostatectomy slide")
```

### 12.3 Familia B — las herramientas clínicas del baseline (MCP)

Ya están implementadas y funcionando; la tabla de cuál existe en cada tarea está en §3.5. Lo relevante para planear:

- Se sirven por **MCP sobre stdio** ([src/chimera_agent_baseline/mcp_server.py](src/chimera_agent_baseline/mcp_server.py)), un subproceso por tarea. Son agnósticas del framework: si cambias LangGraph por otra cosa, las herramientas siguen valiendo.
- Cada `get_*` es declarativa: un `ToolSpec` con `name`, `description` y los campos del `*-clinical-data.json` que devuelve.

**Probarlas sueltas, sin GPU ni LLM:**

```bash
python -m chimera_agent_baseline.mcp_server \
    --data-dir data/task2/agent_input \
    --resource-dir resources \
    --tool-registry task2 \
    --enable-predictor
```

**Añadir una herramienta propia** — en [src/chimera_agent_baseline/tools/definitions.py](src/chimera_agent_baseline/tools/definitions.py):

```python
MY_TOOL = ToolSpec(
    name="get_my_data",
    description="Retrieve my custom data for a patient case.",
    fields=("my_field", "another_field"),   # claves de *-clinical-data.json
)
TASK2_TOOLS.append(MY_TOOL)                 # o añadirlo a la lista literal
```

El servidor la recoge sola. Para herramientas que no siguen el patrón "devuelve un campo precalculado" (una llamada a un modelo, un cálculo), se registran con `@mcp.tool()` directamente en `mcp_server.py`, como hacen `search_guidelines` y `get_image_predictor`.

Tres avisos:

1. **Cambiar la `description` es una palanca real**: es lo que el LLM lee para decidir si la llama, y `tool_score` es precisión. Una descripción que diga cuándo *no* usarla vale tanto como una que diga cuándo sí.
2. **No renames sin pensar.** `output/schema.py` mapea `fh → get_family_history`; si renombras o quitas esa herramienta, la variable deja de ser puntuable.
3. **Añadir una herramienta nueva no añade una revelación nueva.** El vocabulario de `reveal_sequence` son seis nombres fijos (§5.3). Una herramienta nueva no aparece ahí — así que **no cuesta `tool_score` ni suma grounding**. Eso la hace barata: una herramienta de cálculo (p. ej. una calculadora de riesgo EAU sobre las variables que ya están en el prompt) es *gratis* desde el punto de vista de la métrica.

### 12.4 Familia C — modelos y conocimiento dentro de la imagen

| Recurso | Qué es | Dónde | Cómo se usa |
|---|---|---|---|
| **Gemma‑4‑E2B‑it** | LLM del baseline (~10 GB bf16), servido por vLLM en proceso | `/opt/ml/model/gemma-4-E2B-it` | `model.provider=vllm`, `model.tool_parser=gemma4`. Se cambia por config, sin tocar código |
| **embeddinggemma‑300m** | Modelo de embeddings del RAG (768‑d), en **CPU**, en un proceso aparte por socket Unix para no competir por la VRAM | `/opt/ml/model/embedding_model` | Se arranca solo (`start_embedding_service`) |
| **DB de guías EAU** | ChromaDB, colección `guidelines`, **1501 chunks**, 768‑d — es la *EAU Prostate Cancer Guidelines* (Cornford et al.) troceada | `/opt/app/resources/guidelines_db` | Herramienta `search_guidelines(query)`, top‑k 5 |

```python
search_guidelines("active surveillance criteria for ISUP grade group 1 prostate cancer")
# -> {"query": ..., "results": [{...chunk, section, page, score...}, ...]}   (5 pasajes)
```

Cuatro cosas que hay que saber del RAG:

- **Es la única fuente de conocimiento clínico licenciada** que el reto te da. Su uso está permitido para investigación no comercial dentro de CHIMERA‑Agent, sin redistribuir la guía, y **citándola** (§6).
- **Es la palanca natural para la puerta de T2**: las reglas EAU que separan `active_surveillance` de `active_treatment` están ahí dentro. Se puede consultar en tiempo de ejecución **o** destilar offline a unas cuantas reglas explícitas en el prompt — que sale más barato y más determinista.
- **Si `resources/embedding_model/` no está en disco antes del build, devuelve resultados vacíos en silencio.** No hay error.
- El notebook (§5.5) encontró que **recupera el pasaje correcto pero con metadatos ruidosos** y un "score" que no es una similitud interpretable. Se puede reconstruir con otro troceado: `python scripts/process_guidelines.py --pdf <tu.pdf>` (requiere el PDF, que no viene en el repo). Si cambias el modelo de embeddings, **hay que reconstruir la DB entera**: consulta y documentos tienen que venir del mismo modelo.

**Bonus que no es un modelo pero se usa como tal**: los formularios reales del urólogo, en `evaluation/pathologist_forms/task1_pathologist_form.html` y `task2_pathologist_form.html` del repo de evaluación. Son **la especificación exacta de lo que vio el anotador**: qué panel estaba visible, qué secciones estaban enmascaradas, y con qué etiquetas se rellenaban `confidence` y `variable_weights`. Para escribir un prompt que produzca el mismo formato de razonamiento que el ground truth, es la mejor fuente que hay.

### 12.5 Lo que el reto NO te da

- **Las imágenes** (mpMRI y WSI). Sólo embeddings.
- **Transcriptómica**. Eso era el CHIMERA de 2025, no éste.
- **Endpoints ni contenedores** de los modelos de imagen preentrenados: no hay nada que llamar.
- **Internet en tiempo de ejecución.** Todo pesa dentro de la imagen o del `model.tar.gz`.

### 12.6 Checklist de uso de las herramientas

- [ ] Decidido si el predictor sobre embeddings entra en la solución y **para qué tarea** (la evidencia dice T2 antes que T3, y T1 nunca).
- [ ] La cabeza entrenada con los splits de `dev/`, guardada en `model/`, cargada perezosamente, y probada con casos **sin** embeddings.
- [ ] `run_predictor` usa las claves literales `"MRI image"` / `"Biopsy slide"` / `"Prostatectomy slide"`.
- [ ] El predictor devuelve un score compacto, nunca vectores.
- [ ] Las descripciones de las herramientas dicen cuándo **no** llamarlas (`tool_score` es precisión).
- [ ] Ninguna herramienta que respalde una variable (`get_family_history`, `get_mri_report`, `get_pathology_report`, `get_lab_results`) ha sido renombrada ni eliminada.
- [ ] El RAG devuelve resultados no vacíos dentro del contenedor construido (probarlo, no suponerlo).
- [ ] Todo modelo o dato externo añadido está declarado en el nombre del algoritmo, su página y el paper.

---

## 13. Fuentes

- `README.md` del baseline, [docs/architecture.md](docs/architecture.md), [docs/models.md](docs/models.md), [docs/user-manual.md](docs/user-manual.md)
- [src/chimera_agent_baseline/output/schema.py](src/chimera_agent_baseline/output/schema.py) — el contrato
- [inference.py](inference.py) — el contrato del contenedor de GC
- `evaluate.py` del repo de evaluación oficial (`DIAGNijmegen/CHIMERA-agent`) — las métricas
- [dev/score_local.py](dev/score_local.py) y [dev/baseline_reference.json](dev/baseline_reference.json) — la línea base
- [delete/exploratory_analysis.ipynb](delete/exploratory_analysis.ipynb) — el análisis del que salen los hallazgos de §8
- `https://chimera-agent.grand-challenge.org/chimera-agent/`, su página de submission y la de repositorios
- `evaluation/ground_truth/section_variable_mapping.json` — el mapa variable → sección de §4.1
- `evaluation/pathologist_forms/task{1,2}_pathologist_form.html` — los formularios reales del urólogo
