# `expert_modelate` — expertos clásicos de machine learning para CHIMERA-agent 2026

Un **experto inicial** es un modelo estadístico entrenado sobre los datos
etiquetados del reto que, antes de que ningún LLM delibere, entrega dos cosas:

1. un **veredicto** — una clase, o una magnitud con su error;
2. una **incertidumbre descompuesta** que dice cuánto se sostiene ese veredicto y
   *por qué* no se sostiene más.

La segunda parte es la que justifica el diseño. Un clasificador que dice "sí" con
un 0.62 y no dice nada más no le sirve a un deliberador posterior: no puede saber
si ese 0.62 es un caso limpio con poco margen o un caso al que le faltan la mitad
de las variables. Aquí cada veredicto viene con tres números separados —
incertidumbre del modelo, incertidumbre por datos ausentes, e incertidumbre
irreducible — y con un tramo de fiabilidad que traduce esos números a la escala
`clear` / `borderline` / `uncertain` que el formulario de CHIMERA exige.

## Estructura

```
expert_modelate/
├── chimera_experts/              paquete compartido por las tres tareas
│   ├── io.py                     carga de casos, tolerante a ficheros ausentes
│   ├── features_structured.py    bloque A — structured-prompt.json
│   ├── features_labs.py          bloque B — analítica
│   ├── features_psa.py           bloque C — trayectoria de PSA
│   ├── features_radiology.py     bloque D — informe radiológico (NegEx)
│   ├── dataset.py                ensamblado de bloques y ablación
│   ├── uncertainty.py            descomposición epistémica/aleatoria, escalera
│   ├── models.py                 catálogo de candidatos + envoltorio de incertidumbre
│   ├── evaluation.py             CV repetida, LOOCV, bootstrap pareado
│   ├── psa_projector.py          Experto 2 — proyección con predicción conforme
│   ├── expert_classifier.py      traducción al esquema de salida de CHIMERA
│   ├── reasoning_model.py        Experto 4 — traza de razonamiento del urólogo
│   └── train_expert.py           rutina de entrenamiento compartida
├── task_one/                     Tarea 1 — decisión de biopsia   ← implementada
│   ├── expert_one/               clasificador sobre structured-prompt.json
│   ├── expert_two/               regresor: proyección del PSA
│   ├── expert_three/             clasificador de fusión multi-fuente
│   ├── reasoning_model/          predictor de confidence / weights / reveal_sequence
│   ├── train/                    todos los experimentos y sus artefactos
│   └── run_experts.py            inferencia: panel de los tres expertos
├── task_two/                     Tarea 2 — pendiente
└── task_three/                   Tarea 3 — pendiente
```

## Instalación

```bash
pip install -r requirements.txt      # numpy, scipy, scikit-learn, pandas, matplotlib, joblib
```

No hace falta GPU, ni PyTorch, ni descargar pesos: todo son estimadores de
scikit-learn sobre variables tabulares y texto procesado con reglas.

## Uso rápido (Tarea 1)

```bash
cd task_one
python expert_two/train_expert_two.py          # el proyector de PSA va primero
python expert_one/train_expert_one.py
python expert_three/train_expert_three.py --blocks ABD --model extra_trees
python reasoning_model/train_reasoning_model.py
python run_experts.py --case PT-pseudo_0020cfca66c8 --out ./salida
```

`run_experts.py` escribe los dos ficheros que el reto espera
(`prostate-biopsy-decision.json` y `prostate-biopsy-decision-reasoning.json`) más
un `expert-panel.json` con la carga ampliada para el deliberador.

## Principios de diseño

**Todo veredicto es trazable hasta un campo de un JSON de entrada.** No hay
variables construidas a partir de conocimiento externo no verificable. El texto
libre que generan los expertos sólo contiene cifras presentes en el caso, porque
el reto penaliza explícitamente los hallazgos no respaldados.

**Los datos ausentes no se rellenan y se olvidan.** Un valor imputado se marca
como imputado, y la incertidumbre del veredicto crece en proporción a cuánto
depende de esa imputación, medido por imputación múltiple.

**Lo que no aporta, se retira.** Cada bloque de variables pasa por una ablación
con bootstrap pareado. Un bloque que no mueve la métrica se documenta como
redundante en lugar de quedarse porque "no hace daño": con 91 casos, cada
variable extra sí hace daño.

**Los suelos se publican junto a los resultados.** Cada tabla incluye la
prevalencia, la regla PI-RADS y la regla EAU. Un modelo que no las bate no es un
resultado.

## Estado

| Tarea | Estado | Métrica principal |
|---|---|---|
| 1 — decisión de biopsia | **implementada** — 4 expertos, AUC 0.794 [0.698, 0.881] | *case score* (decisión + razonamiento) |
| 2 — estratificación tras biopsia | **implementada** — 5 expertos + formulario, acierto 0.861 [0.778, 0.944] sobre un techo de consistencia de 0.931 | *case score* (decisión + razonamiento) |
| 3 — recurrencia bioquímica | pendiente | C-index de Harrell |

La tarea 2 se comporta distinto a la 1 y conviene decirlo aquí: su etiqueta se
derivó retrospectivamente de la histopatología, de modo que un mapa
`ISUP → conducta` de un solo predictor ya acierta 0.861 y **ningún modelo
aprendido lo bate**. Lo que sí mejora es la *probabilidad* —Extra-Trees empata
en decisión y gana en Brier y ECE— y, sobre todo, la **descomposición**: la
cascada de guía separa el mismo acierto en dos preguntas contestables
(AUC 0.940 y 0.881) y una que la cohorte no puede contestar (AUC 0.500).
Detalle en [`task_two/README.md`](task_two/README.md).

La bibliografía completa está en [`task_one/train/README.md`](task_one/train/README.md).
