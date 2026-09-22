# Plan: fine-tuning con LoRA del agente CHIMERA (modelo "solo entrenado")

**Objetivo.** Medir qué consigue **Gemma 4 E2B-it + un adaptador LoRA** cuando corre
dentro del **mismo agente del reto** (bucle ReAct de LangGraph + herramientas MCP +
nodo form-fill), **sin expertos, sin reglas y sin cascadas**. El LLM decide, llama a
las herramientas y rellena el formulario. Es un experimento de verificación: la
pregunta es *cuánto aporta el entrenamiento por sí solo* con los pocos datos que hay.

El plan está escrito para ejecutarse en un repositorio limpio que solo tiene los
datos de entrada y los de salida (ground truth). Todo lo que hace falta del
repositorio original está resumido en el **Anexo A**.

---

## 0. Cifras que hay que tener presentes

| Tarea | Casos con etiqueta | Casos totales | Métrica de ranking | Peso en OVERALL |
|---|---:|---:|---|---:|
| T1 — biopsia (sí/no) | **91** | 195 | `ranking_score` del evaluador (puerta de decisión + componentes) | 2 |
| T2 — tratamiento (4 clases) | **72** | 153 | `ranking_score` | 2 |
| T3 — recurrencia (meses + evento) | **75** | 75 | c-index | 1 |

`OVERALL = (2·T1 + 2·T2 + 1·T3) / 5`.

Referencias para comparar (evaluador oficial, juez de razonamiento apagado):

| Sistema | T1 | T2 | T3 | Nota |
|---|---:|---:|---:|---|
| Baseline sin tocar (Gemma 4 E2B zero-shot) | 0,635 | 0,446 | 0,664 | `dev/baseline_reference.json` |
| Solución entregada (expertos + reglas) | 0,839 | 0,778 | 0,883 | **dentro de muestra** (optimista) |
| Solución entregada, estimación honesta | ~0,761 | — | ~0,824 | fuera de muestra |

Hechos del baseline que el LoRA tiene que corregir:

- T1: acierto 0,67, pero recall de `no` = **0,14**. El modelo dice "sí" a casi todo.
- T2: acierto 0,57 y `mean_tool_score` = 0,0.
- La **puerta de decisión** manda: si la decisión es errónea, el resto de
  componentes del caso no puntúa. El 80 % del esfuerzo va a acertar la decisión.

Con 163 casos etiquetados para T1+T2 y 75 para T3, **cualquier número se tiene que
dar con validación cruzada y con intervalo**. Una sola partición no sirve.

---

## 1. Restricciones que el modelo entrenado tiene que respetar

Vienen del contenedor de Grand Challenge. Si el modelo entrenado no las cumple, no
sirve para comparar con el agente del reto.

| Restricción | Valor | Consecuencia para el entrenamiento |
|---|---|---|
| Imagen base | `pytorch/pytorch:2.9.1-cuda12.6-cudnn9-runtime`, Python 3.11 | Entrenar con **torch 2.9.x** |
| Motor de inferencia | **vLLM 0.25.0** (en proceso, `LLM.chat`, parser `gemma4`) | El modelo final tiene que cargar en vLLM 0.25.0 |
| Transformers | **5.12.1** (fijado con `--no-deps`, junto a `tokenizers==0.22.2`) | Entrenar con **la misma versión**: plantilla de chat y tokenizador idénticos |
| Otras fijadas | `mcp==1.29.0`, `langchain-core==1.4.8`, `langgraph==1.2.6`, `langchain-mcp-adapters==0.2.2` | Solo inferencia; no se tocan |
| Sin red | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` | Pesos completos dentro de `/opt/ml/model`, nada que descargar |
| Tiempo | **15 min por caso** (presupuesto útil ~780 s) | El LoRA no puede alargar las trayectorias; se enseña a llamar pocas herramientas |
| GPU | Debe caber en **16 GB** (el perfil entregado tenía un pico de 13,3 GB) | Con los pesos fusionados el tamaño no cambia; LoRA en tiempo de ejecución añade memoria |
| Contexto | `max_model_len = 32768` | Las trayectorias de entrenamiento tienen que caber holgadas (en la práctica 4–10 k tokens) |
| Esquema de salida | `output/schema.py` **bloqueado** | El JSON del form-fill tiene que validar (Anexo A.4) |
| Muestreo por defecto | `temperature=1.0`, `top_p=0.95`, `max_new_tokens=4096` | Evaluar con este valor **y** con temperatura baja (ver §9) |

**Decisión de diseño: fusionar el LoRA en los pesos** (`merge_and_unload`) y
entregar un checkpoint normal de Gemma 4. Así el agente no cambia ni una línea (solo
la ruta del modelo) y no dependes de si vLLM 0.25.0 soporta LoRA en tiempo de
ejecución para la arquitectura multimodal de Gemma 4. Dejar el LoRA sin fusionar
(`enable_lora=True` + `LoRARequest`) queda como alternativa, y obliga a tocar
`ChatVLLM._generate` para pasar `lora_request`.

---

## 2. Dos entornos separados

### 2.1 Entorno de entrenamiento (GPU de ≥24 GB; A100/H100 recomendable)

```bash
python3.11 -m venv .venv-train && source .venv-train/bin/activate
pip install "torch==2.9.1" --index-url https://download.pytorch.org/whl/cu126
pip install "transformers==5.12.1" "tokenizers==0.22.2" \
            peft accelerate datasets safetensors pydantic jinja2 scikit-learn pandas
