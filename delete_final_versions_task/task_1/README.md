# Junta clínica con expertos entrenados — tarea 1, versión final

Decisión de biopsia de próstata (CHIMERA-Agent, tarea 1). Una **pizarra** con
quince intervenciones donde cuatro expertos entrenados, una biblioteca de
precedentes, un especialista en la guía EAU y un registrador que abre documentos
construyen el expediente; un **protocolo escrito** toma la decisión por reglas de
acierto medido; y un urólogo consultor —el modelo de lenguaje— redacta la nota
clínica que va al registro.

Es la cuarta generación de esta pizarra y la que se entrega. Las tres anteriores
están en [`../solution_task_one`](../solution_task_one) (0.6749),
[`../solution_task_one_correction_claude`](../solution_task_one_correction_claude)
(0.7125) y [`../solution_task_one_correction_II`](../solution_task_one_correction_II)
(0.7069). Ésta es **independiente**: no importa nada de ellas.

> ## Resultado
>
> Evaluador **oficial** de los organizadores, juez de razonamiento desactivado,
> **91 casos etiquetados**, temperatura 0, casos sin salida contados como fallo.
> Corrida completa de los 195 casos en [`runs/final`](runs/final).
>
> | | baseline T=0 | pizarra v1 | pizarra v2 | junta | **ENTREGA** |
> |---|---|---|---|---|---|
> | `ranking_score` | 0.6428 | 0.6749 | 0.7125 | 0.7069 | **0.8390** |
> | `mean_case_score` | 0.4913 | 0.5499 | 0.6006 | 0.6068 | **0.7470** |
> | puerta de decisión | 0.6813 | 0.6923 | 0.7473 | 0.7582 | **0.9121** |
> | F1(`yes`) | 0.7943 | 0.8000 | 0.8244 | 0.8070 | **0.9310** |
> | `confidence_score` | 0.7661 | 0.7063 | 0.7500 | 0.7536 | 0.7651 |
> | `variable_weight_score` | 0.6516 | 0.8365 | 0.8088 | 0.7977 | **0.8506** |
> | `important_decisive_factor_score` | 0.5609 | 0.7421 | 0.7264 | 0.7295 | **0.7723** |
> | `tool_score` | 0.6468 | 0.7698 | 0.8664 | 0.8816 | 0.8685 |
> | `section_grounding_score` | 0.9960 | 0.9138 | 0.8887 | 0.8653 | 0.8431 |
>
> **+0.196 sobre el baseline a la misma temperatura** (76 casos suben, 9 bajan,
> 6 empatan; prueba de signos p = 2·10⁻¹⁴) y **+0.132 sobre la mejor generación
> anterior** (58 suben, 30 bajan, p = 0.004).
>
> ### Dónde se gana: el cubo clínico difícil
>
> | cubo | n | pizarra v2 | junta | **ENTREGA** |
> |---|---|---|---|---|
> | `bx = None` | 24 | 1.000 | 1.000 | **1.000** |
> | `bx = Negative` | 18 | 0.889 | 0.889 | **0.889** |
> | `bx = Positive` | 49 | 0.571 | 0.592 | **0.878** |
> | **total** | 91 | 0.747 | 0.758 | **0.912** |
>
> Los 49 casos con biopsia previa positiva son el problema que ninguna generación
> anterior resolvió. Pasan de 0.59 a 0.88, y ahí está toda la ganancia.
>
> ### Integridad de la entrega, sobre los 195 casos
>
> | | |
> |---|---|
> | casos entregados | **195/195**, 0 fallos |
> | salidas que validan contra `Task1Output` | **195/195** |
> | notas que describen el procedimiento en vez del paciente | **0/195** (generación anterior: 187/195) |
> | notas con un grado de biopsia que ningún documento recoge | **0/195** (sin la guardia: 5/195; la guardia actuó en 10 casos) |
> | variables registradas *important*/*decisive* que la nota nombra | **0.923** de recall, 0.753 de precisión |
> | confianza entregada frente a la del urólogo | **0.753** de `confidence_score`, la mejor de las seis fuentes |
> | lo abierto coincide con el plan | **195/195** |
> | `family_history` abierta (el urólogo: 0/91) | **0/195** |
> | respaldo determinista del formulario | 0 · de la nota, 2 |
> | precedente idéntico (imposible en el test) | 0 |
> | tiempo por caso, modelo ya cargado | 30 s (p90 34 s) |
>
> ### Con el juez de razonamiento encendido
>
> Todo lo anterior está medido con el juez apagado, que es el modo determinista.
> Encendido —el `build_rationale_judge()` de los organizadores, un `GEval` de
> DeepEval sobre Ollama con `gemma4:e4b` y su rúbrica literal— los pesos cambian
> (el razonamiento entra con 0.20 y el aterrizaje baja de 0.175 a 0.05), así que
> **estas cifras no son comparables con las de arriba**, sólo entre sí:
>
> | | baseline T=0 | junta (3ª gen.) | **ENTREGA** |
> |---|---|---|---|
> | `ranking_score` | 0.6378 | 0.6907 | **0.8368** |
> | `mean_case_score` | 0.4813 | 0.5743 | **0.7426** |
> | **`rationale_score`** | 0.7968 | 0.6116 | **0.8012** |
> | casos juzgados (los que pasan la puerta) | 62/91 | 69/91 | **83/91** |
>
> **El juez confirma la corrección de la nota clínica.** La tercera generación
> —aquella en la que 187 de 195 notas nombraban un participante de la junta o un
> mecanismo del sistema— saca **0.6116**; la de entrega, **0.8012**. Son +0.19 en
> el componente que pesa 0.20, y salen de reescribir el prompt del presidente,
> no de cambiar ninguna decisión. De las 83 notas juzgadas, **29 obtienen un 1.00
> redondo** y sólo 4 bajan de 0.5.
>
> Un matiz honesto: el baseline saca 0.7968 de razonamiento, prácticamente lo
> mismo que la entrega. Su prosa nunca fue el problema —escribe como un clínico
> porque no tiene una junta que describir—; lo que falla es la decisión, y por
> eso sólo llega a la puerta en 62 de 91 casos frente a nuestros 83. El juez
> puntúa la nota de los casos que pasan, así que un buen razonamiento sobre una
> decisión equivocada no se llega a puntuar nunca.
>
> Se reproduce con `.venv-eval/bin/python dev/score_with_judge.py` (§8). Una sola
> pasada del juez; a temperatura 0 pero un LLM juzgando sigue teniendo varianza.
>
> ### La cifra honesta, al lado
>
> | configuración | `ranking_score` | qué mide |
> |---|---|---|
> | **entrega** | **0.8390** | lo que se entrega. Los expertos vieron las etiquetas de estos 91 casos, así que es optimista respecto al test |
> | *techo* | 0.9469 | dejando que la biblioteca devuelva el caso idéntico. Imposible en el test; sólo mide el mecanismo |
> | *honesto* | 0.7607 | expertos reentrenados out-of-fold: la cota inferior de generalización |
>
> Sobre el conjunto de test las tres son **el mismo programa**. La corrida con LLM
> dio 0.8390 y la simulación sin LLM predecía 0.8390: el modelo de lenguaje no
> movió la nota ni una milésima, que es exactamente lo que el diseño pretendía.


---

## 1. Las tres cosas que definen esta versión

**1. El modelo de lenguaje no decide.** Hace lo que sabe hacer —recuperar, leer,
resumir, redactar— y no hace lo que se midió tres veces que hace mal. En los 49
casos con biopsia previa positiva, que es el cubo donde se gana o se pierde la
tarea, los votos del LLM están en el azar: el registrador acierta 0.47 y el
verificador 0.49. La decisión la toma una cascada de reglas cuyo acierto está
medido y escrito en el acta, y la sala aporta **lo que recupera**, que es
justamente lo que alimenta esas reglas. No es una renuncia: es el reparto que los
datos sostienen, y hay una tabla que lo mide en el cuaderno.

**2. La nota clínica describe al paciente, no al procedimiento.** El `free_text`
que el reto puntúa es la traza de razonamiento de un clínico. En la generación
anterior, 187 de 195 notas (96 %) nombraban un participante de la junta o un
mecanismo del sistema, porque el prompt del presidente le enumeraba los
participantes, le entregaba el acta entera y le daba la decisión como
«PANEL-PROTOCOL respondió … por la regla …». Aquí el presidente **no ve el acta ni
la lista de participantes**: recibe un parte clínico construido en código, con la
justificación en palabras de urólogo, y lo que escribe se comprueba con una lista
de patrones que da **0 falsos positivos sobre los 91 textos reales del urólogo**.
El análisis completo está en [`PROMPTS.md`](PROMPTS.md).

**2-bis. Ningún hecho clínico sin documento que lo sostenga.** La guardia de
procedencia miraba números con decimales, y a propósito ignoraba los enteros de
una cifra porque aparecen en cualquier texto. Eso dejaba fuera justo el hecho más
decisivo de esta tarea: el grado de la biopsia previa. Medido sobre una corrida
completa de 195 casos, el registrador escribió un grado que **no está en el
fichero clínico** en 13 informes (6.7 %) —entrecomillado, como si lo citara— y 5
de esas invenciones llegaron a la nota entregada. El protocolo nunca se dejó
engañar, porque lee el texto crudo de la herramienta y no el resumen; la nota
clínica sí. Ahora se comprueba en las tres capas donde puede colarse: se le reta
al registrador, se borra del parte del presidente y se verifica la nota final.
La corrida anterior se conserva en
[`runs/_sin_guardia_de_grados/`](runs/_sin_guardia_de_grados) como evidencia.

**3. Lo que se mide es lo que se entrega.** La biblioteca de precedentes, cuando
el caso que se decide está en la serie etiquetada, encuentra su propio panel a
distancia cero y devuelve la decisión que el urólogo tomó con él. En el test eso
**no puede ocurrir nunca**, así que no aporta un solo punto en el reto y a cambio
convierte la nota local en un espejismo. Va apagado. Se puede encender
(`--self-match`) para ver el techo del mecanismo, y el cuaderno publica las tres
cifras juntas.

---

## 2. La sesión, intervención por intervención

```
ESTADO 0   pizarra en blanco
   │
   ├─ 1  INTAKE ............... structured-prompt.json, campo por campo        ─┐ ESTADO 1
   ├─ 2  INTAKE ............... el mismo, con templates/prompts/agent_prompt.j2 │
   ├─ 3  EXPERT-STRUCTURED .... Experto 1: Extra-Trees sobre el panel           │
   ├─ 4  EXPERT-COHORT ........ el criterio medido de esta situación clínica    │
   ├─ 5  EXPERT-LIBRARY ....... los 3 precedentes etiquetados más cercanos      │
   ├─ 6  EXPERT-TRACE ......... Experto 4: qué abre y qué pesa el urólogo      ─┘ → FIJA EL PLAN
   │
   ├─ 7  EXPERT-EAU ........... RAG sobre la guía; critica a los expertos         → ESTADO 2
   ├─ 8  MODERATOR ............ preguntas abiertas; una pregunta por documento    → ESTADO 3
   ├─ 9  EXPERT-IMAGE ......... sólo si el moderador lo convoca
   ├─ 10 REGISTRAR ............ abre exactamente el plan; grado, sesiones, RM     → ESTADO 4
   │
   ├─ 11 EXPERT-PSA ........... Experto 2: proyecta la serie que se abrió       ─┐ ESTADO 5
   ├─ 12 EXPERT-FUSION ........ Experto 3: sobre los documentos abiertos          │
   ├─ 13 PANEL-PROTOCOL ....... la cascada, con la regla que disparó            ─┘ → DECIDE
   │
   ├─ 14 VERIFIER ............. ¿decidible ya? ¿falta un documento del plan?      → ESTADO 6
   │        ├─ falta uno ──► vuelve al MODERATOR (pase 2: intervenciones 15, 16…)
   │        └─ listo ──►
   │
   └─ 15 CHAIR ................ la nota clínica y el formulario validado          → ESTADO 7
```

La numeración es **global y monótona**: si el verificador reabre, la segunda
vuelta no es «ronda 2 · intervención 8», son las intervenciones 15, 16 y 17.
Citar «intervención 10» identifica un turno único, y eso es lo que hace que el
acta sea una traza y no un adorno. Se persiste entera, en JSON y en Markdown,
para los 195 casos.

### Quién es quién

| # | interviene | qué es | qué lee | qué aporta |
|---|---|---|---|---|
| 3 | EXPERT-STRUCTURED | Experto 1, Extra-Trees + bagging × imputación múltiple | el panel (39 variables) | apuesta con barra de error y tramo de fiabilidad medido |
| 4 | EXPERT-COHORT | reglas | el panel | el criterio que la serie confirma para esta situación |
| 5 | EXPERT-LIBRARY | kNN por cubo | panel + las 91 trazas | precedentes con lo que el urólogo decidió y escribió |
| 6 | EXPERT-TRACE | Experto 4, logística por casilla con puerta LOOCV | el panel | qué documentos abre el urólogo y qué pesa → **el plan** |
| 7 | EXPERT-EAU | LLM + RAG | la guía EAU | qué exige la guía, con cita literal |
| 8 | MODERATOR | LLM | el acta | las preguntas abiertas y la de cada documento |
| 9 | EXPERT-IMAGE | código | los embeddings congelados | qué dan los vectores (medido: nada en T1) |
| 10 | REGISTRAR | LLM + MCP | los documentos del plan | qué dicen, con sus valores y sus citas |
| 11 | EXPERT-PSA | Experto 2, Extra-Trees anclado + jackknife+ | la serie de PSA abierta | trayectoria con banda conforme |
| 12 | EXPERT-FUSION | Experto 3, Extra-Trees sobre A+B+D | panel + analítica + RM **abiertas** | la mejor apuesta del panel (AUC 0.794) |
| 13 | PANEL-PROTOCOL | código | todo lo anterior | **la decisión**, por regla escrita |
| 14 | VERIFIER | LLM + RAG | el acta y la guía | si el expediente está en condiciones |
| 15 | CHAIR | LLM | un parte clínico sin locutores | **la nota clínica** y el formulario |

### Lo que cada experto declara, y en qué vocabulario

Cada experto —entrenado o de reglas— cierra su turno con el mismo bloque: **qué
variables pesó, a qué nivel y con qué confianza, en las palabras del formulario**
(`not_used` / `noted` / `important` / `decisive`; `clear` / `borderline` /
`uncertain`), con el valor del paciente al lado y, si es un modelo, la parte de
su señal que cada variable explica. El protocolo lo consolida en una **tabla de
variables de la sala** —valor, lo que marcó cada experto, lo que se registra— que
va al acta y al turno del verificador, que la contesta variable por variable. Al
presidente **no** le llega: se midieron las tres variantes sobre los 195 casos y
darle la tabla, entera o resumida, **empeora** la nota (la fracción de variables
registradas que llega a nombrar baja de 0.932 a 0.890 y 0.900). Le ayuda razonar
sobre los hechos clínicos y llegar a ellas solo. Los papeles LLM hablan con esas
mismas palabras: el especialista en la guía critica niveles, el moderador
pregunta por variables, el verificador contesta con niveles y su propia
confianza.

Una advertencia medida antes de decidir qué va al formulario: los niveles de los
clasificadores miden *cuánto movió su predicción* una variable —para ellos el
estado de biopsia previa es el 43 % de la señal y PI-RADS apenas varía en esta
serie—; para el urólogo, PI-RADS es la puerta de entrada. Subir al formulario una
variable por acuerdo del panel **baja la nota** (0.8390 → 0.8365, evaluador
oficial), así que los pesos que se entregan siguen siendo los del Experto 4,
entrenado contra la traza del urólogo, y las variables de los demás alimentan el
razonamiento. El cuaderno de anatomía mide el acuerdo de cada fuente con el
urólogo, variable por variable.

Los cuatro expertos entrenados vienen de
[`../../delete_expert_modelate/task_one`](../../delete_expert_modelate/task_one)
y se cargan de sus artefactos. Los que leen documentos (2 y 3) hablan **después**
del registrador y **sólo sobre lo que se abrió**: si el informe de RM no está
sobre la mesa, el Experto 3 se abstiene; si falta la analítica, habla con ese
bloque en blanco y su incertidumbre por datos ausentes lo refleja. Es la
diferencia entre un experto que cita un documento y uno que lo lee por debajo de
la mesa.

---

## 3. El protocolo: cómo se decide

Una cascada ordenada por acierto medido. Cada peldaño se lee en el acta con la
regla que disparó y el historial que la sostiene.

```
1. criterio de cohorte    sin biopsia previa:  PI-RADS >= 3                      24/24
                          biopsia negativa:    PI-RADS >= 4                      16/18
                          biopsia positiva:    PSA >= 20 · edad >= 78 · PI-RADS <= 2 → diferir   9/10
2. grado documentado      GG >= 2 → tratar, no re-biopsiar    7/8
                          GG 1 en vigilancia → confirmatoria  3/4
3. voto ponderado         Experto 3 × tramo × 1.5  +  Experto 1 × tramo
                          tramo: firm 3 · supports 2 · discuss 1 ;  biopsia si p >= 0.45
```

**De dónde salen las reglas del cubo difícil.** Los 49 casos con biopsia previa
positiva son el problema que ninguna generación anterior resolvió: kNN sobre el
panel acierta 0.43–0.47, el clasificador en su tramo bajo 0.55, y los votos del
LLM 0.47–0.49. Lo que sí hay es el propio urólogo, que en su `free_text` explica
el criterio con todas las letras. Leídos los 49:

| lo que escribe | regla | n | acierto |
|---|---|---|---|
| «start treatment and do a PSMA-PET» | PSA ≥ 20 → diferir | 6 | 5 |
| «stop checking PSA, no need for diagnostics» | edad ≥ 78 → diferir | 2 | 2 |
| «now normal MRI» | PI-RADS ≤ 2 → diferir | 2 | 2 |
| «needs treatment without repeat biopsy as earlier biopsy showed ISUP4» | grado documentado GG ≥ 2 → diferir | 8 | 7 |
| «only one previous biopsy… would lean toward one confirmatory biopsy» | GG 1 en vigilancia → biopsiar | 4 | 3 |
| «need to know initial ISUP», «has the lesion grown» | el resto: información ausente | ~28 | 0.64 por defecto «sí» |

Las tres primeras son criterio de guía —enfermedad de alto riesgo va a
estadificación, expectativa de vida limitada no necesita más diagnóstico, sin
lesión no hay nada que muestrear— y la serie las confirma. **El grado documentado
vive en las notas previas**, y sólo llega ahí si el registrador las abre: es el
punto donde la deliberación del LLM sí decide el caso. Y como un modelo pequeño
lo copia mal («ISUP 2» donde el documento dice «Gleason 3+4»), el grado se extrae
con expresión regular del **texto crudo que devolvió la herramienta**, se traduce
Gleason→ISUP y se escribe en el acta con la cita.

**La biblioteca no vota.** Fuera del caso idéntico su acierto en el cubo positivo
es 0.47 —azar—, y darle medio voto costaba 0.033 de ranking. Sigue hablando: sus
precedentes son evidencia para la sala y su moda por cubo alimenta los pesos. Lo
que se le quita es el voto, que es lo que no se ganó.

---


## 4. La votación, paso a paso

La sección 3 dice que el protocolo es «una cascada ordenada por acierto medido» y
lista los peldaños. Lo que no explica es **el mecanismo del peldaño 4**, que es el
único donde hay aritmética. Esta sección lo escribe entero.

Sobre los 91 etiquetados de la corrida de entrega, los peldaños se reparten así:

| peldaño | casos | qué lo dispara |
|---|---:|---|
| 2 · criterio de cohorte | 52 | PI-RADS ≥3 sin biopsia previa, ≥4 con biopsia negativa, PSA ≥20… |
| 3 · grado documentado | 12 | el registrador encuentra un GG en las notas abiertas |
| 4 · voto ponderado | 27 | ninguno de los anteriores reclama el caso |

### Qué aporta cada experto al voto

Cada experto llega con dos cosas: su probabilidad `p` y su **tramo de fiabilidad**,
medido, no declarado. El tramo fija el peso:

| tramo | peso (`tier_weight`) |
|---|---:|
| `firm` | 3.0 |
| `supports` | 2.0 |
| `discuss` | 1.0 |

Encima de eso, dos correcciones que **no** son ajustes de conveniencia:

- **El Experto 3 (fusión) lleva multiplicador 1.5** (`fusion_mult`). Su AUC es
  **0,794** frente a **0,758** del Experto 1. Un experto que discrimina mejor pesa
  más, y la cifra que lo justifica está medida sobre la misma serie.
- **La biblioteca de precedentes vale 0.0** (`library_weight`). No es que no
  hable: sus precedentes son evidencia para la sala y su moda por cubo alimenta
  los pesos del formulario. Lo que se le quita es **el voto**. La razón está
  medida: en el cubo `bx=Positive` su acierto es **0,47**, que es azar, y darle
  medio voto costaba **0,033 de ranking** en la configuración de entrega (0,8054
  con 0.5 frente a 0,8384 con 0.0).

### La fórmula

```
p = Σ(pᵢ · wᵢ) / Σ(wᵢ)          biopsia si  p ≥ 0.45
```

El umbral 0,45 es la **carga de la prueba**: diferir a un hombre con cáncer
conocido y PSA en ascenso exige una razón positiva, no la ausencia de una razón
negativa. Se eligió sobre los 91 con el evaluador oficial, y la rejilla entera se
publica en la §7 porque el umbral se ajustó sobre el mismo conjunto con el que se
mide:

| umbral | ranking |
|---:|---:|
| 0.50 | 0,8215 |
| **0.45** | **0,8384** |
| 0.40 | 0,8222 |

### Un ejemplo trabajado, de principio a fin

Caso **`PT-pseudo_075dd468b384`** de `runs/labeled/output`. Ningún criterio de
cohorte lo reclama y no hay grado documentado, así que cae al peldaño 4. Entran
tres voces:

| experto | respuesta | `p` | tramo | peso |
|---|---|---:|---|---:|
| EXPERT-STRUCTURED | yes | 0,5361 | `discuss` | 1.0 |
| EXPERT-FUSION | yes | 0,6210 | `supports` × 1.5 | **3.0** |
| EXPERT-LIBRARY | **no** | 0,3475 | k=3 precedentes | **0.0** |

La aritmética:

```
numerador   = 0,5361·1,0 + 0,6210·3,0 + 0,3475·0,0 = 2,3991
denominador = 1,0 + 3,0 + 0,0                      = 4,0
p           = 2,3991 / 4,0                         = 0,5998
0,5998 ≥ 0,45  ->  biopsia: yes
```

Fíjate en lo que pasa con la biblioteca: **disiente** —dice `no` con p 0,3475— y
su disidencia queda escrita en el acta como voz discrepante, pero **no mueve el
resultado**, porque su peso es 0. Es exactamente el comportamiento que se buscaba:
que hable quien tiene algo que decir y que vote sólo quien se lo ha ganado.

### Qué NO es este mecanismo

- **No es un promedio.** Los pesos no son iguales: salen del tramo de fiabilidad
  medido de cada experto.
- **No es una mayoría.** En el ejemplo hay 2 votos a favor y 1 en contra, pero lo
  que decide es la masa ponderada, no el recuento. Con los pesos invertidos el
  mismo reparto de votos daría lo contrario.
- **El LLM no tiene voto.** No es una postura de principio: está medido tres veces
  (generaciones v1, v2 y junta). En el cubo indeterminado el registrador acierta
  **0,47**, el verificador **0,49** y el presidente **0,59** — y ese 0,59 ya lleva
  dentro el reto mecánico. El presidente escribe la nota clínica y firma la
  decisión que el protocolo produjo; no la elige.

## 5. Incertidumbre, confianza y peso de las variables

Ésta es la sección que faltaba, y la razón principal de este documento.

### Tres nociones de importancia, y sólo una se entrega

«Qué variable importa» significa tres cosas distintas, y confundirlas es fácil:

| noción | qué mide | de dónde sale |
|---|---|---|
| **atributiva** | qué mueve la predicción del modelo | permutación out-of-fold; lo que declara cada experto |
| **normativa** | qué exige mirar la guía | el peldaño que disparó |
| **conductual** | qué marcó el urólogo en su traza | EXPERT-TRACE |

**Sólo la conductual se entrega**, porque es la única que el evaluador puntúa: el
patrón contra el que compara `variable_weight_score` son las casillas que rellenó
el urólogo, no las que el modelo considera influyentes.

Y esto no es una preferencia estética, está medido: promover pesos por acuerdo
del panel —la política `board`, que sube a `important` una variable cuando al
menos dos expertos la marcan y su sección está abierta— **baja la nota de 0,8390
a 0,8365**. Se entrega la conductual (`form_weights: "trace"`); las otras dos
quedan como auditoría y alimentan el razonamiento de la sala.

### El presupuesto de varianza

La incertidumbre epistémica se compone **en cuadratura**:

```
σ²_epist = σ²_model + σ²_missing + σ²_panel
```

- `σ²_model` — dispersión entre los miembros del ensemble.
- `σ²_missing` — término *between* de Rubin: dispersión entre imputaciones.
- `σ²_panel` — varianza muestral entre las `p` de los expertos disponibles. Con
  menos de dos expertos es 0,0 por construcción, no por convenio.

Se suman en cuadratura porque son varianzas **de la misma cantidad** bajo fuentes
de incertidumbre independientes; es la regla de composición de Rubin (1987) para
imputación múltiple, extendida a las otras dos fuentes.

**La aleatoria no se suma.** La entropía normalizada `H` se reporta aparte porque
mezclar una varianza de Bernoulli con un error típico da una barra de anchura casi
constante que no discrimina entre casos: justo lo contrario de lo que se le pide a
una medida de incertidumbre. La separación entre epistémica y aleatoria sigue a
Depeweg et al. (2018).

En el código, el presupuesto vive en
[`common/uncertainty_forms.py`](../common/uncertainty_forms.py) (`VarianceBudget`,
`pool_variance`), y los términos los producen los expertos entrenados en
`common/chimera_experts/uncertainty.py`.

### La confianza la produce el peldaño que decidió, no la probabilidad

Una `p` de 0,52 no significa lo mismo si la produjo un criterio de cohorte que
acierta 24/24 que si salió de un voto entre expertos en desacuerdo. Por eso la
confianza **no** se deriva de la probabilidad: se deriva del **peldaño**, con un
techo por peldaño medido sobre su propio acierto (`RUNG_CEILING`), y dentro de ese
techo baja un escalón si la dispersión epistémica del caso supera el cuantil 0,66
de la cohorte.

La política de entrega es `agreement`, y la razón está medida: empata en ranking
con la alternativa `trace` (0,8390 frente a 0,8384) y **gana en el componente que
de verdad mide la confianza** (0,765 frente a 0,759). Entre dos políticas que
puntúan igual en el total, se entrega la que informa.

> **Lo que esta versión NO puede afirmar.** La política `confidence_from_rung`
> —la que deriva la confianza del peldaño con calibración por peldaño— **no está
> validada fuera de muestra**. Medirla exige veredictos en LOO anidado con
> calibración interior sin fuga, y el coste real de ese cálculo se midió en
> **169,83 horas en serie**. El caché histórico llamado `honest` usa cinco
> particiones, no LOO, así que no sirve para esa comparación. Lo que se entrega
> es la política `agreement`, que sí está medida; la calibración por peldaño
> queda documentada y sin adoptar. Ver `common/analysis/forms_report.json`.

## 6. Las guardias: lo verificable se verifica en código

| guardia | qué comprueba | qué hace si falla |
|---|---|---|
| `decide.process_language` | la nota describe al paciente, no el procedimiento | devuelve el turno con la lista; si reincide, redacta la nota de forma determinista |
| `decide.unsourced_values` | todo número del informe está en una herramienta, el panel o el acta | devuelve el turno una vez con la lista |
| `decide.unsourced_grades` | **ningún grado de biopsia afirmado sin documento** que lo recoja | reta al registrador, lo borra del parte del presidente y lo comprueba en la nota entregada |
| `decide.documented_grade` | el grado de la biopsia previa, sobre el texto crudo | lo escribe en el acta con su cita y lo pasa al protocolo |
| `decide.enforce_grounding` | ninguna variable pesada sin su sección abierta | la baja a `not_used` y lo anota |
| `decide.validate_output` | el registro valida contra `Task1Output` | rehace la nota y revalida; se anota `schema_ok` |
| plan fijo | el registrador abre exactamente lo que el Experto 4 listó | lo que se pida de más se cae con motivo escrito |
| plan vacío | sin plan, no se le enlazan herramientas de documento | mecánicamente no puede abrir nada |
| línea `VERDICT` | reabrir exige una afirmación explícita y un documento del plan sin abrir | si no la escribe, la sesión se cierra |
| respaldo determinista | el presidente no entrega JSON válido | nota clínica construida desde los hechos; ningún caso se pierde |

---

## 7. Los parámetros, y el sesgo que llevan dentro

Cinco parámetros del protocolo se eligieron con
[`analysis/simulate.py`](analysis/simulate.py), que evalúa una configuración sin
cargar el modelo en segundos, **sobre los mismos 91 casos con los que después se
puntúa**. Eso es sesgo de selección y hay que decirlo: la rejilla completa (128
combinaciones) mueve el `ranking_score` entre **0.77 y 0.84**, así que el número
que se publica está en el extremo alto de una distribución que se exploró.

| parámetro | elegido | alternativas medidas |
|---|---|---|
| umbral del voto ponderado | **0.45** | 0.50 → 0.8215 · 0.45 → 0.8384 · 0.40 → 0.8222 · 0.35 → 0.8064 |
| peso de la biblioteca | **0.0** | 0.5 → 0.8054 · 0.0 → 0.8384 |
| regla del grado documentado | **activa** | inactiva → −0.001 aquí, −0.031 en la configuración honesta |
| política de confianza | **acuerdo** | acuerdo 0.8390 · traza 0.8384 (la traza da `clear` constante: empata y no informa) |
| política de pesos | **modelo + moda** | moda pura → 0.8344 |
| pesos del formulario | **traza (Experto 4)** | subidos por acuerdo del panel (≥ 2 expertos) → 0.8365 |
| qué ve el presidente de la tabla | **nada** | tabla entera → recall 0.890 · lista corta → 0.900 · nada → **0.932** (misma nota oficial en las tres) |
| k de la biblioteca | **3** | 1, 5, 7 dentro de ±0.008 |

Dos de los seis se eligieron por principio y no por la tercera cifra decimal: la
biblioteca no vota porque su acierto en el cubo difícil es el azar, y la
confianza sale del acuerdo porque produce una señal por caso en vez de una
constante. Los otros cuatro son ajuste, y por eso se publica la rejilla.

---

## 8. Cómo se corre

```bash
source .venv/bin/activate

# 1. el panel de expertos, una vez (~30 min con el out-of-fold; --no-oof: 3 min)
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_using_experts_final.experts.panel

# 2. la nota esperada sin LLM, y la rejilla de parámetros
PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_using_experts_final.analysis.simulate --grid

# 3. la corrida de entrega: los 195 casos
delete_solution_one/solution_task_one_using_experts_final/runs/launch.sh final "--all-cases"

# 4. los dos cuadernos (nbclient; el venv no trae nbconvert)
python delete_solution_one/solution_task_one_using_experts_final/analysis/_build_notebook.py
python delete_solution_one/solution_task_one_using_experts_final/analysis/_build_anatomia.py
PYTHONPATH=src:. python delete_solution_one/solution_task_one_using_experts_final/analysis/_run_notebook.py
PYTHONPATH=src:. python delete_solution_one/solution_task_one_using_experts_final/analysis/_run_notebook.py \
    --notebook anatomia_del_agente.ipynb

# 5. la nota oficial, por si se quiere sin cuaderno
python dev/score_local.py --tasks 1 --count-missing \
    --output-root delete_solution_one/solution_task_one_using_experts_final/runs/final/output

# 6. y con el JUEZ DE RAZONAMIENTO encendido, que es como puntúa Grand Challenge.
#    Necesita Ollama con gemma4:e4b y DeepEval, que va en un venv aparte para no
#    tocar el entorno de entrega (mcp y vLLM están fijados ahí).
uv venv .venv-eval --python 3.12 && uv pip install --python .venv-eval/bin/python deepeval ollama scikit-learn
.venv-eval/bin/python dev/score_with_judge.py \
    --output-root delete_solution_one/solution_task_one_using_experts_final/runs/final/output \
    --json-out .../runs/judge/entrega.json
```

Cada caso escribe: los dos ficheros de Grand Challenge, el acta completa en JSON
y Markdown, una línea en `summary.jsonl` con la telemetría, y las filas de
`telemetry.jsonl` (una por llamada al modelo y por llamada a herramienta).

---

## 9. Qué falta para subirlo a Grand Challenge

En el reto **cada caso es un contenedor**: `inference.py` recibe en `/input` los
tres ficheros de un paciente, arranca el modelo y escribe dos ficheros en
`/output`. Esta solución se desarrolló con un runner por lotes, y quedan tres
cosas por hacer. No son de diseño, son de empaquetado.

1. **`inference.py` llama al ReAct del baseline.** El adaptador ya está escrito,
   dentro de este paquete y sin tocar el upstream:
   [`gc_entry.run_task1_case`](gc_entry.py) monta el caso en un directorio
   temporal con el layout que el MCP espera, arranca el servidor, construye el
   grafo, valida contra `Task1Output` y escribe los dos ficheros; si algo falla
   escribe igualmente una salida válida, porque un caso sin salida no es un cero
   sino un caso perdido. Integrarlo es sustituir el cuerpo de `interf0_handler`
   por:

   ```python
   from delete_solution_one.solution_task_one_using_experts_final.gc_entry import run_task1_case

   return run_task1_case(
       structured_prompt=input_structured_prompt,
       clinical_data=input_prostate_biopsy_decision_clinical_data,
       neural_representations=input_prostate_modality_level_neural_representations,
       output_path=OUTPUT_PATH,
       embedding_model_dir=EMBEDDING_MODEL_PATH,
   )
   ```

   Queda por hacer la prueba en contenedor (`./do_test_run.sh`): el adaptador
   está verificado en sus partes —el respaldo produce una salida que valida— pero
   no se ha ejecutado dentro de la imagen.
2. **La imagen no lleva lo que hace falta.** `Dockerfile_Baseline` copia `src/`,
   `templates/`, `resources/` y `configs/`. Hay que añadir este paquete y
   `delete_expert_modelate/chimera_experts`, y meter en el **tarball del modelo**
   los cuatro `.joblib` (~80 MB) y los 91 casos etiquetados (~3 MB), porque la
   biblioteca de precedentes y la moda por cubo los leen en tiempo de ejecución.
3. **Fijar `scikit-learn==1.9.0`**, `scipy` y `joblib` en `requirements.txt`: los
   artefactos se deserializan con esa versión.

Y dos avisos: el tiempo por contenedor es carga del modelo (~90 s) + servicio de
embeddings (~30 s) + la junta (~25 s) ≈ **2–3 min**, que hay que contrastar con
el límite del reto; y un caso que no esté en `artifacts/panel_cache.json` —todo
caso de test— se puntúa en vivo con `Panel.ensure()`, verificado contra el caché,
lo que añade 30–80 s.

---

## 10. Mapa de ficheros

| fichero | qué contiene |
|---|---|
| [`board.py`](board.py) | el acta: intervenciones numeradas, render, hilo, volcado |
| [`roster.py`](roster.py) | el catálogo desde la lista MCP viva; el plan por secciones |
| [`prompts.py`](prompts.py) | los cinco prompts y el **parte clínico** del presidente |
| [`PROMPTS.md`](PROMPTS.md) | el análisis de los cinco prompts, uno por uno |
| [`graph.py`](graph.py) | el grafo LangGraph con las quince intervenciones |
| [`protocol.py`](protocol.py) | la cascada, y la justificación clínica de cada regla |
| [`decide.py`](decide.py) | las guardias, el parser del grado, la nota determinista, la validación |
| [`telemetry.py`](telemetry.py) | tokens, tiempo, memoria y herramientas, por papel |
| [`gc_entry.py`](gc_entry.py) | el adaptador de un caso para Grand Challenge |
| [`sampling.py`](sampling.py) | muestreo por papel (temperatura y tope de tokens) |
| [`experts/panel.py`](experts/panel.py) | carga de los cuatro artefactos, precálculo en lote, puntuación en vivo |
| [`experts/vocab.py`](experts/vocab.py) | el vocabulario compartido: variables, niveles y confianza, con los valores del caso |
| [`experts/*.py`](experts/) | cómo habla cada experto, con su bloque de variables |
| [`analysis/report.py`](analysis/report.py) | lectura y puntuación con el evaluador oficial |
| [`analysis/simulate.py`](analysis/simulate.py) | el protocolo sin LLM; la rejilla de parámetros |
| [`analysis/analisis_final.ipynb`](analysis/analisis_final.ipynb) | **el cuaderno de verificación**: mide |
| [`analysis/anatomia_del_agente.ipynb`](analysis/anatomia_del_agente.ipynb) | **el cuaderno de anatomía**: qué entra, qué sale, los prompts que vio el modelo, el diagrama, y las variables de la sala |
| [`runs/launch.sh`](runs/launch.sh) | lanza una corrida en tmux |
| [`runs/judge/`](runs/judge) | la puntuación con el juez encendido: log y JSON por corrida |
| `dev/score_with_judge.py` | puntúa con el evaluador oficial **y el juez**; corre con `.venv-eval` |

El paquete es autocontenido y borrable. Importa de `chimera_agent_baseline` sin
modificarlo y de `delete_expert_modelate/chimera_experts` para deserializar los
artefactos de los expertos.

---

## 11. Bibliografía

**Arquitectura de pizarra**
- Erman, Hayes-Roth, Lesser, Reddy (1980). *The Hearsay-II Speech-Understanding System.* ACM Computing Surveys 12(2).
- Hayes-Roth (1985). *A blackboard architecture for control.* Artificial Intelligence 26(3).
- Nii (1986). *Blackboard Systems.* AI Magazine 7(2).

**Razonamiento basado en casos**
- Aamodt, Plaza (1994). *Case-Based Reasoning: Foundational Issues, Methodological Variations, and System Approaches.* AI Communications 7(1).
- Kolodner (1993). *Case-Based Reasoning.* Morgan Kaufmann.

**Colaboración entre LLM, y sus límites**
- Du, Li, Torralba, Tenenbaum, Mordatch (2023). *Improving Factuality and Reasoning in Language Models through Multiagent Debate.* arXiv:2305.14325.
- Chen, Saha, Bansal (2023). *ReConcile: Round-Table Conference Improves Reasoning via Consensus among Diverse LLMs.* arXiv:2309.13007.
- Tang et al. (2023). *MedAgents: LLMs as Collaborators for Zero-shot Medical Reasoning.* arXiv:2311.10537.
- Kim et al. (2024). *MDAgents: An Adaptive Collaboration of LLMs for Medical Decision-Making.* NeurIPS 2024.
- Wang et al. (2024). *Rethinking the Bounds of LLM Reasoning: Are Multi-Agent Discussions the Key?* ACL 2024.
- Huang et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR 2024.
- Turpin, Michael, Perez, Bowman (2023). *Language Models Don't Always Say What They Think.* NeurIPS 2023.

**Combinar expertos por fiabilidad medida**
- Dietterich (2000). *Ensemble Methods in Machine Learning.* MCS 2000.
- Kuncheva (2004). *Combining Pattern Classifiers.* Wiley.
- Chow (1970). *On Optimum Recognition Error and Reject Tradeoff.* IEEE Trans. Inf. Theory.

**Incertidumbre, calibración e imputación**
- Breiman (2001). *Random Forests.* Machine Learning 45(1). · Geurts, Ernst, Wehenkel (2006). *Extremely randomized trees.* Machine Learning 63(1).
- Lakshminarayanan, Pritzel, Blundell (2017). *Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles.* NeurIPS 2017.
- Depeweg, Hernández-Lobato, Doshi-Velez, Udluft (2018). *Decomposition of Uncertainty in Bayesian Deep Learning.* ICML 2018.
- Rubin (1987). *Multiple Imputation for Nonresponse in Surveys.* Wiley. · van Buuren, Groothuis-Oudshoorn (2011). *mice.* J Stat Softw 45(3).
- Guo, Pleiss, Sun, Weinberger (2017). *On Calibration of Modern Neural Networks.* ICML 2017.
- Barber, Candès, Ramdas, Tibshirani (2021). *Predictive inference with the jackknife+.* Annals of Statistics 49(1).
- Varma, Simon (2006). *Bias in error estimation when using cross-validation for model selection.* BMC Bioinformatics 7:91.

**Recuperación y guía clínica**
- Lewis et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020.
- EAU-EANM-ESTRO-ESUR-ISUP-SIOG Guidelines on Prostate Cancer (2024): biopsia dirigida sobre PI-RADS ≥ 3; re-biopsia tras negativa sobre PI-RADS 4-5; biopsia confirmatoria en vigilancia activa; PSA > 20 ng/mL como alto riesgo.

> Las referencias van por autor, año, título y sede. Si van a un artículo,
> conviene verificar páginas y DOI en la fuente original.
