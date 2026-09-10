# Bitácora V1

## Fase 0 — copia y línea base

Desarrollada y verificada. Evidencia: `verification/phase0.json`. Los scores históricos se congelaron en `baseline_scores/`. No se ha adoptado ninguna mejora estadística.

## Fase 1 — entrega

En ejecución. Se corrige el productor T2 y su ruta de expertos en lote; guardia estricta; normalización de serializadores y runner; slugs configurables; presupuesto vLLM máximo de 20 GiB y fracción 0,80; medición de recursos.

La GPU sólo es accesible fuera del sandbox. Acceso al host comprobado: RTX 5090, 32607 MiB; Docker y Ollama disponibles.

## Fase 1 — cierre parcial (11-sep-2026)

El bloqueo de Development está resuelto en lo que se puede comprobar en local.
`verification/gpu_smoke_20260911_002810/validation.json`: las tres interfaces con
exit 0, dos ficheros, esquema válido y pico **21 502 MiB** bajo `--memory=32g`,
frente al techo de 22 GiB. El smoke anterior de la versión antigua daba exit 137
y cero ficheros en `interf0`.

Cobertura real en contenedor: **T3 75/75**, T1 **18/195**, T2 **0/153**. Falta GPU.

Pendiente y bloqueante: **1.2.3**, confirmar el slug de cada socket de salida en la
página del algoritmo. Es comprobación manual del usuario.

## Fase 6 — los cinco experimentos, con su veredicto

Ninguno adoptado. Tres rechazados por su propia medición y dos elegibles a la espera
de decisión.

| Experimento | DEV | VAL | Veredicto |
|---|---|---|---|
| T1 umbral 0,35 | 0,7623 → **0,8010** | 0,7566 → **0,7297** | Rechazado: no reproduce en VAL |
| T1 confianza | 0,75 las tres políticas | no leído | Rechazado: no bate a la moda |
| T2 formulario por experiencia | F1 0,6548 → **0,5834** | no leído | Rechazado: empeora en DEV |
| T3 horizonte `a=105` | 0,7699 → 0,7715 | 0,7181 → 0,7305 | **Elegible**, sin adoptar |
| T3 portavoz anidado | c 0,6427 → **0,7903**, IC [0,0012, 0,3188] | 0,8696 → **0,8870** | **Elegible**, sin adoptar |

**Sobre el umbral de T1.** Es el caso que justifica el protocolo entero: +0,039 en DEV
y −0,027 en VAL. Adoptarlo mirando sólo DEV habría empeorado la entrega.

**Sobre la experiencia profesional de T2.** Era la apuesta más prometedora del plan
—72 trazas completas, el `structured-prompt` más rico— y no salió: el candidato
empeora el F1 de factores en DEV, así que VAL no llegó a leerse. Se conserva la moda.

**Sobre el portavoz de T3.** El plan pre-registró en 6.3.2 que la decisión se tomaría
con validación anidada y selección dentro del bucle externo, no por el número. Corrido
así, `ASGDE` gana 14 de 15 pliegues y el c-index sobre los 75 pasa de **0,7372 a 0,8235**
(+0,0863, que son **+0,017 de OVERALL**). El IC pareado de DEV excluye cero y VAL
reproduce la dirección. Los límites, sin maquillar: 19 eventos en total, el IC del
conjunto roza cero ([−0,0041, 0,2021]), VAL tiene exposición histórica y no es una
cohorte externa, y el `time_score` cae de 0,7540 a 0,7121 — no entra en el ranking de
T3, pero sí en `mean_case_score`. Adoptarlo es decisión del usuario.

## Fase 7 — orquestación

`tasks_complete/` con `runner.py`, `evaluar.py`, `experimento.py` y `contrato.py`.
Delegan en los runners ya medidos: no hay una cuarta implementación de ninguna junta.
`contrato.py` reúne la compuerta de la fase 1 en un comando; `experimento.py` codifica
los cuatro motivos de rechazo del criterio 6.4 para que la decisión no dependa del
optimismo de quien mira la tabla. Cubierto por 12 tests.

