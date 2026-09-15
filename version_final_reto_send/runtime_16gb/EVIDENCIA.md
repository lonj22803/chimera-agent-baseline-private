# Evidencia utilizada para diseñar V2

Consulta y auditoría: **11-09-2026**. Los resultados nuevos de este directorio son diagnósticos; no se ha entrenado ni evaluado una solución V2.

## 1. Qué se tomó como punto de partida

Código del repositorio: `4907a97ddd56f2aa5f9477ac25d724eba12fdcab`. Evaluador local de los organizadores: `92365b94b0eca90daec9021ffdb18c581dcc4619`, en `../CHIMERA-agent-eval/evaluation/evaluate.py`. Los hashes exactos están en [auditoria_base.json](analisis/auditoria_base.json).

Se contrastaron el [PLAN V1](../delete_final_versions_task_V1/PLAN.md), su [BITACORA](../delete_final_versions_task_V1/BITACORA.md), [ENTREGA](../delete_final_versions_task_V1/ENTREGA.md), el [informe de la versión anterior](../delete_final_versions_task/resultados/INFORME.md), los JSON de experimentos y las rutas de inferencia. Hay párrafos de estado antiguos que contradicen entradas posteriores; para la configuración entregada manda el código y el cierre final de la bitácora. Por ejemplo, `selected` es el portavoz T3 por defecto; `enhanced` T2/T3 quedó apagado. Las mejoras de los prompts V1 ya medidas no equivalen a esas variantes `enhanced` posteriores.

| Referencia | T1 | T2 | T3 | OVERALL |
|---|---:|---:|---:|---:|
| V1 sin juez, artefacto de contenedor | 0,83903 | 0,77839 | 0,88319 | 0,82360 |
| V1 sin juez, sustituyendo T3 por estimación anidada | 0,83903 | 0,77839 | 0,82345 | 0,81166 |
| V1 con juez, pase 1, misma sustitución | 0,83781 | 0,81587 | 0,82345 | 0,82616 |
| V1 con juez, pase 2, misma sustitución | 0,83770 | 0,81587 | 0,82345 | 0,82612 |

**El agregado con sustitución es una referencia mixta interna.** Corrige la evaluación dentro de muestra de T3, pero no deshace la selección histórica de reglas, umbrales y formularios de T1/T2. No es una estimación anidada de las tres tareas ni una validación externa. El intervalo pareado del incremento de c-index T3 frente a CAPRA-S es `[-0,00414; 0,20206]`: incluye cero. La mejora observada es prometedora, con incertidumbre considerable.

Fuentes numéricas: [scores_v1_no_judge.json](../delete_final_versions_task_V1/verification/scores_v1_no_judge.json), [survival_total.json](../delete_final_versions_task_V1/experiments/results/survival_total.json), [pase T1](../delete_final_versions_task_V1/experiments/results/paired_judge_task1.json), [pase T2](../delete_final_versions_task_V1/experiments/results/paired_judge_task2.json). `results_v1/` estaba vacío al revisar el espacio de trabajo.

Los datos presentes son 195/153/75 entradas y 91/72/75 etiquetas en T1/T2/T3. T1: 56 `yes`, 35 `no`. T2: 31 tratamiento, 25 vigilancia activa, 14 vigilancia continuada y sólo 2 espera vigilante. T3: 19 eventos y 56 censuras. Los 423 casos de cobertura no equivalen a 423 casos puntuables.

## 2. Qué experimentos no conviene repetir sin cambiar su premisa

| Ensayo anterior | Resultado observado | Consecuencia para V2 |
|---|---|---|
| T1, umbral 0,35 | DEV 0,7623→0,8010; VAL 0,7566→0,7297 | No volver a barrer umbrales sobre el mismo histórico como si VAL estuviera intacto |
| Extender guardias entre cohortes | DEV 0,9333→0,8333 | Preservar contexto diagnóstico y de tratamiento; una regla no se traslada por similitud superficial |
| Reordenar cascada T1 / guardia de PSAD | DEV 0,9219→0,8438 en el cambio de orden | Comparar cada política sobre los mismos pacientes y decisiones completas |
| T1, añadir bloques C/E/F | Ninguno ganó a ABD; F solo AUC 0,3791 | No añadir dimensiones sin una hipótesis de representación distinta |
| T2, formulario por experiencia | F1 DEV 0,6548→0,5834 | No reintroducir kNN de formularios; estudiar una política conjunta pequeña con fuentes verificables |
| T2, `ct` importante si palpable | DEV +0,0031; VAL −0,0019 | No copiar una excepción porque su explicación clínica suene convincente |
| T2, 17 familias | Regla de grado/Extra Trees 0,88; RF 0,8533; kNN 0,66 | El cuello de botella puede estar en la representación y el objetivo, no en la familia |
| T2, combinar expertos | Satura en 0,88 o empeora; E1/E2/E4 repetían decisiones | La diversidad debe demostrar correcciones adicionales fuera de muestra |
| T3, árboles/kNN | DEV 0,7631/0,7515/0,5476 frente a 0,7903 del selector | No proponer los mismos clasificadores por horizonte como innovación |
| T3, mapa CAPRA con `a=105` | `time_score` 0,7540→0,7589; c-index idéntico | No sumar esta mejora a la del portavoz `selected`: se midió otro mapa y otro ancla |
| Clustering de errores | p=0,22/0,31 | No entrenar un detector de excepciones sobre 8/7 fallos históricos |
| Prompts V1 | Mejoras pequeñas T1/T2; mayor en prosa T3 | Mantener el avance; T3 prosa no mueve el ranking |

