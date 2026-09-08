# Junta clínica sobre pizarra — tarea 1 (decisión de biopsia)

Tercera generación de [`../solution_task_one`](../solution_task_one) y
[`../solution_task_one_correction_claude`](../solution_task_one_correction_claude).
Mismo clasificador —el que la ablación dejó elegido, y aquí no se reabre esa
decisión— y **la sesión reordenada como una junta médica**: siete estados de
pizarra, nueve papeles, intervenciones numeradas, y un verificador que puede
devolver la sesión al moderador.

> ## Resultado
>
> Evaluador **oficial**, juez de razonamiento desactivado, **91 casos
> etiquetados**, temperatura 0, casos sin salida contados como fallo.
>
> | | baseline (T=0) | pizarra v2 | **junta** |
> |---|---|---|---|
> | `ranking_score` | 0.6428 | **0.7125** | 0.7069 |
> | `mean_case_score` | 0.4913 | 0.6006 | **0.6068** |
> | puerta de decisión | 0.6813 | 0.7473 | **0.7582** |
> | F1(`yes`) | 0.7943 | **0.8244** | 0.8070 |
> | `tool_score` | 0.6468 | 0.8664 | **0.8816** |
> | `variable_weight_score` | 0.6516 | **0.8088** | 0.7977 |
> | `confidence_score` | **0.7661** | 0.7500 | 0.7536 |
> | `important_decisive_factor_score` | 0.5609 | 0.7264 | **0.7295** |
> | `section_grounding_score` | **0.9960** | 0.8887 | 0.8653 |
>
> **+0.064 sobre el baseline a la misma temperatura. −0.006 frente a la pizarra
> v2**, que es un empate dentro del ruido.
>
> 91/91 casos entregados · 0 fallos · 2 respaldos deterministas · ~29 s/caso.
>
> Las tres corridas completas, para que se vea de dónde sale cada punto:
>
> | corrida | qué cambió | `ranking_score` |
> |---|---|---|
> | `runs/full` | la junta tal como salió del piloto | 0.5952 |
> | `runs/full2` | el reto al presidente salta sobre la disidencia (§3, error 9) | 0.7055 |
> | `runs/full3` | + tercer turno para que la prosa sostenga la decisión | **0.7069** |
>
> ### Exactitud de la decisión, que es donde sí gana
>
> | cubo clínico | n | baseline | pizarra v2 | **junta** |
> |---|---|---|---|---|
> | `bx = None` | 24 | — | 1.000 | **1.000** |
> | `bx = Negative` | 18 | — | 0.889 | **0.889** |
> | `bx = Positive` | 49 | — | 0.571 | **0.592** |
> | **total** | 91 | — | 0.747 | **0.758** |
>
> ### Un matiz del que no conviene fiarse
>
> La junta responde «yes» 58 veces cuando la verdad son 56. La v2 responde
> **75**. Es decir: la v2 sobre-predice biopsia de forma masiva, y eso le
> **infla el F1(`yes`) por recall** — que es la mitad del `ranking_score`. La
> junta decide mejor y está mucho mejor calibrada, y empata en la métrica
> porque la métrica premia el sesgo a «yes». Sesgar la salida hacia «yes»
> subiría el número; sería maquillarlo a costa de la validez clínica, y no se ha
> hecho.
>
> ### El hallazgo incómodo
>
> En el tramo `discuss` del cubo indeterminado —**36 de los 49 casos**— la junta
> acierta ~0.47: exactamente lo mismo que el clasificador solo. **Los LLM no
> aportan nada a la decisión en los 36 casos difíciles.** Toda la ventaja sobre
> el baseline sale de dos sitios, y conviene decirlo sin adornos: la economía de
> revelaciones (`tool_score` +0.235) y deferir a los expertos con historial
> medido. La discusión multi-agente mejora *cómo se justifica* la decisión —
> `important_decisive_factor_score` +0.167, `variable_weight_score` +0.147 sobre
> el baseline— no *cuál* es. Es exactamente lo que advierten Wang et al. (ACL
> 2024) y la razón de que aquí se mida todo.

