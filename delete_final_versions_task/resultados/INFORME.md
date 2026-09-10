# Las tres juntas, corridas enteras y puntuadas con el evaluador oficial

Corrida del 10 de septiembre de 2026, commit `b180202`. Los **238 casos
etiquetados** de la base —91 de la tarea 1, 72 de la 2 y 75 de la 3— pasados por
las tres juntas y puntuados dos veces con el `evaluate.py` de los organizadores:
una con el juez de razonamiento apagado (determinista, comparable entre corridas)
y otra con el juez encendido, que es como puntúa Grand Challenge.

Los casos sin etiqueta no se corren aquí: el evaluador no puede puntuarlos, y una
corrida que no se puede puntuar no responde a ninguna de las preguntas de este
informe. La cobertura de los 423 casos completos está verificada en las corridas
de entrega de cada tarea (`task_N/runs/`).

| | |
|---|---|
| Cómo se reproduce | `./run_all.sh` — cinco fases en serie, idempotentes |
| Puntuación | `evaluate.py` de `DIAGNijmegen/CHIMERA-agent`, importado, no reimplementado |
| Actas | `task_N/boards/` y `task_3/output/task3/*/acta.md`; índice en [PIZARRAS.md](PIZARRAS.md) |
| Datos crudos | [`scores/`](scores/) — agregados del evaluador y análisis derivado |

---

## 1. Resultado

| Tarea | Casos | Puerta de decisión | `ranking_score` sin juez | `ranking_score` con juez | `mean_rationale_score` | Baseline |
|---|---:|---:|---:|---:|---:|---:|
| **1 · biopsia** | 91 | 91,2% | 0,8390 | 0,8256 | 0,6783 | 0,6428 |
| **2 · tratamiento** | 72 | 90,3% | 0,7784 | 0,8150 | 0,8431 | 0,4457 |
| **3 · recurrencia** | 75 | no aplica | 0,7372 | 0,7372 | 0,3987 | 0,6636 |
| **OVERALL** (2:2:1) | | | **0,7944** | **0,8037** | | 0,5651 |

**Cómo se compone el número** (leído de `evaluate.py`, no supuesto):

```
T1, T2:   ranking_score = (mean_case_score + F1) / 2
          F1 = f1(yes) en T1 · f1 ponderado por soporte en T2
T3:       ranking_score = c_index          ← y nada más
```

De ahí salen tres consecuencias que conviene tener presentes al leer la tabla:

1. **La mitad del ranking de T1 y T2 es la decisión pura.** El F1 no depende del
   juez ni de la prosa: es determinista. Por eso las dos columnas de T1 comparten
   puerta y difieren sólo en `mean_case_score`.
2. **`mean_case_score` lleva dentro una puerta multiplicativa.** Si la decisión es
   incorrecta el caso vale cero por muy bien escrita que esté la nota; sólo los
   casos que la pasan reciben los componentes restantes.
3. **El ranking de T3 no puede moverlo el juez**, y en efecto sale idéntico en las
   dos columnas. Su nota clínica sólo afecta a `mean_case_score`, que se publica al
   lado porque es donde el juez sí entra.

Apagar el juez no pone su peso a cero: lo **redistribuye** entre los otros
componentes. Las dos columnas no son comparables entre sí.

### Los componentes, y lo que cambia al encender el juez

| Componente | Peso sin juez | Peso con juez | T1 | T2 | T3 |
|---|---:|---:|---:|---:|---:|
| juicio de la nota | **0 — no se juzga** | 0,200 | 0,6783 | 0,8431 | 0,3987 |
| pesos de variables | 0,275 | 0,250 | 0,8506 | 0,8382 | — |
| confianza declarada | 0,225 | 0,200 | 0,7651 | 0,9000 | — |
| factores important/decisive | 0,175 | 0,150 | 0,7723 | 0,6732 | — |
| uso de herramientas | 0,150 | 0,150 | 0,8685 | 1,0000 | — |
| anclaje a secciones | 0,175 | 0,050 | 0,8431 | 0,2171 | — |

### Esta corrida reproduce la de entrega a diez decimales

No es una coincidencia aproximada. Los tres rankings sin juez, recalculados hoy
desde cero sobre una corrida nueva de los 238 casos, coinciden **dígito a dígito**
con los que quedaron registrados en las corridas de entrega:

