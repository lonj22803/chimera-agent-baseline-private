# Junta clínica con expertos entrenados — tarea 1 (decisión de biopsia)

Cuarta generación de la pizarra:
[`solution_task_one`](../solution_task_one) (v1, 0.6749) →
[`solution_task_one_correction_claude`](../solution_task_one_correction_claude) (v2, 0.7125) →
[`solution_task_one_correction_II`](../solution_task_one_correction_II) (junta, 0.7069) →
**esta**. Es la junta de la tercera generación —mismos siete estados, mismas
intervenciones numeradas, mismo verificador con derecho a reabrir— con los
**cuatro expertos entrenados de
[`delete_expert_modelate/task_one`](../../delete_expert_modelate/task_one)**
sentados en la sala, una **biblioteca de precedentes**, y un **protocolo
escrito** que consolida lo que dicen y deja en el acta con qué regla lo hizo.

> ## Resultado
>
> Evaluador **oficial**, juez de razonamiento desactivado, **91 casos
> etiquetados**, temperatura 0, casos sin salida contados como fallo. Las dos
> corridas completas están en `runs/deployed` y `runs/honest` (actas, salidas,
> `summary.jsonl`, `compare.json`).
>
> | | baseline (T=0) | pizarra v1 | pizarra v2 | junta | **expertos · `deployed`** | **expertos · `honest`** |
> |---|---|---|---|---|---|---|
> | `ranking_score` | 0.6428 | 0.6749 | 0.7125 | 0.7069 | **0.9765** | **0.7807** |
> | `mean_case_score` | 0.4913 | 0.5499 | 0.6006 | 0.6068 | **0.9530** | 0.6874 |
> | puerta de decisión | 0.6813 | 0.692 | 0.747 | 0.758 | **1.000** (91/91) | 0.835 (76/91) |
> | F1(`yes`) | 0.7943 | 0.8000 | 0.8244 | 0.8070 | **1.0000** | 0.8739 |
> | `confidence_score` | 0.7661 | 0.706 | 0.750 | 0.754 | **1.000** | 0.803 |
> | `variable_weight_score` | 0.6516 | 0.837 | 0.809 | 0.798 | **0.947** | 0.840 |
> | `important_decisive_factor_score` | 0.5609 | 0.742 | 0.726 | 0.730 | **0.975** | 0.768 |
> | `tool_score` | 0.6468 | 0.770 | 0.866 | 0.882 | **1.000** | 0.866 |
> | `section_grounding_score` | 0.9960 | 0.914 | 0.889 | 0.865 | 0.840 | 0.841 |
>
> 91/91 casos entregados en las dos corridas · 0 fallos · 0 respaldos
> deterministas · 33 s/caso · 0 reaperturas.
>
> **`deployed` es el techo teórico exacto** (copiar la traza del urólogo con la
> guardia de aterrizaje da 0.9765, §0) y **sube en los 91 casos** frente a la
> pizarra v2 y frente a la junta (90 de 91 frente a la v1). Es rendimiento
> dentro de muestra: el peldaño «precedente idéntico» disparó en los 91 casos.
>
> **`honest` es la cifra que vale**: +0.074 sobre la junta, +0.068 sobre la
> pizarra v2, +0.138 sobre el baseline. Pareado contra la junta: 53 casos
> suben, 32 bajan, 6 empatan. La simulación sin LLM (§4) predijo 0.7807 y la
> corrida con LLM dio 0.7807: el modelo de lenguaje no movió ni una décima,
> que es exactamente lo que el diseño pretendía.
>
> ### Exactitud de la decisión por cubo
>
> | cubo clínico | n | pizarra v2 | junta | `deployed` | `honest` |
> |---|---|---|---|---|---|
> | `bx = None` | 24 | 1.000 | 1.000 | 1.000 | **1.000** |
> | `bx = Negative` | 18 | 0.889 | 0.889 | 1.000 | **0.889** |
> | `bx = Positive` | 49 | 0.571 | 0.592 | 1.000 | **0.735** (36/49) |
> | **total** | 91 | 0.747 | 0.758 | 1.000 | **0.835** |
>
> El cubo positivo pasa de 0.59 a 0.73 fuera de muestra, y ahí está toda la
> ganancia honesta. Por peldaño del protocolo en `honest`: reglas de cohorte
> 51/54, grado documentado 10/12, voto ponderado de los expertos 17/27 (0.63,
> donde todo lo medido antes estaba en 0.47). El presidente disintió del
> protocolo en 22 casos y el protocolo acertó 14 de ellos; en `deployed`,
> 23 disidencias y 23 aciertos del protocolo.
>
> ### Lo que no conviene leer de más
>
> `honest` gana `tool_score` (0.866 frente a 0.882 de la junta: −0.016) y
> `section_grounding_score` (0.841 frente a 0.865) porque abre lo que el
> Experto 4 predice que abriría el urólogo —incluido el laboratorio en el 61 %
> del cubo positivo— y porque pesa `bx` aunque no se pueda aterrizar. Son las
> dos apuestas medidas del §0 y §2, y las dos salen a cuenta en el total.


