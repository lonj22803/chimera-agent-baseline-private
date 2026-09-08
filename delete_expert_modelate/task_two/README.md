# Tarea 2 — recomendación de manejo tras la biopsia

Cinco expertos entrenados sobre los **72 casos con ground truth** de
`data/task2`, más el modelo del formulario de razonamiento. Cada uno entrega
una distribución sobre las cuatro conductas, no una etiqueta, y esa
distribución viene con su incertidumbre abierta en tres términos.

| Experto | Qué contesta | Qué lee | Papel en la junta |
|---|---|---|---|
| **1** — [grado y guía](expert_one/) | conducta + incertidumbre | bloque G | **ancla**: reproduce el razonamiento con el que se derivó la etiqueta |
| **2** — [patología digital](expert_two/) | conducta + riesgo de *upgrade* | G+H+J+K | segunda lectura del grado: ¿la biopsia se queda corta? |
| **3** — [aptitud](expert_three/) | ¿se beneficia del tratamiento? | A+I | el eje de `watchful_waiting`; **declara que no tiene evidencia** |
| **4** — [fusión](expert_four/) | conducta + incertidumbre | A+C+D+G+H+I+J+K | control: ¿alguna fuente añade algo cuando compite con todas? |
| **5** — [cascada de guía](expert_five/) | las tres preguntas encadenadas | GH / AGH / AGI | **descompone** el veredicto en partes rebatibles |
| — [formulario](reasoning_model/) | `confidence`, `variable_weights`, `reveal_sequence` | A+G+I | el 82.5 % del `case_score` que no es la decisión |

```bash
python expert_one/train_expert_one.py
python expert_two/train_expert_two.py
python expert_three/train_expert_three.py
python expert_four/train_expert_four.py
python expert_five/train_expert_five.py
python reasoning_model/train_reasoning_model.py
python run_experts.py --all --out ./outputs
```

---

## Los cinco expertos, medidos

Leave-one-out sobre los 72 casos etiquetados. La columna que ordena es el
acierto exacto, porque es lo único que el evaluador puntúa:

| experto | bloques | vars | modelo | acierto | Brier | ECE | Δ vs regla | p |
|---|---|---|---|---|---|---|---|---|
| **1** — grado | G | 28 | `random_forest` | **0.8611** | **0.2619** | **0.0425** | +0.0000 | 1.000 |
| **2** — patología | G+H+J+K | 86 | `extra_trees` | 0.8611 | 0.2733 | 0.0627 | +0.0000 | 1.000 |
| **4** — fusión | A+C+D+G+H+I+J+K | 184 | `extra_trees` | 0.8611 | 0.2652 | 0.0760 | +0.0000 | 1.000 |
| **5** — cascada | GH / AGH / AGI | 184 | `cascade[extra_trees]` | 0.8611 | 0.2842 | 0.0857 | +0.0000 | 1.000 |
| **3** — aptitud | A+I | 63 | `extra_trees_balanced` | 0.6389 | 0.4865 | 0.1069 | −0.2222 | **0.001** |
| *regla de guía* | — | 1 | — | *0.8611* | *0.2781* | *0.1152* | — | — |
| *prevalencia* | — | 0 | — | *0.4306* | *0.6741* | — | — | — |

Cuatro de los cinco producen **exactamente la misma matriz de confusión**, caso
a caso, que la regla de un solo predictor. Con 28, 86, 184 y 184 variables. El
quinto es significativamente peor.

Lo que sí separa a los cuatro empatados es la **calidad de la probabilidad**:

- el **Experto 1** es el mejor calibrado del panel (ECE 0.0425 frente a 0.1152
  de la regla, casi un tercio) y el único con la escalera de fiabilidad
  monótona (0.875 → 0.833 → 0.750);
- el **Experto 5** es el peor en Brier de los cuatro, y es el que hay que
  conservar igualmente, porque es el único que entrega el veredicto **abierto en
  sus tres pasos**.

### Tres de los cinco son el mismo experto

Comprobado caso a caso sobre las probabilidades leave-one-out guardadas:

| | exp. 1 | exp. 2 | exp. 3 | exp. 4 |
|---|---|---|---|---|
| **exp. 1** (28 vars) | — | **72/72** | 44/72 | **72/72** |
| **exp. 2** (86 vars) | **72/72** | — | 44/72 | **72/72** |
| **exp. 3** (63 vars) | 44/72 | 44/72 | — | 44/72 |
| **exp. 4** (184 vars) | **72/72** | **72/72** | 44/72 | — |

