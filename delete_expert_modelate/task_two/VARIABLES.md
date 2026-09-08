# Cómo se eligieron las variables de la tarea 2

Este documento explica **por qué existe cada variable** que entra en los
expertos, qué se descartó y con qué evidencia. No es la lista de columnas —esa
está en el código— sino el criterio.

---

## El principio: bloques por pregunta clínica, no un selector automático

Con 72 casos etiquetados y 208 variables candidatas, un selector de
características (RFE, Lasso, importancia de permutación con umbral) elige ruido.
El problema no es de regularización sino de conteo: cualquier procedimiento que
mire las etiquetas para decidir qué columnas conserva gasta la muestra en esa
decisión, y luego la validación cruzada sobre las columnas ya elegidas devuelve
una cifra optimista que no se cumple fuera.

Así que las variables **no se seleccionan: se agrupan**. Cada bloque responde a
una pregunta clínica concreta, contiene todo lo que esa pregunta necesita y
nada de otra, y se mide entero. El bloque es la unidad de decisión; la columna
individual, no.

Eso tiene tres consecuencias buenas:

1. **La ablación es interpretable.** «El bloque de fragilidad no aporta» es una
   frase clínica; «la variable 47 no aporta» no lo es.
2. **Cada nodo de la cascada puede ver su bloque y sólo el suyo.** El nodo que
   decide si el paciente se beneficia del tratamiento no debe ver el grado del
   tumor, porque esa no es la pregunta que contesta.
3. **La incertidumbre por datos ausentes tiene sentido.** Un caso sin informe de
   patología pierde un bloque completo, no columnas sueltas, y la barra del
   veredicto se ensancha en proporción.

---

## Los nueve bloques, y qué justifica cada uno

### A — `structured` (38 variables tras poda)

Se **reutiliza tal cual de la tarea 1**. Lee `structured-prompt.json`: PSA y sus
transformaciones, volumen, densidad, PI-RADS, tacto rectal, edad, comorbilidad,
medicación. No se tocó una línea porque el esquema del fichero es el mismo y
duplicarlo habría creado dos verdades sobre las mismas columnas.

Detalles que ya venían y siguen valiendo aquí:

- **PSAD recalculada además de la publicada.** La del fichero está redondeada a
  dos decimales, lo que colapsa próstatas grandes; se conservan las dos.
- **5-ARI y alfabloqueantes como banderas.** Finasterida y dutasterida reducen
  el PSA a la mitad (Thompson 2003); sin esa bandera, cualquier regla basada en
  PSA mide dos cosas mezcladas.
- **`comorbidity_reported` separada de `n_comorbidities`.** Un `medhx` vacío
  significa «no reportado», no «sin comorbilidad». Se marca la ausencia en vez
  de imputarla a cero.

### G — `grading` (28 variables) · **nuevo**

Es el bloque que la tarea 2 necesita y la 1 no tiene, porque en la 1 la biopsia
todavía no existe. Lee los cuatro campos de los que **la etiqueta se derivó
retrospectivamente**: `bx_isup`, `bx_gl_prim`, `bx_gl_sec`, `ct`.

Tres decisiones que no son obvias:

- **Las reglas de guía entran como variables, no como un `if` final.** `eau_low`,
  `eau_intermediate`, `eau_high`, `nccn_ir_favourable`, `as_eligible_strict`…
  se calculan y se le entregan al clasificador. Así el modelo puede aprender
  *cuándo la guía no se cumplió*, que es exactamente donde están los casos
  difíciles. Si la regla fuera post-proceso, esos casos serían invisibles.
- **El patrón primario se separa de la suma.** Un 4+3 y un 3+4 suman lo mismo y
  no son el mismo paciente. De ahí `gleason_pattern4_primary` además de
  `gleason_sum`.
- **`cTx` no es un estadio bajo.** Se codifica como ausente (`NaN`) con una
  bandera `ct_unknown` aparte, en lugar de dejarlo caer al fondo de la escala
  ordinal.

### H — `pathology` (27 variables) · **nuevo**

Lee el informe de anatomía patológica en texto libre, que trae tres cosas que
ningún campo estructurado codifica:

1. **La trayectoria.** Un ISUP 1 con dos biopsias estables no es un ISUP 1
   recién diagnosticado, y la etiqueta lo distingue —`continued_surveillance`
   frente a `active_surveillance`—. El número de *timepoints* y la dirección del
   cambio sólo están en el texto.
