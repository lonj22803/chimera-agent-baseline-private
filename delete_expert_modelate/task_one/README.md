# Tarea 1 — decisión de biopsia

Cuatro expertos entrenados sobre los 91 casos con ground truth de
`data_filtered/task1`, cada uno con su veredicto y su incertidumbre.

| Experto | Qué entrega | Qué lee | Modelo | Rendimiento |
|---|---|---|---|---|
| **1** — [estructurado](expert_one/) | biopsia sí/no + incertidumbre | bloque A | Extra-Trees | AUC 0.758 [0.653, 0.854] |
| **2** — [proyector de PSA](expert_two/) | PSA a 6 meses ± IC, tendencia | psa_trend + contexto | Extra-Trees anclado + conforme | MAE(log) 0.315 · cobertura 0.952 |
| **3** — [fusión](expert_three/) | biopsia sí/no + incertidumbre | bloques A+B+D | Extra-Trees | **AUC 0.794 [0.698, 0.881]** |
| **4** — [traza de razonamiento](reasoning_model/) | `confidence`, `variable_weights`, `reveal_sequence` | bloque A | logística por casilla + puerta LOOCV | 0.722 vs 0.696 (moda) |

Cómo ejecutarlos:

```bash
python expert_two/train_expert_two.py                                   # primero: el 3 puede consumirlo
python expert_one/train_expert_one.py       --model extra_trees
python expert_three/train_expert_three.py   --blocks ABD --model extra_trees
python reasoning_model/train_reasoning_model.py
python run_experts.py --all --out ./outputs                             # inferencia sobre los 195 casos
```

---

## Lo que hay que saber antes de leer los números

**El objetivo no es «¿tiene cáncer?», es «¿el urólogo biopsiaría?».** Son
etiquetas distintas y la diferencia domina el problema:

| PI-RADS | biopsia previa | n | % «sí» |
|---|---|---|---|
| 5 | ninguna | 15 | **1.00** |
| 5 | negativa | 6 | 0.83 |
| 5 | **positiva** | 24 | **0.42** |
| 4 | ninguna | 5 | 1.00 |
| 4 | positiva | 19 | 0.58 |

Misma imagen, decisión opuesta según lo que ya se sabe del paciente. Volver a
biopsiar a quien ya tiene cáncer confirmado no aporta información nueva.

De ahí que las calculadoras de riesgo publicadas —que predicen *presencia de
cáncer*— rindan por debajo del azar en esta tarea: la regla PI-RADS ≥ 3 obtiene
sensibilidad 1.00 con especificidad 0.17, porque manda a biopsia a todo el que
tiene lesión. Y de ahí que la variable más importante de los tres clasificadores
sea `bx_positive`, no `pirads`.

**Con 91 casos, casi nada es significativo.** Los intervalos de confianza son
anchos (±0.10 de AUC) y las diferencias entre modelos razonables no lo son. Los
números de estos README sirven para **ordenar** candidatos, no como estimación
insesgada del rendimiento en el conjunto de test del reto. El protocolo, sus
limitaciones y el sesgo de selección están documentados en
[`train/README.md`](train/README.md).

---

## Resultados principales

### Comparación de clasificadores

19 candidatos × 2 conjuntos de variables, CV estratificada repetida
(`train/artifacts/bakeoff_stage1.csv`). Los seis primeros de cada conjunto:

| bloque A (39 vars) | AUC | | bloques A-E (102 vars) | AUC |
|---|---|---|---|---|
| extra_trees | 0.762 | | **extra_trees** | **0.786** |
| grad_boosting | 0.762 | | random_forest | 0.741 |
| logreg_l1 | 0.717 | | random_forest_calibrated | 0.732 |
| decision_tree | 0.715 | | decision_tree | 0.719 |
| random_forest | 0.714 | | deep_ensemble_mlp | 0.716 |
| logreg_elasticnet | 0.702 | | grad_boosting | 0.715 |
| *regla PI-RADS ≥ 3* | 0.475 | | *regla PI-RADS ≥ 3* | 0.475 |
| *regla EAU + PSAD* | 0.473 | | *regla EAU + PSAD* | 0.473 |
| *prevalencia* | 0.449 | | *prevalencia* | 0.449 |