---

## 1. La sesión, estado por estado

```
ESTADO 0   pizarra en blanco
   │
   ├─ INTERVENCIÓN 1  INTAKE ............. structured-prompt.json, crudo          ─┐ ESTADO 1
   ├─ INTERVENCIÓN 2  INTAKE ............. el mismo, con templates/prompts/agent_prompt.j2 ─┘
   │
   ├─ INTERVENCIÓN 3  EXPERT-CLASSIFIER .. veredicto · incertidumbre · confianza  ─┐ ESTADO 2
   ├─ INTERVENCIÓN 4  EXPERT-COHORT ...... el criterio medido de esta situación   ─┘
   │
   ├─ INTERVENCIÓN 5  EXPERT-EAU ......... RAG sobre la guía; critica al clasificador  → ESTADO 3
   │
   ├─ INTERVENCIÓN 6  MODERATOR .......... preguntas abiertas + plan de verificación   → ESTADO 4
   │
   ├─ INTERVENCIÓN 7  EXPERT-IMAGE ....... sólo si el moderador lo convoca        ─┐ ESTADO 5
   ├─ INTERVENCIÓN 8  REGISTRAR .......... abre documentos y expone lo que dicen  ─┘
   │
   ├─ INTERVENCIÓN 9  VERIFIER ........... ¿se puede decidir ya, según la guía?        → ESTADO 6
   │        ├─ no ──► vuelve al MODERATOR (intervenciones 10, 11, 12…) hasta 3 pases
   │        └─ sí ──►
   │
   └─ INTERVENCIÓN 10 CHAIR .............. el formulario validado + el hilo         → ESTADO 7
```

La numeración es **global y monótona**: si el verificador reabre, la segunda
vuelta no es "ronda 2 · intervención 5", son las intervenciones 10, 11 y 12.
Citar «intervención 8» identifica un turno único, y eso es lo que hace que el
hilo del presidente sea auditable en lugar de decorativo.

### Cómo se lee el acta

```
--- INTERVENTION 4 · EXPERT-COHORT (cohort criterion; what the labelled series did …) ---

This patient's situation: prior positive biopsy. I have no answer for him, and that is
the finding.
…
```

Cada participante abre dirigiéndose por su papel al colega que le afecta. No es
adorno: el evaluador puntúa `free_text` con un lector clínico, y un acta donde
se ve quién movió a quién es de donde el presidente saca esa prosa **sin
inventársela**.

---

## 2. Lo que cambia respecto a la pizarra v2, y por qué

| # | Cambio | Motivo |
|---|---|---|
| 1 | El clasificador habla en **5 líneas** en vez de 18 | los números íntegros siguen en `data`; lo que se recorta es el contexto que leen los demás modelos, que es donde una explicación de más se convierte en una alucinación de más |
| 2 | El **especialista EAU habla antes** que el moderador y **critica al clasificador** | así la agenda se fija sobre lo que la guía exige, no sobre lo que a un LLM le parece que falta |
| 3 | El moderador emite **preguntas abiertas**, no sólo una lista de documentos | una pregunta se puede declarar contestada o no; una lista de documentos sólo se puede declarar abierta |
| 4 | **EXPERT-IMAGE sólo habla si lo convocan** | en la v2 intervenía en los 91 casos para decir en los 91 que no aporta nada: nueve líneas de contexto por caso a cambio de cero información |
| 5 | Un **verificador** sustituye al «moderador de cierre», con RAG propio y hasta **3 pases** | el cierre pasa de contar votos a comprobar contra la guía si el expediente está en condiciones |
| 6 | **Guardia de procedencia**: ningún número sin fuente | ver §4; es la respuesta real a «bajar la temperatura», que ya no es posible |
| 7 | El catálogo de herramientas sale de la **lista MCP viva** | ver §3, error nº 1 |
| 8 | **Muestreo por papel** (`sampling.py`) | temperatura y tope de tokens por interviniente, para poder medir en vez de suponer |

