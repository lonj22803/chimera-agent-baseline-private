# Experto 2 — proyección del PSA

**Qué hace.** Dada la serie de PSA de un paciente y su contexto clínico, proyecta
el valor esperado a un horizonte (6 meses por defecto), con un intervalo de
cobertura garantizada, y declara si la tendencia sube, baja, o no es resoluble.

**Qué lee.** `prostate-biopsy-decision-clinical-data.json` → `psa_trend` y
`laboratory_results`; `structured-prompt.json` → edad, volumen prostático,
PI-RADS y medicación.

**Qué entrega.** Un `PSAProjection`: valor proyectado, intervalo al 95 %,
dirección (`rising` / `falling` / `indeterminate`) con su confianza, tiempo de
duplicación del PSA, velocidad en ng/mL/año, y la calidad del ajuste.

**Modelo.** Extra-Trees anclado sobre `log(PSA)`, con intervalo conforme
*jackknife+*.

---

## Por qué este modelo

### Por qué se regresa `log(PSA)` y no `PSA`

El PSA de esta cohorte va de 0.2 a 190 ng/mL. Un error cuadrático en escala
natural estaría dominado por media docena de pacientes y el modelo se ajustaría
a ellos. Además, en enfermedad activa el PSA crece de forma aproximadamente
exponencial, de modo que `log(PSA)` es lineal en el tiempo y su pendiente tiene
significado clínico directo: es el *PSA doubling time*, PSADT = ln 2 / pendiente,
la formulación de Pound et al. (*JAMA* 1999) y el estándar operativo en
seguimiento de cáncer de próstata.

### Por qué el modelo va **anclado**

Un ensemble de árboles no extrapola: promedia hojas. La primera versión de este
experto, entrenada para predecir el nivel absoluto de `log(PSA)`, proyectaba un
paciente con PSA de 187 ng/mL hacia 55 ng/mL — un descenso — porque arrastraba la
predicción hacia el centro de la cohorte. En un paciente con un PSADT de 3.5
meses eso es un fallo grave y además silencioso.

La corrección es reparametrizar: el regresor aprende el **incremento** sobre
`log(PSA)` de la última medida, y la predicción es `ancla + incremento`. La
regresión a la media pasa entonces a tirar del *cambio* hacia cero —"sin
cambio", el prior conservador correcto— en lugar de tirar del *nivel* hacia la
media de la cohorte. Es la misma idea que modelar diferencias en series no
estacionarias (Box y Jenkins 1970, cap. 4). El anclaje mejoró todas las métricas
y estrechó el intervalo (ver tabla).

### Por qué el intervalo es conforme y no de Student

El intervalo de predicción de una regresión lineal supone que el modelo es
correcto y que los residuos son normales. Con un ensemble de árboles sobre 373
ejemplos, ninguna de las dos cosas es defendible. La predicción conforme
*jackknife+* (Barber, Candès, Ramdas y Tibshirani, *Ann Statist* 2021) garantiza
cobertura de al menos 1 − 2α en muestra finita bajo el único supuesto de
intercambiabilidad. Es lo único que hace honesto el `±` que se le entrega al
deliberador.

Consecuencia práctica: **todos** los métodos cubren el 95 % — eso lo garantiza la
construcción. Lo que los distingue es la **anchura** de la banda. Por eso la tabla
de cobertura es la tabla que decide.

### De dónde salen los datos de entrenamiento

El proyector no necesita la etiqueta de biopsia, así que entrena con los **195
casos**, no sólo con los 91 etiquetados. Cada serie aporta ejemplos por prefijos
(predecir el punto *k* a partir de los *k−1* anteriores): 373 ejemplos de 195
pacientes.

La validación cruzada va **agrupada por paciente** (`GroupKFold`). Es obligatorio:
dos prefijos del mismo paciente comparten casi toda la serie, y repartirlos entre
entrenamiento y test inflaría la métrica sin que nada lo delatara.

---

## Resultados

Validación cruzada agrupada por paciente, 5 particiones × 6 semillas, 373
ejemplos de 195 pacientes. Fuente: `../train/artifacts/psa_projector_bakeoff.csv`.

| modelo | MAE log | RMSE log | error relativo mediano | R² |
|---|---|---|---|---|
| **extra_trees_anchored** | **0.315** | **0.551** | 16.1 % | **0.600** |
| extra_trees | 0.321 | 0.560 | 15.6 % | 0.587 |
| random_forest | 0.332 | 0.580 | 15.8 % | 0.557 |
| random_forest_anchored | 0.334 | 0.574 | 17.8 % | 0.566 |
| grad_boosting | 0.351 | 0.587 | 21.1 % | 0.546 |
| grad_boosting_anchored | 0.353 | 0.588 | 20.9 % | 0.545 |
| huber / huber_anchored | 0.357 | 0.593 | 19.4 % | 0.536 |
| ridge_anchored | 0.377 | 0.597 | 24.9 % | 0.530 |
| ridge | 0.378 | 0.599 | 25.2 % | 0.528 |
| bayesian_ridge | 0.385 | 0.596 | 27.5 % | 0.531 |
| *suelo:* repetir el último valor | 0.618 | 0.822 | 54.8 % | 0.111 |
| *suelo:* extrapolación log-lineal | 0.619 | 1.073 | 13.5 % | **−0.517** |