2. **Los patrones adversos.** Cribiforme e intraductal cambian el manejo de un
   ISUP 2 aunque el grade group no cambie (Kweldam 2015, van Leenders 2020).
3. **El grado que predice la patología digital.** El informe cierra con
   `AI-predicted ISUP grade group`, salida del modelo de *Gleason grading*
   automático del reto. Su **discrepancia con el ISUP clínico** (`path_ai_gap`)
   es la variable de riesgo de *upgrade*.

La negación se resuelve con **NegEx** (Chapman 2001), el mismo del bloque D. Sin
él, `cribriform` mediría la longitud del informe: el corpus escribe *«No
cribriform or intraductal patterns identified»* en 98 de 153 casos con la misma
frecuencia con que lo afirma. Cada concepto es **ternario** —1.0 afirmado, 0.0
negado, `NaN` no mencionado— porque «negado» y «no mencionado» son evidencias
distintas.

### I — `frailty` (25 variables) · **nuevo**

Existe por una sola clase: `watchful_waiting`. Las guías la reservan a quien
**no se beneficiaría** de un tratamiento curativo por esperanza de vida corta,
no a quien tiene poco cáncer. La separan del resto variables que no describen
el tumor, y ninguna estaba disponible con la forma que hace falta:

- **`ipss` llegaba como texto y el bloque A lo convertía a `NaN`.** El campo es
  `"IPSS score: 12/35 (moderate LUTS)"`. Se extrae el numerador y sus tramos
  (Barry 1992: 0-7 leve, 8-19 moderado, 20-35 grave). Importa: dos de las diez
  excepciones a la regla de guía son pacientes con LUTS graves a quienes se
  trata para resolver a la vez el cáncer de bajo riesgo y la obstrucción
  (T2-030 con IPSS 33, T2-043).
- **Charlson ajustado por edad, convertido a supervivencia a 10 años.** No es
  una predicción clínica; es una variable ordenada que resume edad y
  comorbilidad en la escala en la que la guía razona. T2-031 (77 años, EPOC,
  fibrilación auricular) sale con 0.214 y es uno de los dos `watchful_waiting`.
- **Capacidad funcional y soporte social desde texto libre.** `exercise`
  («limited mobility — chair-based exercises only» → 0; «cycling 3x/week» → 3) y
  `living` («assisted-living facility» → 0; «lives with partner» → 2).

### C — `psa_trend`, D — `radiology_nlp`, B/E — labs y notas

Reutilizados de la tarea 1 sin cambios. `B` (analítica) se dejó fuera del
conjunto de trabajo porque sus variables útiles —hemoglobina, eGFR, fosfatasa
alcalina, testosterona— ya entran por el bloque I, donde tienen el papel
correcto: reserva fisiológica, no marcador tumoral. `E` (notas previas) se
excluyó porque la ablación de la tarea 1 mostró que **resta** (+0.004 al
retirarlo).

### J — `embedding_summary` (15 variables) y K — `pc_*` (16) · **nuevos**

Las representaciones neuronales traen dos modalidades en la tarea 2:
`MRI image` (1×1024) y `Biopsy slide` (0 a 3 × 960). `Prostatectomy slide` está
**vacío en los 153 casos**.

Dos decisiones:

- **El número de preparaciones varía, así que hay que agregar.** Se usa el
  esquema de *multiple-instance learning*: media, máximo por dimensión y
  desviación entre preparaciones. El máximo se conserva aparte porque es el que
  tiene sentido clínico —el manejo lo fija el foco de mayor grado, no el
  promedio (Campanella 2019).
- **Ninguna dimensión cruda entra en un modelo.** 1984 columnas con 72 casos no
  es un problema de regularización, es un problema de conteo. El bloque expone
  resúmenes de norma (baratos, interpretables) y una **PCA de 8 componentes
  ajustada sobre los 153 casos sin mirar la etiqueta** —es una transformación no
  supervisada, así que incluir los no etiquetados no filtra nada—. Explica el
  94 % de la varianza de la RM y el 93 % de la biopsia.
- **Los casos sin esa modalidad reciben `NaN`, no ceros.** Un cero en un espacio
  PCA es el centroide, y hacer pasar «no tengo imagen» por «soy el caso medio»
  es justo el error que la incertidumbre por datos ausentes tiene que capturar.

---

## Las dos podas automáticas, y por qué son las únicas