Lo que **no** cambia, porque estaba medido y funciona: el Random Forest sobre
`A-core` (gana al kNN de la v1 en 10 de 10 semillas, Wilcoxon p = 0.002), la
`reveal_sequence` derivada de los `ToolMessage` reales, la guardia de
aterrizaje, el reto al presidente cuando anula a un experto con historial, el
respaldo determinista que impide perder un caso, y el marco clínico por cubo de
biopsia previa.

---

## 3. Los errores que encontré en el planteamiento

Ninguno de estos es una objeción al diseño que pediste: son cosas que, tal cual
estaban enunciadas, habrían fallado en tiempo de ejecución o habrían costado
puntuación. Van resueltas en el código.

### Error 1 — `get_pathology_report` no existe en la tarea 1

El encargo pedía que el moderador tuviera en su contexto `get_psa_trend`,
`get_lab_results`, `get_mri_report`, **`get_pathology_report`**,
`get_previous_notes`, `get_family_history` y `search_guidelines`, y ponía como
ejemplo un moderador que pide `radiology_report` **y `pathology_report`**.

`src/chimera_agent_baseline/tools/definitions.py` es explícito:

```python
# Tasks 1 and 2 expose the same masked Extended EHR sections, except that
# Task 1 does not expose the pathology report.
TASK1_TOOLS = [PSA_TREND, LAB_RESULTS, MRI_REPORT, PREVIOUS_NOTES, FAMILY_HISTORY]
```

y `Task1Output.reveal_sequence` sólo admite cinco literales, entre los que
`pathology_report` **no está**. Anunciarle a un modelo pequeño una herramienta
que no puede llamar es la forma más barata de provocar una alucinación: acaba
escribiendo «el informe de anatomía patológica indica…» sobre un documento que
nadie le sirvió.

Y hay un agravante que ya estaba ahí: la plantilla upstream
`templates/prompts/agent_prompt.j2` **menciona el informe de patología** en su
lista de documentos solicitables, también para la tarea 1. Es upstream y no se
toca. Lo que hace la intervención 2 es corregirlo en voz alta, con la lista
derivada del catálogo real:

> One correction to that last paragraph before anybody acts on it: the documents
> this task actually serves are radiology_report, psa_trend, previous_notes,
> laboratory_results, plus the family-history anamnesis. There is NO pathology
> report to pull up in a task-1 biopsy decision.

**Cómo queda:** [`roster.py`](roster.py) construye el catálogo desde la lista MCP
viva. Si un día la tarea 1 expone la patología, aparece sola; mientras no la
exponga, nadie la ve, y una sección inexistente en el plan del moderador se cae
con un motivo escrito en el acta.

### Error 2 — la temperatura ya estaba en 0.0; no se puede bajar

Pediste comprobar si bajarla un poco mejora las respuestas. **Ya estaba en el
suelo.** `run_task1.py` de la v2 declara `--temperature` con valor por defecto
`0.0`, y el `run_config.json` de la corrida completa lo confirma:
`"temperature": 0.0`. El `1.0` de `configs/config.yaml` es lo que trae el
repositorio de fábrica, y el runner lo pisa. A temperatura 0 el modelo es
*greedy*: no muestrea, con lo que `top_p: 0.95` tampoco tiene efecto.

Y la evidencia sobre esa palanca ya estaba tomada en la propia tabla de la v2: el
control del baseline puntúa **0.6351 a T = 1.0** y **0.6428 a T = 0**. La
dirección era la correcta y el recorrido está agotado.

**Lo que sí queda, y está implementado** ([`sampling.py`](sampling.py)):

* **tope de tokens por papel**, que es la palanca que de verdad ataca lo que
  observaste («explicaba de más»): en un modelo pequeño la deriva crece con la
  longitud del turno, no con la temperatura. EAU 700, moderador 600, registrador
  1100, verificador 900, presidente 1200 — ajustados a las 200/300/260 palabras
  que pide cada prompt;
* **temperatura por papel**, por si quieres medir si *subirla* un punto ayuda a
  la prosa del presidente sin estropear el JSON. Por defecto 0.0 en todos;