Los Expertos 1, 2 y 4 no coinciden «en acierto» ni «en matriz de confusión»:
emiten **las mismas 72 decisiones**, una por una. Leer el informe de patología,
las preparaciones de biopsia, la radiología, la serie de PSA y la comorbilidad
—156 variables adicionales— no cambia ni un caso respecto de leer el grado.

La consecuencia para la junta es directa y conviene no disimularla: **sentar a
esos tres como voces independientes sería una ficción.** Sus errores no están
correlacionados, son idénticos. Las únicas dos perspectivas realmente distintas
del panel son el eje de grado (Expertos 1/2/4, que discrepan en cero casos) y el
eje de aptitud (Experto 3, que discrepa en 28) — y el segundo es
significativamente peor. El Experto 5 no añade una tercera decisión sino una
**descomposición** de la primera.

Por eso el panel elige portavoz por fiabilidad medida en lugar de votar: una
votación entre tres copias y un experto malo tiene un resultado conocido de
antemano.

Sobre la monotonía de la escalera conviene no adornar nada: se cumple en uno de
cinco expertos, y con 72 casos repartidos en tres tramos esa ordenación es en sí
misma una cantidad ruidosa. Que el Experto 1 la cumpla no demuestra que su
incertidumbre esté mejor ordenada; su ECE, medido sobre los 72 casos y no sobre
tramos de 12, sí es un argumento.

---

## Lo que hay que saber antes de leer los números

### La etiqueta es casi una función de un solo campo

El ground truth se derivó retrospectivamente de la histopatología y del PSA
según EAU/NCCN. Eso se nota:

| `bx_isup` | AS | CS | AT | WW | n | conducta mayoritaria |
|---|---|---|---|---|---|---|
| 0 | 1 | **13** | 0 | 0 | 14 | `continued_surveillance` |
| 1 | **21** | 1 | 3 | 0 | 25 | `active_surveillance` |
| 2 | 3 | 0 | **13** | 2 | 18 | `active_treatment` |
| 3 | 0 | 0 | **5** | 0 | 5 | `active_treatment` |
| 4 | 0 | 0 | **8** | 0 | 8 | `active_treatment` |
| 5 | 0 | 0 | **2** | 0 | 2 | `active_treatment` |

Un mapa `ISUP → conducta`, reajustado en cada pliegue leave-one-out, acierta
**62 de 72 = 0.8611**. Ese es el suelo real de la tarea. La prevalencia de la
clase mayoritaria (0.4306) no lo es: nadie va a presentar eso.

### La métrica es una puerta, no una nota

El evaluador oficial puntúa la recomendación con **acierto exacto** y, si
falla, pone el `case_score` del caso a cero sin mirar el resto. No hay crédito
parcial entre `active_surveillance` y `continued_surveillance`. Por eso el
criterio de todos los experimentos es el acierto de las cuatro clases y no el
F1 macro.

### `watchful_waiting` tiene dos casos

Dos de 72. Ningún clasificador de cuatro salidas lo va a predecir nunca, y
predecirlo sería la decisión equivocada bajo la métrica. Lo que sí se puede
hacer —y es lo que hace el Experto 5— es **descomponer** la etiqueta para que
esa clase salga de una pregunta con 33 casos en vez de 2.

---

## Resultados principales

### Comparación de clasificadores

17 candidatos sobre los bloques A+G (64 variables), leave-one-out
(`train/artifacts/bakeoff_stage1_AG.csv`):

| modelo | acierto | IC 95 % | F1 macro | Brier | ECE |
|---|---|---|---|---|---|
| *regla de guía* | 0.8611 | [0.778, 0.944] | 0.661 | 0.2781 | 0.1152 |
| **extra_trees** | **0.8611** | [0.778, 0.944] | 0.661 | **0.2706** | **0.0851** |
| random_forest | 0.8472 | [0.750, 0.931] | 0.652 | 0.2732 | 0.1001 |
| extra_trees_balanced | 0.8472 | [0.750, 0.931] | 0.656 | 0.2760 | 0.0587 |
| logreg_l1 | 0.8194 | [0.722, 0.903] | 0.635 | 0.3050 | 0.0799 |
| lda | 0.8056 | [0.708, 0.889] | 0.629 | 0.3456 | 0.1797 |
| deep_ensemble_mlp | 0.7917 | [0.694, 0.889] | 0.615 | 0.3644 | 0.0909 |
| knn | 0.7639 | [0.653, 0.861] | 0.598 | 0.3601 | 0.1423 |
| gaussian_nb | 0.4861 | [0.375, 0.611] | 0.370 | 1.0232 | 0.5123 |
| *prevalencia* | 0.4306 | [0.319, 0.542] | 0.151 | 0.6741 | — |

