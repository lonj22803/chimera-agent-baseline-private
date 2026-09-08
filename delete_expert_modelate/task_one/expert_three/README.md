# Experto 3 — fusión multi-fuente

**Qué hace.** Decide si se recomienda biopsia, leyendo además del prompt
estructurado la analítica y el informe radiológico en texto libre.

**Qué lee.** Bloques **A + B + D**:
- A — `structured-prompt.json`
- B — analítica de `prostate-biopsy-decision-clinical-data.json`
- D — informe radiológico de la misma fuente, extraído con detección de negación

**Modelo.** Extra-Trees sobre 75 variables, envuelto en bagging × imputación
múltiple.

**Rendimiento.** AUC 0.794 en CV repetida [IC 95 % 0.698–0.881]; 0.791 en
leave-one-out; **0.811** con el envoltorio. Es el mejor de los tres.

---

## Por qué A+B+D y no todo

La ablación (`../train/artifacts/ablation_blocks.csv`, Extra-Trees, CV 5×10)
recorrió las combinaciones con sentido clínico:

| bloques | contenido | vars | AUC | IC 95 % |
|---|---|---|---|---|
| **ABD** | **estructurado + analítica + radiología** | **75** | **0.794** | [0.696, 0.876] |
| ABCD | + serie de PSA | 94 | 0.790 | [0.683, 0.873] |
| AD | estructurado + radiología | 58 | 0.787 | [0.689, 0.872] |
| ABCDE | todo | 102 | 0.786 | [0.681, 0.871] |
| ACD | sin analítica | 77 | 0.785 | [0.684, 0.869] |
| ABDE | + notas | 83 | 0.783 | [0.681, 0.864] |
| BCDE | sin el prompt estructurado | 63 | 0.782 | [0.675, 0.870] |
| ACDE | sin analítica, con notas | 85 | 0.777 | [0.670, 0.864] |
| AB | estructurado + analítica | 56 | 0.770 | [0.665, 0.860] |
| ABC | + serie de PSA | 75 | 0.766 | [0.657, 0.857] |
| A | sólo estructurado | 39 | 0.762 | [0.658, 0.854] |
| AC | estructurado + serie de PSA | 58 | 0.758 | [0.648, 0.852] |
| ABCE | sin radiología | 83 | 0.756 | [0.646, 0.852] |
| AE | estructurado + notas | 47 | 0.730 | [0.619, 0.831] |

Y la ablación *leave-one-block-out* sobre el conjunto completo, que es la que
detecta redundancia:

| bloque retirado | AUC | Δ AUC | p (bootstrap pareado) |
|---|---|---|---|
| radiología (D) | 0.756 | **−0.030** | 0.188 |
| analítica (B) | 0.777 | −0.009 | 0.544 |
| estructurado (A) | 0.782 | −0.005 | 0.812 |
| serie de PSA (C) | 0.783 | −0.004 | 0.872 |
| notas (E) | 0.790 | **+0.004** | 0.772 |

Tres lecturas.

**El informe radiológico es el único bloque que aporta de forma visible.**
Quitarlo cuesta −0.030 de AUC, el triple que cualquier otro. Es también el único
bloque que introduce información que no está en ninguna otra parte: el tamaño de
la lesión, su zona y la intensidad de la restricción en difusión no aparecen en
`structured-prompt.json`.

**Las notas previas restan.** Quitarlas *mejora* el AUC en +0.004. No aportan
señal y sí una decena de columnas que el imputador tiene que rellenar. Se
retiran, que es lo que la evidencia dice; conservarlas «porque no hacen daño»
sería falso: con 91 casos, cada variable de más sí hace daño.

**La serie de PSA no aporta al clasificador.** Quitarla cuesta −0.004 (p = 0.87).
Esto no invalida al Experto 2 —que responde a otra pregunta, *dónde estará el
PSA*— pero sí dice que, para decidir la biopsia, la tendencia observada no añade
nada al PSA actual. La sección final documenta la prueba explícita de si la
proyección *aprendida* añade algo por encima de la tendencia observada.

Ninguna de estas diferencias es estadísticamente significativa por separado
(todos los p > 0.18). Con 91 casos no lo serían aunque fueran reales. La elección
de ABD se apoya en la combinación de tres cosas: es la mejor en punto estimado,
el bloque D es el que más pesa en la ablación *leave-one-out*, y el bloque E es
el único con signo negativo.