Evidencia en [experiments/results](../delete_final_versions_task_V1/experiments/results) y en la bitácora. Estas conclusiones son locales a los ensayos. Por ejemplo, el ensayo MRI usó Extra Trees; **no demuestra que toda representación de MRI carezca de señal**. Y una combinación de rangos calculados sobre pacientes de test no es entregable por caso, pero una transformación ajustada y congelada sólo en entrenamiento sí puede serlo. V1 ya utiliza esta segunda idea en T3.

## 3. Auditorías nuevas que cambian el diseño

### 3.1 Consultas realmente hechas frente a consultas declaradas

En los **72/72** registros de la corrida histórica T2, `revealed` difiere de `reveal_sequence`. La política [protocol.trace de V1](../delete_final_versions_task_V1/task_2/agent/protocol.py) sigue declarando `[]` mientras prescribe un plan interno de seis secciones. El [README del contrato](../README.md) define ese campo como las secciones consultadas; por tanto, V2 debe derivarlo de las lecturas efectivas.

La auditoría reproduce el ranking histórico con el evaluador oficial y cambia únicamente esa declaración a las lecturas que quedaron registradas:

| T2, mismas decisiones y mismos documentos | Declaración histórica | Lecturas reales |
|---|---:|---:|
| Sin juez | 0,778386 | 0,772518 |
| Con score histórico de prosa congelado | 0,815033 | 0,764994 |
| Tool score | 1,0000 | 0,0000 |
| Grounding de secciones | 0,2171 | 1,0000 |

**No se ha llamado de nuevo al juez.** La segunda fila aísla la aritmética manteniendo sus puntuaciones originales; no mide cómo juzgaría un texto nuevo. El impacto sobre OVERALL es −0,00235 sin juez y −0,02002 con score de prosa congelado. Es suficientemente grande para priorizar el problema.

La salida no es seguir ocultando consultas. La salida propuesta es una ruta que aprovecha de verdad el panel inicial rico de T2 y sólo consulta un documento cuando aporta una distinción necesaria. Habrá que volver a medir decisiones, formularios y prosa de esa ruta; no es válido quitar las consultas al JSON conservando información extraída de ellas.

### 3.2 Negación y cronología

Dos pruebas sintéticas contra el extractor actual, sin entrenarlo:

- `No histological progression. ISUP grade group 1.` produce simultáneamente `path_traj_stable=1` y `path_traj_progress=1`.
- Un informe que presenta primero `Timepoint 2` con GG1 y después `Timepoint 1` con GG2 produce delta `+1`, siguiendo el orden del texto; el cambio entre esos momentos es `−1`.

Entre las 153 entradas T2, **16** producen simultáneamente las banderas de estabilidad y progresión. Ese recuento **no equivale a 16 errores**: pueden describir momentos o lesiones diferentes. Justifica una auditoría temporal con citas y evaluación de extracción. Las pruebas sí demuestran dos limitaciones de mecanismo de [features_pathology.py](../delete_final_versions_task_V1/common/chimera_experts/features_pathology.py).

V1 ya tiene variables de trayectoria, fragilidad y patología. V2 no las presenta como nuevas: cambia cómo representa su evidencia, negación, tiempo y conflictos.

### 3.3 Correspondencias entre tareas

La igualdad exacta de vectores MRI identifica **170 grupos presentes en más de una tarea**, aunque T1/T2 no comparten los mismos IDs textuales. Esto es una pista fuerte de datos relacionados, no prueba suficiente para declarar identidad de paciente. La auditoría no publica IDs ni los utiliza para predecir.

Consecuencias: auditar los grupos antes de un aprendizaje compartido; mantener juntos sus registros en la evaluación; impedir que una representación del sujeto de validación llegue al entrenamiento desde otra tarea. No demuestra por sí solo fuga en V1, cuyas cabezas son específicas de tarea. Sí invalida asumir independencia por el nombre del directorio al diseñar una V2 multitarea.

### 3.4 T3: referencia congelada y empates artificiales

El portavoz desplegado usa `F_train(raw)=(n_ref<raw+0,5*n_ref==raw)/75` y después un mapa exponencial. La referencia tiene 75 valores distintos. Para riesgos nuevos que no coinciden con esos valores, hay a lo sumo **76 intervalos de salida**, incluyendo las dos colas. La CDF es monótona **no estricta**: dos riesgos distintos pueden acabar con los mismos meses.