| Tarea | Esta corrida | Registrado en `task_N/runs/` |
|---|---|---|
| 1 | `0,8390295552762397` | `0,8390295553` |
| 2 | `0,7783863062229879` | `0,7783863062` |
| 3 | `0,7371681415929203` | `0,7371681415929203` |
| OVERALL | `0,7943999729` | `0,7943999729` |

Y no sólo el agregado: coinciden también los seis componentes, la puerta de
decisión caso por caso, y el reparto de casos entre los peldaños del protocolo
(52 / 27 / 12 en T1). **Eso es el diseño funcionando, no suerte.** Si el modelo de
lenguaje votara, dos corridas no darían el mismo número: un modelo de 2B a
temperatura 0 sigue siendo sensible al orden de la caché y al lote. Aquí la
decisión la toma código determinista alimentado por lo que la sala recuperó, y lo
único que el modelo aporta —la prosa— no entra en el ranking cuando el juez está
apagado. La reproducibilidad es la consecuencia medible de haberle quitado el voto.

La columna con juez es la excepción, y por la misma razón: es lo único que depende
de la opinión de un modelo sobre un texto.

El `section_grounding` de T2 es bajo **a propósito**: entrega `reveal_sequence`
vacío en lugar de silenciar casillas del formulario. Los documentos sí se abren;
el campo vacío no representa ausencia de lectura. Con el juez encendido ese
componente pasa de pesar 0,175 a 0,05, y es parte de por qué T2 sube al encenderlo.

---

## 2. Cómo se aborda cada tarea

Las tres comparten una idea y no comparten nada más: **una pizarra**, donde cada
participante habla en un turno numerado y lo que dice queda escrito literalmente;
**un protocolo en código**, que toma la decisión por reglas cuyo acierto está
medido; y **un presidente**, el modelo de lenguaje, que escribe la nota clínica
pero no vota. Los votos, los umbrales y las políticas de confianza no se trasladan
de una tarea a otra: cada una midió las suyas.

### 2.1 Tarea 1 — ¿biopsiar a este paciente?

**El problema.** De los 91 casos etiquetados, 49 tienen biopsia previa positiva, y
ese cubo es donde se gana o se pierde la tarea: ninguna variable del panel decide
por sí sola, kNN acierta 0,43–0,47 y —medido tres veces— **los votos del modelo de
lenguaje están en el azar** (el registrador 0,47, el verificador 0,49). Lo que sí
hay es el propio urólogo, que en su texto libre explica el criterio con todas las
letras. Leer esos 49 textos es de donde salen las reglas.

**Quince intervenciones.** Un ordenanza lee el expediente; cuatro expertos
entrenados abren la sesión (Extra-Trees sobre el panel, criterio de cohorte,
biblioteca de precedentes y un modelo de traza que predice *qué documentos abre el
urólogo*, y que con eso **fija el plan**); un especialista en la guía EAU critica
con cita literal; un moderador formula una pregunta por documento; el registrador
abre exactamente el plan; y sólo entonces hablan los expertos que leen documentos.
La numeración es global: si el verificador reabre, la segunda vuelta son las
intervenciones 15, 16 y 17, no «ronda 2». Eso hace que citar un turno identifique
un momento único y el acta sea una traza, no un adorno.

**Quién decide.** Una cascada de tres peldaños, ordenada por acierto medido:
criterio de cohorte → grado documentado en las notas previas → voto ponderado de
los expertos con umbral 0,45. El peldaño 2 es el punto donde la deliberación del
LLM sí decide el caso: el grado vive en las notas y sólo llega ahí si el
registrador las abre. Y como un modelo de 2B lo copia mal, el grado se extrae con
expresión regular del **texto crudo que devolvió la herramienta**, no del resumen.

**Tres guardias, las tres nacidas de un fallo medido.** El presidente no ve el acta
ni la lista de participantes —recibe un parte clínico construido en código—, porque
cuando la veía, 187 de 195 notas nombraban un participante o un mecanismo del
sistema, y el juez penaliza exactamente ahí. El registrador inventaba el grado de
la biopsia previa en el 5-7 % de los informes, entrecomillado como si lo citara: se
comprueba en tres capas. Y la biblioteca de precedentes tiene apagado el
`self-match`, porque encontrarse a sí misma sube la nota local a 0,9469 y en el test
no puede ocurrir nunca.