Extra-Trees gana en las dos configuraciones, que es el único criterio de
desempate defendible con esta muestra. Los ensembles de árboles baten a los
lineales por ~0.05 de AUC (significativo frente a `logreg_l2`, p = 0.025); el
*deep ensemble* de MLP queda por debajo y peor calibrado, de modo que aquí no
compensa su coste. kNN y kNN probabilístico son los peores del grupo aprendido
(0.646–0.665): con 39-102 dimensiones y 91 casos, la distancia euclídea no
significa gran cosa.

### Qué fuente aporta qué

Ablación *leave-one-block-out* (`train/artifacts/ablation_leave_one_out.csv`):

| bloque retirado | Δ AUC | p |
|---|---|---|
| informe radiológico (D) | **−0.030** | 0.188 |
| analítica (B) | −0.009 | 0.544 |
| prompt estructurado (A) | −0.005 | 0.812 |
| serie de PSA (C) | −0.004 | 0.872 |
| notas previas (E) | **+0.004** | 0.772 |

El informe radiológico es el único bloque que aporta de forma visible. Las notas
previas restan. De ahí que el Experto 3 use **A+B+D** (AUC 0.794) y no el
conjunto completo (0.786).

### ¿Hace falta un experto sobre `prostate-modality-level-neural-representations.json`?

**No.** Sonda lineal sobre el vector de 1024 dimensiones, comparada con el
escalar `cspca` que ya viene resuelto en `structured-prompt.json`
(`train/artifacts/embedding_probe.csv`):

| predictor | n | AUC | IC 95 % |
|---|---|---|---|
| sonda lineal, PCA 4 | 89 | 0.387 | [0.267, 0.500] |
| sonda lineal, PCA 8 | 89 | 0.446 | [0.313, 0.584] |
| sonda lineal, PCA 16 | 89 | 0.416 | [0.297, 0.544] |
| sonda lineal, PCA 32 | 89 | 0.444 | [0.326, 0.576] |
| sonda lineal, PCA 64 | 89 | 0.443 | [0.321, 0.573] |
| **escalar `cspca` del prompt** | 89 | **0.560** | [0.433, 0.699] |

Todas las sondas quedan **por debajo del azar**. Entrenar una cabeza sobre el
embedding gastaría los 91 casos en reaprender, peor, algo que el organizador ya
entrega calibrado.

Conviene aclarar un punto sobre el repositorio del reto: `chimera-agent-baseline`
**no** trae un predictor de imagen entrenado. `FeatureStore` es sólo un cargador
—su propio docstring dice «the baseline does not consume features»— y
`tools/predictor.run_predictor` es un *stub* que devuelve un valor fijo con el
comentario «replace with your trained head». El único resumen de la RM realmente
disponible es el escalar `cspca`, y por eso entra en el bloque A y no como
experto aparte.

### ¿Aporta la proyección del Experto 2 al clasificador?

**No.** Se entrenó el Experto 3 con y sin el bloque G (la salida del Experto 2
como variables):

| variante | vars | AUC CV | AUC LOO | AUC envoltorio | Brier |
|---|---|---|---|---|---|
| **ABD** | 75 | **0.794** | **0.791** | **0.811** | 0.180 |
| ABD + G (Experto 2) | 80 | 0.792 | 0.784 | 0.802 | 0.179 |

La proyección aprendida no añade nada sobre lo que el PSA actual ya dice, algo
que la ablación del bloque C (−0.004, p = 0.87) ya anticipaba. El Experto 2 sigue
siendo útil, pero como **salida independiente para el deliberador**, no como
variable del clasificador: responde a otra pregunta.

### Las escaleras de fiabilidad

Todo out-of-fold.

