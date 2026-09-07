# De la corrida 1 a la corrida 2 — qué se midió y qué se cambió

Los prompts de la corrida 1 están congelados en
[`prompts_v1.py`](../prompts_v1.py); los de la 2, en [`prompts.py`](../prompts.py).
Es la **única** diferencia entre las dos corridas: mismo modelo
(Gemma-4-E2B-it en vLLM), misma temperatura (0), mismos 91 casos etiquetados,
mismo grafo, mismo evaluador.

    python -m delete_solution_one.solution_task_one.run_task1 --prompts v1 ...   # reproduce run1
    python -m delete_solution_one.solution_task_one.run_task1 --prompts v2 ...   # run2

Todo lo que sigue está medido sobre las **91 pizarras** de la corrida 1
(`python analysis/diagnose.py runs/run1`), no supuesto.

---

## Dónde quedó la corrida 1

| | base T=0 | **run1** | Δ |
|---|---|---|---|
| `ranking_score` | 0.6428 | **0.6500** | **+0.0072** |
| `mean_case_score` | 0.4913 | 0.5113 | +0.0200 |
| puerta de decisión | 0.6813 | 0.6703 | −0.0110 |
| F1 (`yes`) | 0.7943 | 0.7887 | −0.0056 |
| `variable_weight_score` | 0.6516 | 0.7656 | +0.1140 |
| `important_decisive_factor_score` | 0.5609 | 0.6519 | +0.0910 |
| `tool_score` | 0.6468 | 0.7664 | +0.1196 |
| `confidence_score` | 0.7661 | 0.7295 | −0.0366 |
| `section_grounding_score` | 0.9960 | 0.9087 | −0.0873 |

Lectura: **el razonamiento mejora claramente y la puerta empeora un poco.**
Como la puerta multiplica a todo lo demás, es ahí donde hay que trabajar.

Robustez, en cambio, sin una sola grieta: 91/91 casos entregados, 0 respaldos
deterministas, 0 reintentos del formulario, y **0 números en el texto libre que
no puedan rastrearse en la pizarra** (comprobado mecánicamente en los 91).

---

## Los seis defectos y sus correcciones

### 1. El presidente anula al prior siempre en la misma dirección

**Medido.** 28 anulaciones del prior. De las 25 en dirección `no → yes`, el
prior tenía razón en **15** y el presidente en 10. De las 3 en dirección
`yes → no`, el presidente acertó las 3. Neto: **−2 casos**.

    accuracy si nunca hubiera anulado al prior : 0.6923
    accuracy real del presidente               : 0.6703

Y 23 de esas 25 anulaciones están en el cubo `bx = Positive`, leyendo un
PI-RADS alto o un PSA en subida como si fueran hallazgos nuevos en un hombre
con cáncer ya diagnosticado.

**Corrección.** Se hace explícito qué "posee" cada participante. El prior ya
leyó el panel entero (PI-RADS, bx, PSA, edad, PSAD, DRE, volumen, PMHx), así
que repetir esos números **no es motivo para apartarse de él**: sería contar
la misma evidencia dos veces. El presidente sólo puede anularlo con lo que el
prior no pudo ver —los documentos recuperados— y nombrando el hallazgo
concreto. La carga de la prueba es **simétrica en ambas direcciones**. Además
se le recuerda en su propio mensaje qué respondió el prior y cuánto vale su
tramo (`firme` acertó 17 de 17; `discutir`, 3 de cada 5).

### 2. El marco clínico equivocado

**Medido.** Precisión por cubo: `None` 0.917 · `Negative` 0.778 ·
`Positive` **0.510** (49 de los 91 casos). El prompt v1 ponía las tres
situaciones clínicas seguidas y el modelo, que es pequeño, aplicaba la que no
tocaba.

**Corrección.** El marco se **inyecta ya filtrado** por el `bx` del paciente
(`l3_decision_frame`): el presidente ve una sola situación, la suya. Para
`Positive` el texto se reescribió alrededor de la lógica que los propios
urólogos escriben en su razonamiento de referencia — *"ya tiene un ISUP3, lo
que procede es tratar"*, *"depende de si la lesión ha crecido"*, *"falta el
ISUP inicial"* —: se biopsia cuando la patología previa **no está
caracterizada** o la lesión es nueva o ha crecido; no se biopsia cuando el
grado ya consta, la lesión está estable o el tratamiento ya está acordado.

