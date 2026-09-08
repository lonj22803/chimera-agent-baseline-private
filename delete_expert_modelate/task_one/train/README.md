# `train/` — el laboratorio de la Tarea 1

Aquí vive **todo lo que se corrió** para decidir cómo son los tres expertos. Ningún
número de los README de los expertos se ha puesto a ojo: cada uno sale de un CSV
de `artifacts/`, y cada CSV sale de un script de este directorio.

## Cómo reproducirlo

```bash
cd expert_modelate/task_one/train
python run_bakeoff.py       # comparación de 19 clasificadores × 2 conjuntos de variables
python run_ablation.py      # ablación por bloques + sonda sobre el vector neuronal de RM
```

El bakeoff tarda ~1 h y la ablación ~40 min en una CPU de sobremesa. Los
entrenadores de cada experto viven en sus propias carpetas y aceptan `--model`
para saltarse la selección cuando ya se conoce el ganador.

Semilla global `SEED = 20260907` (`chimera_experts/evaluation.py`). Todo es
reproducible bit a bit con esa semilla.

---

## 1. El problema estadístico, antes que el algorítmico

91 casos etiquetados (56 `yes`, 35 `no`) y ~100 variables candidatas. Con esa
proporción, la elección de modelo se decide en la tercera cifra decimal y es
trivial auto-engañarse. Tres decisiones de protocolo salen de ahí:

**No se usa una partición train/test fija.** Con 91 casos, un test del 20 % son
18 casos: el error típico de un AUC estimado sobre 18 casos es de ±0.13. Sería
ruido con formato de resultado.

**La métrica primaria es validación cruzada estratificada repetida (5 × 20),
no leave-one-out.** En muestras pequeñas la varianza dominante de LOOCV viene de
la partición concreta, no del modelo; repetir la validación con 20 semillas
distintas y promediar reduce esa componente, que es el argumento de Kohavi
(IJCAI 1995). LOOCV se reporta igualmente como métrica secundaria porque es
determinista y por tanto comparable entre ejecuciones, pero no es la que decide.

**Los intervalos son bootstrap sobre los casos (2000 réplicas), y las
comparaciones entre modelos son bootstrap *pareado*.** Comparar dos modelos
mirando si sus intervalos se solapan es un error estadístico conocido: los dos
se evalúan sobre los mismos casos, de modo que sus errores están correlacionados
y el test correcto es sobre la *diferencia*. `bakeoff_pairwise.csv` contiene esas
diferencias con su intervalo y su valor p.

Una advertencia que conviene tener presente al leer los resultados: el modelo se
**selecciona** y se **evalúa** sobre la misma validación cruzada, de modo que el
AUC del ganador está optimistamente sesgado por selección (Varma y Simon, *BMC
Bioinformatics* 2006). Con 19 candidatos y n = 91 ese sesgo es del orden de
+0.02–0.04 de AUC. Las cifras de los README son útiles para **ordenar** los
candidatos entre sí, no como estimación insesgada del rendimiento en el conjunto
de test del reto.

---

## 2. Qué se comparó

### Clasificadores (`run_bakeoff.py`, 19 candidatos)

| Familia | Candidatos | Por qué está |
|---|---|---|
| Suelos | `prior_only`, `rule_pirads3`, `rule_eau_psad` | Sin batirlos, no hay nada que contar |
| Lineales | `logreg_l2`, `logreg_l1`, `logreg_elasticnet`, `lda` | La forma funcional de las calculadoras validadas (ERSPC/RPCRC, PBCG) |
| Árboles | `decision_tree`, `random_forest`, `extra_trees`, `random_forest_calibrated`, `grad_boosting`, `hist_gradient_boosting` | No linealidades e interacciones; `hist_gradient_boosting` admite NaN nativamente |
| Instancias / márgenes | `knn`, `knn_probabilistic`, `svm_rbf`, `svm_linear`, `gaussian_nb` | Familias que el usuario pidió comparar explícitamente |
| Redes | `deep_ensemble_mlp` | El método de referencia para incertidumbre epistémica (Lakshminarayanan 2017), como control de coste/beneficio |

Los dos suelos de guía clínica merecen una nota. `rule_pirads3` es la lectura
literal de PI-RADS v2.1 (categoría ≥ 3 → biopsia); `rule_eau_psad` es la
recomendación EAU 2024 (PI-RADS ≥ 4, o PI-RADS 3 con densidad de PSA ≥ 0.15).
Ambas se implementan como clasificadores cuya *decisión* es la regla pero cuya
*probabilidad* se calibra con la frecuencia empírica de cada rama, para que sean
comparables en Brier y ECE con el resto.

### Regresores del proyector de PSA (`../expert_two/train_expert_two.py`)

