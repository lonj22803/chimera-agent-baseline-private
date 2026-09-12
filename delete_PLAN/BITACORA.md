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

## ADOPTADO — el portavoz de la tarea 3 (11-sep-2026)

`CHIMERA_T3_SPOKESPERSON` pasa de `capra` a **`selected`** por defecto.

**c-index 0,7371681416 → 0,8234513274 (+0,0863). OVERALL sin juez 0,7944 → 0,8117 (+0,0173).**

Es la mayor palanca que quedaba: vale lo mismo que arreglar los ocho fallos de
decisión de la tarea 1 juntos (+0,0022 cada uno).

**Por qué se adopta, y por qué no es una elección post-hoc.** El paso 6.3.2 del plan
pre-registró cómo se tomaría esta decisión *antes* de medir: validación anidada con
la selección de portavoz **dentro** de cada pliegue externo, no por comparar OOF
almacenados. Corrido así, `ASGDE` gana 14 de 15 pliegues, el IC pareado de DEV
excluye cero ([0,0012, 0,3188]) y VAL reproduce la dirección (0,8696 → 0,8870).
Pasó su propia prueba. Descartarlo entonces habría sido sesgo, no prudencia.

**Verificado antes de fijarlo.** Se recalculó el c-index de la cohorte de 75 casos
con los dos portavoces, de punta a punta desde `Panel.horizon`, no leyendo el JSON
del experimento. Ambos valores quedan anclados en `test_invariantes_t3.py`, junto a
una comprobación de que el defecto es el adoptado: cambiarlo sin querer rompe la
suite en vez de cambiar la nota en silencio.

**Los límites, sin maquillar.** 19 eventos en total. El IC pareado del conjunto roza
cero ([−0,0041, 0,2021]). VAL tiene exposición histórica: es confirmación, no cohorte
externa. Y el `time_score` cae de 0,7540 a 0,7121 — no entra en el ranking de T3,
que es sólo c-index, pero sí en `mean_case_score`, que se publica al lado.

**Vuelta atrás:** `Panel(spokesperson='capra')` o `CHIMERA_T3_SPOKESPERSON=capra`.

## Un hallazgo que reordena el trabajo restante

**La prosa de la tarea 3 no mueve el ranking.** El `ranking_score` de T3 es el
c-index y nada más; los 0,3987 de `rationale_score` sólo entran en `mean_case_score`,
que se publica pero no clasifica. El trabajo de la fase 5.2 es cosmético para el
leaderboard, y conviene saberlo antes de gastar GPU en pases del juez ahí.

Lo que sí tiene valor de ranking, por orden: los fallos de decisión de T1 (+0,0022
por caso) y T2 (+0,0028 por caso), y la prosa de T1/T2, que sí pesa 0,20 del
`case_score` y por tanto la mitad del ranking de esas dos tareas.

## RECHAZADO — extender las guardias de cohorte a los tres cubos (11-sep-2026)

Buscando el margen para pasar de 0,8117 a 0,87, el primer candidato salió del
análisis de los ocho fallos de decisión de la tarea 1. **Seis de los ocho son
falsos positivos**: el sistema sobre-biopsia. Tres de ellos los reclama el criterio
de cohorte y dos el grado documentado.

**La hipótesis.** Las tres guardias de abstención (`psa>=20`, `edad>=78`,
`pirads<=2`) sólo se aplican en el cubo `bx=Positive`, porque salieron de leer los
49 `free_text` de ese cubo. Su razonamiento clínico —"un hombre de 82 años con
enfermedad de bajo riesgo no necesita más diagnóstico"— parecía no depender de
haber tenido una biopsia positiva. Si generalizara, arreglaría `175e6ad47991`
(cubo Negative, 79 años, etiqueta `no`).

**El resultado: empeora.** Sobre los mismos 30 casos de DEV la exactitud cae de
**0,9333 a 0,8333**. Arregla uno y rompe cuatro. VAL no se lee.

**Por qué, y esto vale la pena conservar.** La asimetría no era un descuido: **el
mismo PSA significa cosas distintas según haya cáncer confirmado o no.** Con
biopsia positiva previa, PSA≥20 pide estadificación en lugar de más tejido; sin
biopsia previa, PSA≥20 es justamente el motivo para biopsiar. Extender la guardia
invierte la decisión donde más importa. Con la edad pasa igual: el único caso de
≥78 sin biopsia previa está etiquetado `yes`.

**Un detalle de método que casi me engaña.** La primera medición daba 30 casos
para la regla base y 36 para el candidato, porque las guardias hacen decidir casos
del cubo Positive que la base dejaba indeterminados. Comparar exactitudes sobre
denominadores distintos no dice nada. `medir()` acepta ahora un `universo` para que
ambas se midan sobre los mismos casos.

Evidencia: `experiments/results/cohort_guards.json`, `experiments/cohort_guards.py`.

## Cobertura 1.4.1 — T1 y T3 completas y limpias (11-sep-2026)

En contenedor real, con vLLM y expertos desplegados:

| Tarea | Casos | Tiempo | Pico VRAM | Contrato | Formularios |
|---|---|---:|---:|---|---|
| T1 | **195/195** | 5 216 s | 21 502 MiB | 0 errores | 0 incompletos |
| T3 | **75/75** | 311 s | 21 502 MiB | 0 errores | no aplica |
| T2 | en marcha | | | | |