---

## 0. Lo primero: dos cifras, no una

Esta solución se mide de dos maneras, y las dos van juntas porque miden cosas
distintas:

| modo | panel de expertos | biblioteca de precedentes | qué mide |
|---|---|---|---|
| **`deployed`** | los artefactos tal como se entrenaron (sobre los 91 etiquetados) | contiene el propio caso | lo que se empaquetaría para el reto, corrido sobre sus propios datos de entrenamiento: **rendimiento dentro de muestra** |
| **`honest`** | reentrenado out-of-fold, 5 particiones, misma receta | excluye el propio caso (leave-one-out) | lo que ese mismo paquete haría sobre un caso que nunca vio: **la cifra de generalización** |

Sobre un caso del test real los dos modos **son el mismo programa**: el caso no
está en el entrenamiento ni en la biblioteca en ninguno de los dos. La
diferencia entre las dos notas es el precio de la memorización, y se publica
junto al resultado porque pediste que la junta hable desde los datos y la
verdad. La cifra alta es la que pediste; la cifra honesta es la que vale.

El techo teórico está medido: copiar exactamente la traza del urólogo lector
en los 91 casos da `ranking_score` **0.9733**, y con la guardia de aterrizaje
**0.9765**. No se puede llegar a 1: `bx` se aterriza con el informe de
patología, que en la tarea 1 no existe, así que toda variable `bx` pesada es
un *ungrounded* inevitable — y quitarla cuesta más en pesos y factores de lo
que devuelve en aterrizaje (medido: −0.05 frente a +0.03).

---

## 1. La sesión, intervención por intervención

```
ESTADO 0   pizarra en blanco
   │
   ├─ 1  INTAKE ............... structured-prompt.json, crudo               ─┐ ESTADO 1
   ├─ 2  INTAKE ............... el mismo, con templates/prompts/agent_prompt.j2 │
   ├─ 3  EXPERT-STRUCTURED .... Experto 1: Extra-Trees sobre el panel          │
   ├─ 4  EXPERT-COHORT ........ el criterio medido de esta situación           │
   ├─ 5  EXPERT-LIBRARY ....... los 3 precedentes etiquetados más cercanos     │
   ├─ 6  EXPERT-TRACE ......... Experto 4: qué abre y qué pesa el urólogo     ─┘  → fija el plan
   │
   ├─ 7  EXPERT-EAU ........... RAG sobre la guía; critica a los expertos        → ESTADO 2
   ├─ 8  MODERATOR ............ preguntas abiertas; una pregunta por documento   → ESTADO 3
   ├─ 9  EXPERT-IMAGE ......... sólo si el moderador lo convoca
   ├─ 10 REGISTRAR ............ abre exactamente el plan; grado, sesiones, RM   → ESTADO 4
   │
   ├─ 11 EXPERT-PSA ........... Experto 2: proyecta la serie que se abrió      ─┐ ESTADO 5
   ├─ 12 EXPERT-FUSION ........ Experto 3: sobre los documentos que se abrieron │
   ├─ 13 PANEL-PROTOCOL ....... la cascada, con la regla que disparó           ─┘
   │
   ├─ 14 VERIFIER ............. ¿se puede decidir ya, según la guía?            → ESTADO 6
   │        ├─ no, y un documento DEL PLAN quedó sin abrir ──► MODERATOR (pase 2: 15, 16, …)
   │        └─ sí ──►
   │
   └─ 15 CHAIR ................ la prosa + el formulario; reto si disiente      → ESTADO 7
```

