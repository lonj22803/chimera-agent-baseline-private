# Tarea 2 — decisión de tratamiento (4 clases)

**Pregunta** (fija en `agent_prompt.j2`): ¿qué manejo recomiendas a este paciente con
cáncer de próstata diagnosticado?

## Datos

| | |
|---|---|
| Casos con ground truth | **72** de 153: `active_treatment` 31 · `active_surveillance` 25 · `continued_surveillance` 14 · `watchful_waiting` **2** |
| Entrada | `task2/agent_input/<case>/structured-prompt.json` (el panel de T1 + `ct`, `bx_isup`, `bx_gl_prim`, `bx_gl_sec`, `bx_gl_tert`) + `prostate-treatment-decision-clinical-data.json` |
| Ground truth | `task2/ground_truth/<case>/prostate-treatment-decision.json` (la acción) + `prostate-treatment-decision-reasoning.json` |
| Ejemplo real | `../../fixture_data/task2/` (caso `T2-001`) |

## Herramientas (`../../contract/tool_schemas/tools_task2.json`)

| Herramienta | Campo devuelto | Sección en `reveal_sequence` |
|---|---|---|
| `get_mri_report` | `radiology_report` | `radiology_report` |
| `get_pathology_report` | `pathology_report` | `pathology_report` |
| `get_psa_trend` | `psa_trend` | `psa_trend` |
| `get_previous_notes` | `previous_notes` | `previous_notes` |
| `get_lab_results` | `laboratory_results` | `laboratory_results` |
| `get_family_history` | `family_history` | `family_history` |
| `search_guidelines(query)` | pasajes de guías (RAG) | — |

## Salida (esquema bloqueado)

```jsonc
// prostate-treatment-decision.json
"active_surveillance"   // | continued_surveillance | watchful_waiting | active_treatment
// prostate-treatment-decision-reasoning.json
{"confidence": "...",
 "variable_weights": {"ct","fh","age","psa","psad","cspca","pirads","bx_isup","bx_gl_sec","bx_gl_prim","comorbidity": "..."},
 "reveal_sequence": [...],
 "free_text": "..."}
```

## Qué aprende el modelo

- **react**: las secciones del `reveal_sequence` del urólogo en orden canónico
  (`get_mri_report` → `get_pathology_report` → `get_psa_trend` → `get_previous_notes`
  → `get_lab_results` → `get_family_history`), y después un razonamiento que termina en
  `Recommended management: <acción>.`
- **form_fill**: el JSON con `action`, `confidence`, pesos elegibles y `reasoning`.

## Lo que hay que vigilar

- **`watchful_waiting` tiene 2 casos.** No se puede aprender ni medir con fiabilidad:
  `make_folds.py` los reparte, pero cualquier recall de esa clase es anecdótico.
- El baseline acierta el 57 %, y **nunca** predice `continued_surveillance` ni
  `watchful_waiting` (recall 0). La confusión clave es `active_surveillance` frente a
  `continued_surveillance`: depende de si el paciente ya estaba en vigilancia, algo que
  está en las notas previas y en el `enc_type`.
- `mean_tool_score` del baseline es 0,0 en T2: el `reveal_sequence` es donde el LoRA más
  puede ganar sin tocar la decisión.
