# Tarea 3 — tiempo hasta la recurrencia bioquímica (meses + evento)

**Pregunta** (fija en `agent_prompt.j2`): tras el tratamiento primario, ¿cuántos meses
hasta la recurrencia bioquímica?

## Datos

| | |
|---|---|
| Casos con ground truth | **75**, de ellos **19 con evento** (`event=1`) y 56 censurados |
| Entrada | `task3/agent_input/<case>/structured-prompt.json` (**simplificado**: `case_id`, `task`, `age`, `psa`, `dre`, `active_treatment_prior_to_surgery`) + `prostate-time-to-recurrence-or-last-follow-up-clinical-data.json` |
| Ground truth | `task3/ground_truth/<case>/prostate-time-to-recurrence-or-last-follow-up.json` → `{"months_to_recurrence": float, "event": 0|1}` (el razonamiento es opcional) |
| Ejemplo real | `../../fixture_data/task3/` (caso `T3-001`; su razonamiento viene del sistema entregado y solo sirve como ejemplo de formato) |

## Herramientas (`../../contract/tool_schemas/tools_task3.json`)

| Herramienta | Campo devuelto |
|---|---|
| `get_mri_report` | `radiology_report` |
| `get_pathology_report` | `pathology_report` (biopsia) |
| `get_surgical_pathology_report` | `surgical_pathology_report` (prostatectomía: ISUP, pT, márgenes, vesículas, ganglios) |
| `get_previous_notes` | `previous_notes` |
| `get_family_history` | `family_history` |
| `search_guidelines(query)` | pasajes de guías (RAG) |

No hay `get_psa_trend` ni `get_lab_results`. Algunos campos pueden venir a `null`.

## Salida

```jsonc
// prostate-time-to-recurrence-or-last-follow-up.json
{"months_to_recurrence": 65.7, "event": 0}
// prostate-time-to-recurrence-or-last-follow-up-reasoning.json
"texto libre"
```

El esquema bloqueado (`Task3Output`) **solo tiene `months_to_recurrence` y `reasoning`**.
El `event` lo escribe `run.py` como `structured.get("event", 0)`, es decir, **siempre 0**.
Por eso el acierto de evento del baseline (0,74) es exactamente la proporción de casos
sin evento. El LLM no puede cambiarlo a través del formulario.

## Qué aprende el modelo

- **react**: no hay `reveal_sequence` del lector, así que la política es fija: llamar a
  las 5 herramientas clínicas (en T3 no se puntúa el uso de herramientas). Después, un
  razonamiento que termina en
  `Estimated time to biochemical recurrence or last follow-up: <m> months.`
- **form_fill**: `months_to_recurrence` = meses del GT (1 decimal) y el razonamiento.

## Lo que hay que vigilar

- **La métrica de ranking es el c-index**, que solo mira el orden. En los casos
  censurados (`event=0`), los meses del GT son el último seguimiento, no una
  recurrencia. Entrenar a copiar esos meses mezcla las dos cosas. Es una limitación
  conocida del experimento "solo LLM".
- Con 75 casos y 19 eventos, los intervalos del c-index serán muy anchos. **Evalúa T3
  aparte** (brazo L2 del plan) para que no tape el resultado de T1/T2.
- Si quieres que `event` salga de algo distinto de 0, la única vía es cambiar
  `_write_task_outputs` en `agent_baseline/src/chimera_agent_baseline/run.py` (por
  ejemplo, `event = 1 if months < umbral`). Es legal, porque solo `schema.py` está
  bloqueado, pero ya no es "el agente sin tocar". Hay que declararlo.