**En esta corrida:** 91/91 casos completados, 91 con esquema válido, 13 con grado documentado hallado en las notas, 0 reaperturas del verificador y 0 auto-coincidencias de la biblioteca.

### 2.2 Tarea 2 — ¿qué tratamiento?

**El problema es el contrario.** Aquí el grado ya viene estructurado y la etiqueta
es casi función de `bx_isup`: la regla ISUP sola acierta 62/72 = 0,861, y el techo
de consistencia del perfil es 0,931. Queda poquísimo margen en la decisión, así que
el trabajo de la sesión está en el **82,5 % del `case_score` que no es decisión**:
justificar, calibrar y anclar. Eso no elimina la puerta multiplicativa — una nota
perfecta sobre una decisión errónea sigue valiendo cero.

**Cinco expertos, y el hallazgo incómodo.** Los expertos 1, 2 y 4 emiten las mismas
72 decisiones, una por una — no «acierto parecido»: **idénticas**. Sentarlos como
tres votos independientes sería una ficción, así que se sientan como *réplicas
confirmatorias* y el portavoz se elige por fiabilidad medida, no por votación.
Combinarlos, además, empeora: voto blando y producto de expertos dan 0,7639.

**El experto que rescata.** El experto 3 (aptitud) es el peor de los cinco —0,6389—
y sólo habla cuando los otros cuatro están en `discuss`. En esta corrida es portavoz
en **3 casos y acierta 3**. Los tres son excepciones a la regla ISUP:
es el mecanismo de la escalera funcionando. Pero son tres casos y dentro de
muestra: ilustra el diseño, no demuestra que generalice.

**En esta corrida:** 72/72 casos, 72 con esquema válido, 0 reaperturas, 3 notas de respaldo.

### 2.3 Tarea 3 — ¿cuándo recurre?

**Otro problema distinto.** No hay decisión que puntuar ni formulario: hay que dar
`event` y `months_to_recurrence`, y el ranking es sólo el c-index. En el baseline
esta tarea **tumbaba la cola entera**: dos casos resistieron ocho reintentos
devolviendo «Cannot be determined», porque se le pedía al modelo una fecha de
recurrencia sin explicarle que una observación censurada es seguimiento sin evento
observado. Repetir el encargo no resuelve una contradicción semántica.

**El número lo produce un experto, no el LLM.** CAPRA-S fija el orden del riesgo y
EXPERT-HORIZON lo convierte en meses con un mapa `a·exp(-0,1·CAPRA-S)`
estrictamente decreciente. Que sea estrictamente decreciente no es un detalle: la
concordancia usa la inversión riesgo↔tiempo, así que optimizar la magnitud del
horizonte **no puede dañar el orden**, y hay un test que lo fija. El presidente
recibe el horizonte ya calculado y sólo escribe su explicación; `decide.finish`
añade la semántica de la censura. Eso elimina por construcción el aborto por
negativa del modelo.

**Un techo que no es nuestro.** El `mean_rationale_score` de T3 está limitado por
cómo el evaluador oficial construye el contexto del juez: `input_ctx` recibe sólo
`clinical_data` —los documentos enmascarados— y **nunca** `structured-prompt.json`,
que es donde vive el `psa`. El prompt de la tarea pide citar el PSA preoperatorio;
cuando el presidente lo cita correctamente, el juez lo marca como alucinación
porque no tiene el campo delante. Pasa en 4 de los 5 casos peor juzgados. No se
arregla desde nuestro lado, y se publica como límite medido en vez de esconderlo.

**En esta corrida:** 75/75 casos, event=1 en 12, mediana 62.8 meses (rango 28.2–93.7), 5 notas de respaldo.

---

## 3. Lo que enseñan las pizarras

Las actas no son un registro decorativo: son la única forma de responder a *por qué*
un caso salió como salió. El evaluador da un número por caso; el acta dice qué
peldaño lo reclamó, con qué evidencia y quién la puso sobre la mesa.

| Tarea | Actas | Intervenciones (media) | Rango | Reaperturas | Turnos registrados |
|---|---:|---:|---:|---:|---:|
| 1 | 91 | 14,00 | 14–14 | 0 | 1274 |
| 2 | 72 | 12,04 | 12–13 | 0 | 867 |
| 3 | 75 | 11,00 | 11–11 | 0 | 825 |