Dos lecturas importan aquí.

**El aprendizaje sí se justifica.** El ganador reduce el MAE a la mitad frente a
los dos suelos (0.315 frente a 0.618 y 0.619).

**Extrapolar linealmente es peor que no hacer nada.** El R² de la extrapolación
log-lineal es **negativo**: prolongar la recta ajustada a una serie de 2-4 puntos
ruidosos da peores predicciones que devolver la media de la cohorte. Su error
relativo *mediano* es engañosamente bueno (13.5 %) porque acierta en los casos
fáciles y se dispara catastróficamente en los difíciles — que es exactamente el
perfil de error que no se quiere en una ayuda a la decisión.

### Cobertura y anchura del intervalo

Fuente: `../train/artifacts/psa_projector_coverage.csv`.

| modelo | cobertura empírica | anchura mediana (factor) |
|---|---|---|
| **extra_trees_anchored** | 0.952 | **×3.49** |
| extra_trees | 0.952 | ×3.65 |
| random_forest_anchored | 0.952 | ×3.65 |
| grad_boosting_anchored | 0.952 | ×3.87 |
| ridge / huber / bayesian_ridge | 0.952 | ×4.03 – ×4.13 |
| repetir el último valor | 0.952 | ×5.50 |
| extrapolación log-lineal | 0.952 | ×12.25 |

A igual cobertura, el ganador da una banda **3.5 veces más estrecha** que la
extrapolación log-lineal. Ése es el valor real del aprendizaje: no acertar más a
menudo, sino poder prometer lo mismo diciendo mucho más.

---

## Limitación conocida de estos datos

La serie `psa_trend` de este corpus es sólo **parcialmente coherente** con el PSA
del caso:

- `psa` coincide con el último punto de la serie en 194 de 195 casos;
- `psap` (el PSA previo del prompt estructurado) coincide con el **penúltimo**
  punto en apenas **8 de 195**;
- `log(psap)` predice `log(psa)` con **R² = 0.944**, mientras que el penúltimo
  punto de la serie sólo llega a **R² = 0.507**.

Es decir: hay dos historias de PSA en el caso y no son la misma. El proyector se
valida contra la más ruidosa de las dos, porque es la única con estructura
temporal explícita. El efecto es que su intervalo resulta **conservador** —
demasiado ancho más que demasiado estrecho—, que es el sentido correcto del
error, pero conviene saberlo antes de leer la anchura de la banda como si fuera
fisiología. Ocho casos de la cohorte tienen un salto final de la serie
fisiológicamente implausible (3.3 → 187 ng/mL, 19.1 → 190 ng/mL) que ningún
modelo puede anticipar desde la historia previa.

---

## Variables que usa

De la serie: número de puntos, intervalo temporal, hueco hasta el horizonte,
`log(PSA)` primero / último / medio / mínimo / máximo, desviación típica en log,
pendiente log por mes, sigma residual del ajuste, **la propia predicción
log-lineal** (para que el regresor sólo tenga que aprender su sesgo), último
salto y su duración, monotonía, y razón respecto al nadir.

Del contexto: edad, `log(volumen prostático)`, % de PSA libre, testosterona,
PI-RADS, y dos indicadores de medicación — inhibidores de la 5-alfa-reductasa y
alfa-bloqueantes. Los 5-ARI reducen el PSA en torno a un 50 % (Thompson et al.,
*NEJM* 2003) y rompen cualquier extrapolación que los ignore.

---

## Ficheros

| Fichero | Qué es |
|---|---|
| `train_expert_two.py` | entrenador: bakeoff de regresores, cobertura, ajuste final |
| `model/expert_two_psa_projector.joblib` | modelo + residuos de calibración + metadatos |
| `demo_expert_two.ipynb` | comportamiento con los datos: trayectorias, cobertura, tendencias |
| `../train/artifacts/psa_projector_bakeoff.csv` | tabla de comparación |
| `../train/artifacts/psa_projector_coverage.csv` | tabla de cobertura |

Implementación en `chimera_experts/psa_projector.py` (modelo, `AnchoredRegressor`,
`jackknife_plus_interval`) y `chimera_experts/features_psa.py` (parseo de fechas,
ajuste de trayectoria, PSADT).

## Bibliografía

- Barber, R.F., Candès, E.J., Ramdas, A., Tibshirani, R.J. *Predictive inference with the jackknife+.* Ann Statist 49(1):486-507, 2021.
- Geurts, P., Ernst, D., Wehenkel, L. *Extremely randomized trees.* Mach Learn 63:3-42, 2006.
- Box, G.E.P., Jenkins, G.M. *Time Series Analysis: Forecasting and Control.* Holden-Day, 1970.
- Pound, C.R. et al. *Natural history of progression after PSA elevation following radical prostatectomy.* JAMA 281(17):1591-1597, 1999.
- Carter, H.B. et al. *Longitudinal evaluation of prostate-specific antigen levels in men with and without prostate disease.* JAMA 267(16):2215-2220, 1992.
- Thompson, I.M. et al. *The influence of finasteride on the development of prostate cancer.* N Engl J Med 349:215-224, 2003.
- Vovk, V., Gammerman, A., Shafer, G. *Algorithmic Learning in a Random World.* Springer, 2005.
