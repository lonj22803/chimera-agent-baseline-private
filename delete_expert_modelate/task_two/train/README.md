# Tarea 2 — protocolo experimental

Todo lo que se mide aquí sale de los **72 casos con ground truth** de
`data/task2/ground_truth`. Los 153 casos de `agent_input` se usan sólo para
ajustar la PCA de los embeddings, que es una transformación no supervisada y
por tanto no filtra la etiqueta.

## La métrica no se elige

El evaluador oficial (`evaluation/evaluate.py` del repositorio del reto) puntúa
la recomendación con **acierto exacto** y trata el resultado como una **puerta**:

```python
if ds == 0.0:
    base["gate"] = f"{task}_decision_failed"
    return base          # case_score = 0
```

No hay crédito parcial entre `active_surveillance` y `continued_surveillance`.
Un caso con la conducta equivocada puntúa cero aunque el formulario de
razonamiento sea perfecto. De ahí que el criterio principal de todos los
experimentos sea el acierto de las cuatro clases y no el F1 macro, que
premiaría un modelo mejor repartido pero peor puntuado.

Se reportan además F1 macro y acierto equilibrado —porque un modelo que sólo
acierta la clase mayoritaria es una respuesta distinta a la misma cifra— y el
Brier multiclase y el ECE, porque un experto que va a una junta con una
probabilidad mal calibrada estropea la deliberación aunque acierte.

## Validación

**Leave-one-out** como protocolo principal. Con 72 casos y una clase de dos
(`watchful_waiting`), cualquier partición en *k* pliegues deja pliegues sin esa
clase; LOO es la única que la conserva siempre en entrenamiento y además no
depende de una semilla. El coste —72 ajustes— es asumible con estos modelos.

Como segunda vista, **CV estratificada 4×5 repetida**, que entrena con
particiones más pequeñas —la situación real del reto— y cuya dispersión entre
repeticiones dice cuánto de lo medido depende del reparto.

Las diferencias entre modelos se contrastan con **bootstrap pareado** sobre los
mismos casos. Comparar dos intervalos marginales que se solapan no dice nada
sobre cuál de los dos modelos es mejor caso a caso.

## Los suelos, publicados con los resultados

| suelo | qué hace | acierto LOO |
|---|---|---|
| `prior_only` | devuelve siempre la distribución de entrenamiento | 0.4306 |
| `grade_rule` | mapa `ISUP grade group → conducta`, **reajustado en cada pliegue** | **0.8611** |

El segundo es el que importa. El ground truth se derivó retrospectivamente de
la histopatología y del PSA según EAU/NCCN, de modo que un mapa de un solo
predictor explica 62 de los 72 casos. Cualquier modelo aprendido que no lo bata
no es un resultado.

La regla **no** trae el mapa escrito: lo estima por clase mayoritaria dentro de
cada grado en la partición de entrenamiento. Así el suelo se mide con el mismo
protocolo que los modelos y no queda inflado por haber mirado las etiquetas de
prueba.

## El techo, también

Cinco de los 72 casos comparten perfil de guía **exacto** —mismo ISUP, mismos
patrones de Gleason, mismo estadio, mismo tramo de PSA, mismo PI-RADS— con otro
caso de etiqueta distinta:

| perfil | casos y etiquetas |
|---|---|
| ISUP 1, 3+3, cT1c, PSA<10, PI-RADS 2 | T2-001 `active_surveillance` · T2-108 `continued_surveillance` |
| ISUP 1, 3+3, cT1c, PSA<10, PI-RADS 4 | 9 × `active_surveillance` · T2-043 `active_treatment` |
| ISUP 2, 3+4, cT1c, PSA<10, PI-RADS 4 | T2-008 `active_surveillance` · T2-032 `watchful_waiting` · 2 × `active_treatment` |
| ISUP 0, 0+0, cT1c, PSA≥10, PI-RADS 5 | T2-018 `active_surveillance` · T2-059 `continued_surveillance` |

Ningún clasificador que lea esas variables puede acertar los cinco a la vez. El
**techo de consistencia es 0.931**, y la regla de guía está en 0.861: la
distancia entre ambas cifras son cinco casos.

## ¿Se puede saber dónde falla la regla?

No. Se entrenó un detector binario del objetivo *«la regla falla en este caso»*
(10 positivos de 72), leave-one-out, un bloque cada vez:

| bloque | AUC | fallos en el top-10 de sospecha |
|---|---|---|
| grado (G) | 0.631 | 3 / 10 |
| serie de PSA (C) | 0.618 | 2 / 10 |
| embeddings (J+K) | 0.518 | 1 / 10 |
| todos (ACDGHIJK) | 0.463 | 0 / 10 |
| patología (H) | 0.444 | 2 / 10 |
| clínico (A) | 0.395 | 0 / 10 |
| radiología (D) | 0.363 | 0 / 10 |
| fragilidad (I) | 0.277 | 0 / 10 |

Con 10 positivos, un AUC de 0.63 y uno de 0.28 son el mismo resultado: ruido.
Las excepciones son juicio clínico idiosincrásico —y al menos dos son
inconsistencias de anotación: el texto libre de T2-031 dice *«patient with 2
negative biopsies»* en un caso con ISUP 2 y Gleason 4+3—. **Ningún especialista
va a corregir la regla de forma sistemática con esta muestra.**

Esto no invalida el panel: cambia su propósito. Los expertos no están para
sobrescribir la guía sino para **decir cuándo su margen es estrecho**, y ahí sí
hay señal medible —el margen de la propia regla separa 0.904 de acierto (n=52)
de 0.750 (n=20).

## Scripts

```bash
python run_bakeoff.py --stage 1 --blocks AG        # 17 candidatos, un conjunto fijo
python run_bakeoff.py --stage 2 --model extra_trees # el ganador contra 20 combinaciones
python run_architecture.py extra_trees              # plano vs cascada vs panel
python run_ablation.py extra_trees                  # leave-one-block-out y block-only
```

Los artefactos se escriben en `artifacts/` como CSV.

## Bibliografía

* Mottet N. *et al.*, *EAU-EANM-ESTRO-ESUR-SIOG Guidelines on Prostate Cancer*, Eur Urol 2021.
* NCCN Clinical Practice Guidelines in Oncology: Prostate Cancer, v4.2024.
* Epstein J.I. *et al.*, *A Contemporary Prostate Cancer Grading System*, Eur Urol 2016.
* Varma S., Simon R., *Bias in error estimation when using cross-validation for model selection*, BMC Bioinformatics 2006.
* Breiman L., *Bagging Predictors*, Mach Learn 1996.
* Depeweg S. *et al.*, *Decomposition of Uncertainty in Bayesian Deep Learning*, ICML 2018.
* Rubin D.B., *Multiple Imputation for Nonresponse in Surveys*, Wiley 1987.
* Silla C.N., Freitas A.A., *A survey of hierarchical classification*, Data Min Knowl Discov 2011.
* Chapman W.W. *et al.*, *A Simple Algorithm for Identifying Negated Findings*, J Biomed Inform 2001.
* Kweldam C.F. *et al.*, *Cribriform growth is highly predictive for postoperative metastasis*, Mod Pathol 2015.