| tramo | `confidence` | Experto 1 | | Experto 3 | |
|---|---|---|---|---|---|
| | | n | acierto | n | acierto |
| `firm` | `clear` | 33 | **0.879** | 36 | 0.861 |
| `supports` | `borderline` | 20 | 0.600 | 24 | **0.708** |
| `discuss` | `uncertain` | 38 | 0.553 | 31 | **0.613** |

El acierto cae de forma monótona en los dos. Si no cayera, la incertidumbre no
estaría midiendo nada.

La fusión no mejora el tramo alto —el experto barato ya acierta 9 de cada 10 ahí—
sino los dos difíciles, y encoge el tramo `discuss` de 38 casos a 31. Leer el
texto libre sirve sobre todo para **rescatar casos que el experto barato no
resolvía**.

### Validación externa del ordenamiento de dificultad

Los casos que el urólogo marcó como inciertos son los que el modelo falla:

| confianza del urólogo | n | acierto del Experto 1 |
|---|---|---|
| `clear` | 58 | 0.724 |
| `borderline` | 18 | 0.611 |
| `uncertain` | 15 | 0.533 |

Dos estimadores independientes —un clínico y un ensemble— coinciden en qué casos
son difíciles.

---

## Cómo se usa esto en la deliberación

`run_experts.py` procesa los 195 casos en 2 min 48 s (inferencia en lote) y
produce por caso:

- `prostate-biopsy-decision.json` y `prostate-biopsy-decision-reasoning.json` — los dos ficheros que el reto exige;
- `expert-panel.json` — la carga ampliada: probabilidad e incertidumbre descompuesta de cada experto, tramo de fiabilidad, proyección de PSA con su intervalo, e importancia de las variables.

> **Aviso.** `run_experts.py --all` incluye los 91 casos con ground truth, que
> son los mismos con los que se ajustaron los expertos. Comparar esas
> predicciones con sus etiquetas da un 0.945 de acierto que **no es
> rendimiento**: es memorización. Las cifras válidas son las out-of-fold de las
> tablas anteriores. El modo `--all` está para generar salidas, no para evaluar.

El **portavoz** del panel no es una votación por mayoría. Es el experto de mayor
fiabilidad medida: entre los que están en el tramo más alto, gana el de mejor AUC
out-of-fold. Promediar dos expertos que leen las mismas variables no es una
segunda opinión —sus errores están correlacionados— y disfrazaría de consenso lo
que es un único punto de vista. Cuando ningún experto pasa de `discuss`, el panel
lo dice explícitamente y deja la decisión abierta: es para eso que existe la
escalera.

---

## Limitaciones, dichas de frente

1. **n = 91.** Los intervalos de AUC miden ±0.10. Casi ninguna diferencia entre modelos razonables es significativa.
2. **Sesgo de selección.** El modelo se elige y se evalúa sobre la misma validación cruzada. Con 19 candidatos, el AUC del ganador está optimistamente sesgado en torno a +0.02–0.04 (Varma y Simon 2006).
3. **La serie `psa_trend` es sólo parcialmente coherente** con el PSA del caso: `psap` coincide con el penúltimo punto en 8 de 195 casos. Detalle y consecuencias en [`expert_two/README.md`](expert_two/README.md).
4. **La cohorte casi no tiene enfermedad localmente avanzada.** Las columnas de invasión de vesículas seminales y adenopatías quedan sin varianza.
5. **Algunas importancias son ruido.** `pmhx_hypercholesterolaemia` aparece cuarta en el Experto 1 y no hay mecanismo que lo justifique. Se publica en lugar de podarse.
6. **El corpus es sintético o pseudonimizado**, con al menos 8 series de PSA fisiológicamente implausibles. Nada de lo medido aquí es evidencia clínica.
7. **El reparto de tramos del panel sobre los 195 casos** (73 `firm`, 58 `supports`, 64 `discuss`) mezcla casos vistos y no vistos en entrenamiento. Sobre los 104 sin ground truth —los que el reto evaluará— el reparto es 32 / 34 / 38, es decir, un tercio de los casos llega al tramo alto.

## Bibliografía

Completa en [`train/README.md`](train/README.md). Las referencias que sostienen
cada decisión concreta están en el README del experto correspondiente.