**Ningún modelo bate a la regla en decisión.** Extra-Trees la empata y la gana
en **probabilidad**: Brier 0.2706 frente a 0.2781 y ECE 0.0851 frente a 0.1152.
Ese es el único argumento defendible para preferir el modelo aprendido, y es
suficiente: a una junta que delibera le sirve más una probabilidad calibrada
que una etiqueta segura de sí misma.

### Arquitectura: ¿una cabeza, tres encadenadas, o un panel?

| arquitectura | acierto | F1 macro | Brier |
|---|---|---|---|
| plano, bloque G | 0.8472 | 0.652 | 0.263 |
| plano, A+G | **0.8611** | 0.661 | 0.271 |
| plano, A+G+H | 0.8472 | 0.652 | 0.280 |
| plano, A+G+H+I | 0.8472 | 0.652 | 0.269 |
| plano, todos los bloques | **0.8611** | 0.661 | 0.265 |
| **cascada** GH / AGH / AGI | **0.8611** | 0.661 | 0.284 |
| cascada, todos los bloques | **0.8611** | 0.661 | 0.270 |

Todo converge a 0.8611. Añadir fuentes no mueve la decisión y la cascada
tampoco. **Pero la cascada dice algo que el plano no puede decir:**

| nodo | pregunta | n | positivos | AUC LOO | acierto | suelo |
|---|---|---|---|---|---|---|
| 1 (GH) | ¿hay cáncer confirmado? | 72 | 58 | **0.940** | 0.972 | 0.806 |
| 2 (AGH) | ¿está indicado tratar? | 58 | 33 | **0.881** | 0.897 | 0.569 |
| 3 (AGI) | ¿se beneficia del tratamiento? | 33 | 31 | **0.500** | 0.939 | 0.939 |

El mismo 0.8611 se descompone en **dos preguntas bien contestadas y una que la
cohorte no puede contestar**. El nodo 3 está exactamente en el azar y su
acierto de 0.939 es el de decir "apto" siempre. Los dos casos reales de
`watchful_waiting` quedan en las posiciones 10 y 36 de 72 al ordenar por
P(watchful_waiting): sin señal.

Publicar ese 0.500 es el punto. Una junta a la que se le entrega un veredicto
compuesto sin sus partes no puede saber que el tercer paso es un juicio clínico
sin respaldo estadístico; con las partes, sí.

### Qué sabe cada especialista por su cuenta

Un clasificador entrenado **sólo** con su bloque, leave-one-out
(`train/artifacts/panel_extra_trees.csv`):

| especialista | bloque | vars | acierto | IC 95 % | Brier | ECE | Δ vs regla | p |
|---|---|---|---|---|---|---|---|---|
| grado | G | 28 | **0.8472** | [0.764, 0.931] | **0.2627** | **0.0337** | −0.0139 | 0.735 |
| patología | H | 27 | 0.8056 | [0.708, 0.889] | 0.3205 | 0.0862 | −0.0556 | **0.021** |
| clínico | A | 38 | 0.6250 | [0.514, 0.736] | 0.4803 | 0.1307 | −0.2361 | **0.001** |
| embeddings | J+K | 31 | 0.5833 | [0.472, 0.694] | 0.5013 | 0.0973 | −0.2778 | **0.000** |
| radiología | D | 18 | 0.5278 | [0.417, 0.639] | 0.6279 | 0.1702 | −0.3333 | **0.000** |
| **fragilidad** | I | 25 | **0.3889** | [0.278, 0.500] | 0.7159 | 0.1159 | −0.4722 | **0.000** |
| **serie de PSA** | C | 19 | **0.3611** | [0.250, 0.472] | 0.6775 | 0.1703 | −0.5000 | **0.000** |
| *prevalencia* | — | — | *0.4306* | [0.319, 0.542] | *0.674* | — | — | — |

Y las tres formas de combinarlos:

| combinación | acierto | Brier | ECE | Δ vs regla | p |
|---|---|---|---|---|---|
| apilado (logística sobre probabilidades fuera de pliegue) | 0.8472 | 0.2881 | 0.1139 | −0.0139 | 0.735 |
| voto blando | 0.7639 | 0.4145 | 0.2205 | −0.0972 | **0.000** |
| producto de expertos | 0.7639 | 0.3651 | 0.2312 | −0.0972 | **0.000** |