El `Dockerfile_Baseline` **no** se ha reapuntado a V1: 7.3 espera a que 1.4.1 esté
completa, para poder volver atrás con una línea.

## Paso 1.2.3 — slugs confirmados (11-sep-2026)

Cerrado. El usuario leyó las Interfaces del algoritmo `blackboard-experts-and-llms`
y los seis sockets de salida coinciden **exactamente** con lo que el código escribe
en modo `canonical`.

La ambigüedad venía de confundir dos campos distintos. GC trunca el **slug** a 50
caracteres para identificarlo, pero el campo **Write to** lleva el nombre completo:

    slug      prostate-time-to-recurrence-or-last-follow-up-reas
    write to  /output/prostate-time-to-recurrence-or-last-follow-up-reasoning.json

El mismo corte aparece en la entrada `...-clin`, que lee de `...-clinical-data.json`.
Así que las dos hipótesis que quedaban abiertas se descartan: este algoritmo **no**
declara la errata `prostate-biospy-decision`, y el razonamiento de T3 **no** se
escribe truncado.

Consecuencia práctica: `canonical` pasa a ser el valor por defecto de
`CHIMERA_SLUG_STRICT`. El modo alias, que publicaba las dos grafías como red de
seguridad, ahora sería un fallo — escribiría un tercer fichero que GC no declara,
y un fichero de más también cuenta como *extra output files*. Se conserva sólo
como salida de emergencia.

Se añadió `tasks_complete/contrato.py::GC_OUTPUTS` con los seis nombres leídos de
la página, y la compuerta los compara contra lo que el código produce: un cambio
silencioso en cualquiera de los dos lados rompe la suite. 155 tests en verde.

Confirmado de paso que el razonamiento de T3 es **Kind: String** — cadena JSON
suelta, que es lo que `to_gc_outputs` ya escribía.

## Paso 7.3 — el entrypoint deja de estar duplicado (11-sep-2026)

Se comprobó primero si las reglas permiten tocar `inference.py`. Sí lo permiten:
[README.md:355-361](../README.md#L355) dice *"even the entry-point if you want"* y la
tabla de ficheros bloqueados tiene una única fila, `output/schema.py`;
[delete/README.md:420](../delete/README.md#L420) lo repite por su cuenta. **Aun así no
se toca**, porque es el contrato del contenedor y lo que acaba de hacer pasar Debug.

El problema real no era el permiso sino la duplicación: `verification/inference_v1.py`
era una copia de las 504 líneas de `inference.py` que difería en **una sola** — el
paquete del que sale `dispatch`. Un arreglo en el staging del tmpdir o en un manejador
de interfaz se habría aplicado a una copia y no a la otra, en silencio, y cuál se
entrega depende de qué monte el Dockerfile.

Ahora son **60 líneas**: importa el módulo real y reasigna `run_merged_solution`. Los
tres manejadores resuelven ese nombre en los globales de `inference` cuando lo llaman,
así que reciben la versión V1 sin que su código cambie. Cero líneas copiadas.

Dos detalles que costaron pensar y quedan fijados por tests:

1. **El envoltorio va junto a `inference.py`, no encima.** El smoke lo montaba sobre
   `/opt/app/inference.py`; con un envoltorio eso lo haría importarse a sí mismo. Pasa
   a `/opt/app/inference_v1.py` con `--entrypoint python3 ... inference_v1.py`.
2. **Las pruebas sustituyen el módulo real, no el envoltorio.** `INPUT_PATH`,
   `OUTPUT_PATH` y `USE_MERGED_SOLUTION` los leen los manejadores de sus propios
   globales; parchear una copia local no habría tenido efecto. El test usa
   `_wrapper.base`, lo que además hace que ahora ejercite el `inference.py` que se
   entrega en vez de un fork que podía derivar.

Verificado dentro del contenedor: `import inference_v1` resuelve
`base -> /opt/app/inference.py` y la redirección queda aplicada. 157 tests en verde.
