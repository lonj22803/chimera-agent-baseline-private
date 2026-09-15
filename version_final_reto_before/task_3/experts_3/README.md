# Tarea 3 — cinco expertos (paso 5.3)

75 casos, 19 eventos. Cox de Breslow con ridge fuerte (alpha 1/10); 5 pliegues externos × 5 semillas y 3 internos. Poda, imputación media, escalado y PCA se ajustan dentro de cada entrenamiento. Se eligen 1/2/4 componentes dentro de la CV interna. Fusión usa un componente estructurado y 1/2/4 de embeddings: máximo cinco coeficientes. Las cargas PCA también se estiman con pocos casos: limitar coeficientes no elimina el riesgo de sobreajuste.

Cada predicción publicada promedia cinco predicciones fuera de muestra. IC percentil de 1000 remuestreos de casos; son condicionales a las predicciones, no incluyen incertidumbre de reentrenamiento ni selección. Las AUC IPCW y la semántica Harrell se extraen como funciones puras del evaluador oficial, sin ejecutar el juez.

## Comparativa

| experto | c-index | IC 95% (1000) | AUC 12 / 24 / 36 / 60 |
|---|---:|---|---|
| expert_one | 0.7372 | [0.5918, 0.8597] | 0.8058 / 0.7698 / 0.7719 / 0.7523 |
| expert_two | 0.7726 | [0.6533, 0.8843] | 0.8086 / 0.7626 / 0.7659 / 0.8443 |
| expert_three | 0.7106 | [0.558, 0.8527] | 0.7015 / 0.7134 / 0.7193 / 0.7536 |
| expert_four | 0.8319 | [0.7358, 0.9107] | 0.8676 / 0.8294 / 0.8399 / 0.9096 |
| expert_five | 0.7372 | [0.5918, 0.8597] | 0.8058 / 0.7698 / 0.7719 / 0.7523 |
| baseline actual (referencia histórica) | 0.6636 | no disponible | no disponible |
| CAPRA-S crudo (referencia histórica) | 0.7372 | ver ancla medida | ver ancla medida |
| constante 60 meses | 0.5000 | [0.5000, 0.5000] | 0.5 / 0.5 / 0.5 / 0.5 |

Las referencias históricas no se reestiman como si se dispusiera de sus predicciones. El score CAPRA-S y el grupo de riesgo por caso se publican en expert_one_report.json.

- expert_two: Δ frente al ancla +0.0354, IC pareado [-0.0643882049240864, 0.15001344086021506]. Supera puntualmente al ancla; no implica una mejora demostrada.
- expert_three: Δ frente al ancla -0.0265, IC pareado [-0.24444659341054392, 0.19233295964125552]. No aporta frente al ancla.
- expert_four: Δ frente al ancla +0.0947, IC pareado [-0.02108114607668001, 0.22708388696961646]. Supera puntualmente al ancla; no implica una mejora demostrada.

## Sondas históricas rehechas con Cox y CV anidada

No se conservan 4/8/16 PCs elegidos mirando la cohorte: se eligen 1/2/4 dentro de cada entrenamiento para limitar los coeficientes a cinco. La biopsia se evalúa sólo donde está disponible; su cohorte no es directamente comparable. Suelos históricos de referencia: baseline 0.6636 · CAPRA-S 0.7372 · constante 60 meses 0.5000.

| sonda (n) | c-index | IC 95% (1000) | AUC 12 / 24 / 36 / 60 |
|---|---:|---|---|
| CAPRA-S Cox (75) | 0.7389 | [0.5901, 0.857] | 0.8203 / 0.7738 / 0.7770 / 0.7419 |
| RM Cox (75) | 0.6345 | [0.4963, 0.7677] | 0.6549 / 0.6476 / 0.6680 / 0.6685 |
| biopsia Cox (51) | 0.6433 | [0.4233, 0.8379] | 0.6295 / 0.6340 / 0.6505 / 0.7632 |
| CAPRA-S + prostatectomia Cox (75) | 0.8265 | [0.743, 0.8997] | 0.8589 / 0.8304 / 0.8530 / 0.8615 |
| prostatectomia Cox (75) | 0.7106 | [0.558, 0.8527] | 0.7015 / 0.7134 / 0.7193 / 0.7536 |

## Ablación por bloque

Suelos de toda esta tabla: baseline 0.6636 · CAPRA-S 0.7372 · constante 60 meses 0.5000.