# opcional, solo si hay que hacer QLoRA en 16 GB:
pip install bitsandbytes
```

- **Fija `peft` y `accelerate` con `pip freeze > requirements-train.txt`** en cuanto
  funcione. Hay que comprobar que la versión de `peft` que se instale soporta
  transformers 5.x.
- **No hace falta `trl`.** Con ~300 ejemplos, un `Trainer` de HF con un collator
  propio que enmascare la pérdida es más fácil de controlar y evita otro conflicto de
  versiones. Si usas `trl`, comprueba que acepta transformers 5.12.1 antes de nada.

### 2.2 Entorno de inferencia/evaluación

Exactamente el contenedor del reto (Anexo A.1), con vLLM 0.25.0. Todas las
evaluaciones del §9 se hacen aquí, nunca con `model.generate` de HF: lo que se mide
tiene que ser lo que correría en Grand Challenge.

---

## 3. Estructura del repositorio limpio

```
repo-lora/
  data/                                  # lo que ya tienes
    task1/agent_input/<case>/{structured-prompt,*-clinical-data}.json
    task1/ground_truth/<case>/...        # salidas: decisión + razonamiento del urólogo
    task2/...  task3/...
  vendor/chimera_contract/               # §4: copia congelada del contrato del agente
    schema.py  form_fill_prompts.py  system_prompt.py  agent_prompt.j2  tools.py
  lora/
    00_inventory.py        # §5  inventario y chequeos de calidad del GT
    01_splits.py           # §6  pliegues de validación cruzada
    02_build_sft.py        # §7  trayectorias de entrenamiento
    03_check_template.py   # §8.1 fidelidad de la plantilla de chat y del parser
    04_train.py            # §8  entrenamiento LoRA
    05_merge_export.py     # §10 fusión + exportación + pruebas de paridad
    06_eval_fold.sh        # §9  agente + evaluador oficial en el pliegue retenido
    07_report.py           # §9  tabla final con IC
  agent/                   # el agente baseline sin tocar (git submodule o copia fijada)
  eval/                    # DIAGNijmegen/CHIMERA-agent (evaluation/evaluate.py), fijado por commit
  runs/<exp>/<fold>/...    # adaptadores, fusionados, salidas, puntuaciones
