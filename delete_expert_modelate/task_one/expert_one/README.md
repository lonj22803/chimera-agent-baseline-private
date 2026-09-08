# Experto 1 — clasificador sobre `structured-prompt.json`

**Qué hace.** Decide si se recomienda biopsia, con una probabilidad y su
incertidumbre descompuesta.

**Qué lee.** Sólo `structured-prompt.json` (bloque A). No abre el informe
radiológico ni la analítica.

**Modelo.** Extra-Trees (1000 árboles, `min_samples_leaf=3`), envuelto en
bagging × imputación múltiple.

**Rendimiento.** AUC 0.758 en CV repetida [IC 95 % 0.653–0.854]; 0.744 en
leave-one-out; 0.778 con el envoltorio de ensemble.

---

## Por qué existe un experto que lee menos que los otros

Podría parecer que el Experto 3, que lee cinco fuentes, hace innecesario a éste.
No es así, por dos razones.

**Es el que sigue en pie cuando falla el resto.** El bloque A está completo en los
195 casos. El informe radiológico puede venir con una redacción que el extractor
no cubra; la serie de PSA puede tener dos puntos en lugar de cinco. Este experto
no depende de nada de eso.

**Su desventaja no está establecida.** El bootstrap pareado sobre los mismos 91
casos da una diferencia de AUC frente al mejor modelo de −0.024, con intervalo
[−0.082, +0.032] y p = 0.376. Con esta muestra, la ventaja de leer más fuentes es
real en el punto estimado pero **no es estadísticamente distinguible de cero**.
Decir otra cosa sería sobre-vender el resultado.

## Por qué Extra-Trees

De 19 candidatos evaluados con el mismo protocolo (`../train/artifacts/bakeoff_stage1.csv`),
sobre el bloque A:

| modelo | AUC | exact. balanceada | Brier | ECE | sd entre repeticiones |
|---|---|---|---|---|---|
| **extra_trees** | **0.762** | 0.616 | **0.193** | 0.115 | **0.024** |
| grad_boosting | 0.762 | 0.668 | 0.202 | 0.115 | 0.022 |
| logreg_l1 | 0.717 | 0.607 | 0.215 | 0.110 | 0.033 |
| decision_tree | 0.715 | 0.562 | 0.207 | 0.137 | 0.046 |
| random_forest | 0.714 | 0.582 | 0.210 | 0.104 | 0.032 |
| logreg_elasticnet | 0.702 | 0.584 | 0.229 | 0.148 | 0.030 |
| deep_ensemble_mlp | 0.697 | 0.550 | 0.243 | 0.195 | 0.026 |
| lda | 0.695 | 0.584 | 0.255 | 0.206 | 0.027 |
| random_forest_calibrated | 0.694 | 0.650 | 0.215 | 0.099 | 0.033 |
| hist_gradient_boosting | 0.681 | 0.627 | 0.230 | 0.098 | 0.034 |
| logreg_l2 | 0.679 | 0.557 | 0.260 | 0.223 | 0.035 |
| gaussian_nb | 0.677 | 0.602 | 0.270 | 0.266 | 0.031 |
| svm_rbf | 0.669 | 0.538 | 0.223 | 0.067 | 0.031 |
| knn_probabilistic | 0.665 | 0.498 | 0.222 | 0.060 | 0.024 |
| svm_linear | 0.663 | 0.512 | 0.227 | 0.068 | 0.053 |
| knn | 0.660 | 0.507 | 0.225 | 0.091 | 0.029 |
| *regla PI-RADS ≥ 3* | 0.475 | 0.571 | 0.217 | 0.014 | 0.010 |
| *regla EAU + PSAD* | 0.473 | 0.605 | 0.212 | 0.019 | 0.013 |
| *prevalencia* | 0.449 | 0.500 | 0.237 | 0.000 | 0.000 |

Extra-Trees y *gradient boosting* empatan en AUC (0.762). El desempate va a
Extra-Trees por dos motivos medidos: su AUC leave-one-out es 0.744 frente a 0.686
del boosting, y es el ganador también sobre el conjunto completo de bloques
(0.786 frente a 0.715), de modo que es el único candidato que gana en las dos
configuraciones. Preferir el modelo que gana de forma consistente, y no el que
gana por 0.000 en una sola tabla, es la única defensa razonable contra el ruido
de selección con n = 91.