* `--token-scale` multiplica todos los topes a la vez, para comprobar si el
  recorte ayuda o estorba sin editar la tabla.

### Error 3 — el bucle de 3 pases puede comprar información que no tiene presupuesto

`tool_score` del evaluador oficial es **precisión**, no cobertura:

```python
# evaluation/evaluate.py :: cost_aware_tool_score
Score = |agent_tools ∩ pathologist_tools| / |agent_tools|
```

Abrir de menos es gratis; abrir de más se paga. El urólogo abrió imagen en el
97 % de los 91 casos, la serie de PSA en el 87 %, las notas previas en el 85 %,
el laboratorio en el 45 % y los antecedentes familiares en **0 %**. Tres
documentos dan una precisión esperada de ~0.90; el cuarto la baja a ~0.79.

Un bucle que reabre tres veces «para conseguir los datos que faltan» gasta
precisión en cada vuelta. **Cómo queda:** la reapertura exige las tres
condiciones a la vez —queda pase, queda presupuesto y queda un documento cerrado
que pueda contestar—, con techo de 3 revelaciones y un cuarto documento
autorizable **una sola vez** cuando el verificador nombra explícitamente cuál
falta. Sin la tercera condición, reabrir es releer, que es exactamente el gasto
inútil que se midió en la generación anterior.

### Error 4 — `get_family_history` no se le pide, se le quita

El urólogo la reveló **0 de 91 veces**. La v2 se lo pedía por escrito al modelo.
Aquí directamente **no se enlaza** al registrador: puede pedirla el resto del
mundo, pero él no tiene la herramienta. Impedir mecánicamente es más fiable que
pedir por favor.

### Error 5 — el verificador no puede tener la última palabra sobre reabrir

Huang et al. (ICLR 2024) miden que un LLM no juzga con fiabilidad si su propio
trabajo necesita corrección; en la v2 se observó en directo (`reopen: false` en
el 100 % de los casos, incluidos los que tenían dos posturas opuestas). Aquí el
verificador escribe una línea mecánica:

```
VERDICT: <ready | not-ready> | SUGGEST: <biopsy | defer> | MISSING: <documento | none>
```

y **el grafo aplica la regla**. Si no escribe la línea, se cierra: reabrir tiene
que costar una afirmación explícita, nunca un silencio.

### Error 7 — el verificador pedía el laboratorio por reflejo, y el filtro del plan se lo negaba

**Encontrado corriendo**, no leyendo: piloto de 10 casos, semilla 7. El
verificador nombró `laboratory_results` como lo que faltaba en **7 de 10 casos**.
No porque lo necesitara: es el único documento que normalmente queda cerrado,
así que es el nombre que sale cuando se le pregunta qué falta.

Dos consecuencias, las dos malas:

* se abrió el laboratorio en **4 de 10** casos —frente al 45 % del urólogo y al
  6/91 de la generación anterior— y `tool_score` cayó a **0.8167** (la v2 saca
  0.8782);
* y un caso peor: `PT-pseudo_…563c222a` gastó **los tres pases** pidiendo el
  laboratorio, que `clean_plan` volvía a tirar cada vez por no venir
  justificado, y terminó con **un solo documento abierto**. La regla de
  reapertura y el filtro del plan no estaban de acuerdo, así que el bucle giraba
  en vacío.

Lo que cuesta abrir de más, medido sobre los 91 casos etiquetados (precisión
media esperada según lo que abrió el urólogo en cada uno):

| documentos abiertos | precisión esperada |
|---|---|
| imagen | 0.9670 |
| imagen + PSA | **0.9176** ← el suelo del plan |
| imagen + PSA + notas | **0.8938** ← el plan normal |
| imagen + PSA + notas + **laboratorio** | 0.7830 |

El cuarto documento cuesta **−0.11 de `tool_score`**. Tiene que comprarse con
algo.

**Cómo queda:** tres cambios que se refuerzan.

1. El verificador sólo puede nombrar el laboratorio si ha escrito **en su propio
   texto** una de las tres preguntas que lo justifican (fracción de PSA libre,
   infección o prostatitis que explique el PSA, aptitud para el procedimiento).
   Si no, se ignora el nombramiento.