```

**Fija por hash de commit** el agente baseline y el repositorio del evaluador. Si los
organizadores cambian `evaluate.py`, tus números dejan de ser comparables.

---

## 4. Congelar el contrato del agente (lo que el modelo verá en inferencia)

El principio de todo el plan: **el modelo se entrena con los mismos tokens que verá
al ejecutarse**. Para eso hay que reproducir, carácter a carácter, lo siguiente:

1. `SYSTEM_PROMPT` del agente (`agent/prompts.py`).
2. La plantilla del caso `templates/prompts/agent_prompt.j2`, renderizada con el
   `structured-prompt.json` (es el primer `HumanMessage`).
3. La **lista de herramientas** que el servidor MCP expone por tarea, **en el mismo
   orden y con los mismos esquemas**: las de la tarea más `search_guidelines`
   (Anexo A.2). Lo más seguro es volcarla desde el agente real:
   `tools = await client.get_tools()` → `convert_to_openai_tool(t)` → `tools_task{N}.json`.
4. El formato de la respuesta de cada herramienta: `json.dumps({"case_id": ..., <campo>: <valor>})`,
   y `{"case_id": ..., "note": "No data available for this tool and case."}` cuando no
   hay dato (Anexo A.3).
5. El prompt del form-fill: `_SYSTEM_PROMPT`, `_user_prompt(...)` y
   `_build_skeleton_instructions(...)` de `agent/form_fill.py` (Anexo A.4).
6. `eligible_variables(task, called_tools)`: solo se pueden ponderar las variables
   del panel y las que respalda una herramienta llamada (`fh` exige
   `get_family_history`).

Copia esas funciones **tal cual** en `vendor/chimera_contract/` e impórtalas desde el
constructor de datos. No las reescribas.

---

## 5. Paso 1 — Inventario y calidad del ground truth (`00_inventory.py`)

Para cada caso etiquetado, lee el GT y genera una tabla con:

- T1: `decision` (yes/no), `confidence`, `variable_weights`, `reveal_sequence`, `free_text`.
- T2: `action`, `confidence`, `variable_weights`, `reveal_sequence`, `free_text`.
- T3: `months_to_recurrence`, `event` (y el razonamiento si lo hay).

Chequeos obligatorios (cada uno produce una lista de casos, no un aviso suelto):

| Chequeo | Por qué importa | Qué hacer |
|---|---|---|
| Distribución de clases por tarea | T1 ~62 % "sí"; T2 `watchful_waiting` ≈ 2/72 | Estratificar y, si hace falta, reponderar |
| `variable_weights` con peso ≠ `not_used` en una variable **no elegible** (p. ej. `fh` sin `family_history` en `reveal_sequence`) | El form-fill no deja emitirla; enseñarla es enseñar algo imposible | Opción A: añadir `get_family_history` a la trayectoria. Opción B: forzar `not_used`. Decide una y registra cuántos casos toca |
| `reveal_sequence` con secciones que no existen en la tarea (p. ej. `pathology_report` en T1) | La herramienta no existe en T1 | Quitarla |
| Herramientas que devuelven "no data" | El modelo tiene que aprender a no pedirlas | Contar por tarea |
| Longitud en tokens de cada respuesta de herramienta | Determina `max_seq_len` | Percentiles 50/95/max |
| `free_text` con menos de 40 caracteres | `reasoning` exige `min_length=40` | Ampliar con la plantilla del §7.4 |
| ¿Hay varios lectores por caso? | Si sí, es aumento de datos gratis | Una trayectoria por lector |

---

## 6. Paso 2 — Particiones (`01_splits.py`)

- **Validación cruzada estratificada, 5 pliegues, por tarea**, semilla fija.
  Estratos: T1 = decisión; T2 = acción (juntando `watchful_waiting` con la clase más
  cercana solo *para estratificar*, porque con 2 casos no se puede repartir en 5);
  T3 = evento.
- Un caso = una unidad. Si un paciente aparece en varias tareas o tiene varios
  lectores, **todas sus muestras van al mismo pliegue** (agrupar por `pid`).
- Dentro de cada pliegue de entrenamiento, reserva ~15 % como validación interna para
  la parada temprana. El pliegue de test **no se mira** hasta el final.
- Guarda las particiones en JSON y no las regeneres nunca.

Opcional, si quieres algo aún más honesto: validación cruzada anidada (bucle interno
para elegir épocas y rango), a costa de 5× GPU.

---

## 7. Paso 3 — Construir trayectorias SFT (`02_build_sft.py`)

Cada caso etiquetado genera **dos ejemplos de entrenamiento**, porque en inferencia
el mismo modelo se llama en dos contextos distintos.

### 7.1 Ejemplo A — el bucle ReAct (llamar a herramientas y razonar)

```
[system]    SYSTEM_PROMPT
[user]      agent_prompt.j2 renderizado con structured-prompt.json
[assistant] tool_call get_mri_report(case_id=...)           ← pérdida
[tool]      {"case_id": ..., "radiology_report": "..."}     ← sin pérdida
[assistant] tool_call get_psa_trend(case_id=...)            ← pérdida
[tool]      {...}                                           ← sin pérdida
...
[assistant] texto final de razonamiento (sin tool_calls)    ← pérdida
```

- **Qué herramientas llamar** = las secciones del `reveal_sequence` del urólogo,
  traducidas con el mapa sección→herramienta (Anexo A.2). Así el modelo aprende a
  abrir lo que abre el lector y el `tool_score` sale solo.
- **Orden**: el evaluador ignora el orden, así que usa uno **canónico y estable**
  (el que sugiere el prompt: `get_mri_report` → `get_pathology_report` →
  `get_psa_trend` → `get_previous_notes` → `get_lab_results` → `get_family_history`).
  Con tan pocos datos, un orden fijo se aprende antes que uno aleatorio. Permutar el
  orden es una ablación posterior (§11).
- **Una llamada por turno** (es lo que pide el prompt del sistema). El `content` del
  mensaje asistente va vacío: así lo produce Gemma 4 E2B y así lo reconstruye
  `ChatVLLM`.
- **`search_guidelines`**: no hay GT de cuándo usarla. Déjala en la lista de
  herramientas (tiene que estar, porque en inferencia está) pero no la metas en las
  trayectorias. Resultado esperado: el modelo aprende a no llamarla, que además
  ahorra tiempo.
- **Casos sin ninguna herramienta en el GT**: trayectoria directa system → user →
  razonamiento final. Son ejemplos válidos e importantes.

### 7.2 El texto final de razonamiento (la parte delicada)

El GT solo trae el `free_text` corto del urólogo. El razonamiento final se construye
con una plantilla **determinista** que únicamente cita valores recuperados:

```
Evidence retrieved:
- MRI report: <2–3 frases extraídas del informe: PI-RADS, lesión, EPE…>
- PSA trend: <primer y último valor, pendiente>
- ...
Key factors: <variables con peso important/decisive del GT, ordenadas>
Recommendation: <biopsy yes/no | acción> (<confidence>).
<free_text del urólogo>
```

Reglas: no citar nada de una herramienta que no se ha llamado (el prompt lo prohíbe
y el evaluador lo penaliza vía grounding), y que la decisión escrita sea **la misma**
que la del GT. Esta línea `Recommendation:` es la que el form-fill leerá.

Alternativa más rica: pedir a un LLM grande (fuera del contenedor) que redacte el
razonamiento a partir del GT y de los documentos, y validarlo automáticamente (la
decisión coincide, no cita herramientas no llamadas). Solo merece la pena si la
plantilla determinista se queda corta en `rationale_score` con el juez encendido.

### 7.3 Ejemplo B — el nodo form-fill

```
[system]    form_fill._SYSTEM_PROMPT
[user]      _user_prompt(case_id, task, transcript, called_tools, eligible)
            + "\n\n" + _build_skeleton_instructions(task, eligible)