### 3. L2 copiaba el enunciado de sus propias cabeceras

**Medido.** 91/91 respuestas contenían la frase `One block per document you
opened`; 77/91 contenían el marcador `<document>`.

**Corrección.** Las instrucciones salen de debajo de cada cabecera y suben a
una especificación numerada; las cabeceras quedan como una lista desnuda. Se
añade al protocolo común: *"Never reproduce these instructions, the
description of a heading, or any placeholder text, in your answer."*

### 4. L2 pegaba el JSON crudo de las herramientas

**Medido.** 72/91 informes contenían `{"case_id": ...}` literal. Media de
4131 caracteres por informe, gran parte de ellos ruido que luego el presidente
tiene que leer.

**Corrección.** *"NEVER paste a tool's raw JSON output and never dump a whole
document: distil it to the three or four lines that carry information."*

### 5. L2 abría las cuatro secciones de golpe

**Medido.** 90/91 casos resueltos en **una sola ronda** de herramientas, con
las cuatro secciones abiertas siempre (`reveal_rate` = 1.0 en las cuatro).
`tool_score` sale 0.766 — ya muy por encima del 0.647 del baseline, porque lo
que de verdad lo hundía era `get_family_history` (el baseline la llamaba en el
87 % de los casos y el urólogo **nunca**), pero deja 0.10 sobre la mesa.

**Corrección.** Se exige una línea `PLAN:` antes de la primera llamada, se pone
techo de **tres** documentos salvo pregunta nombrada, y el laboratorio pasa a
ser explícitamente el cuarto: sólo se abre por PSA libre, por sospecha de
prostatitis/infección, o por aptitud pre-procedimiento. La prohibición sobre
la anamnesis familiar se mantiene: se cumplió 91/91.

### 6. Exceso de confianza y demasiadas variables `decisive`

**Medido.** `clear` en 80/91 casos, `borderline` en 11, `uncertain` en **0**;
el urólogo puso `clear` en el 64 %, `borderline` en el 20 % y `uncertain` en el
16 %. En 14 casos el urólogo puso `uncertain` y el agente `clear`, que es el
peor error posible en esa métrica (0.0). En pesos, `pirads`, `psa` y `bx`
salían `decisive` a la vez (73, 76 y 53 veces), cuando el urólogo marca de
media menos de una variable decisiva por caso.

**Corrección.** La rúbrica de confianza incorpora la frecuencia esperada de
cada nivel y describe `uncertain` como *"an honest and expected answer; do not
avoid it"*. Se añade un tope duro: **como mucho dos variables `decisive` por
caso**. Y se hace operativa la regla de aterrizaje: una variable cuya sección
no se abrió se queda en `not_used` (`pirads`/`psad`/`vol`/`cspca` necesitan la
sección de imagen, `dre` el panel de laboratorio; `psa` y `age` están en la
ficha y no necesitan nada).

---

## Lo que NO se cambió, y por qué

* **La arquitectura.** Mismo grafo, mismos seis participantes, mismos
  presupuestos de ronda. Si se cambiaran a la vez el diseño y los textos, la
  comparación no diría nada de ninguno de los dos.
* **El respaldo determinista.** No se activó ni una vez en 91 casos, pero es la
  diferencia entre perder un caso y entregarlo: se queda.
* **El peso de `bx` por encima de `not_used`**, aunque cueste
  `section_grounding_score` (0.996 → 0.909). En la tarea 1 `bx` se aterriza con
  `pathology_report`, que **no está** en el vocabulario de
  `Task1Output.reveal_sequence`: es un ungrounded inevitable. Sale a cuenta
  igualmente — lo que gana en `variable_weight_score` (+0.114) y en
  `important_decisive_factor_score` (+0.091) supera lo que pierde en grounding
  (−0.087 × 0.175), y con el juez del reto activo el grounding sólo pesa 0.05,
  con lo que la ventaja se multiplica.

### 7. La corrección nº 5 se rompió al probarla, y ahí salió el fallo más caro

