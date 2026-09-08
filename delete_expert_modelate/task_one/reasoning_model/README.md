# Experto 4 — modelo de la traza de razonamiento

**Qué hace.** Predice las tres casillas del formulario de CHIMERA que se puntúan
*además* de la decisión: `confidence`, `variable_weights` y `reveal_sequence`.

**Qué lee.** 13 variables de `structured-prompt.json`.

**Modelo.** Un clasificador multinomial (regresión logística regularizada) por
casilla, con una **puerta de LOOCV** que sólo conserva el modelo de las casillas
que baten a «predecir siempre la moda».

**Rendimiento.** Acierto medio 0.722 sobre las 16 casillas, frente a 0.696 del
suelo de la moda y 0.688 del modelo aprendido sin puerta.

---

## Por qué hace falta

El *case score* de CHIMERA-agent no puntúa sólo el `yes`/`no`: puntúa también el
formulario de razonamiento contra la traza que rellenó el urólogo. Ese formulario
es, por tanto, **un objetivo supervisado más**, con 91 ejemplos etiquetados en
`data_filtered/task1/ground_truth/*/prostate-biopsy-decision-reasoning.json`.

La primera versión de los expertos derivaba `variable_weights` de la importancia
de permutación del clasificador. Es lo honesto para explicar *qué usó el modelo*,
pero se mide mal contra el urólogo:

| variable | modelo (importancia) | urólogo (moda) | urólogo (rango medio 0-3) |
|---|---|---|---|
| `bx` | **decisive** | important | 1.87 |
| `pirads` | noted | **decisive** | 2.47 |
| `psa` | noted | important | 1.77 |
| `age` | noted | important | 1.67 |
| `comorbidity` | **important** | noted | 0.85 |
| `psad` | not_used | noted | 1.29 |
| `cspca` | noted | **not_used** | 0.46 |
| `dre` | noted | noted | 1.26 |
| `vol` | noted | noted | 1.18 |
| `fh` | not_used | noted | 0.77 |

Correlación de rangos de Spearman entre ambos órdenes: **ρ = 0.26 (p = 0.47)**.
Coincidencia exacta de categoría: **2 de 10**.

La divergencia tiene una explicación concreta y no es un fallo del clasificador.
PI-RADS apenas varía en esta cohorte —162 de 195 casos son PI-RADS 4 o 5—, de
modo que explica poca **varianza de la decisión** aunque sea clínicamente la
puerta de entrada. El estado de biopsia previa, en cambio, parte la cohorte en
dos grupos con tasas de biopsia del 83 % y el 47 %, y domina la importancia
predictiva.

Las dos lecturas son correctas y responden a preguntas distintas. Se conservan
las dos:

- la **importancia de permutación** viaja en `expert-panel.json`, para que el deliberador sepa qué movió realmente la predicción;
- la **traza predicha por este modelo** va a `prostate-biopsy-decision-reasoning.json`, porque ahí lo que se mide es el parecido con el urólogo.

## Que los pesos del urólogo sean predecibles no es evidente — se comprobó

Si el urólogo rellenara el formulario igual en todos los casos, predecirlo sería
copiar una plantilla y no habría nada que aprender. No es así en dos casillas:

`pirads` en función del PI-RADS del caso:

| PI-RADS del caso | important | decisive |
|---|---|---|
| 3 | 7 | 0 |
| 4 | 22 | 11 |
| 5 | 14 | 30 |

`bx` en función del estado de biopsia previa:

| biopsia previa | not_used | noted | important | decisive |
|---|---|---|---|---|
| ninguna | 1 | 16 | 6 | 1 |
| negativa | 0 | 8 | 8 | 2 |
| **positiva** | 2 | 0 | 32 | **15** |

En las demás casillas el urólogo es casi constante (`dre` es `noted` en 64 de 91;
`vol` en 69 de 91), y ahí la moda es efectivamente el mejor predictor disponible.

## Resultados, casilla por casilla

Leave-one-out sobre las 91 trazas. El suelo correcto no es el azar sino
**predecir siempre la moda**: si el urólogo puso `important` en `pirads` el 49 %
de las veces, un modelo que no bata ese 49 % no ha aprendido nada del caso.

