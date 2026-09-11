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

---

# Continuación (11-sep, tarde)

## Fase 6 — los candidatos medidos: 17 probados, 4 adoptados

### ADOPTADO — el portavoz de la tarea 3

`CHIMERA_T3_SPOKESPERSON` pasa de `capra` a **`selected`**.
**c-index 0,7371681416 → 0,8234513274 (+0,0863). OVERALL +0,0173.**

El paso 6.3.2 pre-registró *cómo* se decidiría antes de medir: validación anidada con
la selección de portavoz **dentro** de cada pliegue externo. Corrido así, `ASGDE` gana
14 de 15 pliegues, el IC pareado de DEV excluye cero ([0,0012, 0,3188]) y VAL reproduce
(0,8696 → 0,8870). Pasó su propia prueba.

Límites publicados: 19 eventos en total; el IC pareado del conjunto roza cero
([−0,0041, 0,2021]); VAL tiene exposición histórica; y `time_score` cae de 0,7540 a
0,7121 —no entra en el ranking de T3, sí en `mean_case_score`—.
Vuelta atrás: `CHIMERA_T3_SPOKESPERSON=capra`.
Evidencia: `experiments/results/{nested_survival,survival_total}.json`.

### ADOPTADO — los prompts de V1 en las tres tareas

Pases pareados: base y candidato en **una sola carga del juez**, dos pases cada uno.

| tarea | rationale base | rationale V1 | Δ pase 1 | Δ pase 2 |
|---|---:|---:|---:|---:|
| T1 | 0,8012 / 0,7964 | **0,8120 / 0,8108** | +0,0108 | +0,0145 |
| T2 | 0,8431 / 0,8492 | **0,8523 / 0,8523** | +0,0092 | +0,0031 |
| T3 | 0,4053 / 0,3760 | **0,4680 / 0,4600** | +0,0627 | +0,0840 |

**Los tres mejoran en los dos pases.** T2 era la arriesgada —su CHAIR ya era el mejor de
las tres y el plan advertía que alargarlo podía empeorar— y no lo hizo. T3 da la mayor
ganancia, coherente con que era el único CHAIR sin few-shot, sin marco clínico y sin
bucle de reto.

**La medición pareada se justificó sola.** El INFORME de la línea base publicaba
`rationale 0,6783` para T1; la **misma** salida, en esta carga, da **0,80**. Un salto de
0,12 entre cargas del juez, mayor que cualquier efecto medido. Comparar contra un número
de otra carga no habría dicho nada.

En T3 el candidato difiere de la base en **dos** cosas —prompts y portavoz—, así que la
comparación mide el efecto combinado. No se separa porque ambas se adoptan.

### RECHAZADOS — los trece restantes