La observación de fondo: **los ensembles de árboles baten a los lineales por
~0.05 de AUC** (0.762 frente a 0.717 del mejor lineal), y contra `logreg_l2` la
diferencia es significativa (p = 0.025). Eso dice que la señal de esta tarea es
no lineal e interactiva, lo cual encaja con lo que se ve en los datos (siguiente
sección). El *deep ensemble* de MLP, que es el método de referencia para
incertidumbre en redes, queda por debajo (0.697) y con la peor calibración de su
grupo: aquí no compensa su coste.

## Por qué las reglas de guía clínica fracasan, y qué dice eso del problema

Las dos reglas obtienen **AUC por debajo de 0.5** con sensibilidad ~1.00 y
especificidad 0.14–0.23. Eso no es un fallo de las guías: es que el objetivo de
esta tarea no es el que las guías predicen.

Las calculadoras validadas (ERSPC/RPCRC, PBCG) y la regla PI-RADS predicen
**presencia de cáncer clínicamente significativo**. La etiqueta de la Tarea 1 es
**la decisión del urólogo de biopsiar**, que condiciona sobre lo que ya se sabe
del paciente. La diferencia se ve en una tabla:

| PI-RADS | biopsia previa | n | % «sí» |
|---|---|---|---|
| 5 | ninguna | 15 | **1.00** |
| 5 | negativa | 6 | 0.83 |
| 5 | **positiva** | 24 | **0.42** |
| 4 | ninguna | 5 | 1.00 |
| 4 | negativa | 9 | 0.89 |
| 4 | positiva | 19 | 0.58 |

**Misma imagen, decisión opuesta.** Un PI-RADS 5 sin biopsia previa va a biopsia
en el 100 % de los casos; el mismo PI-RADS 5 en un paciente con cáncer ya
confirmado, sólo en el 42 %. Volver a biopsiar a quien ya tiene diagnóstico no
aporta información nueva.

Una regla monótona en PI-RADS no puede representar eso: por construcción manda a
biopsia a todo el que tiene lesión, incluidos los 26 pacientes en los que sobra.
De ahí la especificidad de 0.17 con sensibilidad 1.00.

Esto es lo que justifica entrenar en lugar de aplicar una calculadora publicada,
y se confirma en la importancia de permutación: la variable más importante del
modelo es `bx_positive` (+0.066 de caída de AUC), por delante de `pirads_ge4`
(+0.033).

## Rendimiento y escalera de fiabilidad

Todo medido **out-of-fold**. Un tramo `firm` calculado sobre datos de
entrenamiento sería trivialmente perfecto.

| métrica | valor | IC 95 % |
|---|---|---|
| AUC (CV repetida 5×20) | 0.758 | [0.653, 0.854] |
| AUC (leave-one-out) | 0.744 | — |
| AUC (con envoltorio de ensemble) | 0.778 | — |
| Exactitud balanceada | 0.625 | [0.530, 0.727] |
| Brier | 0.195 | — |
| ECE | 0.115 | — |

| tramo | `confidence` | n | cobertura | **acierto** |
|---|---|---|---|---|
| `firm` | `clear` | 33 | 36 % | **0.879** |
| `supports` | `borderline` | 20 | 22 % | 0.600 |
| `discuss` | `uncertain` | 38 | 42 % | 0.553 |

Ésta es la tabla que importa. El acierto cae de forma monótona al bajar por la
escalera: en el 36 % de los casos el experto se moja y acierta casi 9 de cada 10; en
el 42 % declara que no distingue, y ahí acierta poco más que la moneda. Si el
acierto no cayera, la incertidumbre no estaría midiendo nada.

Para un deliberador esto significa: en los 33 casos `firm`, este experto solo ya
resuelve el caso. En los 38 `discuss`, hay que ir a los documentos.

## Variables y su traducción al formulario

Las 12 más importantes por permutación (caída de AUC, medida fuera de la
partición de ajuste):