La numeración sigue siendo global y monótona, nadie edita lo de otro, y el
cuerpo de cada intervención es lo que dijo el participante. Lo nuevo es
**quién está en la sala y cuándo habla cada uno**, y el orden no es cosmético:

* los expertos que sólo leen el panel (1, cohorte, biblioteca, traza) hablan
  **antes** de que se abra nada, para que la guía y el moderador tengan algo
  que criticar y una lista de documentos que respetar;
* los expertos que leen documentos (Experto 2 sobre la serie de PSA, Experto 3
  sobre la analítica y el informe de RM) hablan **después** del registrador y
  **sólo sobre lo que el registrador abrió**. Si el informe de RM no está sobre
  la mesa, el Experto 3 se abstiene; si la analítica no está, habla con ese
  bloque en blanco y su `epistemic_missing` lo refleja. Es la diferencia entre
  un experto que cita un documento y uno que lo lee por debajo de la mesa;
* el protocolo habla después de todos y antes del verificador, para que el
  verificador compruebe **la posición del panel contra lo recuperado**, no una
  opinión suelta.

---

## 2. Lo que cambia respecto a la junta anterior, y por qué

| # | Cambio | Motivo, medido |
|---|---|---|
| 1 | **El plan lo fija EXPERT-TRACE** (Experto 4 + precedentes); el moderador reparte preguntas, no documentos | `tool_score` es precisión contra lo que abrió el urólogo, y lo que abre depende del caso: el modelo entrenado sobre sus 91 trazas conserva modelo para la apertura del laboratorio (gana a la moda en LOOCV) y usa la frecuencia por cubo para el resto. Un documento fuera de esa lista **nunca** se abre |
| 2 | **El LLM no vota.** PANEL-PROTOCOL decide por cascada; el presidente escribe la prosa y, si disiente, se le devuelve el turno con la carga de la prueba (heredado) | medido en las actas de la junta anterior sobre el cubo difícil: registrador 20/43, verificador 24/49, presidente 29/49 — y el 29 ya lleva el reto mecánico. Ver §3 |
| 3 | **El criterio de cohorte se extiende al cubo positivo** con tres reglas de panel (PSA ≥ 20, edad ≥ 78, PI-RADS ≤ 2 → diferir) | salen del texto del propio urólogo lector: 9 de 10 en la serie etiquetada. Ver §3 |
| 4 | **El grado documentado de la biopsia previa** se lee con una expresión regular del texto crudo que devolvió la herramienta, y decide (GG ≥ 2 → tratar; GG 1 en vigilancia → confirmatoria) | 10 de 12 en la serie; un modelo pequeño escribe "ISUP 2" donde el documento dice "Gleason 3+4". +0.03 de ranking honesto |
| 5 | **Carga de la prueba en el cubo positivo**: biopsia si p(biopsia) ≥ 0.40 en el voto ponderado | el urólogo difiere sólo con razón positiva; en la serie, el umbral 0.40 gana al 0.50 por +0.04 honesto (36/49 frente a 32/49) |
| 6 | **Biblioteca de precedentes** (razonamiento basado en casos, k = 3 por cubo) | fuera de muestra vale 0.92 sin biopsia previa, 0.78 tras negativa, **0.47 con positiva** — por eso pesa 0.5 en el voto y no decide nada por sí sola. Dentro de muestra devuelve el propio caso y lo declara |
| 7 | **El presidente firma la posición del panel**; su `confidence` y sus `variable_weights` se registran pero se entrega la traza del Experto 4 | la política `trace` (moda por cubo + modelo donde bate a la moda) da confianza 0.803 frente a 0.789 de la política por acuerdo, y pesos 0.840 frente a 0.829 de la moda pura |
| 8 | La reapertura sólo ocurre si el registrador **dejó sin abrir un documento del plan** | reabrir para abrir de más es lo que costó precisión en la junta anterior; aquí no hay nada fuera del plan que abrir |

Lo que **no** cambia, porque estaba medido y funciona: las intervenciones
numeradas, la `reveal_sequence` derivada de los `ToolMessage` reales, la
guardia de procedencia del registrador, la guardia de aterrizaje, el reto al
presidente sobre la disidencia con tres turnos, el respaldo determinista, el
catálogo desde la lista MCP viva, `get_family_history` sin enlazar, y el
especialista EAU con recuperación obligatoria.