Tres lecturas importan más que la obvia:

**Fragilidad y serie de PSA quedan por debajo de la prevalencia.** No aportan
poco: aportan menos que no saber nada. Para las cuatro clases, por su cuenta son
ruido.

**Ninguna combinación bate al mejor especialista solo.** El apilado lo empata
gastando siete modelos en vez de uno, y las dos combinaciones simétricas pierden
casi diez puntos —significativamente, p < 0.001—. Promediar un experto de 0.847
con dos de 0.36 no produce consenso sino dilución. Es la razón de que el
portavoz del panel sea el experto de mayor fiabilidad medida y no una votación.

**El especialista de grado es además el mejor calibrado de todos**, con un ECE
de 0.0337 frente al 0.1152 de la regla de guía. Esa es su aportación real: no
decide distinto, decide con una probabilidad que se puede creer.

Qué contesta cada bloque **pregunta a pregunta** —donde se ve que los embeddings
sí llevan señal (AUC 0.844 y 0.796) aunque su acierto de cuatro clases sea
0.583— está en [`VARIABLES.md`](VARIABLES.md).

El criterio completo con el que se construyó cada bloque está en
[`VARIABLES.md`](VARIABLES.md).

### Qué fuente aporta: la ablación

Extra-Trees sobre el conjunto completo (184 variables, acierto 0.8611),
leave-one-out y bootstrap pareado (`train/artifacts/ablation_extra_trees.csv`):

| bloque retirado | acierto | Δ | p | | sólo ese bloque | acierto | Δ vs regla | p |
|---|---|---|---|---|---|---|---|---|
| **grado (G)** | **0.7917** | **−0.0694** | **0.008** | | grado (G) | 0.8472 | −0.0139 | 0.735 |
| patología (H) | 0.8611 | +0.0000 | 1.000 | | patología (H) | 0.8056 | −0.0556 | 0.021 |
| clínico (A) | 0.8611 | +0.0000 | 1.000 | | clínico (A) | 0.6250 | −0.2361 | 0.001 |
| radiología (D) | 0.8611 | +0.0000 | 1.000 | | PCA embeddings (K) | 0.5833 | −0.2778 | 0.000 |
| serie de PSA (C) | 0.8611 | +0.0000 | 1.000 | | resúmenes emb. (J) | 0.5556 | −0.3056 | 0.000 |
| fragilidad (I) | 0.8611 | +0.0000 | 1.000 | | radiología (D) | 0.5278 | −0.3333 | 0.000 |
| resúmenes emb. (J) | 0.8611 | +0.0000 | 1.000 | | fragilidad (I) | 0.3889 | −0.4722 | 0.000 |
| PCA embeddings (K) | 0.8611 | +0.0000 | 1.000 | | serie de PSA (C) | 0.3611 | −0.5000 | 0.000 |

**Un solo bloque importa.** Retirar el de grado cuesta siete puntos y es la
única retirada significativa. Retirar cualquier otro —patología, radiología,
fragilidad, serie de PSA, o **las dos modalidades de representaciones
neuronales**— no cambia ni una predicción: Δ exactamente cero en los 72 casos.

Y por el otro lado: el bloque de grado **solo** (28 variables) es
estadísticamente indistinguible de la regla de guía (p = 0.735) y del modelo
completo con 184 variables. Las otras 156 variables no compran nada.

Esto no dice que las demás fuentes no tengan señal —la tienen, y se mide en
[`VARIABLES.md`](VARIABLES.md): los embeddings alcanzan AUC 0.844 y 0.796 en los
dos nodos contestables—. Dice que su señal es **redundante** con la del grado,
que llega antes y más limpia.

### El techo, no sólo el suelo

Cinco de los 72 casos comparten perfil de guía **exacto** con otro de etiqueta
distinta:

| perfil | casos |
|---|---|
| ISUP 1, 3+3, cT1c, PSA<10, PI-RADS 2 | T2-001 `active_surveillance` · T2-108 `continued_surveillance` |
| ISUP 1, 3+3, cT1c, PSA<10, PI-RADS 4 | 9 × `active_surveillance` · T2-043 `active_treatment` |
| ISUP 2, 3+4, cT1c, PSA<10, PI-RADS 4 | T2-008 `active_surveillance` · T2-032 `watchful_waiting` · 2 × `active_treatment` |
| ISUP 0, 0+0, cT1c, PSA≥10, PI-RADS 5 | T2-018 `active_surveillance` · T2-059 `continued_surveillance` |