Ridge, Bayesian ridge, Huber, bosque aleatorio, Extra-Trees y *gradient
boosting*, cada uno en versión directa y en versión **anclada** (aprende el
incremento sobre `log(PSA)` de la última medida en lugar del nivel absoluto).
Contra dos suelos: repetir el último valor, y extrapolar la recta log-lineal.

---

## 3. Cómo se mide la incertidumbre, y por qué así

Un veredicto sin incertidumbre no le sirve a un deliberador: si no sabe cuánto
fiarse, no puede integrarlo. Se reportan **tres magnitudes separadas**, porque
responden a preguntas distintas y se reducen por vías distintas.

**σ_modelo (epistémica del modelo)** — desviación típica de la probabilidad entre
los miembros del *bagging*: cuánto se movería la respuesta con otra muestra de
entrenamiento. Es la receta de los *deep ensembles* (Lakshminarayanan, Pritzel y
Blundell, NeurIPS 2017) aplicada a estimadores clásicos. Baja con más datos.

**σ_ausencia (epistémica por datos faltantes)** — desviación típica entre
imputaciones múltiples del mismo caso. Es el término *between-imputation* de las
reglas de Rubin (1987). Vale **exactamente cero** en un caso completo y crece con
cada variable ausente. Esta es la pieza que responde al requisito del reto de que
la incertidumbre aumente cuando faltan modalidades: no se postula un factor de
penalización, se **mide** volviendo a imputar y viendo cuánto se mueve la
respuesta.

**H (aleatoria)** — entropía normalizada de la probabilidad media: cuánto se
contradijo el urólogo entre pacientes que el modelo no distingue. No baja con más
datos del mismo tipo. La separación sigue a Depeweg et al. (ICML 2018).

Las dos epistémicas **sí** se suman en cuadratura: son varianzas de la misma
cantidad bajo dos fuentes independientes de variación, que es la condición bajo
la que las reglas de Rubin lo autorizan. La aleatoria **no** se suma a ellas.
Mezclar una varianza de Bernoulli con un error típico produce una barra de
anchura casi constante en todos los casos, que no discrimina nada: se probó y se
descartó.

### La escalera operativa

| tramo | criterio | `confidence` de CHIMERA |
|---|---|---|
| `firm` | `p ± 1.96·σ` no cruza 0.5 | `clear` |
| `supports` | `p ± σ` no cruza 0.5 | `borderline` |
| `discuss` | `p ± σ` cruza 0.5 | `uncertain` |

Es abstención informada: la propiedad que separa una probabilidad útil de un
número (Guo et al., ICML 2017; Niculescu-Mizil y Caruana, ICML 2005). Los tramos
publicados en los README de cada experto están medidos **out-of-fold** — un tramo
`firm` calculado sobre los datos de entrenamiento sería trivialmente perfecto.

### El intervalo del proyector de PSA es de otra clase

Para el Experto 2 no se usa el ensemble sino **predicción conforme jackknife+**
(Barber, Candès, Ramdas y Tibshirani, *Ann Statist* 2021), que garantiza
cobertura en muestra finita sin suponer que el modelo sea correcto ni que los
residuos sean normales. Con esa garantía, todos los métodos cubren el 95 %; lo que
los distingue es la **anchura** de la banda, y ahí es donde se ve qué regresor es
mejor.

---

## 4. Ficheros de `artifacts/`

| Fichero | Contenido |
|---|---|
| `bakeoff_stage1.csv` | 19 candidatos × 2 conjuntos de variables, CV 5×10 |
| `bakeoff_stage2.csv` | finalistas con CV 5×20, LOOCV e IC bootstrap |
| `bakeoff_pairwise.csv` | comparaciones pareadas contra el campeón y contra la regla EAU |
| `bakeoff_oof.npz` | probabilidades out-of-fold crudas, para reanálisis |
| `missingness_ABCDE.csv` | tasa de ausencia por variable |
| `ablation_blocks.csv` | AUC por combinación de bloques de variables |
| `ablation_leave_one_out.csv` | pérdida de AUC al quitar cada bloque |
| `embedding_probe.csv` | sonda lineal sobre el vector de RM frente al escalar `cspca` |
| `psa_projector_bakeoff.csv` | comparación de regresores del Experto 2 |
| `psa_projector_coverage.csv` | cobertura y anchura del intervalo conforme |
| `expert_*_selection.csv` | tabla de selección de cada experto |
| `expert_*_importance.csv` | importancia de permutación out-of-fold |
| `expert_*_oof.csv` | probabilidad, σ y completitud out-of-fold por caso |
| `reasoning_model_loo.csv` | acierto LOOCV por casilla del formulario, frente a la moda |
| `reasoning_model_summary.json` | casillas que conservan modelo y acierto del híbrido |

---

## 5. Bibliografía del protocolo