| casilla | n | LOO modelo | moda | ganancia | ¿se conserva? |
|---|---|---|---|---|---|
| `weight::pirads` | 91 | **0.703** | 0.495 | **+0.209** | sí |
| `weight::bx` | 91 | **0.626** | 0.505 | **+0.121** | sí |
| `weight::dre` | 91 | 0.747 | 0.703 | +0.044 | sí |
| `reveal::laboratory_results` | 91 | 0.593 | 0.549 | +0.044 | sí |
| `reveal::radiology_report` | 91 | 0.967 | 0.967 | 0.000 | no |
| `reveal::family_history` | 91 | 1.000 | 1.000 | 0.000 | no |
| `reveal::psa_trend` | 91 | 0.857 | 0.868 | −0.011 | no |
| `weight::vol` | 91 | 0.736 | 0.758 | −0.022 | no |
| `weight::comorbidity` | 91 | 0.670 | 0.692 | −0.022 | no |
| `reveal::previous_notes` | 91 | 0.824 | 0.846 | −0.022 | no |
| `weight::psa` | 91 | 0.527 | 0.560 | −0.033 | no |
| `weight::cspca` | 89 | 0.629 | 0.663 | −0.034 | no |
| `weight::fh` | 91 | 0.615 | 0.703 | −0.088 | no |
| `weight::psad` | 91 | 0.473 | 0.571 | −0.099 | no |
| `confidence` | 91 | 0.527 | 0.637 | −0.110 | no |
| `weight::age` | 91 | 0.505 | 0.615 | −0.110 | no |

**Sólo 4 de 16 casillas superan el listón de +0.03**, y sólo dos por margen
amplio. En las otras doce el modelo aprendido es *peor* que la moda: con 91 casos
y 13 predictores, aprender una casilla casi constante sólo añade varianza.

Por eso la puerta. El resultado del híbrido —modelo donde gana, moda donde no—:

| estrategia | acierto medio |
|---|---|
| **híbrido (modelo donde gana, moda donde no)** | **0.722** |
| sólo la moda | 0.696 |
| modelo aprendido en todas las casillas | 0.688 |

Nótese que el modelo aprendido aplicado a todo es *peor* que no aprender nada.
Éste es el resultado que justifica la puerta y que un informe menos cuidadoso
habría ocultado publicando sólo el 0.722.

**Advertencia de método.** La selección de qué casillas conservan modelo se hace
con el mismo LOOCV con el que se mide, de modo que el 0.722 está ligeramente
sesgado al alza por selección (Varma y Simon, *BMC Bioinformatics* 2006). Con 16
casillas y dos ganadores de margen amplio (+0.21 y +0.12) el sesgo es pequeño,
pero la tabla por casilla es más informativa que el promedio y por eso se publica
entera.

## Un resultado colateral: la confianza del urólogo predice dónde falla el modelo

La casilla `confidence` no se puede predecir desde las variables estructuradas
(0.527 frente a 0.637 de la moda). Pero **sí es informativa sobre la dificultad
del caso**:

| confianza declarada por el urólogo | n | σ media del Experto 1 | acierto del Experto 1 |
|---|---|---|---|
| `clear` | 58 | 0.096 | **0.724** |
| `borderline` | 18 | 0.101 | 0.611 |
| `uncertain` | 15 | 0.106 | **0.533** |

Los casos que el urólogo marcó como inciertos son los casos en los que el modelo
se equivoca. Es una **validación externa** del ordenamiento de dificultad: dos
estimadores independientes —un clínico y un ensemble— coinciden en qué casos son
difíciles. La σ del modelo apunta en la misma dirección pero con un margen
estrecho (0.096 → 0.106), lo que sugiere que hay dificultad que el clínico ve y
el modelo no.

## Ficheros

| Fichero | Qué es |
|---|---|
| `train_reasoning_model.py` | entrenador y evaluación LOOCV |
| `model/reasoning_trace_model.joblib` | modelo + métricas + casillas conservadas |
| `../train/artifacts/reasoning_model_loo.csv` | tabla completa por casilla |

Implementación en `chimera_experts/reasoning_model.py`. Se conecta a los expertos
clasificadores mediante `BiopsyExpert.load(..., trace_model_path=...)`, y
`run_experts.py` lo carga automáticamente si existe.

Una restricción de coherencia: un experto sólo puede declarar como consultadas
las secciones que sus bloques realmente leen. Si el modelo de traza predice que
se consultó el informe radiológico pero el Experto 1 no lo lee, esa sección se
retira de su `reveal_sequence`. Declarar lo contrario sería exactamente el tipo
de afirmación no respaldada que el reto penaliza.

## Bibliografía

- Varma, S., Simon, R. *Bias in error estimation when using cross-validation for model selection.* BMC Bioinformatics 7:91, 2006.
- Kohavi, R. *A Study of Cross-Validation and Bootstrap for Accuracy Estimation and Model Selection.* IJCAI 1995.
- Hastie, T., Tibshirani, R., Friedman, J. *The Elements of Statistical Learning*, 2.ª ed., Springer 2009, cap. 7 (selección de modelo y el suelo de la clase mayoritaria).
