# Tarea 1 — decisión de biopsia (sí / no)

**Pregunta** (fija en `agent_prompt.j2`): ¿hay que biopsiar a este paciente?

## Datos

| | |
|---|---|
| Casos con ground truth | **91** (56 `yes` · 35 `no`) de 195 |
| Entrada | `task1/agent_input/<case>/structured-prompt.json` + `prostate-biopsy-decision-clinical-data.json` |
| Ground truth | `task1/ground_truth/<case>/prostate-biopsy-decision.json` (`"yes"`/`"no"`) + `prostate-biopsy-decision-reasoning.json` |
| Ejemplo real | `../../fixture_data/task1/` (caso `PT-pseudo_0bd72f429a8b`) |

## Herramientas (orden y esquema exactos en `../../contract/tool_schemas/tools_task1.json`)

| Herramienta | Campo devuelto | Sección en `reveal_sequence` |
|---|---|---|
| `get_mri_report` | `radiology_report` | `radiology_report` |
| `get_psa_trend` | `psa_trend` | `psa_trend` |
| `get_previous_notes` | `previous_notes` | `previous_notes` |
| `get_lab_results` | `laboratory_results` | `laboratory_results` |
| `get_family_history` | `family_history` | `family_history` |
| `search_guidelines(query)` | pasajes de guías (RAG) | — |

**No hay `get_pathology_report` en T1**, aunque el prompt del sistema la menciona. Si el
modelo la llama, el agente responde `is not a valid tool`. El LoRA debería eliminar esas
llamadas.

## Salida (esquema bloqueado)

```jsonc
// prostate-biopsy-decision.json
"yes"
// prostate-biopsy-decision-reasoning.json
{"confidence": "clear|borderline|uncertain",
 "variable_weights": {"bx","fh","age","dre","psa","vol","psad","cspca","pirads","comorbidity": "not_used|noted|important|decisive"},
 "reveal_sequence": ["radiology_report", ...],   // lo rellena el código a partir de las herramientas llamadas
 "free_text": "..."}
```

`fh` solo se puede ponderar si se llamó a `get_family_history`. El resto de variables
están en el panel y siempre se pueden ponderar.

## Qué aprende el modelo (ver `sft_react.txt` y `sft_form_fill.txt`)

- **react**: una llamada por cada sección del `reveal_sequence` del urólogo, en orden
  canónico (`get_mri_report` → `get_psa_trend` → `get_previous_notes` → `get_lab_results`
  → `get_family_history`), y después un razonamiento que termina en
  `Recommendation: biopsy recommended.` / `no biopsy at this time.`
- **form_fill**: el JSON con `biopsy_decision`, la `confidence` y los `variable_weights`
  del urólogo (solo las variables elegibles) y su `free_text` como `reasoning`.

## Lo que hay que vigilar

- El baseline sin entrenar detecta **solo el 14 % de los `no`** (acierto 0,67). Hay que
  mirar el recall de `no` por pliegue, no solo el acierto global.
  `train_lora.py --oversample 2` duplica los casos de la clase minoritaria.
- Casos del GT que ponderan `fh` sin haber abierto `family_history`: por defecto
  (`--fh-policy add_tool`) se añade la llamada. `build_sft.py` informa cuántos son.
- Métrica: `ranking_score` del evaluador. Si la decisión es errónea, el resto del caso no
  puntúa (puerta de decisión).