2. La reapertura exige ahora un documento **que sobreviviría al filtro del plan**
   de la vuelta siguiente, no simplemente uno cerrado. Se acabó el bucle en
   vacío.
3. Un **suelo de plan** determinista (`roster.FLOOR`): imagen y serie de PSA
   entran siempre en el primer pase. Cuesta 0.024 de precisión frente a abrir
   sólo la imagen, y a cambio pone la trayectoria del PSA sobre la mesa, que es
   una de las cuatro cosas de las que depende esta decisión. En el piloto hubo
   casos que se quedaron sin ella.

### Error 8 — la sala perseguía valores que ya estaban en el panel

También del piloto. El especialista en la guía escribía bajo *lo que aún nos
falta*: «the PSA density — the guideline makes the 0.15 ng/mL/cc threshold
decisive». El PSA density **está impreso en la intervención 1**. El moderador lo
convertía en pregunta abierta («Q1. What is the PSA density value?»), el
registrador salía a buscarlo, y en un caso el verificador acabó autorizando un
cuarto documento para recuperar un número que estaba sobre la mesa desde el
principio.

**Cómo queda:** prohibido en los dos prompts, con la lista de valores del panel
enumerada, y respaldado por una regla mecánica —`roster.drops_panel_question`—
que tira la pregunta y lo anota en el acta. La regla distingue «¿cuál es el PSA
density?» (se cae) de «¿comparan las notas el grado previo?» (se queda): un
valor del panel sólo es legítimo en una pregunta si lo que se pide es algo que
vive dentro de un documento.

### Error 9 — el reto al presidente saltaba por el motivo equivocado

**El más caro de todos, y sólo aparece corriendo los 91.** La primera corrida
completa dio `ranking_score` **0.5952** — por debajo del baseline. La causa,
localizada:

El presidente anuló a un colega con historial medido en **15 casos** y acertó en
**1**. El reto heredado de la generación anterior sólo se disparaba cuando su
razonamiento *no citaba nada recuperado* — y desde que el registrador abre tres
documentos en todos los casos, el presidente siempre puede citar algo, así que
saltó 7 veces y nunca donde hacía falta.

Quién tiene historial, medido out-of-fold sobre los 91:

| colega | dónde | acierto |
|---|---|---|
| `EXPERT-COHORT` | sin biopsia previa | 24/24 |
| `EXPERT-COHORT` | biopsia previa negativa | 16/18 |
| `EXPERT-CLASSIFIER` | `bx=Positive`, tramos `firm`+`supports` (13 casos) | **0.923** |
| `EXPERT-CLASSIFIER` | `bx=Positive`, tramo `discuss` (36 casos) | 0.472 |

**Cómo queda:** el reto se dispara sobre la **disidencia**, no sobre la falta de
citas, y agota tres turnos: aviso con la carga de la prueba, aviso con el
historial del colega, y si sigue disintiendo manda el colega y se le pide el
formulario una tercera vez con la decisión ya fijada. Resultado medido:
**0.5952 → 0.7055**.

Y la tercera vuelta no es cosmética. Sin ella —segunda corrida completa— la
anulación actuaba en 12 casos volteando sólo el booleano, y dejaba formularios
que dicen `yes` sobre una prosa que empieza *«Deferral is appropriate»*. Con el
juez de razonamiento apagado eso no puntúa; en el reto real sí, y es incoherente
para cualquiera que lo lea.

### Error 6 — el criterio de cohorte no estaba en el encargo, y quitarlo era una regresión

Es la única adición al orden que pediste, y va como intervención 4 para que se
vea en el acta si pesa en el dictamen. Sobre los 91 casos etiquetados: sin
biopsia previa → PI-RADS ≥ 3 acierta **24/24**; biopsia previa negativa →
PI-RADS ≥ 4 acierta **16/18**; biopsia previa positiva → el panel **no** lo
determina, y decirlo explícitamente vale más que callarse, porque impide que el
presidente lea el silencio como un «diferir». Es de donde sale que la v2
acertara 1.000 y 0.889 en esos dos cubos. Cabe en cuatro líneas y no le quita el
turno a nadie.