La transformación es válida para un contenedor por paciente, pero puede perder orden. V2 separa dos preguntas: si un mapa continuo conserva mejor la discriminación, y si un modelo de supervivencia puede dar meses mejor calibrados. No se ha medido todavía una ganancia por resolverlo; tampoco se atribuyen todos los empates históricos a este mecanismo sin comprobarlos.

También debe auditarse la selección interior T3: [train/protocol.py::select](../delete_final_versions_task_V1/task_3/experts_3/train/protocol.py) agrega log-riesgos crudos de modelos de pliegues distintos. Su escala y origen no están garantizados como comparables. El bucle externo sí aplica una referencia de entrenamiento. V2 exigirá comparabilidad también dentro de la selección y medirá concordancia dentro de cada pliegue.

## 4. Reglas comprobadas y límites de la comprobación

- El [README oficial](https://github.com/DIAGNijmegen/chimera-agent-baseline#what-not-to-change) permite cambiar modelos, prompts, herramientas, grafo y entrypoint. Bloquea el esquema de salida. El README local explicita acceso al EHR extendido a través de herramientas.
- El [evaluador público](https://github.com/DIAGNijmegen/CHIMERA-agent/blob/main/evaluation/evaluate.py) puntúa decisiones, formularios, consultas y prosa; T3 clasifica por concordancia. La frase del README «tool use is not scored» contradice el código de evaluación. Para medir se fija el evaluador y su mapping, sin modificarlo.
- La [entrega V1](../delete_final_versions_task_V1/ENTREGA.md) documenta seis nombres de archivo confirmados en la interfaz del algoritmo y un smoke con pico de 21 502 MiB. La [compuerta local](../delete_final_versions_task_V1/verification/contrato_423.json) documenta cobertura 423/423. Eso no prueba por sí solo aceptación remota de Development ni latencia de arranque frío para todos los casos.
- Se intentó consultar la [web del reto](https://chimera-agent.grand-challenge.org/chimera-agent/) y su [página de reglas](https://chimera-agent.grand-challenge.org/rules/); devolvieron **403**. No se pudo confirmar por esa vía el reglamento completo vigente, las cuotas de envíos ni el presupuesto temporal oficial. No se inventan. El plan principal usa los datos y pesos ya disponibles, evita dependencias externas en inferencia y deja esa comprobación como requisito de la futura entrega. No bloquea diseñar V2.

## 5. Investigación externa aplicada, no promesas de rendimiento

| Fuente primaria | Qué aporta | Aplicación y límite |
|---|---|---|
| [Koh et al., Concept Bottleneck Models, ICML 2020](https://proceedings.mlr.press/v119/koh20a.html) | Intermedios semánticos sobre los que se puede intervenir | Inspira hechos clínicos editables y verificables; no justifica entrenar una red grande con 72 etiquetas |
| [Covert et al., Dynamic Feature Selection, ICML 2023](https://proceedings.mlr.press/v202/covert23a.html) | Adquirir información según lo ya observado | Inspira selección de documentos por utilidad; V2 empieza con un planificador pequeño, no con RL |
| [scikit-learn: CV anidada](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html) | Separar selección y estimación | Se extiende a extractores aprendidos, memorias, calibración, formularios y política de consultas |
| [scikit-learn: calibración](https://scikit-learn.org/stable/modules/calibration.html) | Ajustar probabilidades sobre predicciones no usadas para entrenar el predictor | Calibración pequeña dentro de los pliegues; no interpretar una banda heurística como cobertura garantizada |
| [scikit-survival: evaluación](https://scikit-survival.readthedocs.io/en/v0.25.0/user_guide/evaluating-survival-models.html) | Separar concordancia de calibración bajo censura | C-index oficial como objetivo y Brier/IPCW como diagnóstico, con censoring model aprendido en train |
| [EAU: evaluación diagnóstica](https://uroweb.org/guidelines/prostate-cancer/chapter/diagnostic-evaluation) | Contextualizar MRI, densidad PSA y biopsia previa | Fundamenta conceptos y preguntas; no convierte un umbral nuevo en una mejora estadística |
| [EAU: tratamiento](https://uroweb.org/guidelines/prostate-cancer/chapter/treatment) | Estado funcional, expectativa vital, vigilancia y hallazgos patológicos adversos | Fundamenta dimensiones separadas; no se deduce fragilidad sólo de edad ni se redefine la clase oficial `continued_surveillance` |

Las guías consultadas deben distinguirse de la versión congelada que ya viaja en `resources/`. Si se actualiza el corpus, será un experimento versionado, no una sustitución silenciosa durante validación. Ninguna fuente externa contiene una medición de la V2 propuesta.

## 6. Reproducción

Desde la raíz del repositorio:

```bash
PYTHONPATH=src:. .venv/bin/python version_final_reto.runtime_16gb/analisis/auditar_base.py
```

Acepta `--eval-repo /ruta/CHIMERA-agent-eval`. Importa las funciones oficiales y comprueba que reconstruyen los rankings históricos antes de calcular los deltas. No reentrena, no ejecuta inferencia GPU y no realiza llamadas al juez. Guarda cifras agregadas, pruebas sintéticas y hashes en `analisis/auditoria_base.json`.