---

## 3. El hallazgo: el cubo positivo se decide en las notas, y el urólogo lo dice

Las tres generaciones anteriores se estancaron en el mismo sitio: los 49 casos
con biopsia previa positiva. Todas trataron ese cubo como un problema del
panel o del LLM, y en los dos frentes está medido que no hay señal:

| fuente | acierto en `bx = Positive` | cómo se midió |
|---|---|---|
| kNN por precedente, panel estructurado, k = 1…9 | 0.43 – 0.47 | leave-one-out |
| Experto 1 (panel), tramo `discuss` | 0.55 | out-of-fold |
| registrador de la junta anterior (`LEAN`) | 20 / 43 | actas de `runs/full3` |
| verificador de la junta anterior (`SUGGEST`) | 24 / 49 | idem |
| presidente de la junta anterior | 29 / 49 | idem, ya con el reto mecánico |

Lo que sí hay es el propio urólogo, que en su `free_text` explica el criterio
con todas las letras. Leídos los 49:

| lo que escribe | regla | n | acierto |
|---|---|---|---|
| "start treatment and do a PSMA-PET", "patient with a clear PCa diagnosis" | PSA ≥ 20 → diferir | 6 | 5 |
| "stop checking PSA, no need for diagnostics" | edad ≥ 78 → diferir | 2 | 2 |
| "now normal MRI" | PI-RADS ≤ 2 → diferir | 2 | 2 |
| "he has a ISUP3 cancer diagnosis already", "earlier biopsy showed ISUP4", "Gleason 5 pattern" | grado documentado GG ≥ 2 → tratar, no re-biopsiar | 8 | 7 |
| "only one previous biopsy 2 yrs ago… confirmatory biopsy", "AS… needs confirmatory biopsy" | grado documentado GG 1 en vigilancia → biopsiar | 4 | 3 |
| "need to know if the lesion has grown", "need initial ISUP" | información ausente: el urólogo decide con el hueco; «sí» por defecto | ~28 | 0.64 |

Las tres reglas de panel son criterio de guía (enfermedad de alto riesgo →
estadificación; expectativa de vida limitada → no más diagnóstico; sin lesión →
nada que muestrear) y la serie etiquetada las confirma. El grado documentado
vive **en las notas previas**, y sólo un lector de texto lo saca: por eso el
registrador tiene que declararlo en cuatro líneas obligatorias (`PRIOR GRADE`,
`BIOPSY SESSIONS`, `SURVEILLANCE`, `TREATMENT`), y por eso el código lo lee
además con `decide.documented_grade` sobre el texto crudo de la herramienta —
Gleason 3+4 → GG 2, 4+4 → GG 4, ISUP n → GG n — y lo escribe en el acta con la
cita. Lo que el LLM resume se lee; lo que decide se comprueba.

---

## 4. El protocolo del panel

Es una cascada ordenada por acierto medido. Cada peldaño se puede leer en el
acta, con la regla que disparó y el historial del colega que la sostiene:

```
1. precedente idéntico        la serie etiquetada contiene este mismo panel       (sólo dentro de muestra)
2. criterio de cohorte        sin biopsia previa:  PI-RADS ≥ 3                    24 / 24
                              biopsia negativa:    PI-RADS ≥ 4                    16 / 18
                              biopsia positiva:    PSA ≥ 20 · edad ≥ 78 · PI-RADS ≤ 2 → diferir   9 / 10
3. grado documentado          GG ≥ 2 → diferir (7/8) · GG 1 → biopsiar (3/4)
4. voto ponderado             Experto 3 × tramo × 1.5 + Experto 1 × tramo + precedentes × 0.5
                              tramo: firm 3 · supports 2 · discuss 1;  biopsia si p ≥ 0.40
```

Los parámetros se eligieron **sin LLM y sobre la cifra honesta**
(`analysis/simulate.py --grid`: 72 configuraciones × 5 segundos), porque con
el juez apagado el `case_score` depende sólo de lo que el código fija:

| configuración honesta (panel OOF, biblioteca LOO) | ranking | puerta | `Positive` |
|---|---|---|---|
| sin regla del grado, umbral 0.50 | 0.7077 | 0.747 | 28 / 49 |
| + regla del grado | 0.7390 | 0.791 | 32 / 49 |
| + umbral 0.45 | 0.7317 | 0.780 | 31 / 49 |
| + **umbral 0.40** | **0.7807** | **0.835** | **36 / 49** |
| id., confianza por acuerdo en vez de traza | 0.7794 | 0.835 | 36 / 49 |
| id., pesos por moda pura | 0.7774 | 0.835 | 36 / 49 |

Aviso obligado: el umbral y la política se eligen sobre los mismos 91 casos con
los que se mide, así que la cifra honesta lleva un sesgo de selección pequeño
(tres umbrales, dos políticas de confianza, tres de pesos). Se publica la tabla
entera para que se vea cuánto es.

---

## 5. Los expertos, en calidad de qué hablan

| intervención | experto | lee | habla cuando | fiabilidad medida (out-of-fold, 91 casos) |
|---|---|---|---|---|
| 3 | **EXPERT-STRUCTURED** — Experto 1, Extra-Trees + bagging × imputación múltiple | bloque A (panel) | siempre, antes de abrir nada | acierto 0.681; `firm` 0.879 (n 33) · `supports` 0.600 (20) · `discuss` 0.553 (38) |
| 4 | **EXPERT-COHORT** — reglas | panel | siempre | 24/24 · 16/18 · 9/10 |
| 5 | **EXPERT-LIBRARY** — kNN por cubo, 7 variables del panel estandarizadas | panel + la serie etiquetada | siempre | 0.92 · 0.78 · 0.47 (LOO, k = 3) |
| 6 | **EXPERT-TRACE** — Experto 4, logística por casilla con puerta LOOCV | panel | siempre; fija el plan | conserva modelo en `bx`, `dre`, `pirads` y la apertura del laboratorio; moda en el resto |
| 11 | **EXPERT-PSA** — Experto 2, Extra-Trees anclado + jackknife+ | la serie de PSA **abierta** | sólo si `psa_trend` se abrió | MAE(log) 0.315, cobertura 0.952; no vota |
| 12 | **EXPERT-FUSION** — Experto 3, Extra-Trees sobre A+B+D | panel + analítica + RM **abiertas** | sólo si `radiology_report` se abrió | completo: 0.736; `firm` 0.861 (36) · `supports` 0.708 (24) · `discuss` 0.613 (31). Sin analítica: 0.703 |

Los cuatro artefactos se cargan de `delete_expert_modelate/task_one/*/model/`
y se pasan por los 195 casos **una sola vez en lote**
(`experts/panel.py` → `artifacts/panel_cache.json`): puntuar un caso suelto
cuesta 20 s por las 300 pasadas del imputador; los 195 en lote, tres minutos.
El mismo módulo reentrena la receta de cada bundle en 5 particiones para el
modo honesto, y los tramos que salen reproducen exactamente los de los README
de los expertos — lo que confirma que se está usando el mismo modelo.

**Un caso que no está en el caché se puntúa en vivo** (`Panel.ensure`, llamado
por la primera intervención de experto): es la ruta del reto, donde cada caso
llega en su propio contenedor. Verificado que reproduce el caché
(probabilidades idénticas; el tramo puede moverse en el límite por el muestreo
del imputador). Cuesta 30–80 s por caso.

**Sobre el Experto 2.** La ablación de su autor midió que la proyección no
añade nada al clasificador (AUC 0.794 frente a 0.792). Aquí no entra en el
voto: es una salida independiente para el deliberador —hacia dónde va el PSA y
con qué banda— y lo dice en su turno.

**Sobre EXPERT-IMAGE.** Sigue en la sala y sigue diciendo lo que midió el
cuaderno exploratorio (AUC 0.43 en la tarea 1): que no aporta. Sólo habla si
el moderador lo convoca.

---

## 6. La memorización, dicha de frente

En modo `deployed`, sobre los 91 casos etiquetados, el peldaño 1 dispara en
los 91: la biblioteca encuentra el propio caso a distancia 0 y devuelve la
decisión, la confianza, los pesos y los documentos que el urólogo abrió. El
acta lo escribe tal cual —"IDENTICAL PANEL: this is the same case, already in
the labelled series"— y el `run_config.json` y el `summary.jsonl` lo registran
(`library_self_match`). La nota de ese modo es, por construcción, el techo de
copiar la traza con guardia: **0.9765** en la simulación.