| variable | caída de AUC |
|---|---|
| `bx_positive` | +0.0658 |
| `pirads_ge4` | +0.0334 |
| `bx_none` | +0.0303 |
| `pmhx_hypercholesterolaemia` | +0.0215 |
| `dre_suspicious` | +0.0198 |
| `n_comorbidities` | +0.0155 |
| `pirads_ge3` | +0.0088 |
| `bmi` | +0.0088 |
| `age` | +0.0064 |
| `pirads` | +0.0040 |
| `log_vol` | +0.0038 |
| `pmhx_coronary_artery_disease` | +0.0036 |

Una advertencia: `pmhx_hypercholesterolaemia` en cuarto lugar es casi seguro
ruido. Esa columna tiene un 42 % de ausencias y no hay mecanismo por el que la
hipercolesterolemia decida una biopsia. Con 91 casos y 39 variables, una
importancia de +0.02 está dentro de lo que produce el azar. Se deja en la tabla
en lugar de podarla porque ocultarla sería peor.

**Los pesos que van al formulario del reto no salen de esta tabla.** Salen del
modelo de traza (`../reasoning_model/`), entrenado contra las 91 trazas reales
del urólogo. El motivo está documentado allí: el orden de importancia predictiva
y el orden que declara el urólogo correlacionan sólo ρ = 0.26 (p = 0.47), porque
PI-RADS apenas varía en esta cohorte y por tanto explica poca varianza de la
decisión aunque sea clínicamente la puerta de entrada. Las dos lecturas son
válidas y responden a preguntas distintas, así que se conservan las dos: la
importancia viaja en la carga ampliada para el deliberador, la traza predicha va
al fichero puntuable.

## La incertidumbre

Tres números separados, nunca uno solo. La justificación completa está en
[`../train/README.md`](../train/README.md); en resumen:

- `epistemic_model` — dispersión entre los 30 miembros del bagging. Baja con más datos.
- `epistemic_missing` — dispersión entre las 10 imputaciones múltiples. Vale **exactamente cero** en un caso completo y crece con cada variable ausente (regla *between* de Rubin). Es lo que hace que la barra se ensanche cuando falta información, medido y no postulado.
- `aleatoric` — entropía normalizada. No baja con más datos del mismo tipo.

Las dos epistémicas se suman en cuadratura; la aleatoria no se mezcla con ellas.

El cuaderno `demo_expert_one.ipynb` incluye una prueba de degradación
controlada: se borran variables de un caso completo, de más a menos importante, y
se comprueba que `epistemic_missing` sube de forma monótona.

## Ficheros

| Fichero | Qué es |
|---|---|
| `train_expert_one.py` | entrenador |
| `model/expert_one.joblib` | modelo, importancias, métricas, escalera, predicciones out-of-fold |
| `demo_expert_one.ipynb` | comportamiento con los datos |
| `../train/artifacts/expert_one_*.csv` | selección, importancia, out-of-fold |

## Bibliografía

- Geurts, P., Ernst, D., Wehenkel, L. *Extremely randomized trees.* Mach Learn 63:3-42, 2006.
- Breiman, L. *Bagging Predictors.* Mach Learn 24:123-140, 1996.
- Fisher, A., Rudin, C., Dominici, F. *All Models are Wrong, but Many are Useful.* JMLR 20(177), 2019.
- Lakshminarayanan, B., Pritzel, A., Blundell, C. *Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles.* NeurIPS 2017.
- Depeweg, S. et al. *Decomposition of Uncertainty in Bayesian Deep Learning.* ICML 2018.
- Rubin, D.B. *Multiple Imputation for Nonresponse in Surveys.* Wiley, 1987.
- Guo, C. et al. *On Calibration of Modern Neural Networks.* ICML 2017.
- Turkbey, B. et al. *PI-RADS Version 2.1.* Eur Urol 76(3):340-351, 2019.
- EAU-EANM-ESTRO-ESUR-ISUP-SIOG *Guidelines on Prostate Cancer*, 2024.
- Roobol, M.J. et al. *Rotterdam Prostate Cancer Risk Calculator.* JMIR Mhealth Uhealth 5(3):e29, 2017.
- Alberts, A.R. et al. *Improving the Rotterdam ERSPC Risk Calculators.* Eur Urol 75(2):310-318, 2019.