### Dónde se equivoca cada mecanismo

El agregado oficial no puede decir esto, porque no conoce el protocolo. Repartiendo
los aciertos por el peldaño que decidió cada caso:

**Tarea 1.** El protocolo de T1 es una cascada: cada caso lo reclama el primer peldaño que aplica, y el acta escribe cuál fue.

| Peldaño del protocolo | Casos | Aciertos | Acierto |
|---|---:|---:|---:|
| 1 · criterio de cohorte | 52 | 49 | 0,9423 |
| 3 · voto ponderado | 27 | 24 | 0,8889 |
| 2 · grado documentado | 12 | 10 | 0,8333 |

**Tarea 2.** En T2 la regla es única —fiabilidad medida— y lo que cambia es qué experto acaba hablando por la sala.

| Portavoz elegido | Casos | Aciertos | Acierto |
|---|---:|---:|---:|
| expert_one | 68 | 61 | 0,8971 |
| expert_three | 3 | 3 | 1,0000 |
| expert_five | 1 | 1 | 1,0000 |

### Las guardias, contadas

| Tarea | Esquema válido | Nota de respaldo | Formulario de respaldo | Prosa retada | Reaperturas |
|---|---:|---:|---:|---:|---:|
| 1 | 91/91 | 1 | 1 | 4 | 0 |
| 2 | 72/72 | 3 | 3 | 0 | 0 |
| 3 | 75/75 | 5 | no aplica | no aplica | no aplica |

El índice completo, ordenado para ir primero a las actas que más enseñan —las de
los casos que el protocolo falló— está en [PIZARRAS.md](PIZARRAS.md).

---

## 4. Coste

| Tarea | s/caso (media) | s/caso (mediana) | Total | Tokens de entrada/caso | Llamadas LLM/caso |
|---|---:|---:|---:|---:|---:|
| 1 | 26,2 | 25,1 | 39,7 min | 44857 | 7,2 |
| 2 | 38,0 | 37,3 | 45,6 min | 35054 | 12,0 |
| 3 | 1,6 | 1,3 | 2,0 min | — | — |

La GPU es de uso exclusivo: T1 y T2 levantan vLLM con los pesos locales y ocupan
~31 GB de los 32 de la tarjeta; T3 y el juez hablan con Ollama. No caben a la vez,
así que las cinco fases van estrictamente en serie.

---

## 5. Qué NO demuestra esta corrida

- **Los expertos de T1 y T2 se entrenaron sobre esta misma cohorte etiquetada.** Que
  la corrida reproduzca la simulación verifica la ejecución; no demuestra
  generalización. T3 reproduce predicciones out-of-fold, que es más honesto, pero
  tampoco es validación externa.
- **El juez no es determinista, ni siquiera sin recargar el modelo.** Dos pases
  consecutivos de T2 dieron 0,8031 y 0,8150 sin tocar nada. El número con juez es
  una medición puntual; comparar dos corridas por esa columna no es válido.
- **Ninguna de estas cifras es el test.** Son los casos etiquetados, que es lo único
  que se puede puntuar en local.
- El techo honesto de T1 medido con expertos out-of-fold es 0,7607, frente al 0,8390
  histórico de la corrida desplegada. La diferencia es exactamente el efecto de
  haber ajustado los expertos sobre la cohorte.

---

## 6. Mapa

```
resultados/
├── run_all.sh          las cinco fases, en serie e idempotentes
├── analizar.py         destila las corridas y las notas a scores/analisis.json
├── pizarras.py         construye el índice de actas
├── informe.py          escribe este documento desde los JSON
├── INFORME.md          esto
├── PIZARRAS.md         índice de las 238 actas, las fallidas primero
├── scores/
│   ├── no_judge.json   agregados del evaluador oficial, juez apagado
│   ├── judge_task*.json  ídem con el juez encendido, por tarea
│   └── analisis.json   mecanismo, actas y coste por tarea
├── task_1/  boards/ · output/task1/ · summary.jsonl · telemetry.jsonl
├── task_2/  boards/ · output/task2/ · summary.jsonl · telemetry.jsonl
└── task_3/  output/task3/<caso>/acta.md · summary.jsonl · telemetry.jsonl
```