`dataset_task2.build_matrix` aplica dos filtros, **ambos ciegos a la etiqueta**:

1. **Columnas sin varianza.** Una columna constante entre sus valores observados
   no discrimina nada. Aquí caen `task` (siempre 2), `enc_dept` (siempre
   «Urology - outpatient») y `active_treatment_flag`, que es **0 en los 153
   casos** pese a ser el campo que en principio marcaría al paciente ya en
   tratamiento.
2. **Columnas demasiado dispersas** (menos de 6 observaciones o del 8 %). Además
   de no ser estimables, una columna con 6 observaciones sobre 72 puede quedar
   **entera ausente** dentro de una partición de entrenamiento, y ahí el
   imputador iterativo no tiene con qué construir su modelo y falla. El umbral
   se aplica sobre la cohorte completa, antes de partir, para que no dependa de
   la partición.

El umbral bajó de 8 (tarea 1, 91 casos) a 6 porque mantener el absoluto habría
tirado columnas que con 72 casos sí son estimables.

**No hay ninguna poda que mire `y`.** Ni umbral de importancia, ni selección
univariante, ni RFE. Es deliberado: con 72 casos, cualquiera de las tres
convierte la validación cruzada posterior en una cifra que no se cumple fuera.

---

## Qué dice la evidencia sobre cada bloque

Cada especialista entrenado **sólo** con su bloque, leave-one-out, acierto de
las cuatro clases (`train/artifacts/panel_extra_trees.csv`):

| especialista | bloque | vars | acierto | IC 95 % | F1 macro | Brier |
|---|---|---|---|---|---|---|
| grado | G | 28 | **0.8472** | [0.764, 0.931] | 0.652 | **0.263** |
| patología | H | 27 | 0.8056 | [0.708, 0.889] | 0.625 | 0.320 |
| clínico | A | 38 | 0.6250 | [0.514, 0.736] | 0.509 | 0.480 |
| embeddings | J+K | 31 | 0.5833 | [0.472, 0.694] | 0.398 | 0.501 |
| radiología | D | 18 | 0.5278 | [0.417, 0.639] | 0.361 | 0.628 |
| **fragilidad** | I | 25 | **0.3889** | [0.278, 0.500] | 0.265 | 0.716 |
| **serie de PSA** | C | 19 | **0.3611** | [0.250, 0.472] | 0.263 | 0.677 |
| *prevalencia* | — | — | *0.4306* | [0.319, 0.542] | *0.151* | *0.674* |
| *regla de guía* | — | — | *0.8611* | [0.778, 0.944] | *0.661* | *0.278* |

Léase con cuidado, porque hay cuatro lecturas y sólo una es la obvia:

**1. Sólo dos bloques tienen señal propia.** Grado (0.8472) y patología (0.8056)
están cerca de la regla. Los demás quedan lejos.

**2. Fragilidad y serie de PSA quedan por debajo de la prevalencia.** No es que
aporten poco: aportan **menos que no saber nada**. Para las cuatro clases, esos
dos bloques por su cuenta son ruido, y un panel que los deje votar empeora.

**3. Eso no significa que el bloque I sobre.** Su papel no es clasificar las
cuatro conductas —para eso no sirve— sino contestar el nodo 3 de la cascada,
*«¿se beneficia del tratamiento?»*. Y ahí la medida honesta es que **tampoco
sirve**: AUC 0.500 sobre 33 casos con 2 negativos. Se mantiene entrenado y se
publica ese 0.500 precisamente para que la junta lea que no hay evidencia, en
lugar de recibir un veredicto compuesto que parezca informado. Un bloque que
mide su propia ignorancia es más útil que un bloque ausente.

**4. Combinar empeora.** El voto blando de los siete especialistas da 0.7639,
casi diez puntos por debajo del mejor experto solo. Promediar un experto de
0.8472 con dos de 0.36 no produce consenso: produce dilución. Por eso el
portavoz del panel es **el experto de mayor fiabilidad medida dentro del tramo
más alto**, y no una votación.

---

## Qué contesta cada bloque, pregunta a pregunta

El acierto de cuatro clases esconde que las tres preguntas de la guía no las
contesta la misma fuente. AUC leave-one-out de cada bloque sobre cada nodo
binario de la cascada (`train/logs/embeddings_nodes.log`):