**Validación y selección**
- Kohavi, R. *A Study of Cross-Validation and Bootstrap for Accuracy Estimation and Model Selection.* IJCAI 1995.
- Varma, S., Simon, R. *Bias in error estimation when using cross-validation for model selection.* BMC Bioinformatics 7:91, 2006.
- Efron, B., Tibshirani, R. *An Introduction to the Bootstrap.* Chapman & Hall, 1993.

**Incertidumbre y calibración**
- Lakshminarayanan, B., Pritzel, A., Blundell, C. *Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles.* NeurIPS 2017.
- Depeweg, S., Hernández-Lobato, J.M., Doshi-Velez, F., Udluft, S. *Decomposition of Uncertainty in Bayesian Deep Learning for Efficient and Risk-sensitive Learning.* ICML 2018.
- Guo, C., Pleiss, G., Sun, Y., Weinberger, K.Q. *On Calibration of Modern Neural Networks.* ICML 2017.
- Niculescu-Mizil, A., Caruana, R. *Predicting Good Probabilities With Supervised Learning.* ICML 2005.
- Brier, G.W. *Verification of forecasts expressed in terms of probability.* Mon Weather Rev 78:1-3, 1950.

**Datos ausentes**
- Rubin, D.B. *Multiple Imputation for Nonresponse in Surveys.* Wiley, 1987.
- van Buuren, S., Groothuis-Oudshoorn, K. *mice: Multivariate Imputation by Chained Equations in R.* J Stat Softw 45(3), 2011.

**Predicción conforme**
- Barber, R.F., Candès, E.J., Ramdas, A., Tibshirani, R.J. *Predictive inference with the jackknife+.* Ann Statist 49(1):486-507, 2021.
- Vovk, V., Gammerman, A., Shafer, G. *Algorithmic Learning in a Random World.* Springer, 2005.

**Modelos**
- Breiman, L. *Bagging Predictors.* Mach Learn 24:123-140, 1996.
- Breiman, L. *Random Forests.* Mach Learn 45:5-32, 2001.
- Geurts, P., Ernst, D., Wehenkel, L. *Extremely randomized trees.* Mach Learn 63:3-42, 2006.
- Fisher, A., Rudin, C., Dominici, F. *All Models are Wrong, but Many are Useful: Learning a Variable's Importance...* JMLR 20(177), 2019.

**Extracción de texto clínico**
- Chapman, W.W., Bridewell, W., Hanbury, P., Cooper, G.F., Buchanan, B.G. *A simple algorithm for identifying negated findings and diseases in discharge summaries.* J Biomed Inform 34(5):301-310, 2001.
- Alain, G., Bengio, Y. *Understanding intermediate layers using linear classifier probes.* ICLR 2017 (workshop).

**Dominio clínico**
- Turkbey, B. et al. *Prostate Imaging Reporting and Data System Version 2.1.* Eur Urol 76(3):340-351, 2019.
- EAU-EANM-ESTRO-ESUR-ISUP-SIOG *Guidelines on Prostate Cancer*, edición 2024.
- Kasivisvanathan, V. et al. *MRI-Targeted or Standard Biopsy for Prostate-Cancer Diagnosis* (PRECISION). N Engl J Med 378:1767-1777, 2018.
- Roobol, M.J. et al. *Rotterdam Prostate Cancer Risk Calculator.* JMIR Mhealth Uhealth 5(3):e29, 2017.
- Alberts, A.R. et al. *Prediction of High-grade Prostate Cancer Following Multiparametric MRI: Improving the Rotterdam ERSPC Risk Calculators.* Eur Urol 75(2):310-318, 2019.
- Ankerst, D.P. et al. *Prostate Biopsy Collaborative Group Risk Calculator.* J Urol 200(6):1216-1222, 2018.
- Catalona, W.J. et al. *Use of the percentage of free prostate-specific antigen to enhance differentiation of prostate cancer from benign prostatic disease.* JAMA 279(19):1542-1547, 1998.
- Carter, H.B. et al. *Longitudinal evaluation of prostate-specific antigen levels in men with and without prostate disease.* JAMA 267(16):2215-2220, 1992.
- Pound, C.R. et al. *Natural history of progression after PSA elevation following radical prostatectomy.* JAMA 281(17):1591-1597, 1999.
- Thompson, I.M. et al. *The influence of finasteride on the development of prostate cancer.* N Engl J Med 349:215-224, 2003.
- Kicinski, M., Vangronsveld, J., Nawrot, T.S. *An epidemiological reappraisal of the familial aggregation of prostate cancer.* PLoS One 6(10):e27130, 2011.
- Charlson, M.E. et al. *A new method of classifying prognostic comorbidity in longitudinal studies.* J Chronic Dis 40(5):373-383, 1987.