[assistant] {"case_id": ..., "task": N, "biopsy_decision"/"action": ...,
             "confidence": ..., "variable_weights": {...solo elegibles...},
             "reasoning": "..."}                                   ← pérdida
```

- `transcript` = el texto final del ejemplo A, **el mismo**.
- `called_tools` y `eligible` se calculan con las funciones copiadas (§4).
- El JSON objetivo sale del GT: decisión, confianza, pesos de las variables elegibles
  (las no elegibles no aparecen) y `reasoning` = `free_text` (≥40 caracteres).
- `reveal_sequence` **no** va en el JSON: el nodo lo reconstruye a partir de los
  `ToolMessage`. Por eso el ejemplo A es el que decide el `tool_score`.
- Valida cada JSON objetivo con el modelo dinámico (`build_dynamic_model`) antes de
  guardarlo. Si no valida, el ejemplo se descarta y se registra.

### 7.4 Tarea 3

- GT: `months_to_recurrence` + `event`. No hay `reveal_sequence` del lector.
- Política de herramientas fija: llamar a las 5 de T3 (en T3 no se puntúa el uso de
  herramientas y son pocas).
- Objetivo del form-fill: los meses del GT redondeados a 1 decimal. Aviso: el c-index
  solo mira el **orden**, y los casos censurados (`event=0`) no son tiempos reales de
  recurrencia. Con 75 casos, que un LLM de 2B aprenda a ordenar riesgos a partir de
  prosa es poco probable. **Incluye T3 como experimento aparte** y no dejes que tape
  el resultado de T1/T2.
- El esquema bloqueado de T3 solo tiene `months_to_recurrence` y `reasoning`. El
  `event` del fichero de salida lo pone el runner; revisa cómo lo hace el agente que
  uses como marco.

### 7.5 Formato en disco

JSONL con `{"case_id", "task", "fold", "kind": "react"|"form_fill", "messages": [...], "tools": [...]}`,
donde `messages` usa el formato OpenAI (`role`, `content`, `tool_calls`,
`tool_call_id`, `name`), el mismo que `_to_openai_messages` entrega a `llm.chat`.

---

## 8. Paso 4 — Entrenamiento LoRA (`04_train.py`)

### 8.1 Antes de entrenar: fidelidad de la plantilla (`03_check_template.py`)

Este es el paso que más fácilmente se salta y el que más resultados estropea.

1. Renderiza cada ejemplo con
   `tokenizer.apply_chat_template(messages, tools=tools, tokenize=False)` usando el
   tokenizador **de la carpeta del modelo** con transformers 5.12.1. vLLM `LLM.chat`
   usa esa misma plantilla.
2. **Comprobación de ida y vuelta**: coge el trozo renderizado de cada turno asistente
   con `tool_calls`, pásalo por el parser `gemma4` de vLLM 0.25.0 (el mismo que usa
   `_parse_tool_calls` en `ChatVLLM`) y exige que devuelva exactamente
   `[{name, arguments}]`. Si no coincide, el modelo aprenderá un formato que el
   agente no sabe leer.
3. Comprueba que la plantilla admite turnos `tool` y `tool_calls` en el historial.
   Si la de Gemma 4 no lo hace como esperas, renderiza tú el historial **igual que lo
   hace vLLM** (captura el prompt real que genera vLLM con un caso y compáralo byte a
   byte con el tuyo).
4. **Máscara de pérdida**: etiquetas `-100` en todo salvo los tokens del asistente
   (llamadas + marcadores de fin de turno + texto final + JSON del form-fill). Verifica
   imprimiendo decodificados los tokens con pérdida de 3 ejemplos.

### 8.2 Qué capas adaptar

Gemma 4 E2B es multimodal (texto, visión y audio) y tiene embeddings por capa. Solo
se adapta **el decodificador de texto**:

```python
from peft import LoraConfig
cfg = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.1, bias="none", task_type="CAUSAL_LM",
    target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$",
)
```

Antes, imprime `model.named_modules()` y confirma los nombres reales en
transformers 5.12.1. No adaptes las torres de visión y audio, los embeddings ni
`lm_head`.

Carga el modelo con la **misma clase** con la que después se exportará (la clase
multimodal de Gemma 4 de transformers), para que el `config.json` fusionado sea el
que vLLM espera.

### 8.3 Hiperparámetros de partida (pocos datos → regularizar)

| Parámetro | Valor | Motivo |
|---|---|---|
| Rango `r` / `alpha` | 16 / 32 (probar 8 y 32) | Capacidad baja para ~300 ejemplos |
| Dropout LoRA | 0,1 | Sobreajuste |
| LR | 1e-4, coseno, warmup 5 % | Conservador |
| Épocas | 2–4, **con parada temprana** | Con 160 casos por pliegue sobreajusta rápido |
| Batch efectivo | 8 (1 × 8 de acumulación) | Estabilidad |
| `max_seq_len` | percentil 99 del §5 (+ margen), típicamente 8–12 k | No truncar trayectorias |
| Precisión | bf16, gradient checkpointing | Cabe en 24 GB; QLoRA 4 bits si solo hay 16 GB |
| Mezcla de tareas | **un solo adaptador** con T1+T2 (+T3 en la ablación) | Más datos; el prompt ya dice la tarea |
| Equilibrio de clases | sobremuestrear la clase minoritaria ×2 en T1 `no` y en T2 | El baseline dice "sí" a todo |
| Semillas | 3 por configuración | Con esta N, la varianza entre semillas es del orden del efecto |

**Parada temprana por lo que importa**: la pérdida de validación es orientativa, pero
el criterio es el **acierto de la decisión** en la validación interna, medido
generando con vLLM (o, en su defecto, comparando la probabilidad de los tokens de
decisión del JSON del form-fill con `model.generate` en HF). Guarda el adaptador de
cada época.

### 8.4 Coste esperado

~160 casos × 2 ejemplos por pliegue ≈ 40 pasos/época con batch 8. Del orden de
minutos a una hora por pliegue en una A100. 5 pliegues × 3 semillas × 2–3
configuraciones es asumible.

---

## 9. Paso 5 — Evaluación en el pliegue retenido (`06_eval_fold.sh`, `07_report.py`)

Para cada pliegue y semilla:

1. Fusiona y exporta (§10) → `runs/<exp>/<fold>/merged/`.
2. Ejecuta **el agente baseline sin cambios** con
   `paths.model_dir=runs/<exp>/<fold>/merged` y `agent.pids=[<casos del pliegue de test>]`,
   dentro del contenedor (vLLM 0.25.0), con `USE_RATIONALE_JUDGE=0`.
3. Puntúa con `evaluate.py` oficial (`load_ground_truth_records`, `evaluate_case`,
   `compute_aggregate_metrics`, `aggregate_recurrence_metrics`). Un caso sin salida
   cuenta como fallo, igual que en Grand Challenge.
4. Repite **con el mismo pliegue y el modelo base sin LoRA**. Esa es la comparación
   que responde a la pregunta.

Brazos mínimos:

| Brazo | Modelo | Qué mide |
|---|---|---|
| B0 | Gemma 4 E2B base, agente baseline | Punto de partida |
| L1 | + LoRA (T1+T2) | El efecto del entrenamiento |
| L1-T | L1 con `temperature=0.2` | Cuánto del efecto se pierde por el muestreo a T=1 |
| L2 | + LoRA (T1+T2+T3) | Si T3 ayuda o estorba |

Qué informar (media ± desviación entre pliegues, e IC bootstrap al 95 % sobre casos
agregados fuera de pliegue):

- `ranking_score` T1, T2, T3 y OVERALL ponderado.
- Acierto de decisión, **recall por clase** (T1 `no`, T2 cada acción), matriz de confusión.
- `mean_tool_score`, `section_grounding_score`, kappa de confianza y de pesos.
- Operativa: llamadas a herramientas inexistentes, reintentos del form-fill, casos
  fallidos, **segundos por caso** (tiene que quedar muy por debajo de 780 s).
- Diferencia pareada L1 − B0 por caso (prueba de McNemar para la decisión).

Criterio de éxito honesto: **L1 supera a B0 fuera de pliegue con un IC que no
cruza 0** en OVERALL. Compararlo con el 0,82 de la solución entregada no es justo
(ese número es dentro de muestra); la referencia comparable es la estimación honesta
(~0,76 en T1).

---

## 10. Paso 6 — Fusión, exportación y paridad (`05_merge_export.py`)

```python
base = <ClaseGemma4>.from_pretrained(BASE_DIR, torch_dtype=torch.bfloat16)
model = PeftModel.from_pretrained(base, ADAPTER_DIR).merge_and_unload()
model.save_pretrained(OUT_DIR, safe_serialization=True, max_shard_size="5GB")
# copiar de BASE_DIR, sin tocar: tokenizer*, chat_template*, processor_config*,
# preprocessor_config*, generation_config.json, special_tokens_map.json
```

Comprobaciones antes de dar por bueno el checkpoint:

1. **Paridad HF**: logits del modelo PEFT sin fusionar y del fusionado sobre 3
   ejemplos → diferencia máxima pequeña (tolerancia de bf16).
2. **Carga en vLLM 0.25.0** con los mismos `engine_kwargs` que el agente
   (`enforce_eager=True`, `max_model_len=32768`, perfil de 16 GB si se usa).
3. **Humo del agente**: 3 casos por tarea de punta a punta, que salgan los dos
   ficheros por caso y que validen contra el esquema.
4. **Diff de `config.json`** contra el original: solo pueden cambiar campos
   irrelevantes. Si cambia la arquitectura o faltan las secciones de visión y audio,
   vLLM puede fallar al cargar o cargar otra cosa.

---

## 11. Paso 7 — Ablaciones (solo si L1 ya funciona)

Por orden de valor esperado:

1. **Rango** 8 / 16 / 32 y **épocas** 2 / 3 / 4.
2. **Solo decisión**: entrenar únicamente el ejemplo B (form-fill) frente a A+B.
   Indica si lo que se aprende es a decidir o a usar herramientas.
3. **Orden de herramientas** canónico frente a permutado (aumento ×3).
4. **Razonamiento** con plantilla determinista frente a uno redactado por un LLM
   grande (con el juez de razonamiento encendido; es lo único que lo mide).
5. **Casos sin etiqueta** (104 de T1 y 81 de T2): autodestilación con pseudoetiquetas
   del mejor sistema disponible. **Ojo**: es probable que sean el conjunto de test del
   reto; si los usas, el experimento deja de ser "solo entrenado con GT" y hay que
   decirlo.

---

## 12. Paso 8 — Modelo final y empaquetado

1. Con la configuración ganadora de la validación cruzada (rango, épocas **fijas**,
   no parada temprana), reentrena sobre **todos** los casos etiquetados.
2. Fusiona y exporta (§10) → carpeta `model/gemma-4-E2B-it/` (misma ruta que espera
   el agente; si cambias el nombre, ajusta `model.model_id`/`paths.model_dir`).
3. Empaqueta el tarball del modelo como en la entrega original, con el embedding de
   RAG si mantienes `search_guidelines`.
4. Ejecuta la compuerta en el contenedor sin montar código: sin red, GPU limitada a
   16 GB, un caso por proceso (arranque en frío), y confirma < 15 min por caso.
5. **No publiques** un número de este modelo reentrenado sobre las 238 etiquetas como
   estimación: el número válido es el de la validación cruzada del §9.

---

## 13. Riesgos y cómo detectarlos

| Riesgo | Síntoma | Detección / mitigación |
|---|---|---|
| Plantilla de entrenamiento ≠ plantilla de vLLM | El modelo no llama herramientas, o el parser no las reconoce | §8.1 punto 2, obligatorio |
| Versiones distintas de transformers entre entrenamiento e inferencia | Tokens especiales desplazados, basura en la salida | Usar 5.12.1 en ambos lados |
| Sobreajuste (N ≈ 160 por pliegue) | Pérdida de entrenamiento → 0, validación sube tras la época 1–2 | Parada temprana por decisión, r bajo, dropout |
| Colapso a la clase mayoritaria | Recall de `no` sigue ≈ 0 | Sobremuestreo, informar recall por clase |
| Olvido del formato JSON del form-fill | Reintentos y `RuntimeError` en el nodo | Contar reintentos en §9; el ejemplo B cubre este caso |
| Herramientas alucinadas (`get_pathology_report` en T1) | `is not a valid tool` en las trazas | Contarlas; el LoRA debería reducirlas a 0 |
| Checkpoint fusionado que vLLM no carga | Error de arquitectura o de pesos | §10 puntos 2 y 4 |
| Tiempo por caso | Trayectorias largas a T=1 | Medirlo en §9; el LoRA debería acortarlas |
| Conclusiones por azar | Diferencias de ±0,02 que cambian con la semilla | 3 semillas × 5 pliegues, IC, prueba pareada |

---

## Anexo A — El contrato del agente, resumido

### A.1 Pila de inferencia del contenedor

```
FROM pytorch/pytorch:2.9.1-cuda12.6-cudnn9-runtime   # Python 3.11
pip install -r requirements.txt                       # langchain 1.3.11, langgraph 1.2.6,
                                                      # langchain-mcp-adapters 0.2.2, chromadb 1.5.9,
                                                      # sentence-transformers 5.6.0, hydra-core 1.3.3 …