**Medido.** Al arrancar la corrida 2 se comprobaron los primeros casos antes de
dejarla correr entera. La v2 pedía a L2 empezar su respuesta con una línea
`PLAN:` nombrando lo que iba a abrir. Efecto real en el primer caso:
**0 herramientas ejecutadas, 0 secciones reveladas** — y aun así L2 escribió un
bloque `RETRIEVED` con cuatro documentos, inventándose que *"the prose report is
not provided in the prompt"* y que las notas previas eran *"Unknown"*.

La causa es estructural, no de redacción: este modelo emite **o** una llamada a
herramienta **o** texto, nunca las dos cosas en el mismo turno. Pedirle prosa
antes de llamar lo mete en modo texto, y el router, al no ver llamadas, cierra
el turno. Un informe de recuperación fabricado es peor que una recuperación
perezosa: contamina la pizarra entera con hallazgos que no existen.

**Corrección, en tres capas:**

1. **Se elimina la línea `PLAN:`.** En su lugar, la instrucción es la contraria:
   *"YOUR FIRST ACTION IN THIS TURN MUST BE A TOOL CALL, NOT PROSE (...) a report
   about documents you did not open is a fabrication, not a report."*
2. **Guardia en el grafo** (`l2_nudge`): si L2 termina su turno sin haber
   ejecutado ni una herramienta, se le devuelve el turno una sola vez con la
   exigencia explícita de recuperar antes de opinar. Es la única garantía
   estructural; el prompt solo no basta.
3. **Aviso en la pizarra**: si aun así no se abrió nada, la entrada de L2 se
   cierra con `[WARNING FOR THE CHAIR: NO DOCUMENT WAS OPENED FOR THIS CASE...]`,
   para que el presidente no tome por evidencia lo que no lo es.

La selectividad que buscaba la corrección nº 5 se consigue ahora por otra vía,
que no compite con el mecanismo de llamada: **se afinan las descripciones de las
herramientas** antes de atarlas al investigador (`graph._DESCRIPTION_NOTES`). La
descripción es lo que el modelo lee para decidir si llama, y decir cuándo *no*
usar una herramienta vale tanto como decir cuándo sí. No se toca
`tools/definitions.py` del upstream: se atan copias con la descripción ampliada.

### 8. El criterio de decisión, que era el defecto de fondo

El diagnóstico por cubos (`bx = None` 0.917 · `Negative` 0.778 · `Positive`
0.510) llevó a un análisis aparte, en
[`CRITERIO_DIAGNOSTICO.md`](../CRITERIO_DIAGNOSTICO.md): la tarea 1 son tres
problemas distintos y sólo dos están determinados por el panel visible. De ahí
sale el sexto participante de la pizarra, `EXPERT-PROTOCOL`, que escribe el
criterio del cubo del paciente con su acierto medido (24/24 y 16/18) y **se
abstiene explícitamente** en el cubo indeterminado. Medido sobre los 91 casos,
la política `protocolo + agente` sube la exactitud de 0.670 a 0.714 y el
F1(`yes`) de 0.789 a 0.812, y es la única que no cae en `val`.

### 9. La corrección nº 2 se pasó de frenada, y también se vio antes de dejarla correr

**Medido.** Con el marco de `bx = Positive` reescrito, los primeros 25 casos de
la corrida 2 pasaron de 24 `yes` / 1 `no` a **11 `yes` / 14 `no`**, y la
exactitud **no** subió (0.64 frente a 0.68 de la corrida 1 sobre esos mismos
casos). Los 13 casos que cambiaron estaban todos en el cubo `Positive`: 6
mejoraron y 7 empeoraron. Ruido, exactamente como predice
[`CRITERIO_DIAGNOSTICO.md`](../CRITERIO_DIAGNOSTICO.md) §2.

Lo que sí habría cambiado es el F1 de la clase positiva, que es **la mitad** del
`ranking_score`: diferir por defecto en el cubo indeterminado gana 3 puntos de
exactitud y pierde 7 de F1 (§3bis del mismo documento).