## Cómo se lee el informe radiológico

El bloque D no es una bolsa de palabras: es un extractor de conceptos con
**detección de negación estilo NegEx** (Chapman, Bridewell, Hanbury, Cooper y
Buchanan, *J Biomed Inform* 2001). El informe del corpus es una paráfrasis en
lenguaje natural de una plantilla PI-RADS v2.1, con vocabulario muy variable —
201 formulaciones distintas sólo para describir la difusión — pero semántica
consistente.

Cada concepto devuelve un valor **ternario**: 1.0 afirmado, 0.0 negado, NaN no
mencionado. Distinguir «negado» de «no mencionado» es esencial: un informe que
dice «sin extensión extracapsular» es evidencia; uno que no la menciona, no.

El léxico de negación tuvo que ampliarse bastante respecto al artículo original.
NegEx se diseñó para notas de alta, donde la negación suele preceder al hallazgo
(«no evidence of X»). El informe radiológico la coloca *después* con mucha más
frecuencia («los ganglios pélvicos no muestran adenopatías», «la integridad
capsular se mantiene»). La post-negación se construye por composición de tres
grupos —verbo de reporte, adjetivo de ausencia, sustantivo de propiedad— en
lugar de enumerar frases, para que la cobertura no dependa del vocabulario
concreto de este corpus.

Efecto medido de esa ampliación, sobre 195 informes:

| concepto | antes (regex simple) | después (NegEx) |
|---|---|---|
| restricción en difusión | 47 % de informes resueltos | **97 %** |
| extensión extracapsular | 19 afirmados (17 falsos positivos) | **2 afirmados**, ambos correctos |
| adenopatías | 27 afirmados (todos falsos) | **0 afirmados**, 161 negados |

Además de los conceptos binarios se extraen dos **ordinales**, porque PI-RADS
v2.1 puntúa difusión y T2 en escala, no en presencia/ausencia, y el informe
conserva esa gradación en el adjetivo:

- `rad_dwi_severity` ∈ {0 nula, 1 leve, 2 moderada, 3 marcada} — distribución en los 195 casos: 15 / 2 / 44 / 129, y 5 no mencionados.
- `rad_t2_severity` — 8 / 33 / 154.

El ordinal además esquiva las oraciones adversativas del tipo «restricción leve,
aunque sin restricción marcada», donde el binario negado y el afirmado son ambos
defendibles.

**Hallazgo sobre la cohorte:** prácticamente no hay enfermedad localmente
avanzada. La invasión de vesículas seminales y las adenopatías se reportan como
ausentes en todos los casos que las mencionan; sólo 2 informes afirman extensión
extracapsular. Esas columnas quedan sin varianza y no discriminan, lo cual es un
resultado sobre el corpus, no un fallo del extractor.

## Qué variables acaban pesando

Importancia de permutación out-of-fold (caída de AUC):

| variable | caída de AUC | origen |
|---|---|---|
| `bx_positive` | +0.0567 | A |
| `bx_none` | +0.0247 | A |
| `fpsa_lt15` | +0.0236 | **B** — % PSA libre < 15 % |
| `rad_dwi_restriction` | +0.0177 | **D** — restricción en difusión |
| `rad_dwi_severity` | +0.0118 | **D** — intensidad de la restricción |
| `rad_lesion_ge15mm` | +0.0078 | **D** — lesión ≥ 15 mm |
| `dre_suspicious` | +0.0065 | A |
| `psa_delta_prev` | +0.0047 | A |
| `log_vol` | +0.0041 | A |
| `log_psa` | +0.0034 | A |

Cuatro de las diez primeras vienen de los bloques de texto, y son exactamente las
que la literatura predice: el umbral de %PSA libre de Catalona et al. (*JAMA*
1998), la restricción en difusión y el umbral de 15 mm que separa PI-RADS 4 de 5
(Turkbey et al., *Eur Urol* 2019). Que el modelo las encuentre por su cuenta es
la validación de que el extractor está leyendo lo que dice leer.

Sigue mandando `bx_positive`, por la razón explicada en el README del Experto 1:
la etiqueta es la decisión de biopsiar, no la presencia de cáncer.

## Rendimiento