Lo que queda **sin** ese peldaño, también medido en la simulación:

| configuración | ranking | puerta |
|---|---|---|
| panel entrenado sobre los 91 + biblioteca con el propio caso (`deployed`) | 0.9765 | 91 / 91 |
| panel entrenado sobre los 91 + biblioteca sin el propio caso | 0.8215 | 81 / 91 |
| panel out-of-fold + biblioteca sin el propio caso (`honest`) | 0.7807 | 76 / 91 |

La primera fila es lo que pediste —lo más alto posible, aunque parezca
sobreajuste—; la tercera es lo que un caso nuevo recibiría. Las reglas del
reto se respetan en las dos: los 91 casos etiquetados son el conjunto de
entrenamiento que el organizador entrega, y entrenar un modelo o indexar una
biblioteca con ellos es exactamente para lo que se entregan. Lo que no sería
honesto es presentar la primera cifra como rendimiento, y por eso va la
segunda al lado.

---

## 7. Las guardias: lo verificable se verifica en código

| guardia | qué comprueba | qué hace |
|---|---|---|
| `decide.unsourced_values` | todo valor del informe del registrador aparece en un resultado de herramienta o en el panel | devuelve el turno una vez con la lista |
| `decide.documented_grade` | el grado de la biopsia previa, en el texto crudo de las herramientas | lo escribe en el acta con la cita y lo pasa al protocolo |
| `decide.enforce_grounding` | ninguna variable pesada sin su sección abierta (`pirads`, `psad`, `vol`, `cspca` ← RM; `dre` ← laboratorio; `fh` ← antecedentes) | baja a `not_used` y lo anota |
| plan fijo | el registrador abre exactamente lo que el Experto 4 listó | lo que el moderador pida de más se cae con motivo en el acta |
| reto al presidente | si su decisión difiere de la del protocolo | aviso con la carga de la prueba → aviso con el historial → formulario con la decisión fijada |
| línea `VERDICT` | el verificador tiene que pedir la reapertura por escrito, y sólo por un documento del plan sin abrir | si no la escribe, se cierra |
| respaldo determinista | el presidente no entrega JSON válido | prosa construida desde el acta; la decisión y la traza ya estaban fijadas |

---

## 8. Lo que el reto exige, y cómo se cumple

* **`reveal_sequence` = lo que se llamó.** Se deriva de los `ToolMessage`, no
  de lo que un modelo declara. Los expertos que leen documentos hablan sólo
  sobre secciones ya reveladas por el registrador.
* **Sin hallazgos inventados.** Guardia de procedencia sobre el registrador;
  el presidente tiene prohibido citar un precedente como hecho del paciente y
  el acta lo repite en cada intervención de la biblioteca.
* **Sin informe de patología en la tarea 1.** El intake lo corrige en voz alta
  y el catálogo sale de la lista MCP viva.
* **`get_family_history` nunca se llama** (0 de 91 en el urólogo).
* **`output/schema.py` intacto**; el paquete importa de
  `chimera_agent_baseline` sin modificarlo.
* **Un caso nunca se pierde**: respaldo determinista antes que una excepción.

---

## 9. Mapa de ficheros

| fichero | qué contiene |
|---|---|
| [`board.py`](board.py) | el acta: intervenciones numeradas, los catorce papeles, render, hilo |
| [`roster.py`](roster.py) | el catálogo desde la lista MCP viva; el plan fijado por secciones; las preguntas por documento |
| [`prompts.py`](prompts.py) | los cinco prompts LLM (EAU, moderador, registrador, verificador, presidente) con los expertos presentados |
| [`graph.py`](graph.py) | el grafo LangGraph con las quince intervenciones y el bucle del verificador |
| [`protocol.py`](protocol.py) | la cascada del panel y su intervención |
| [`decide.py`](decide.py) | `reveal_sequence`, guardias, parser del grado, respaldo |
| [`sampling.py`](sampling.py) | muestreo por papel (heredado) |
| [`experts/panel.py`](experts/panel.py) | carga de los cuatro artefactos, precálculo en lote, out-of-fold, `Panel` |
| [`experts/structured.py`](experts/structured.py) · [`fusion.py`](experts/fusion.py) · [`psa.py`](experts/psa.py) · [`trace.py`](experts/trace.py) | cómo habla cada experto entrenado |
| [`experts/cohort.py`](experts/cohort.py) | el criterio por cubo, con las tres reglas del cubo positivo |
| [`experts/library.py`](experts/library.py) | la biblioteca de precedentes |
| [`experts/image.py`](experts/image.py) | el predictor de imagen (heredado) |
| [`analysis/simulate.py`](analysis/simulate.py) | el protocolo sin LLM, puntuado con el evaluador oficial; la rejilla de parámetros |
| [`analysis/compare.py`](analysis/compare.py) | comparación pareada contra las tres generaciones anteriores y el baseline |
| [`analysis/diagnose.py`](analysis/diagnose.py) | diagnóstico por caso: regla, acierto, componentes |
| [`runs/launch.sh`](runs/launch.sh) | lanza una corrida en tmux; dos a la vez con `--gpu-util 0.45` y un socket de embeddings propio |
| `artifacts/panel_cache.json` | el panel precalculado (se regenera con `python -m …experts.panel`) |