270 de 423 casos, exit 0 y sin OOM en las dos. Lo que esto demuestra y no demuestra:
**demuestra** que el arreglo de `variable_weights` en la causa se sostiene sobre los
195 casos de T1 —no sólo sobre los 91 etiquetados— y que el presupuesto de VRAM se
mantiene estable bajo `--memory=32g` durante 87 minutos seguidos; **no demuestra**
nada sobre la calidad de las predicciones, porque la cobertura no es evaluación.

Nota de método: el vigilante dio un falso positivo de fallo porque el filtro casaba
con la cadena `"oom_killed": false`. Corregido a `oom_killed": true` y
`exit_code": [1-9]`. Un filtro que grita con un registro de éxito es peor que no
tenerlo: enseña a ignorar la alarma.

## RECHAZADO — `ct` en el formulario de la tarea 2 (11-sep-2026)

Segundo intento sobre `important_decisive_f1` (0,6732, peso 0,15), el componente
flojo atacable de T2.

La política marca cuatro variables como `important` y el patrón pide **4,43 de
media**: faltaba aproximadamente una. El barrido en DEV dejó claro cuál: de las
siete candidatas **sólo `ct` mejora** (+0,0225 de F1), las otras seis empeoran, y
quitar cualquiera de las cuatro actuales cuesta entre 0,08 y 0,11. Es decir, **el
conjunto actual ya es el óptimo del barrido**, que era la primera cosa útil de saber.

Se midió el efecto **neto** sobre `mean_case_score`, no sólo el F1: subir `ct` de
`noted` a `important` mueve también `variable_weight_score`, que pesa 0,25 frente a
0,15. Sin eso, el F1 solo habría dado una mejora ficticia.

La variante condicional —`ct` important únicamente si el estadio no es cT1c— no era
un ajuste a los datos sino lo que el sistema de estadiaje significa: cT1c es tumor
impalpable detectado sólo por elevación de PSA, así que el estadio no aporta; cT2a en
adelante es enfermedad palpable, que sí pesa al elegir tratamiento. 51 de los 72 casos
son cT1c.

| | DEV | VAL |
|---|---:|---:|
| base | 0,3039 | 0,3208 |
| `ct` si palpable | **0,3070** | **0,3189** |

**Gana en DEV, pierde en VAL. Rechazado.** Aun si hubiera reproducido, la magnitud
era +0,0006 de OVERALL.

## RECHAZADOS — dos cambios arquitectónicos en la cascada de T1 (11-sep-2026)

Buscando exactitud de inferencia por arquitectura, no por umbrales.

**a) Guardia de PSAD en el peldaño 3.** Los tres fallos del voto ponderado comparten
PSAD bajo (0,053, 0,11, 0,126) con `p` apenas sobre el umbral, y PSAD < 0,15 es un
criterio de guía estándar. Parecía limpio. **No separa:** hay ocho casos correctos
con PSAD < 0,15 que la guardia rompería —incluido uno con PSAD 0,01 y etiqueta `yes`—
y las `p` de los fallos (0,53–0,61) se entrelazan con las de los aciertos (0,455 a
0,763). Ninguna frontera en ese plano separa. El peldaño 3 está en su límite con
estas variables.

**b) Reordenar la cascada.** Este parecía el hallazgo bueno: el diseño declara que
los peldaños van *"ordenados por acierto medido"*, y **no lo están**. Dispara 1 → 2 → 3
mientras el acierto es 1 (0,9423) > 3 (0,8889) > 2 (0,8333): el peldaño menos exacto
de los tres intercepta 12 casos antes de que hable el voto ponderado.

Intercambiarlos **empeora**: 0,9219 → **0,8438** en DEV, rompiendo cinco casos que el
grado documentado sí acertaba. VAL no se lee.

**La lección, que vale más que el intento.** El 0,8889 del voto está medido *sobre los
casos que hoy le tocan*, que son otra población —más fácil—. Sobre los 12 casos donde
hay un grado documentado, el voto lo hace peor que la regex. El principio de ordenar
por acierto se refiere a la exactitud de cada peldaño **en los casos que reclama**, no
a su tasa global; comparar tasas marginales entre poblaciones distintas es la trampa.
**La cascada ya estaba bien ordenada**, y ahora está medido en vez de supuesto.

Medido con las predicciones `honest` (out-of-fold) del caché, no las desplegadas: las
desplegadas se ajustaron sobre esta misma cohorte y habrían dado un techo.

## Los 5 casos que no hay que romper — y por qué el peldaño 2 no se toca (11-sep-2026)

Se pidió conservar los cinco casos que el intercambio de cascada rompía. Al buscar
cómo, apareció el dato que cierra la pregunta:

**En DEV el peldaño 2 es 6/6. Sus dos únicos fallos están en VAL.**

| rama del peldaño 2 | DEV | VAL |
|---|---|---|
| predice `no` | 6 casos, **6 correctos** | 1 caso, 0 correctos |
| predice `yes` | **0 casos** | 4 casos, 3 correctos |

La rama que falla —"grado documentado → biopsiar"— **no tiene un solo ejemplo en DEV**.
No se puede ajustar sin mirar el conjunto de confirmación, y mirarlo lo inutiliza: el
número resultante sería incomprobable. La forma de no romper esos cinco casos es no
tocar el peldaño, que ya es óptimo en DEV.