---

## 4. La guardia de procedencia: la respuesta real a las alucinaciones

Con la temperatura ya en cero, lo que queda de alucinación no viene del muestreo
sino del arrastre: el modelo repite un valor del texto que tiene delante, o lo
deriva mal. Eso se detecta **contando**, no rezando.

[`decide.unsourced_values`](decide.py) extrae del informe del registrador todo lo
que parece un valor clínico —decimales, o tres cifras o más— y comprueba que
aparezca en el resultado de alguna herramienta o en el panel. Lo que no aparezca
le devuelve el turno una vez, con la lista delante:

> STOP. These values appear in your report but in none of the documents you
> opened and not on the visible panel: 12.8, 21.5. …

Los enteros de una o dos cifras (un PI-RADS, una numeración) se ignoran a
propósito: aparecen en cualquier texto y sólo producirían falsos positivos. Los
años se ignoran porque el modelo los reformatea legítimamente.

**Un falso positivo deliberado:** un valor *derivado* correctamente —«un ascenso
de 1.3 ng/mL»— sale marcado, porque tampoco está literalmente en ninguna fuente.
Es la razón de que la guardia devuelva el turno en vez de invalidar el informe:
el modelo reescribe «subió de 0.6 a 4.7», que está citado y es mejor prosa para
el evaluador que una resta que nadie puede comprobar.

Comprobado en seco:

```
limpio   : []                     # 4.7 ng/mL, 33.46 mL, 0.14 — todos con fuente
sucio    : ['12.8', '21.5']       # inventados
derivado : ['1.3']                # correcto pero no citable → se le pide que cite
```

---

## 5. Los tres ficheros de entrada, cada uno por su vía

| fichero | quién lo usa | cómo |
|---|---|---|
| `structured-prompt.json` | INTAKE (crudo **y** renderizado) y EXPERT-CLASSIFIER | intervenciones 1 y 2, íntegro |
| `prostate-…-clinical-data.json` | REGISTRAR vía herramientas MCP | sólo lo que el plan pide; produce `reveal_sequence` |
| `prostate-modality-level-neural-representations.json` | EXPERT-IMAGE | `FeatureStore` + `run_predictor`; devuelve un escalar, nunca los vectores |

Un punto de transparencia heredado y que sigue valiendo: `reveal_sequence` se
deriva de las llamadas MCP del agente, no de lo que lea un experto en disco. El
clasificador ve el panel completo sin declararlo como revelación —igual que
`tools/predictor.py` del baseline lee los embeddings directamente—; lo que se
puntúa sigue siendo lo que el agente pide y cita.

---

## 6. Mapa de ficheros

| fichero | qué contiene |
|---|---|
| [`board.py`](board.py) | el acta: intervenciones numeradas, render, hilo, volcado a disco |
| [`roster.py`](roster.py) | el catálogo real de herramientas, el coste de cada una y la limpieza del plan |
| [`prompts.py`](prompts.py) | los cinco prompts (EAU, moderador, registrador, verificador, presidente) |
| [`graph.py`](graph.py) | el grafo LangGraph con los siete estados y el bucle del verificador |
| [`decide.py`](decide.py) | `reveal_sequence`, guardia de procedencia, aterrizaje, respaldo determinista |
| [`sampling.py`](sampling.py) | muestreo por papel; y por qué la temperatura ya no es una palanca |
| [`experts/classifier.py`](experts/classifier.py) | el RF de la ablación, dicho en cinco líneas |
| [`experts/cohort.py`](experts/cohort.py) | el criterio medido por cubo de biopsia previa |
| [`experts/image.py`](experts/image.py) | `FeatureStore` + `run_predictor`, sólo cuando lo convocan |
| [`analysis/compare.py`](analysis/compare.py) | comparación pareada contra el baseline y contra la pizarra v2 |
| [`runs/launch.sh`](runs/launch.sh) | lanza una corrida en tmux |