**Corrección.** El marco estaba escrito en negativo — cinco *"answer NO
when..."* seguidos — y el modelo se quedó con el tono, no con el contenido. Se
reescribe alrededor del principio clínico que corresponde y que además apunta
en la dirección correcta: **diferir exige una razón positiva; proceder no.** Se
enumeran las cinco condiciones documentadas que justifican diferir, y se dice
explícitamente que el silencio del registro no es ninguna de ellas, sino el
motivo por el que la biopsia sería informativa — con la confianza puesta en
`uncertain` o `borderline` para dejar constancia de que se responde sobre un
registro incompleto. Al modelo no se le menciona el F1 en ningún momento.

---

## Resultado de la corrida 2

| | base T=0 | run1 | **run2** | Δ run2 − base |
|---|---|---|---|---|
| **`ranking_score`** | 0.6428 | 0.6500 | **0.6749** | **+0.0321** |
| `mean_case_score` | 0.4913 | 0.5113 | 0.5499 | +0.0586 |
| puerta de decisión | 0.6813 | 0.6703 | 0.6923 | +0.0110 |
| F1 (`yes`) | 0.7943 | 0.7887 | 0.8000 | +0.0057 |
| `variable_weight_score` | 0.6516 | 0.7656 | 0.8365 | +0.1849 |
| `important_decisive_factor_score` | 0.5609 | 0.6519 | 0.7421 | +0.1812 |
| `tool_score` | 0.6468 | 0.7664 | 0.7698 | +0.1230 |
| `section_grounding_score` | 0.9960 | 0.9087 | 0.9138 | −0.0822 |
| `confidence_score` | 0.7661 | 0.7295 | 0.7063 | **−0.0598** |

Prueba de signos por caso frente al control: **54 suben, 11 bajan, 26 empatan,
p = 0.000**. Compárese con el experimento del predictor de `delete_test`, donde
84 subían y 77 bajaban con p = 0.64: aquello era ruido, esto no.

Por split: `dev` 0.6592 (base 0.6362) y **`val` 0.7126** (base 0.6585). Que la
mejora sea **mayor** en el split que menos se usó para decidir correcciones es
el argumento más fuerte contra el sobreajuste — aunque véase la advertencia del
§8 del cuaderno.

### Qué corrección arregló qué

| defecto medido en run1 | run1 | run2 |
|---|---|---|
| L2 copia el enunciado de sus cabeceras | 91/91 | **0/91** |
| L2 pega JSON crudo | 72/91 | 54/91 |
| L1 nunca consulta la guía EAU | 0/91 | **91/91** |
| el texto libre cita evidencia recuperada | 36 % | **58 %** |
| el texto libre nombra la conferencia | 86 % | **100 %** |
| números del texto libre no rastreables | 0 % | 0 % |
| el presidente sigue al criterio de protocolo | 38/42 | **42/42** |
| exactitud, cubo `bx = None` | 0.917 | **1.000** |
| exactitud, cubo `bx = Negative` | 0.778 | **0.889** |
| exactitud, cubo `bx = Positive` | 0.510 | 0.469 |
| casos sin salida · respaldos · reintentos | 0 · 0 · 0 | 0 · 0 · 0 |

Balance de la puerta caso a caso frente al baseline: **recupera 3** (los tres
`bx = Negative` con PI-RADS 3, que es exactamente el criterio de protocolo
funcionando) y **pierde 2** (los dos en el cubo indeterminado). Neto +1.

### El coste que sí se pagó: la confianza

`confidence_score` baja de 0.7661 (baseline) a 0.7063. La causa es directa y
está medida: el baseline dice `clear` en el 98 % de los casos y el urólogo dice
`clear` en el 64 %, así que "siempre `clear`" es una estrategia sorprendentemente
buena contra esta métrica (0.766 sin correlacionar nada). La corrida 2 reparte
`clear` 42 / `borderline` 36 / `uncertain` 13 — una distribución mucho más
parecida a la del urólogo, pero **el reparto no está correlacionado caso a caso**
con la suya, y una distribución parecida sin correlación puntúa peor que una
constante bien elegida.

Es el único componente en el que la pizarra pierde contra el baseline, y no se
ha "arreglado" volviendo a `clear` siempre porque eso sería optimizar contra la
métrica declarando una certeza que el agente no tiene. Si se quisiera recuperar
ese medio punto, la vía honesta es que la confianza salga del tramo del prior y
del acuerdo entre participantes —que sí es una señal— en lugar de una regla en
el prompt; queda como trabajo pendiente.