**Diagnóstico de los dos fallos, leyendo el texto del urólogo (diagnóstico, no ajuste):**

- `b9f0b7018502`, etiqueta `yes`. El urólogo escribió: *"**Rather than new biopsy**,
  consider low threshold for reevaluate MRI ... and possibly PSMA-PET"*, con confianza
  `uncertain`. **Su propio texto contradice la etiqueta.** Nuestra predicción `no`
  coincide con su razonamiento. Es ruido de etiqueta: irreducible.
- `d7d26761c714`, etiqueta `no`. El texto la respalda: *"Low risk PC ... no red flags
  ... entered active surveillance this year"*. Aquí sí fallamos: la regla disparó
  GG1 → biopsiar sobre un paciente ya en vigilancia. Arreglable en principio, pero el
  único ejemplo está en VAL.

La regla que lo arreglaría (GG1 + PSAD baja + ya en vigilancia → diferir) sería n=1
ajustado en VAL. Subiría el número local sin decir nada del número del reto — el
mismo mecanismo que ya falló con el umbral de 0,35: **+0,039 en DEV, −0,027 en VAL**.
No se adopta.

**Consecuencia para el techo:** al menos uno de los 8 fallos de T1 es ruido de
etiqueta, no error. El techo honesto de T1 está por debajo de 91/91.

## RECHAZADO — un experto adicional para la tarea 1 (11-sep-2026)

Se pidió crear un experto nuevo si hacía falta. El candidato era evidente: de los seis
bloques de rasgos que `dataset.py` define para T1, **tres no los usa nadie** —C
(psa_trend), E (notes) y F (embeddings de RM)—. La fusión consume sólo A+B+D.

Validación cruzada estratificada, 5 pliegues × 3 semillas, imputación dentro del
pliegue, **sólo DEV** (64 casos, 39 positivos):

| combinación | columnas | AUC OOF |
|---|---:|---:|
| A (panel solo) | 39 | 0,7270 |
| **A+B+D (fusión actual)** | 72 | **0,8214** |
| A+B+D+E (+notes) | 80 | 0,8032 |
| A+B+C+D (+psa_trend) | 91 | 0,7945 |
| A+B+C+D+E | 99 | 0,7860 |
| A+F | 1063 | 0,4402 |
| A+B+D+F (+embeddings) | 1096 | 0,4877 |
| F solo (embeddings de RM) | 1024 | **0,3791** |

**Ningún bloque sin usar aporta. La fusión actual es el óptimo del barrido.**

Lo más valioso es el dato de F. `image.py` publicaba `TASK1_HEAD_AUC = 0.43`, pero ese
número era la cabeza del baseline aplicada a vectores congelados — no un modelo
ajustado sobre el bloque. Ahora está medido con un modelo entrenado de verdad:
**0,3791**, por debajo del azar y consistente entre semillas (sd 0,038). Los
embeddings de resonancia no llevan señal utilizable para la decisión de biopsia, y
añadirlos es activamente dañino: 1024 dimensiones de ruido ahogan 72 rasgos reales y
la fusión cae de 0,8214 a 0,4877.

Esto cierra con medición una pregunta que estaba a medias: no falta un experto en T1.
La composición actual **es** la mejor combinación de bloques disponible, y C, E y F
están correctamente excluidos. VAL no se lee: no hubo mejora que confirmar.

## RECHAZADO — un experto de otra familia para T2 y T3 (11-sep-2026)

Se preguntó si añadir un kNN probabilístico, un Random Forest u otra familia mejoraría
el poder de decisión. Se midió en lugar de responder con la documentación.

**Tarea 2.** El catálogo ya trae 17 familias, kNN ponderado y Random Forest incluidos.
Corridas todas sobre DEV (50 casos), CV estratificada 5 × 3 semillas, bloques ACDGHIJ:

| modelo | acc CV | sd |
|---|---:|---:|
| **grade_rule (la regla ISUP)** | **0,8800** | 0,0000 |
| extra_trees / extra_trees_balanced | 0,8800 | 0,0000 |
| lda | 0,8733 | 0,0377 |
| random_forest_balanced | 0,8667 | 0,0094 |
| random_forest | 0,8533 | 0,0189 |
| deep_ensemble_mlp | 0,7533 | 0,0094 |
| **knn (k=10, ponderado)** | **0,6600** | 0,0432 |
| gaussian_nb | 0,5933 | 0,0249 |

**Nada bate a la regla.** Extra Trees la empata exactamente; Random Forest queda por
debajo; el kNN se hunde 22 puntos. Confirma con medición propia lo que estaba escrito.

**Tarea 3.** No hay `scikit-survival` ni `lifelines`, así que las familias de árboles se
aplicaron con el enfoque estándar de **supervivencia en tiempo discreto**: clasificar
"evento antes de H" entre los pacientes **en riesgo** en H —excluyendo a los censurados
antes de H, que es como se trata la censura sin sesgar— sumando sobre H = 24, 36 y 60
meses. Criterio: c-index, que es el ranking oficial. DEV = 52 casos, 13 eventos.

| modelo | c-index |
|---|---:|
| **ASGDE (Cox de fusión, adoptado)** | **0,7903** |
| extra_trees | 0,7631 |
| random_forest | 0,7515 |
| CAPRA-S | 0,6427 |
| **kNN probabilístico** | **0,5476** |