| bloque | ¿hay cáncer? | ¿está indicado tratar? | ¿se beneficia? |
|---|---|---|---|
| clínico (A) | **0.983** | 0.487 | *0.758* |
| patología (H) | 0.979 | 0.869 | *0.435* |
| grado (G) | 0.920 | **0.897** | *0.516* |
| PCA de embeddings (K) | 0.847 | 0.788 | *0.613* |
| embeddings (J+K) | 0.844 | 0.796 | *0.645* |
| serie de PSA (C) | 0.727 | 0.473 | *0.000* |
| resúmenes de embeddings (J) | 0.698 | 0.771 | *0.419* |
| fragilidad (I) | 0.681 | 0.451 | *0.194* |
| radiología (D) | 0.659 | 0.632 | *0.419* |
| | n = 72 (58 pos) | n = 58 (33 pos) | n = 33 (**2 neg**) |

Cuatro cosas que sólo se ven aquí:

**1. La tercera columna es ruido y hay que leerla como tal.** Va de 0.000 a
0.758 sin ningún patrón interpretable —la serie de PSA «predice» perfectamente
al revés, el bloque clínico «gana» al de fragilidad que se diseñó para eso—
porque el nodo tiene **dos casos negativos**. Un AUC sobre 31 contra 2 tiene una
varianza que se come cualquier diferencia. Se publica entera precisamente para
que nadie elija el 0.758 y lo presente como hallazgo.

**2. Los embeddings sí llevan señal.** 0.844 y 0.796 en los dos nodos
contestables, muy por encima del azar. Que su acierto de cuatro clases sea 0.583
no significa que estén vacíos: significa que **son redundantes** con el grado y
la patología, que contestan esas mismas preguntas mejor. Es una conclusión
distinta y hay que decirla como es.

**3. La PCA no supervisada mejora a los resúmenes crudos.** 0.847 frente a 0.698
en el primer nodo. Ocho componentes sobre la agregación media/máximo/desviación
extraen del embedding lo que las normas y las esparsidades no capturan, y lo
hacen sin gastar un solo caso etiquetado.

**4. El 0.983 del bloque clínico en el primer nodo no es mérito del modelo.**
El bloque A contiene `bx_positive`/`bx_negative`, que es literalmente el campo
que define ese nodo. Es una comprobación de que la tubería no está rota, no un
resultado.

---

## Lo que se descartó, y por qué

| descartado | motivo |
|---|---|
| dimensiones crudas de los embeddings (1984) | 72 casos; se sustituyen por 8 componentes PCA no supervisada por modalidad |
| `Prostatectomy slide` | vacío en los 153 casos |
| `active_treatment_flag`, `task`, `enc_dept` | constantes en los 153 casos |
| bloque E (notas previas) | la ablación de la tarea 1 lo dio como restante |
| bloque B (analítica) como bloque propio | sus variables útiles entran por I con el papel correcto |
| selección de características supervisada | con 72 casos, sesga la validación posterior |
| `AI-predicted ISUP` como grado | descalibrado: 43 casos con *grade group* 5 frente a 0 de ISUP 5 clínico, e incluso *grade group* 5 en biopsias negativas (T2-018). Entra como **discrepancia**, no como grado |

---

## Bibliografía de las decisiones concretas

* Chapman W.W. *et al.*, *A Simple Algorithm for Identifying Negated Findings*, J Biomed Inform 2001 — NegEx, bloques D y H.
* Kweldam C.F. *et al.*, Mod Pathol 2015 y van Leenders G.J.L.H. *et al.*, Am J Surg Pathol 2020 — cribiforme e intraductal.
* Barry M.J. *et al.*, J Urol 1992 — IPSS y sus tramos.
* Charlson M.E. *et al.*, J Chronic Dis 1987 — pesos e integración con la edad.
* Thompson I.M. *et al.*, N Engl J Med 2003 — 5-ARI y su efecto sobre el PSA.
* Epstein J.I. *et al.*, Eur Urol 2016 — ISUP grade groups.
* Mottet N. *et al.*, Eur Urol 2021 — grupos de riesgo EAU y criterios de vigilancia activa.
* Campanella G. *et al.*, Nat Med 2019 e Ilse M. *et al.*, ICML 2018 — agregación de preparaciones.
* Bulten W. *et al.*, Nat Med 2022 (PANDA) — el tipo de cabeza que produce `AI-predicted ISUP grade group`.
* Varma S., Simon R., BMC Bioinformatics 2006 — por qué no hay selección supervisada.