El paquete es autocontenido: no importa nada de las tres generaciones
anteriores. Depende de `chimera_agent_baseline` (sin tocarlo) y de
`delete_expert_modelate/chimera_experts` para deserializar los artefactos de
los expertos, que es la dependencia que pediste.

---

## 10. Cómo se corre y cómo se mide

```bash
source .venv/bin/activate

# 1. el panel de expertos, una vez (≈ 30 min con el out-of-fold; --no-oof: 3 min)
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_using_experts.experts.panel

# 2. la nota esperada sin LLM, y la rejilla de parámetros sobre la cifra honesta
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_using_experts.analysis.simulate --grid

# 3. las dos corridas completas (91 casos), a la vez en una 5090
delete_solution_one/solution_task_one_using_experts/runs/launch.sh deployed "--mode deployed --gpu-util 0.45"
delete_solution_one/solution_task_one_using_experts/runs/launch.sh honest   "--mode honest   --gpu-util 0.45" \
    "CHIMERA_EMBED_SOCKET=/tmp/chimera_embed_honest.sock"

# 4. la nota oficial y la comparación pareada
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_using_experts.analysis.compare \
    --run delete_solution_one/solution_task_one_using_experts/runs/deployed
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_using_experts.analysis.diagnose \
    --run delete_solution_one/solution_task_one_using_experts/runs/honest --show-wrong
python dev/score_local.py --tasks 1 --count-missing \
    --output-root delete_solution_one/solution_task_one_using_experts/runs/deployed/output
```

---

## 11. Limitaciones, dichas de frente

1. **n = 91.** Todo intervalo mide ±0.10 de AUC; las reglas del cubo positivo
   se apoyan en 6, 2, 2, 8 y 4 casos. Son criterio de guía confirmado por la
   serie, no reglas aprendidas, pero la confirmación es delgada.
2. **La cifra honesta lleva sesgo de selección** (§4): el umbral y las
   políticas se eligieron sobre los mismos 91 casos. Tres umbrales y seis
   políticas: pequeño, no cero.
3. **El registrador no compara la RM** porque los informes casi nunca comparan:
   la pregunta «¿ha crecido la lesión?», que el urólogo hace en ~10 casos,
   queda sin respuesta en el documento, y el urólogo decide con ella ausente.
   Ese ruido es irreducible desde los datos entregados.
4. **El grado documentado se lee con una expresión regular.** Cubre ISUP n,
   grade group n, Gleason a+b y Gleason 6-10; una nota que diga «favorable
   intermediate risk» sin cifra no dispara la regla.
5. **Los precedentes moldean la prosa dentro de muestra.** En modo `deployed`
   el presidente lee las palabras del urólogo sobre este mismo caso; su
   `free_text` se parece a ellas. Con el juez del reto activo eso puntuaría
   alto sobre los 91 y no dice nada sobre un caso nuevo.
6. **El registrador abrió documentos con el plan vacío**, en los 2 casos (de 91)
   en que el urólogo no abrió nada: el prompt decía «make no tool calls» y el
   modelo llamó igualmente a tres o cuatro herramientas. Eran los únicos dos
   casos con `tool_score` < 1 en `deployed`. Se corrigió desenlazando las
   herramientas de documento cuando el plan está vacío (`graph._registrar_model`)
   y se re-corrieron esos dos casos; las salidas anteriores están en
   `runs/deployed_before_fix/` para que se vea el antes y el después.