Los árboles **sí** baten a CAPRA-S (0,6427), lo que respalda a posteriori la adopción
del portavoz de fusión; pero **no lo mejoran**. El kNN queda cerca del azar, coherente
con lo previsto: con 13 eventos en DEV, un vecindario de 7 casos contiene alrededor de
un evento, y eso es ruido, no señal.

VAL no se lee en ninguna de las dos: no hubo mejora que confirmar.

## RECHAZADO — combinar expertos en vez de elegir uno (11-sep-2026)

Se preguntó si en T1 conviene votar con dos o tres expertos en lugar de uno, y cómo
mejorar la inferencia de la pizarra en T3. Las dos preguntas son la misma idea
arquitectónica —**combinar en vez de seleccionar**— y no estaba medida.

**Tarea 1: no.** Diversidad de familias sobre el bloque ABD, AUC fuera de muestra en DEV:

| | AUC |
|---|---:|
| **extra_trees solo (actual)** | **0,8133** |
| ET + RF | 0,7979 |
| ET + RF + GB | 0,7785 |
| las cinco familias | 0,7467 |

Las demás familias valen 0,69–0,71 sobre estos rasgos; promediarlas sólo diluye el
buen modelo. Un experto fuerte y cuatro débiles no forman un comité mejor.

**Tarea 3: parecía funcionar, y es el caso más instructivo del día.**

| | DEV | VAL | **los 75** |
|---|---:|---:|---:|
| ASGDE solo (adoptado) | 0,7903 | 0,8348 | **0,8235** |
| ASGDE 2:1 extra_trees | **0,8078** | **0,8783** | **0,8142** |

Mejora en DEV. Mejora en VAL, con peso predeclarado 2:1 y el ET entrenado **sólo con
DEV**. Y sin embargo **empeora sobre los 75** (−0,0093, IC pareado [−0,0438, +0,0242]).

No es una paradoja: **el promedio de rangos depende del conjunto sobre el que se
ranquea**. Los rangos dentro de DEV y dentro de VAL no componen el mismo orden que los
rangos sobre los 75, así que las dos confirmaciones medían objetos distintos del que se
entregaría. La medida del conjunto completo es la única que corresponde al despliegue,
y dice que no.

**Y hay una razón que lo descarta aunque los números hubieran salido bien:**
`gc_entry.py` lo declara en su cuarta línea — *"Un proceso/contenedor por paciente"*.
El rango de un solo valor es siempre 1,0. **Un conjunto por rangos no es una función
del caso**: necesita una cohorte contra la que ordenar, y el contenedor ve un paciente.
Cualquier combinación futura tiene que ser una función del caso —promediar riesgos
calibrados, no rangos— o no se puede entregar.

Esto respalda de paso la elección del portavoz adoptado: el Cox de fusión produce un
log-riesgo **por caso**, que sí es deployable.

## RECHAZADO — unir dos o tres expertos en la tarea 2 (11-sep-2026)

T2 **elige** un portavoz (E1 → E5 → E3 → respaldo) y nunca combina. Se preguntó si
unir dos o tres decidiría mejor. A diferencia del conjunto por rangos de T3, el voto
blando **sí es función del caso**, así que sería entregable: la pregunta era legítima.

Sólo tres expertos son diversos —E2 y E4 emiten las mismas 72 decisiones que E1—, así
que las combinaciones con sentido son seis. CV estratificada 5 × 3 semillas en DEV,
columnas de probabilidad alineadas al conjunto global de clases (algunos pliegues no
ven `watchful_waiting`, que tiene un solo caso en DEV):

| combinación | acc |
|---|---:|
| **E1 solo (portavoz actual)** | **0,8800** |
| E5 solo | 0,8800 |
| E3 solo | 0,7000 |
| E1 + E5 · E3 + E5 · E1 + E3 + E5 | 0,8800 |
| **E1 + E3** | **0,8600** |

Lo mismo con producto de expertos (media geométrica): idénticos resultados.

**Nada mejora, y unir E1 con E3 empeora.** La razón es estructural: E1 y E5 están
re-expresando la misma regla ISUP —por eso saturan los dos en 0,8800—, así que
combinarlos es promediar dos opiniones idénticas. E3 es el único genuinamente
distinto, pero vale 0,70; sumarlo siempre diluye.

Esto **justifica la arquitectura actual en lugar de sustituirla**: no combinar a E3
sino usarlo como desempate, hablando sólo cuando los demás están en `discuss`, es la
forma de conservar su aporte sin pagar su error. En la corrida real fue portavoz en
3 casos y acertó los 3. Un voto blando permanente habría perdido eso.

## RECHAZADO — agrupamiento para predecir dónde falla el protocolo (11-sep-2026)

La idea: si los fallos se concentraran en una región del espacio de rasgos, un
agrupamiento no supervisado la encontraría sin mirar la etiqueta, y esa región podría
enrutarse a otro experto. Es **distinta** de lo ya probado: en T2 se intentó un
detector *supervisado* (AUC 0,63, ruido), pero agrupar no se había probado en ninguna.

