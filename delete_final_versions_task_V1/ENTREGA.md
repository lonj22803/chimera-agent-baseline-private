# Entrega V1

## Sockets de salida — CONFIRMADOS (11-sep-2026)

Comprobado en la página del algoritmo `blackboard-experts-and-llms`, sección
**Interfaces**. El paso 1.2.3 queda cerrado.

**El detalle que resolvió la ambigüedad: el slug y el nombre de fichero no son lo
mismo.** Grand Challenge corta el *slug* a 50 caracteres para identificarlo, pero
el campo **Write to** lleva el nombre entero. Por eso T3 aparece como
`prostate-time-to-recurrence-or-last-follow-up-reas` y escribe, sin embargo, en
`...-reasoning.json`. El mismo corte se ve en la entrada `...-clin`, que lee de
`...-clinical-data.json`.

| Tarea | Slug (identidad, ≤50) | Write to (el fichero real) |
|---|---|---|
| T1 decisión | `prostate-biopsy-decision` | `/output/prostate-biopsy-decision.json` |
| T1 razonamiento | `prostate-biopsy-decision-reasoning` | `/output/prostate-biopsy-decision-reasoning.json` |
| T2 decisión | `prostate-treatment-decision` | `/output/prostate-treatment-decision.json` |
| T2 razonamiento | `prostate-treatment-decision-reasoning` | `/output/prostate-treatment-decision-reasoning.json` |
| T3 decisión | `prostate-time-to-recurrence-or-last-follow-up` | `/output/prostate-time-to-recurrence-or-last-follow-up.json` |
| T3 razonamiento | `prostate-time-to-recurrence-or-last-follow-up-**reas**` | `/output/prostate-time-to-recurrence-or-last-follow-up-**reasoning**.json` |

**Dos hipótesis previas quedan descartadas:** este algoritmo no declara la errata
`prostate-biospy-decision`, y el razonamiento de T3 no se escribe truncado.

`CHIMERA_SLUG_STRICT=canonical` es **el valor por defecto** y es lo correcto. El
modo alias (variable vacía) escribiría un tercer fichero en T3 que GC no declara,
y un fichero de más también cuenta como *extra output files*. Se conserva sólo
como red de emergencia. `tasks_complete/contrato.py::GC_OUTPUTS` fija los seis
nombres y el test los compara, así que un cambio silencioso rompe la suite.

Confirmado también que el razonamiento de T3 es **Kind: String** — una cadena JSON
suelta, no un objeto. Es lo que `task_3/agent/decide.py::to_gc_outputs` ya escribe.

## Recursos

`CHIMERA_GPU_MEMORY_UTILIZATION` por defecto 0,80; `CHIMERA_VLLM_MAX_GIB=20` limita
la reserva absoluta; `CHIMERA_MAX_MODEL_LEN` permite bisecar contexto. El smoke de
contenedor mide el pico real del dispositivo; RSS no es VRAM.

Último smoke: `verification/gpu_smoke_20260911_002810/` — tres interfaces, exit 0,
dos ficheros, esquema válido, pico **21 502 MiB** bajo el techo de 22 GiB.