| bloque retirado | c-index sin bloque (IC 1000) | Δ completo − sin bloque (IC pareado 1000) | conclusión |
|---|---|---|---|
| A | 0.8221 [0.7294225044795098, 0.9077025691699605] | +0.0097 [-0.015888892254352936, 0.039573133601266554] | redundante: sin evidencia de aporte |
| S | 0.7673 [0.6563193815877837, 0.8673333506746361] | +0.0646 [0.003723383933574407, 0.13222204436386228] | efecto detectado; consultar signo |
| G | 0.8168 [0.7127310494925689, 0.9033956026718443] | +0.0150 [-0.029369280169932222, 0.05809838442901736] | redundante: sin evidencia de aporte |
| D | 0.8593 [0.777409362746588, 0.9293545443589347] | -0.0274 [-0.06351308057200122, 0.004424860399046474] | redundante: sin evidencia de aporte |
| E | 0.7867 [0.6795570642010729, 0.88314132780337] | +0.0451 [-0.03172292493076868, 0.1162386828758287] | redundante: sin evidencia de aporte |

Los bloques sin evidencia de aporte se documentan como redundantes. El modelo completo se conserva como control experimental exigido para el experto cuatro, no como recomendación de despliegue. No se selecciona una nueva combinación con esta ablación.

## Escaleras fuera de muestra

Tramos predeclarados por completitud de fuentes: firm ≥0.90, supports [0.75,0.90), discuss <0.75. Miden disponibilidad, no una probabilidad calibrada de acierto. Suelos: baseline 0.6636 · CAPRA-S 0.7372 · constante 60 meses 0.5000.

| experto | tramo | n | c-index (IC 1000) |
|---|---|---:|---|
| expert_one | firm | 51 | 0.7054 [0.5016467162963657, 0.8634374084562054] |
| expert_one | supports | 24 | 0.8089 [0.5855864170076499, 0.9651550387596899] |
| expert_one | discuss | 0 | no estimable None |
| expert_two | firm | 51 | 0.7515 [0.5795381116952416, 0.8972986548792351] |
| expert_two | supports | 24 | 0.8537 [0.6807719359943731, 0.9804106548279689] |
| expert_two | discuss | 0 | no estimable None |
| expert_three | firm | 51 | 0.7455 [0.5666556291390729, 0.9197104624029715] |
| expert_three | supports | 24 | 0.6423 [0.3281589624692074, 0.9483897202342224] |
| expert_three | discuss | 0 | no estimable None |
| expert_four | firm | 51 | 0.8236 [0.7162952995992221, 0.9142997504678727] |
| expert_four | supports | 24 | 0.8618 [0.623504090377873, 1.0] |
| expert_four | discuss | 0 | no estimable None |
| expert_five | firm | 51 | 0.7054 [0.5016467162963657, 0.8634374084562054] |
| expert_five | supports | 24 | 0.8089 [0.5855864170076499, 0.9651550387596899] |
| expert_five | discuss | 0 | no estimable None |

Monotonía: expert_one: no demostrada / no monótona, expert_two: no demostrada / no monótona, expert_three: no demostrada / no monótona, expert_four: no demostrada / no monótona, expert_five: no demostrada / no monótona.

## Experto cinco: horizonte y event

Portavoz predeclarado: CAPRA-S. No se elige al ganador de la comparación usando los mismos resultados externos. El calibrador selecciona entre tres curvas 90·exp(−0.1·(CAPRA+offset)), offset −0.4/0/0.4, usando sólo el entrenamiento externo; event selecciona entre constante 0, CAPRA≥7 y CAPRA≥9. Las decisiones se miden en el pliegue externo.

time_score OOF: 0.7540; constante 60: 0.7590; Δ -0.0049.

event OOF: 0.7733; constante 0: 0.7467; entrega: CAPRA >= 9.0.

Δ c-index OOF global: +0.0000. Validación del calibrador: leave-one-CAPRA-score-group-out. Cada grupo de empates comparte un calibrador que no ha visto sus etiquetas; bandas disjuntas garantizan el orden entre grupos enteros. Esta validación difiere de la CV estratificada de Cox. La restricción se introdujo para garantizar invariancia global, sin elegirla por time_score. Las bandas restringen la calidad del horizonte. Aceptación global satisfecha.

El artefacto final usa una única curva estrictamente decreciente y conserva el orden en inferencia. Las cifras de entrenamiento final no se presentan como rendimiento. No se implementa el paso siguiente.

## Reproducción

Desde la raíz:
```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python delete_final_versions_task/task_3/experts_3/train/run_training.py
.venv/bin/python -m pytest -q delete_final_versions_task/task_3/experts_3/train/test_acceptance.py
.venv/bin/python -m pytest -q
```

Cada train_expert_N.py ejecuta el protocolo compartido completo para mantener comparables pliegues y ablaciones. Los .joblib usan pickle sin compresión (compatible con joblib.load), sin dependencia nueva; para cargar clases se debe añadir train/ a sys.path y luego pickle.load. Sólo cargar artefactos de confianza. Horizon acepta el score CAPRA-S, mayor = más riesgo, y devuelve (months, event). CoxPipeline.risk devuelve log-hazard, mayor = más riesgo; los valores negativos usados para c-index no son horizontes clínicos.