**El peligro de este experimento era encontrar algo.** Con 5 fallos en 64 casos,
partir en k grupos y quedarse con el más sucio produce enriquecimiento casi siempre,
por el puro azar de repartir cinco bolas en k urnas. Por eso el criterio no fue "hay
un clúster con más errores" sino un **test de permutación**: 5 000 barajas de la
etiqueta acierto/fallo sobre los mismos clústeres.

Tres algoritmos (k-medias, jerárquico, mezcla gaussiana) × k ∈ {2,3,4,5}:

| tarea | fallos | grupo más sucio | p (permutación) |
|---|---|---|---:|
| T1 | 5/64 | 1/3 = 0,333 | **0,2164** |
| T2 | 4/50 | 3/12 = 0,250 | **0,3129** |

**Ninguno se acerca a 0,05**, y eso es *antes* de corregir por las 12 configuraciones
probadas en cada tarea, lo que los alejaría más. El "grupo sucio" de T1 son tres casos
con un fallo: exactamente lo que produce el azar.

**Conclusión: no hay un "dónde falla" que aprender.** Coincide con el detector
supervisado de T2 y lo extiende a T1 y al caso no supervisado. Los fallos son casos
individualmente difíciles —uno de ellos, ya comprobado, es ruido de etiqueta— no una
región del problema. Un experto complementario enrutado por región no tendría a qué
agarrarse.

Nota de método: la primera corrida marcó 50 fallos de 50 en T2 porque comparé nombres
de clase contra los **índices** que devuelve `build_labels`. Se añadió una guarda que
lanza si la tasa de fallo supera 0,5, porque T2 acierta el 90 %: un experimento que
mide un disparate debe romperse, no reportarlo.

## FASE 1 CERRADA — la compuerta pasa entera (11-sep-2026)

Cobertura completa en contenedor real, con vLLM y expertos desplegados:

| Tarea | Casos | Tiempo | Exit | Pico VRAM | Contrato | Formularios |
|---|---|---:|---|---:|---|---|
| T1 | **195/195** | 5 216 s | 0 | 21 502 MiB | 0 errores | 0 incompletos |
| T2 | **153/153** | 7 048 s | 0 | 21 504 MiB | 0 errores | 0 incompletos |
| T3 | **75/75** | 311 s | 0 | 21 502 MiB | 0 errores | no aplica |
| **Total** | **423/423** | **3 h 30 min** | | **< 22 GiB** | **0** | **0** |

`tasks_complete/contrato.py` en verde en sus cuatro comprobaciones: slugs confirmados,
recursos bajo el techo, cobertura completa y formularios completos.
Evidencia: `verification/contrato_423.json`.

**Qué cierra esto.** Los tres motivos por los que la entrega anterior no pasó
Development están medidos y resueltos:

1. `interf0` salía con **exit 137 (OOM) y cero ficheros**; ahora las tres interfaces
   salen con exit 0 y dos ficheros, con el pico estable en 21,5 GiB durante tres horas
   y media seguidas bajo `--memory=32g`.
2. El **16 % de los `-reasoning.json` de T2** salía con 8 claves en vez de 11; ahora
   **0 incompletos sobre los 348 casos de T1 y T2**, no sólo sobre los 163 etiquetados
   que teníamos medidos. Arreglado en la causa (`protocol.py`), no en el borde.
3. Los **slugs** estaban sin confirmar; ahora verificados contra la página del
   algoritmo y anclados en `contrato.py::GC_OUTPUTS` con un test que los compara.

**Qué NO demuestra.** Nada sobre la calidad de las predicciones: la cobertura es
contrato, no evaluación. Los 423 incluyen los casos sin etiqueta, que no se pueden
puntuar.

## Puntuación V1 con el evaluador oficial, juez apagado (11-sep-2026)

Sobre los 238 casos etiquetados, con la salida real del contenedor.

| tarea | línea base | V1 | Δ |
|---|---:|---:|---:|
| T1 · biopsia | 0,8390 | 0,8390 | +0,0000 |
| T2 · tratamiento | 0,7784 | 0,7784 | +0,0000 |
| T3 · recurrencia | 0,7372 | **0,8832** | +0,1460 |
| **OVERALL medido** | 0,7944 | 0,8236 | +0,0292 |
| **OVERALL honesto** | 0,7944 | **0,8117** | **+0,0173** |

**El 0,8236 no es el número que se publica.** La corrida de T3 va en modo `deployed`:
los cinco modelos se ajustaron sobre esos mismos 75 casos y se aplican a ellos, así que
el 0,8832 es **dentro de muestra** — un techo de mecanismo, no rendimiento. Es el mismo
artefacto que el `self_match` de la biblioteca de T1, que sube la nota local a 0,9469 y
en el test no puede ocurrir nunca.

**El número defendible es 0,8117**, que usa la estimación anidada de T3 (0,8235), con
la selección de portavoz dentro de cada pliegue externo.

T1 y T2 salen **idénticos a la línea base hasta el cuarto decimal**, que es lo esperado
—no se adoptó ningún cambio en ellas— y confirma de paso que el renombrado del paquete,
los arreglos de contrato y `tasks_complete` no alteraron ni una predicción.

Nota: la primera cobertura de T3 corrió con el portavoz antiguo, porque el código
congelado en `/tmp` se copió antes de cambiar el defecto. Se re-corrió en contenedor
(75/75, exit 0) y esa es la salida puntuada aquí. El contrato no dependía de ello, así
que la Fase 1 siguió cerrada.