uv pip install "vllm==0.25.0+cu129" (wheels.vllm.ai)
uv pip install --no-deps "mcp==1.29.0" "transformers==5.12.1" "tokenizers==0.22.2"
pip uninstall -y torchcodec
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_USE_FLASHINFER_SAMPLER=0
modelo en /opt/ml/model (enlazado a /opt/app/model)
```

Motor: `LLM(model=..., dtype="auto", max_model_len=32768, gpu_memory_utilization=0.9,
enforce_eager=True, disable_custom_all_reduce=True)` y
`SamplingParams(temperature=1.0, top_p=0.95, max_tokens=4096)`. El chat se hace con
`llm.chat(messages, sampling_params, tools=...)`, se decodifica **con** tokens
especiales y se parsea con el parser `gemma4` de vLLM.

Grafo: `START → agent ⇄ tools → form_fill → END`, `max_iterations=25`. El agente
recibe `[SystemMessage(SYSTEM_PROMPT), HumanMessage(agent_prompt.j2 renderizado)]`.

### A.2 Herramientas por tarea (todas con argumento `case_id: str`)

| Herramienta | Campo(s) de `*-clinical-data.json` | Sección en `reveal_sequence` | T1 | T2 | T3 |
|---|---|---|:-:|:-:|:-:|
| `get_psa_trend` | `psa_trend` | `psa_trend` | ✓ | ✓ | |
| `get_lab_results` | `laboratory_results` | `laboratory_results` | ✓ | ✓ | |
| `get_mri_report` | `radiology_report` | `radiology_report` | ✓ | ✓ | ✓ |
| `get_pathology_report` | `pathology_report` | `pathology_report` | | ✓ | ✓ |
| `get_surgical_pathology_report` | `surgical_pathology_report` | — | | | ✓ |
| `get_previous_notes` | `previous_notes` | `previous_notes` | ✓ | ✓ | ✓ |
| `get_family_history` | `family_history` | `family_history` | ✓ | ✓ | ✓ |
| `search_guidelines(query: str)` | RAG sobre la base de guías | — | ✓ | ✓ | ✓ |

Las descripciones exactas de cada herramienta están en
`src/chimera_agent_baseline/tools/definitions.py`; vuélcalas del servidor MCP real
(§4, punto 3) en lugar de copiarlas a mano.

### A.3 Respuesta de las herramientas

```python
out = {"case_id": case_id}
for f in fields:
    if f in case: out[f] = case[f]