| candidato | DEV | VAL | motivo |
|---|---|---|---|
| T1 umbral 0,35 | 0,7623 → **0,8010** | 0,7566 → **0,7297** | no reproduce en VAL |
| T1 política de confianza | 0,75 las tres | no leído | no bate a la moda |
| T2 formulario por experiencia | F1 0,6548 → **0,5834** | no leído | empeora en DEV |
| T1 guardias de cohorte en los tres cubos | 0,9333 → **0,8333** | no leído | empeora en DEV |
| T2 `ct` en el formulario | 0,3039 → **0,3070** | 0,3208 → **0,3189** | no reproduce en VAL |
| T1 guardia de PSAD en el peldaño 3 | no separa | — | 8 aciertos con PSAD<0,15 se romperían |
| T1 reordenar la cascada | 0,9219 → **0,8438** | no leído | empeora en DEV |
| T1 experto nuevo sobre bloques C/E/F | AUC 0,8214 → 0,8032/0,7945/**0,4877** | no leído | ningún bloque aporta |
| T2 familia nueva (kNN, RF…) | kNN 0,66 · RF 0,85 vs regla **0,88** | no leído | nada bate a la regla ISUP |
| T3 familia nueva | kNN 0,55 · RF 0,75 · ET 0,76 vs **0,79** | no leído | nada bate al Cox adoptado |
| T1 comité de familias | ET solo **0,8133** vs ET+RF 0,7979 | no leído | promediar diluye |
| T3 conjunto ASGDE+ET por rangos | 0,7903 → **0,8078** | 0,8348 → **0,8783** | **empeora sobre los 75**; y no es entregable |
| T2 unir 2 o 3 expertos | todo satura en **0,8800**; E1+E3 baja a 0,8600 | no leído | los buenos repiten la misma regla |
| Agrupamiento para detectar dónde falla | p=0,22 (T1) · p=0,31 (T2) | no leído | sin señal tras permutación |

**Lo que enseñan los rechazos, que vale más que los intentos:**

- **Las guardias de cohorte son específicas del cubo por una razón clínica.** El mismo
  PSA significa cosas opuestas según haya cáncer confirmado: con biopsia positiva previa,
  PSA≥20 pide estadificación; sin ella, es el motivo para biopsiar.
- **La cascada ya estaba bien ordenada.** El 0,8889 del voto está medido sobre los casos
  que hoy le tocan, otra población; en los 12 con grado documentado lo hace peor. El
  principio se aplica a la exactitud *en los casos que cada peldaño reclama*.
- **El conjunto de variables `important` de T2 es el óptimo del barrido.** Añadir
  cualquiera de las siete candidatas empeora salvo `ct`, y `ct` no reproduce.
- **No falta un experto en T1.** A+B+D es el óptimo; el bloque F (embeddings de RM) da
  **AUC 0,3791** con un modelo ajustado de verdad —bajo el azar— y hunde la fusión a
  0,4877. Eso cierra con medición la duda que dejaba el 0,43 de `image.py`.
- **Restricción de despliegue descubierta:** `gc_entry.py` declara *"un proceso/contenedor
  por paciente"*. El rango de un solo valor es siempre 1,0, así que **cualquier
  combinación por rangos o percentiles no es función del caso y no se puede entregar.**
  Se descubrió con un conjunto que mejoraba en DEV **y** en VAL y aun así empeoraba
  sobre los 75: los rangos dentro de cada split no componen el mismo orden que sobre la
  cohorte entera.
- **Al menos uno de los 8 fallos de T1 es ruido de etiqueta.** En `b9f0b7018502` la
  etiqueta dice `yes` pero el urólogo escribió *"rather than new biopsy… PSMA-PET"* con
  confianza `uncertain`. Y los dos fallos del peldaño 2 están en VAL, que es 6/6 en DEV:
  no hay forma honesta de ajustarlo.

## RESULTADO — OVERALL con juez, medido en una sola carga

| tarea | base (pase 1/2) | V1 (pase 1/2) |
|---|---:|---:|
| T1 | 0,8368 / 0,8364 | **0,8378 / 0,8377** |
| T2 | 0,8150 / 0,8156 | **0,8159 / 0,8159** |
| T3 | 0,7372 | 0,8832 *(dentro de muestra)* · **0,8235 honesto** |

| | pase 1 | pase 2 |
|---|---:|---:|
| OVERALL base | 0,8082 | 0,8082 |
| **OVERALL V1 honesto** | **0,8262** | **0,8261** |

**+0,018 sobre la línea base, reproducido en los dos pases.** El número defendible es
**0,826**: sustituye el c-index de T3 en modo `deployed` (0,8832, **dentro de muestra**)
por la estimación anidada. Sin juez: 0,7944 → **0,8117**.

De ese +0,018, la mayor parte viene del portavoz de T3 (+0,017) y el resto de los
prompts, pequeño porque el juicio de la nota pesa 0,20 del `case_score`, que es la
mitad del ranking.

## Qué era el 0,8406 de Debug, y por qué no es comparable

El informe real (`delete_final_versions_task/metrics (1).json`) muestra que **Debug
corrió 12 casos: cuatro por tarea.**

| tarea | Debug (4 casos) | nuestra medición (238) |
|---|---:|---:|
| T1 | **0,6861** | 0,8390 |
| T2 | **0,9155** | 0,8150 |
| T3 | **1,0000** | 0,8235 |
| OVERALL | **0,8406** | 0,8082 |

Un c-index de 1,0 con cuatro pacientes no dice nada. Y T1 salió castigado porque le
tocó `PT-pseudo_1dc32184cab6`, **uno de los ocho fallos ya analizados**.

Corriendo la misma versión sobre esos mismos 12 casos sacamos **0,8436** frente a su
0,8406: nuestra reproducción es fiel y los tres milésimos son el juez siendo otra
instancia. Y V1 sobre esos 12 da 0,8416 — **indistinguible**, porque T3 ya está en el
techo (c-index 1,0) y la mayor mejora de V1 no tiene dónde manifestarse.
**Un subconjunto que no puede mostrar tu mejora no dice nada sobre ella.**

## Herramientas de trabajo

- `tasks_complete/` — `runner.py`, `evaluar.py`, `experimento.py`, `contrato.py`.
  Orquestación que delega en los runners medidos; no hay una cuarta implementación.
- `experiments/iterar.py` — ciclo corto para ajustar prompts (5-17 min según tarea
  frente a las 1,7 h del pase riguroso). Exploratorio: con 20 casos el error del
  `rationale_score` ronda ±0,05.
- `verification/inference_v1.py` — el entrypoint, **60 líneas** en vez de las 504 que
  eran copia. Importa el `inference.py` real y sustituye una sola función.

Dos guardias que hubo que arreglar porque **no comprobaban nada**: el de residencia del
juez usaba `pgrep -f`, que casa con la línea de órdenes de quien busca —se detectaba a
sí mismo— y dependía de un nombre de proceso que Ollama cambió entre versiones; ahora
pregunta a `/api/ps` y compara digest y VRAM. Y el vigilante de la cobertura casaba con
la cadena `"oom_killed": false`, o sea gritaba con un registro de éxito.

## INCIDENTE — pérdida de documentación (11-sep-2026, ~07:19-07:24)

Cinco ficheros desaparecieron del raíz de V1 durante el empaquetado: `PLAN.md`,
`BITACORA.md`, `ENTREGA.md`, `ARQUITECTURA.md` y `ENTREGA_CHECKLIST.md`. La imagen que
los contenía se sobrescribió al reconstruir con el mismo tag, así que no se pudieron
recuperar de ahí. **No se ha identificado la causa.**

Ningún código, peso, artefacto ni resultado de experimento se perdió: `experiments/
results/` y `verification/` están intactos, y todas las cifras de esta bitácora salen de
ahí. Lo perdido era prosa.

**Lo que faltaba era control de versiones.** V1 nunca se puso bajo git —el directorio
figura como `??` sin trackear desde que se creó— así que no había red. Se corrige
comprometiéndolo al repositorio.

`ARQUITECTURA.md` lo escribió Codex y no se conserva copia; se reescribe desde el
código, declarando que es una reconstrucción y no el original.

## CORRECCIÓN — qué midieron en realidad los pases pareados (11-sep-2026)

Al recuperar el `ARQUITECTURA.md` original apareció un dato que obliga a corregir la
atribución de la mejora de prosa.

**Las variantes `enhanced` de los prompts están detrás de banderas y apagadas por
defecto**: `prompt_kit.enhanced(task)` sólo es cierto con `CHIMERA_T{N}_PROMPT=enhanced`,
y la cobertura pasó únicamente `GPU_MEMORY_UTILIZATION`, `SLUG_STRICT` y `VLLM_MAX_GIB`.

Entonces, ¿qué se midió? Diferencias de prompt **reales y activas por defecto**:

- `prompt_kit.secure` — la línea anti-inyección, aplicada a todos los roles sin bandera.
  Era el agujero declarado en la fase 2: T1 y T2 renderizaban documentos recuperados sin
  advertencia mientras T3 sí la llevaba.
- El renombrado `EXPERT-LIBRARY` → `EXPERT-EXPERIENCE` en el texto del roster.
- `prompt_kit.FINALIZE` en el grafo de T2.

**La medición es válida y el +0,018 corresponde a lo que se entrega.** Lo que no es
válido es la frase «los prompts de V1 mejoran» sin matizar: lo que mejora es la
configuración por defecto de V1, no las variantes `enhanced`, que **siguen sin medir**.

Codex las dejó apagadas a propósito, con el criterio correcto escrito en
`ARQUITECTURA.md`: *"el valor por defecto sigue siendo `baseline` hasta superar dos
pases pareados del juez"*. Ese pase no se les ha hecho.

**Queda por tanto una mejora candidata sin explorar**, medible con
`CHIMERA_T2_PROMPT=enhanced` y `CHIMERA_T3_PROMPT=enhanced`, y con `CHIMERA_T3_ADVICE=
enhanced` para las dos intervenciones adicionales de T3 (de 11 a 13).