## Verificación del formato de salida de la tarea 3 (11-sep-2026)

Validación estricta de los 75 casos, en las dos corridas en contenedor:

| comprobación | resultado |
|---|---|
| claves de la decisión | exactamente `{event, months_to_recurrence}` en 75/75 |
| tipo de `event` | `int`, siempre 0 o 1 |
| tipo de `months_to_recurrence` | `float`, finito y ≥ 0 en 75/75 |
| `-reasoning.json` | **cadena JSON suelta** en 75/75 (617–1371 caracteres) |

**Cero incumplimientos.**

La única diferencia con el ejemplo de la página del algoritmo es cosmética: escribimos
`29.838803290639163` donde el ejemplo muestra `31.4`. No es un incumplimiento —en JSON
un número no tiene formato y el evaluador hace aritmética de coma flotante—, pero se
midió por si conviniera igualarlo:

| precisión | valores repetidos | c-index |
|---|---:|---:|
| sin redondear (actual) | 12 | 0,8831858407 |
| 2 decimales | 12 | 0,8831858407 |
| 1 decimal | 12 | 0,8831858407 |
| 0 decimales | 24 | 0,8836283186 |

Redondear a 1 o 2 decimales es **inocuo y está medido**: c-index idéntico dígito a
dígito. A 0 decimales sí cambia, porque crea 12 empates nuevos.

**Se decide no tocarlo.** El formato ya es válido y cualquier cambio en la ruta de
salida añade riesgo por cero ganancia, y es justo la ruta que acaba de pasar la
compuerta 423/423.

Los 12 valores repetidos no son un defecto: son casos con el mismo riesgo derivado de
CAPRA-S, que reciben el mismo horizonte. El c-index los trata como empates y les asigna
medio punto, que es lo correcto.

## Los pases pareados del juez — en marcha (11-sep-2026)

Última pieza del plan: las fases 2.2, 4 y 5.2 exigen medir la prosa, y ninguna estaba
medida. Los prompts de V1 **sí** difieren del original en las tres tareas (27, 8 y 21
líneas) y `prompt_kit` está cableado en las tres, así que hay algo que comparar.

La comparación se hace **pareada**: base y candidato puntuados dentro de una misma
carga de Ollama, dos pases cada uno. Un pase suelto no distingue mejora de ruido —dos
pases consecutivos de T2 dieron 0,8031 y 0,8150 sin tocar nada— y dos cargas distintas
no son comparables en absoluto. Las tres tareas van encadenadas sin descargar el modelo
entre medias.

**Un guardia que no comprobaba nada, y costó dos intentos arreglarlo.**
`paired_judge.py` verifica que el modelo del juez no se haya recargado a mitad de la
medición. Lo hacía con `pgrep -f 'ollama runner'`, y falló dos veces seguidas:

1. **Primero abortó por no encontrar nada.** Esta versión de Ollama lanza el runner como
   `/usr/local/lib/ollama/llama-server`; el patrón antiguo no casaba. Al ejecutarlo a
   mano **sí** daba positivo, porque `pgrep -f` casa con la línea de órdenes de quien
   busca: la comprobación se detectaba a sí misma.
2. **Después abortó por lo contrario**, «Ollama runner changed during paired
   measurement», tras ampliar el patrón. El PID «nuevo» era transitorio y ya no existía
   al investigarlo; `/api/ps` confirmaba **un solo** modelo residente, fijado con
   `keep_alive:-1`, servido por el runner original. Otro falso positivo de `pgrep`.

**Corregido de raíz: el guardia ya no mira procesos, pregunta a `/api/ps`.** Compara
nombre, digest y tamaño en VRAM antes y después. Eso es lo que de verdad importa —si es
la misma carga— y es inmune a nombres de proceso y a líneas de órdenes ajenas.
Verificado: la identidad se mantiene estable aunque otro shell mencione el runner.

Segundo error propio en el mismo sitio: el script que encadenaba T2 y T3 esperaba con
`pgrep -f "experiments.paired_judge"`, que **casa consigo mismo** — nunca habría
arrancado. Reescrito como un bucle en serie sobre las tres tareas.

## Herramienta de ciclo corto para iterar prompts (11-sep-2026)

Se pidió poder hacer ajustes rápidos. Medido el ritmo real del juez: **6,4 s por
llamada**. Eso reordena el diagnóstico.

**El pase riguroso completo son 1,7 h** (238 casos × 2 versiones × 2 pases = 952
llamadas): T1 39 min, T2 31 min, T3 32 min.

**Y el juez no es el cuello de botella del ciclo corto: lo es generar la prosa.**

| ciclo corto, 20 casos | generar (vLLM) | juzgar | total |
|---|---:|---:|---:|
| T1 | 9 min | 4 min | **13 min** |
| T2 | 13 min | 4 min | **17 min** |
| T3 | 1 min | 4 min | **5 min** |

Paralelizar el juez a 4 hilos ahorra 3 minutos de 13. **No compensa**: cambiar las
condiciones de medida por ese margen es mal negocio, así que el paralelismo queda en
`iterar.py` como opción exploratoria y el pase riguroso sigue secuencial.

Lo que sí acelera, por orden: **muestrear** (91 → 20 casos es 4,5×), **empezar por T3**
(5 min por iteración frente a 13 de T1; si el cambio es transversal —y `prompt_kit` lo
es— T3 avisa antes), y **saltarse la regeneración** cuando la prosa ya existe.