7. **El presidente nombra la maquinaria.** Pese a la instrucción, escribe
   «supported by the cohort criterion» o «the panel protocol» en su prosa. Con
   el juez apagado no puntúa; con el juez del reto activo es prosa peor que la
   de un urólogo. Es un límite del modelo de 2B con un acta llena de esas
   palabras, y no se ha reescrito su texto en código: sería inventar.
8. **Dos urólogos lectores, dos estilos.** Los 30 primeros `free_text` son
   telegráficos («need to know…»); los 19 últimos, argumentados. Las reglas
   del §3 salen de los dos, pero el segundo aplica el protocolo de vigilancia
   activa con más consistencia.

---

## 12. Bibliografía

**Arquitectura de pizarra**
- Erman, Hayes-Roth, Lesser, Reddy (1980). *The Hearsay-II Speech-Understanding System.* ACM Computing Surveys 12(2).
- Hayes-Roth (1985). *A blackboard architecture for control.* Artificial Intelligence 26(3).
- Nii (1986). *Blackboard Systems.* AI Magazine 7(2).

**Razonamiento basado en casos (la biblioteca)**
- Aamodt, Plaza (1994). *Case-Based Reasoning: Foundational Issues, Methodological Variations, and System Approaches.* AI Communications 7(1).
- Kolodner (1993). *Case-Based Reasoning.* Morgan Kaufmann.

**Colaboración entre LLM y sus límites**
- Du, Li, Torralba, Tenenbaum, Mordatch (2023). *Improving Factuality and Reasoning in Language Models through Multiagent Debate.* arXiv:2305.14325.
- Chen, Saha, Bansal (2023). *ReConcile.* arXiv:2309.13007.
- Kim et al. (2024). *MDAgents: An Adaptive Collaboration of LLMs for Medical Decision-Making.* NeurIPS 2024.
- Wang et al. (2024). *Rethinking the Bounds of LLM Reasoning: Are Multi-Agent Discussions the Key?* ACL 2024.
- Huang et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR 2024.
- Turpin, Michael, Perez, Bowman (2023). *Language Models Don't Always Say What They Think.* NeurIPS 2023.

**Combinar expertos por fiabilidad medida**
- Dietterich (2000). *Ensemble Methods in Machine Learning.* MCS 2000.
- Kuncheva (2004). *Combining Pattern Classifiers.* Wiley — reglas de combinación ponderadas por competencia.
- Chow (1970). *On Optimum Recognition Error and Reject Tradeoff.* IEEE Trans. Inf. Theory — la abstención informada que sostiene la escalera `firm/supports/discuss`.

**Incertidumbre, calibración e imputación (los expertos heredados)**
- Breiman (2001). *Random Forests.* Machine Learning 45(1). Geurts, Ernst, Wehenkel (2006). *Extremely randomized trees.* Machine Learning 63(1).
- Lakshminarayanan, Pritzel, Blundell (2017). *Deep Ensembles.* NeurIPS 2017.
- Depeweg et al. (2018). *Decomposition of Uncertainty in Bayesian Deep Learning.* ICML 2018.
- Rubin (1987). *Multiple Imputation for Nonresponse in Surveys.* Wiley. van Buuren, Groothuis-Oudshoorn (2011). *mice.* J Stat Softw 45(3).
- Guo, Pleiss, Sun, Weinberger (2017). *On Calibration of Modern Neural Networks.* ICML 2017.
- Barber, Candès, Ramdas, Tibshirani (2021). *Predictive inference with the jackknife+.* Annals of Statistics 49(1).
- Varma, Simon (2006). *Bias in error estimation when using cross-validation for model selection.* BMC Bioinformatics 7:91.

**Recuperación y guía**
- Lewis et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020.
- EAU-EANM-ESTRO-ESUR-ISUP-SIOG Guidelines on Prostate Cancer (2024): biopsia dirigida sobre PI-RADS ≥ 3; re-biopsia tras negativa sobre PI-RADS 4-5; biopsia confirmatoria en vigilancia activa; PSA > 20 ng/mL como alto riesgo.

> Las referencias van por autor, año, título y sede. Si van a un artículo,
> conviene verificar páginas y DOI en la fuente original.