El **techo de consistencia es 0.931**. La regla está en 0.861: la distancia son
cinco casos, y son casos en los que dos pacientes indistinguibles recibieron
conductas opuestas.

### ¿Se puede saber dónde falla la regla?

No. Detector binario del objetivo *«la regla falla aquí»* (10 positivos de 72),
leave-one-out, un bloque cada vez:

| bloque | AUC | fallos en el top-10 de sospecha |
|---|---|---|
| grado (G) | 0.631 | 3 / 10 |
| serie de PSA (C) | 0.618 | 2 / 10 |
| embeddings (J+K) | 0.518 | 1 / 10 |
| todos | 0.463 | 0 / 10 |
| patología (H) | 0.444 | 2 / 10 |
| clínico (A) | 0.395 | 0 / 10 |
| radiología (D) | 0.363 | 0 / 10 |
| fragilidad (I) | 0.277 | 0 / 10 |

Con 10 positivos, 0.63 y 0.28 son el mismo resultado: ruido. Las excepciones
son juicio idiosincrásico, y al menos dos son inconsistencias de anotación —el
texto libre de T2-031 dice *«patient with 2 negative biopsies»* en un caso con
ISUP 2 y Gleason 4+3.

**Ningún especialista va a corregir la regla.** Eso no invalida el panel:
cambia su propósito. Los expertos no están para sobrescribir la guía sino para
decir **cuándo su margen es estrecho**, y ahí sí hay señal:

| margen de la regla | n | acierto |
|---|---|---|
| > 0.60 | 52 | **0.904** |
| 0.30 – 0.60 | 20 | 0.750 |

---

## El formulario de razonamiento

Pasada la puerta de la decisión, el 82.5 % restante del `case_score` sale del
formulario. Tres hechos de esta cohorte que cambian cómo se rellena:

1. **`reveal_sequence` está vacío en los 72 casos.** El `tool_score` premia la
   *precisión* de las herramientas declaradas, así que declarar cualquier
   sección cuando el patrón no declaró ninguna lo pone a cero. La predicción
   correcta es la lista vacía.
2. **`confidence` sólo toma `clear` (58) y `borderline` (14).** `uncertain` no
   aparece nunca; emitirlo sólo puede restar.
3. **Tres de las once casillas están condicionadas.** `bx_isup`, `bx_gl_prim` y
   `bx_gl_sec` aparecen en 52 trazas, exactamente cuando la biopsia dio grado.
   Emitirlas de más no penaliza el `variable_weight_score` —recorre las claves
   del patrón— pero sí el F1 de factores, que cuenta como falso positivo toda
   variable marcada *important* o *decisive* de más.

Cada casilla se compara con su mejor constante usando **la métrica del reto**
—distancia ordinal, no acierto exacto— y el modelo aprendido se adopta sólo si
la bate:

| casilla | LOO aprendido | mejor constante | valor | adoptado |
|---|---|---|---|---|
| `bx_isup` | **0.8718** | 0.8462 | `important` | **sí** |
| `psa` | **0.8657** | 0.8611 | `important` | **sí** |
| `fh` | 0.8843 | 0.8981 | `noted` | no |
| `age` | 0.8056 | 0.8565 | `important` | no |
| `comorbidity` | 0.8102 | 0.8519 | `noted` | no |
| `psad` | 0.8009 | 0.8519 | `noted` | no |
| `cspca` | 0.7810 | 0.8476 | `noted` | no |
| `pirads` | 0.7546 | 0.8194 | `important` | no |
| `ct` | 0.7778 | 0.8102 | `noted` | no |
| `bx_gl_sec` | 0.7308 | 0.7756 | `noted` | no |
| `bx_gl_prim` | 0.7244 | 0.7756 | `noted` | no |
| `confidence` | 0.8958 | 0.9028 | `clear` | no |

Dos de doce. El resto se queda en su constante, que es lo que impide que el
formulario empeore por añadir parámetros.

Componentes resultantes: `variable_weight_score` 0.8545 · F1 de factores 0.6798
· `confidence_score` 0.9028 · `tool_score` 1.0000 · `section_grounding` 0.2154.
Suma ponderada sin juez de razonamiento: **0.7448**.

### Una trampa del evaluador local, documentada y no explotada

El `section_grounding_score` penaliza toda variable pesada por encima de
`not_used` cuya sección de origen no aparezca en el `reveal_sequence`. Con la
lista vacía que esta tarea exige, sólo `psa` y `age` quedan ancladas. Se puede
subir ese componente a 1.0 silenciando las otras nueve casillas:

| política | `var_weight` | F1 factores | *grounding* | sin juez | **con juez** |
|---|---|---|---|---|---|
| plantilla completa | 0.8413 | 0.6582 | 0.2000 | 0.7347 | **0.7696** |
| silenciar lo no anclable | 0.6574 | 0.4608 | 1.0000 | **0.7896** | 0.7340 |

Gana en el evaluador local **porque el juez de razonamiento está desactivado**,
que redistribuye el peso del *grounding* de 0.05 a 0.175. Con la configuración
real del leaderboard la política degenerada pierde 0.036. **No se adopta.**

---

## Cómo se usa esto en la junta

`run_experts.py` produce por caso los dos ficheros del reto más un
`expert-panel.json` con la carga ampliada: distribución de cada experto sobre
las cuatro conductas, incertidumbre descompuesta, tramo de fiabilidad, y —para
el Experto 5— las tres respuestas intermedias por separado.

### Un caso trabajado: T2-031

El más difícil de la cohorte —77 años, EPOC, fibrilación auricular, ISUP 2 con
Gleason 4+3— y uno de los dos `watchful_waiting` reales. Lo que el panel
produce:

| experto | decisión | margen | tramo | P(AS) | P(CS) | P(AT) | P(WW) |
|---|---|---|---|---|---|---|---|
| 1 — grado | `active_treatment` | 0.463 ± 0.307 | `supports` | 0.155 | 0.003 | **0.652** | 0.189 |
| 2 — patología | `active_treatment` | 0.262 ± 0.496 | `discuss` | 0.164 | 0.014 | **0.542** | 0.280 |
| 3 — aptitud | **`watchful_waiting`** | 0.309 ± 0.540 | `discuss` | 0.224 | 0.062 | 0.180 | **0.533** |

El portavoz elige `active_treatment` y **se equivoca**. Pero no se equivoca en
silencio:

- el Experto 1 no dice `firm` sino `supports`, y deja 0.189 de probabilidad en
  la conducta correcta en lugar de aplastarla a cero;
- el Experto 2 se abstiene explícitamente;
- el Experto 3, el que se diseñó para este eje, **nombra la respuesta correcta**
  y a la vez declara que no la puede separar.

Eso es lo que un panel tiene que entregarle a un deliberador: no una etiqueta,
sino un desacuerdo con sus tres incertidumbres. Un clasificador único habría
dicho `active_treatment` y nada más.

El **portavoz** no es una votación por mayoría. Es el experto de mayor
fiabilidad medida: entre los que están en el tramo más alto, gana el de mejor
acierto leave-one-out. Promediar expertos que leen las mismas variables no es
una segunda opinión —sus errores están correlacionados— y disfrazaría de
consenso un único punto de vista. Cuando ninguno pasa de `discuss`, el panel lo
dice y deja la decisión abierta.

---

## Limitaciones, dichas de frente

1. **n = 72, y una clase con 2 casos.** Los intervalos de acierto miden ±0.09. Ninguna diferencia entre modelos razonables es significativa.
2. **`watchful_waiting` no es aprendible aquí.** El nodo que lo produce está en AUC 0.500. Se publica entrenado para que la junta pueda leer que no hay evidencia, no para que lo use como voto.
3. **El techo de consistencia es 0.931.** Cinco casos tienen perfil idéntico a otro con etiqueta contraria. La regla ya está a cinco casos del techo.
4. **Sesgo de selección.** Con 17 candidatos y 72 casos, el acierto del ganador está optimistamente sesgado en torno a +0.02–0.04 (Varma y Simon 2006). Se publica junto al suelo, que sufre el mismo sesgo.
5. **`active_treatment_flag` es 0 en los 153 casos** y `task` y `enc_dept` son constantes: entran en la poda de columnas sin varianza, no en el modelo.
6. **`Prostatectomy slide` está vacío en los 153 casos.** La tercera modalidad que el esquema admite no existe en esta cohorte.
7. **El grado que predice la patología digital está descalibrado** respecto del clínico: 43 casos con *grade group* 5 frente a 0 de ISUP 5 clínico, e incluso *grade group* 5 en biopsias negativas (T2-018). Se usa como variable, no como grado.
8. **El corpus es sintético o pseudonimizado.** Nada de lo medido aquí es evidencia clínica.

El protocolo completo y la bibliografía están en [`train/README.md`](train/README.md).