`experiments/iterar.py` implementa el ciclo `generar → liberar GPU → juzgar` sobre una
muestra de DEV, con `--fase juzgar` para re-juzgar prosa ya generada. Declara su propio
límite: con 20 casos el error típico del `rationale_score` ronda ±0,05, así que sólo
distingue cambios grandes. **No adopta nada**; sirve para decidir a qué dedicarle la
hora del pase riguroso.

Restricción que no se puede esquivar: vLLM (~21 GiB) y el juez (~6,5 GiB) no caben a la
vez, así que cada iteración son dos cargas de GPU en serie. Eso pone un suelo de 2-3
minutos por ciclo aunque se use un solo caso.

## ADOPTADO — los prompts de V1 en la tarea 1 (11-sep-2026)

Pase pareado completo: 91 casos, base y candidato, dos pases, **una sola carga del
juez**, 36 minutos.

| | rationale base | rationale V1 | Δ | ranking base | ranking V1 | Δ |
|---|---:|---:|---:|---:|---:|---:|
| pase 1 | 0,8012 | **0,8120** | +0,0108 | 0,8368 | 0,8378 | +0,0010 |
| pase 2 | 0,7964 | **0,8108** | +0,0145 | 0,8364 | 0,8377 | +0,0013 |

**Mejora en los dos pases, en las dos métricas.** Es el criterio 4.4 del plan, y se
cumple. Los prompts de V1 —armazón común de `prompt_kit`, línea anti-inyección,
few-shot y bucles de reto— quedan validados y se conservan.

La ganancia de ranking es pequeña (+0,001) y era previsible: el juicio de la nota pesa
0,20 del `case_score`, que a su vez es la mitad del ranking, así que +0,0145 de
rationale se traduce en +0,0015 de ranking. Real y reproducible, pero pequeña.

**La medición pareada se justificó sola.** El INFORME de la línea base publicaba
`rationale 0,6783`; la **misma** salida, en esta carga, da **0,80**. Un salto de 0,12
entre cargas del juez, mayor que cualquier efecto que estemos midiendo. Comparar contra
un número de otra carga no habría dicho nada.

Detalle de verificación: el volcado final marca `resident != resident_after`, pero lo
único que cambia es `expires_at`, que se refresca en cada petición por el `keep_alive`.
Nombre, digest, tamaño en VRAM y longitud de contexto son idénticos: **el modelo no se
recargó**. El guardia que corre durante la medición compara justamente la identidad sin
el sello de tiempo, y se mantuvo constante en las 364 llamadas.

## ADOPTADO — los prompts de V1 en la tarea 2 (11-sep-2026)

Pase pareado completo: 72 casos, dos pases, misma carga del juez (digest y VRAM
idénticos antes y después), 28 minutos.

| | rationale base | rationale V1 | Δ | ranking base | ranking V1 | Δ |
|---|---:|---:|---:|---:|---:|---:|
| pase 1 | 0,8431 | **0,8523** | +0,0092 | 0,8150 | 0,8159 | +0,0008 |
| pase 2 | 0,8492 | **0,8523** | +0,0031 | 0,8156 | 0,8159 | +0,0003 |

**Mejora en los dos pases.** Y ésta era la arriesgada: el paso 2.2.1 del plan advertía
que el CHAIR de T2 ya puntuaba 0,8431 —el mejor de las tres tareas— y que llevarlo a la
estructura de T1 **podía empeorar**. No lo hizo.

Un detalle que merece anotarse: el candidato da **0,8523 exacto en los dos pases**
mientras la base oscila entre 0,8431 y 0,8492. La prosa de V1 no sólo puntúa algo más
alto, sino que el juez la valora de forma más estable. Con dos pases no se puede
afirmar que sea un efecto real, pero es coherente con prompts más restringidos: menos
grados de libertad en el texto, menos margen para que el juez cambie de opinión.

## ADOPTADO — los prompts de V1 en la tarea 3 (11-sep-2026)

Pase pareado: 75 casos, dos pases, misma carga, 33 minutos.

| | rationale base | rationale V1 | Δ |
|---|---:|---:|---:|
| pase 1 | 0,4053 | **0,4680** | +0,0627 |
| pase 2 | 0,3760 | **0,4600** | +0,0840 |

**La mayor mejora de prosa de las tres tareas, y con diferencia** (T1 +0,013, T2 +0,006).
Es coherente: el CHAIR de T3 era el único sin few-shot, sin marco clínico y sin bucle
de reto, y su prompt creció 21 líneas. Era donde más margen había y lo confirmó.

**Una atribución que hay que declarar.** El candidato de T3 difiere de la base en **dos**
cosas a la vez —los prompts y el portavoz adoptado—, así que la comparación mide el
efecto combinado. La ganancia de `rationale_score` es atribuible a los prompts con
bastante seguridad (el portavoz sólo cambia la cifra del horizonte, no la estructura del
texto), pero no se puede separar del todo con esta medición. No se separa porque no hace
falta: las dos piezas se adoptan.

`mean_case_score` 0,6562 → 0,6678. Dentro: `event` sube de 0,7733 a 0,7867 y `time` baja
de 0,7540 a 0,7202 — la caída de `time` ya estaba declarada como el precio del portavoz.