| métrica | Experto 3 (ABD) | Experto 1 (A) |
|---|---|---|
| AUC (CV 5×20) | **0.794** [0.698, 0.881] | 0.758 [0.653, 0.854] |
| AUC (leave-one-out) | **0.791** | 0.744 |
| AUC (con envoltorio) | **0.811** | 0.778 |
| Exactitud del ensemble | **0.736** | 0.681 |
| Exactitud balanceada | **0.646** [0.556, 0.742] | 0.625 [0.530, 0.727] |
| Brier | **0.180** | 0.195 |
| ECE | **0.068** | 0.115 |

Gana en las siete métricas. Pero la diferencia de AUC frente al Experto 1 es
**+0.036 con intervalo que cruza el cero** (bootstrap pareado frente al campeón:
−0.024, IC [−0.082, +0.032], p = 0.376). Con 91 casos, leer más fuentes ayuda de
forma consistente pero no demostrable.

### Escalera de fiabilidad

| tramo | `confidence` | n | cobertura | acierto E3 | acierto E1 |
|---|---|---|---|---|---|
| `firm` | `clear` | 36 | 40 % | 0.861 | 0.879 |
| `supports` | `borderline` | 24 | 26 % | **0.708** | 0.600 |
| `discuss` | `uncertain` | 31 | 34 % | **0.613** | 0.553 |

La fusión no mejora el tramo `firm` —el Experto 1 ya acierta casi 9 de cada 10
ahí— sino los dos tramos difíciles: `supports` sube de 0.600 a 0.708 y `discuss`
de 0.553 a 0.613. Además cubre más casos con `firm` (36 frente a 33) y encoge el
tramo `discuss` de 38 casos a 31. Es decir, la lectura del texto libre sirve
sobre todo para **rescatar casos que el experto barato no resolvía**, que es
justamente donde un experto adicional tiene sentido.

## ¿Aporta la proyección del Experto 2?

**No.** Se entrenó una segunda variante con el bloque **G** — la salida del
Experto 2 como variables (`--with-expert-two`):

| variante | vars | AUC CV | AUC LOO | AUC envoltorio | Brier |
|---|---|---|---|---|---|
| **ABD** | 75 | **0.794** | **0.791** | **0.811** | 0.180 |
| ABD + G | 80 | 0.792 | 0.784 | 0.802 | 0.179 |

La proyección aprendida no añade nada sobre lo que el PSA actual ya dice, algo
que la ablación del bloque C (−0.004, p = 0.87) anticipaba. En la importancia de
permutación, la única variable del bloque G que asoma es `e2_direction_is_clear`,
en el puesto 12 con +0.0035 — indistinguible de cero.

Esto **no** invalida al Experto 2: dice que su salida es útil como evidencia
independiente para el deliberador, no como variable de este clasificador. Son
preguntas distintas y la respuesta a una no sirve para la otra.

## Ficheros

| Fichero | Qué es |
|---|---|
| `train_expert_three.py` | entrenador (`--blocks`, `--with-expert-two`) |
| `model/expert_three.joblib` | modelo ABD |
| `model/expert_three_with_e2.joblib` | variante con el bloque G |
| `demo_expert_three.ipynb` | extracción NegEx, ablación, comparación con el Experto 1 |

Implementación del extractor en `chimera_experts/features_radiology.py`.

## Bibliografía

- Chapman, W.W., Bridewell, W., Hanbury, P., Cooper, G.F., Buchanan, B.G. *A simple algorithm for identifying negated findings and diseases in discharge summaries.* J Biomed Inform 34(5):301-310, 2001.
- Turkbey, B. et al. *Prostate Imaging Reporting and Data System Version 2.1.* Eur Urol 76(3):340-351, 2019.
- Catalona, W.J. et al. *Use of the percentage of free prostate-specific antigen to enhance differentiation of prostate cancer from benign prostatic disease.* JAMA 279(19):1542-1547, 1998.
- Geurts, P., Ernst, D., Wehenkel, L. *Extremely randomized trees.* Mach Learn 63:3-42, 2006.
- Fisher, A., Rudin, C., Dominici, F. *All Models are Wrong, but Many are Useful.* JMLR 20(177), 2019.
- Rubin, D.B. *Multiple Imputation for Nonresponse in Surveys.* Wiley, 1987.
- Kasivisvanathan, V. et al. *MRI-Targeted or Standard Biopsy for Prostate-Cancer Diagnosis* (PRECISION). N Engl J Med 378:1767-1777, 2018.