if set(out) == {"case_id"}:
    return json.dumps({"case_id": case_id, "note": "No data available for this tool and case."})
return json.dumps(out)
```

### A.4 Salida (esquema bloqueado) y form-fill

- **T1**: `{case_id, task:1, biopsy_decision: bool, confidence: clear|borderline|uncertain,
  variable_weights: {var: not_used|noted|important|decisive}, reveal_sequence: [...], reasoning (≥40)}`.
  Variables: `bx, fh*, age, dre, psa, vol, psad, cspca, pirads, comorbidity` (* exige `get_family_history`).
- **T2**: igual con `action: active_surveillance|continued_surveillance|watchful_waiting|active_treatment`.
  Variables: `ct, fh*, age, psa, psad, cspca, pirads, bx_isup, bx_gl_sec, bx_gl_prim, comorbidity`.
- **T3**: `{case_id, task:3, months_to_recurrence ≥ 0, reasoning (≥40)}`.
- Ficheros por caso: T1 `prostate-biopsy-decision.json` (`"yes"|"no"`) +
  `prostate-biopsy-decision-reasoning.json` (`confidence, variable_weights, reveal_sequence, free_text`);
  T2 `prostate-treatment-decision.json` + `…-reasoning.json`;
  T3 `prostate-time-to-recurrence-or-last-follow-up.json` (`months_to_recurrence, event`) + `…-reasoning.json`.
- El form-fill es una llamada **aparte** y sin herramientas: `system = _SYSTEM_PROMPT`,
  `user = _user_prompt(...) + "\n\n" + _build_skeleton_instructions(task, eligible)`,
  hasta 3 reintentos con el error de validación añadido. `reveal_sequence` lo rellena
  el código a partir de los `ToolMessage`, no el modelo.

### A.5 Evaluador

`DIAGNijmegen/CHIMERA-agent` → `evaluation/evaluate.py`. Con `USE_RATIONALE_JUDGE=0`,
los pesos de los componentes (tras la puerta de decisión) se redistribuyen:
`variable_weight 0,275 · confidence 0,225 · important_decisive_factor 0,175 ·
section_grounding 0,175 · tool 0,150`. Con el juez encendido los números **no** son
comparables con los de sin juez.