**El c-index que aparece en este fichero (0,8832) es el de modo `deployed`: dentro de
muestra.** El número honesto sigue siendo el anidado, 0,8235.

---

## RESULTADO FINAL — OVERALL con juez, medido en una sola carga

| tarea | base (pase 1/2) | V1 (pase 1/2) |
|---|---:|---:|
| T1 | 0,8368 / 0,8364 | **0,8378 / 0,8377** |
| T2 | 0,8150 / 0,8156 | **0,8159 / 0,8159** |
| T3 | 0,7372 / 0,7372 | 0,8832 *(dentro de muestra)* · **0,8235 honesto** |

| | pase 1 | pase 2 |
|---|---:|---:|
| OVERALL base | 0,8082 | 0,8082 |
| OVERALL V1 medido | 0,8381 | 0,8381 |
| **OVERALL V1 honesto** | **0,8262** | **0,8261** |

**+0,018 sobre la línea base, reproducido en los dos pases.** El número defendible es
**0,826**, que sustituye el c-index dentro-de-muestra de T3 por la estimación anidada.

De ese +0,018, la mayor parte viene del portavoz de T3 (+0,017) y el resto de los
prompts (+0,001 en T1 y T2, pequeño porque el juicio de la nota pesa 0,20 del
`case_score`, que es la mitad del ranking).

## Qué era el 0,8406 de Debug, y por qué no es comparable (11-sep-2026)

El usuario aportó `delete_final_versions_task/metrics (1).json`, el informe real de la
fase Debug de Grand Challenge sobre la versión anterior. **Debug corrió 12 casos: cuatro
por tarea.** El 0,8406 es su media 2:2:1, y está dominado por el azar de muestra pequeña.

| tarea | Debug (4 casos) | nuestra medición (238) | qué pasó |
|---|---:|---:|---|
| T1 | **0,6861** | 0,8390 | falló 1 de 4 → 25 % de error frente al 8,8 % real |
| T2 | **0,9155** | 0,8150 | acertó 4 de 4 |
| T3 | **1,0000** | 0,8235 | c-index perfecto sobre 4 casos |
| OVERALL | **0,8406** | 0,8082 | dos golpes de suerte y uno de mala |

**Un c-index de 1,0 con cuatro pacientes no dice nada**: basta ordenar bien unos pocos
pares. Y T1 salió castigado porque le tocó `PT-pseudo_1dc32184cab6`, que es **uno de los
ocho fallos que ya teníamos analizados** —`bx=Negative`, PI-RADS 4, PSA 0,76, PSAD 0,02,
donde la regla de cohorte dispara `pirads>=4` sobre un PSA casi indetectable—. Intentamos
arreglarlo extendiendo las guardias de abstención a ese cubo y **empeoraba**: arreglaba
ése y rompía cuatro.

**Consecuencia práctica: el 0,8406 no es una estimación del rendimiento en el test, ni
un objetivo que superar.** Con 12 casos, cualquier versión puede sacar entre 0,6 y 0,95
según qué pacientes toquen. Lo que Debug demuestra es que el contenedor **ejecuta**, que
era su propósito.

La comparación que sí informa es la nuestra: 238 casos, pareada, dos pases, misma carga
del juez. Ahí la versión anterior da **0,8082** y V1 da **0,8262**.

Caso por caso, los 12 de Debug (`verification/debug12_comparacion.json`) se puntúan
también con V1 para tener la comparación directa sobre el mismo subconjunto, con el
mismo juez y en la misma carga. Ese número tiene el mismo problema de muestra que el
original y se publica sólo como control, no como resultado.

### V1 sobre los 12 casos exactos de Debug — el control

| tarea | Debug oficial | base (nuestro juez) | V1 | Δ |
|---|---:|---:|---:|---:|
| T1 | 0,6861 | 0,6986 | 0,6936 | −0,0050 |
| T2 | 0,9155 | 0,9105 | 0,9105 | +0,0000 |
| T3 | 1,0000 | **1,0000** | **1,0000** | +0,0000 |
| OVERALL | 0,8406 | 0,8436 | **0,8416** | −0,0020 |

**Dos cosas que esto demuestra, y ninguna es que V1 sea peor.**

1. **Nuestra reproducción del Debug es fiel.** La misma versión, los mismos 12 casos:
   0,8436 contra su 0,8406. Los tres milésimos son el juez siendo otra instancia. El
   aparato de medición está calibrado.
2. **Esa muestra no puede ver la mejora de V1.** T3 ya está en **c-index 1,0**: el techo.
   La mayor ganancia de V1 —el portavoz, +0,086 sobre 75 casos— **no tiene dónde
   manifestarse**. T2 sale idéntico porque los cambios de rationale se cancelan
   (0,7→0,9 en un caso, 1,0→0,8 en otro). Y T1 baja por **una sola llamada al juez** que
   pasó de 0,9 a 0,7; las decisiones son las mismas, 3 de 4 en ambas versiones.

El −0,002 no mide una diferencia entre versiones: mide el ruido de una llamada al juez
sobre un subconjunto donde la mejora real no cabe. **Un subconjunto que no puede
mostrar tu mejora no te dice nada sobre ella.**

Por eso la comparación que informa sigue siendo la de 238 casos, pareada y en dos
pases: **0,8082 → 0,8262**.
