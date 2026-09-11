# Entrega V1

## Sockets de salida — CONFIRMADOS (11-sep-2026)

Comprobado en la página del algoritmo `blackboard-experts-and-llms`, sección
**Interfaces**. El paso 1.2.3 queda cerrado.

**La clave: el slug y el nombre de fichero no son lo mismo.** Grand Challenge corta el
*slug* a 50 caracteres para identificarlo, pero el campo **Write to** lleva el nombre
entero.

| Tarea | Slug (≤50) | Write to |
|---|---|---|
| T1 decisión | `prostate-biopsy-decision` | `/output/prostate-biopsy-decision.json` |
| T1 razonamiento | `prostate-biopsy-decision-reasoning` | `/output/prostate-biopsy-decision-reasoning.json` |
| T2 decisión | `prostate-treatment-decision` | `/output/prostate-treatment-decision.json` |
| T2 razonamiento | `prostate-treatment-decision-reasoning` | `/output/prostate-treatment-decision-reasoning.json` |
| T3 decisión | `prostate-time-to-recurrence-or-last-follow-up` | `/output/prostate-time-to-recurrence-or-last-follow-up.json` |
| T3 razonamiento | `...-follow-up-**reas**` | `/output/...-follow-up-**reasoning**.json` |

**Dos hipótesis descartadas:** este algoritmo no declara la errata
`prostate-biospy-decision`, y el razonamiento de T3 no se escribe truncado.

`CHIMERA_SLUG_STRICT=canonical` es **el valor por defecto** y es lo correcto. El modo
alias escribiría un tercer fichero que GC no declara, y un fichero de más también cuenta
como *extra output files*. `tasks_complete/contrato.py::GC_OUTPUTS` fija los seis nombres
y un test los compara.

El razonamiento de T3 es **Kind: String** — cadena JSON suelta, que es lo que
`to_gc_outputs` escribe.

## Recursos

`CHIMERA_GPU_MEMORY_UTILIZATION` por defecto 0,80; `CHIMERA_VLLM_MAX_GIB` limita la
reserva absoluta; `CHIMERA_MAX_MODEL_LEN` permite bisecar contexto.

Medido: pico **21 502 MiB** sostenido 3 h 30 min bajo `--memory=32g`, RSS 5,9 GiB,
27 s/caso en T1, 46 s en T2, 4 s en T3.

## Entrypoint

`inference_v1.py`: 60 líneas que importan el `inference.py` real —el contrato del
contenedor, intacto— y sustituyen únicamente `run_merged_solution`, la función que
elige el paquete. `src/chimera_agent_baseline/output/schema.py`, el único fichero
bloqueado del reto, no se toca.

Va **junto** a `inference.py`, nunca encima: sustituirlo haría que se importase a sí
mismo.