El paquete es autocontenido y borrable. Importa de `chimera_agent_baseline` sin
modificarlo, y reutiliza del paquete anterior sólo el clasificador ya entrenado y
su extractor de características — no se reabre esa decisión aquí.

---

## 7. Cómo se corre y cómo se mide

```bash
source .venv/bin/activate

# Monte Carlo: 3 muestras aleatorias de 30 casos, el modelo cargado una sola vez
delete_solution_one/solution_task_one_correction_II/runs/launch.sh mc \
    "--sample 30 --seeds 0 1 2"

# los 91 casos etiquetados
delete_solution_one/solution_task_one_correction_II/runs/launch.sh full ""

# comparación pareada contra el baseline y contra la pizarra v2,
# sobre exactamente los mismos casos de cada muestra
python delete_solution_one/solution_task_one_correction_II/analysis/compare.py \
    --auto delete_solution_one/solution_task_one_correction_II/runs --pattern 'mc_s*'

# la nota oficial de una corrida completa
python dev/score_local.py --tasks 1 --count-missing \
    --output-root delete_solution_one/solution_task_one_correction_II/runs/full/output
```

### El experimento de muestreo, si quieres cerrarlo

La temperatura no baja de 0, pero **el tope de tokens sí se mueve**, y es la
palanca que corresponde a lo que observaste. Tres muestras de 30 casos por brazo,
pareadas:

```bash
# brazo A — los topes de sampling.VOICES (lo que va por defecto)
runs/launch.sh mc_t1 "--sample 30 --seeds 0 1 2"
# brazo B — turnos un 40 % más cortos
runs/launch.sh mc_t06 "--sample 30 --seeds 0 1 2 --token-scale 0.6"
# brazo C — la contraprueba: ¿ayuda algo de temperatura en la prosa?
runs/launch.sh mc_t03 "--sample 30 --seeds 0 1 2 --temperature 0.3"
```

El criterio de parada es el mismo que ha regido hasta ahora: **ventaja
consistente entre semillas, no una media favorable**.

---

## 8. Bibliografía

**Arquitectura de pizarra**
- Erman, Hayes-Roth, Lesser, Reddy (1980). *The Hearsay-II Speech-Understanding System.* ACM Computing Surveys 12(2).
- Hayes-Roth (1985). *A blackboard architecture for control.* Artificial Intelligence 26(3).
- Nii (1986). *Blackboard Systems.* AI Magazine 7(2).

**Colaboración entre LLM**
- Du, Li, Torralba, Tenenbaum, Mordatch (2023). *Improving Factuality and Reasoning in Language Models through Multiagent Debate.* arXiv:2305.14325.
- Chen, Saha, Bansal (2023). *ReConcile: Round-Table Conference Improves Reasoning via Consensus among Diverse LLMs.* arXiv:2309.13007.
- Wu et al. (2023). *AutoGen.* arXiv:2308.08155.
- Tang et al. (2023). *MedAgents: LLMs as Collaborators for Zero-shot Medical Reasoning.* arXiv:2311.10537.
- Kim et al. (2024). *MDAgents: An Adaptive Collaboration of LLMs for Medical Decision-Making.* NeurIPS 2024.
- Wang et al. (2024). *Rethinking the Bounds of LLM Reasoning: Are Multi-Agent Discussions the Key?* ACL 2024.

**Límites de la auto-corrección**
- Huang et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR 2024.
- Turpin, Michael, Perez, Bowman (2023). *Language Models Don't Always Say What They Think.* NeurIPS 2023.

**Clasificación e incertidumbre** (la elección del clasificador se hereda, con su estudio)
- Breiman (2001). *Random Forests.* Machine Learning 45(1).
- Lakshminarayanan, Pritzel, Blundell (2017). *Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles.* NeurIPS 2017.
- Depeweg, Hernández-Lobato, Doshi-Velez, Udluft (2018). *Decomposition of Uncertainty in Bayesian Deep Learning.* ICML 2018.

**Recuperación**
- Lewis et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020.

> Las referencias van por autor, año, título y sede. Si van a un artículo,
> conviene verificar páginas y DOI en la fuente original.
