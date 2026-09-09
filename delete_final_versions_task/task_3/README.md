# Junta de pronóstico posoperatorio — tarea 3

La corrida conserva **75/75 casos**, seis notas de respaldo y ningún horizonte
omitido. El ranking es **0,7371681415929203** y la media por caso sin juez es
**0,7636741685**. Con el juez encendido (75/75 juzgados, sin puerta que
filtre): **mean_case_score 0,6898**, **mean_rationale_score 0,5173**.

## Resultado y alcance

| Variante | c-index = ranking | Event | Time | Mean case sin juez | Mean case con juez |
|---|---:|---:|---:|---:|---:|
| Baseline histórico | 0,6636 | 0,7397 | 0,3738 | no disponible | no disponible |
| CAPRA-S crudo | 0,7372 | no define | no define | no define | no define |
| Constante 60 meses, event=0 | 0,5000 | 0,7467 | 0,7590 | 0,7528 | no medido |
| Junta, reproducción OOF | **0,7372** | **0,7733** | **0,7540** | **0,7637** | **0,6898** |

## El rationale_score (0,5173) tiene un techo estructural, no es un fallo del CHAIR

El juez oficial (`evaluate.py`, `judge()` para `task_kind == "recurrence"`)
construye el contexto que le muestra al modelo así:

```python
input_ctx = {..., "clinical_inputs": pred.get("clinical_data", {}), ...}
```

`pred["clinical_data"]` es **sólo los documentos enmascarados** que el
registrador puede abrir (`family_history`, `pathology_report`, `previous_notes`,
`radiology_report`, `surgical_pathology_report`). **Nunca incluye
`structured-prompt.json`** — el bloque siempre visible con `psa`, `age`, `ct`,
etc. — que el propio prompt del presidente le pide citar explícitamente
("preoperative PSA, surgical grade, extension, margins...").

Ejemplo real, caso `T3-002`: el CHAIR escribió *"preoperative PSA of 0,2"*.
Ese valor **es correcto** — `structured-prompt.json` trae `psa: 0.2` — pero el
juez lo marcó como alucinación: *"citing a 'preoperative PSA of 0.2.' The Input
clinical data provides a 'PSA density' of 0.008..., making the stated value an
unsupported hallucination"*. El juez no tenía el campo `psa` en su contexto: no
podía verlo, así que no podía confirmarlo. Se repite en 4 de los 5 casos peor
juzgados (T3-001 PSA "86", T3-017 PSA "160", T3-002 PSA "0,2"), siempre el mismo
patrón: un valor real de `structured-prompt.json`, marcado como inventado
porque el juez sólo ve `clinical_data`.

**No se puede arreglar cambiando el prompt del presidente**: pedirle que deje
de citar el PSA contradice lo que el propio enunciado de la tarea exige
clínicamente, y el techo lo pone la construcción del `input_ctx` del evaluador
*oficial*, no nuestro código. Es un límite real de la rúbrica de esta tarea,
medido y documentado — no oculto, por la misma regla que rechaza `expected_f1_set`
en la tarea 1: lo que no se puede ganar se publica como tal.

Fuente de la corrida: [score_no_judge.json](runs/score_no_judge.json).
La referencia constante procede de [expert_five_report.json](experts_3/train/artifacts/expert_five_report.json);
su media sin juez es la semisuma de event y time. El CAPRA-S crudo expresa riesgo,
no meses: asignarle time_score sin definir un mapa sería una comparación inválida.
El baseline histórico escribe event=0: su 0,7397 refleja la tasa de censura en
su evaluación histórica, no discriminación de eventos. En los 75 casos completos
la constante obtiene 56/75=0,7467; no se mezclan esos denominadores.

| Predicción | TD-AUC 12m | 24m | 36m | 60m |
|---|---:|---:|---:|---:|
| CAPRA-S y horizonte de la junta | 0,8058 | 0,7698 | 0,7719 | 0,7523 |
| Constante 60 meses | 0,5000 | 0,5000 | 0,5000 | 0,5000 |
| Baseline histórico | no disponible | no disponible | no disponible | no disponible |

El juez no interviene en c-index, event, time ni TD-AUC. En tarea 3 el ranking
oficial es **sólo el c-index**; `mean_case_score` incorpora la nota clínica y
siempre se publica al lado del ranking. Una constante logra una media cercana
a 0,75 mientras su ranking es 0,50. La mejora de orden frente al baseline es
+0,0736; el horizonte pierde 0,00495 de time frente a 60 meses. Se conserva esa
pérdida medida, sin ocultarla tras la mejora de ranking.

## Anatomía compartida y las once intervenciones

Se extiende la [anatomía de tarea 1](../task_1/README.md) y la separación entre
fuentes, acta, protocolo y nota de [tarea 2](../task_2/README.md). `common/`
aporta `Board`, carga de casos y guardias de lenguaje de proceso, cifras y
grados sin fuente. La tarea conserva su protocolo, prompts y expertos.

| Orden | Intervención | Qué añade |
|---|---|---|
| 1 | INTAKE | PSA, edad y contexto estructurado |
| 2 | EXPERT-CAPRA | Riesgo CAPRA-S y estado ganglionar desde patología |
| 3 | EXPERT-SURGICAL | Segunda lectura del espécimen y consejo Cox |
| 4 | EXPERT-DIGITAL | Consejo desde vectores congelados; no lectura visual |
| 5 | MODERATOR | Preguntas explícitas a cuatro documentos |
| 6 | REGISTRAR | Documentos clínicos disponibles y ausencias |
| 7 | EXPERT-FUSION | Consejo conjunto tras la lectura |
| 8 | PANEL-PROTOCOL | Fija CAPRA-S como portavoz predeclarado |
| 9 | EXPERT-HORIZON | Meses, event y banda de sensibilidad |
| 10 | VERIFIER | Comprueba limitaciones y coherencia ganglionar |
| 11 | CHAIR | Nota clínica, hasta dos intentos y respaldo determinista |

La implementación de T3 lee directamente los documentos suministrados en
`Case.clinical`; no llama al transporte MCP. Su campo `opened` enumera cuatro
claves previstas incluso cuando alguna está ausente: verificar sólo que la lista
no esté vacía sería insuficiente. El acta conserva los valores y el verificador
las ausencias. No se afirma que cuatro nombres equivalgan a cuatro documentos.

## Los cinco expertos y sus suelos

| Experto | Evidencia | c-index OOF | Función |
|---|---|---:|---|
| 1, CAPRA | PSA y anatomía patológica quirúrgica | 0,7372 | Ancla y portavoz |
| 2, SURGICAL | Variables quirúrgicas, Cox penalizado | 0,7726 | Consejo |
| 3, DIGITAL | Vectores de prostatectomía, Cox | 0,7106 | Consejo |
| 4, FUSION | Clínica y vectores, Cox | 0,8319 | Consejo |
| 5, HORIZON | Mapa de riesgo a meses | 0,7372 | Produce el número |

Suelos compartidos: baseline 0,6636; CAPRA-S 0,7372; constante 60m 0,5000.
La fusión mejora puntualmente +0,0947, pero el IC pareado de 1.000 remuestreos
es **[-0,0211, 0,2271]**: incluye cero. No se sustituye al portavoz CAPRA-S
por el ganador observado. Los [informes de expertos](experts_3/README.md)
publican ablaciones, suelos, escaleras y las TD-AUC de cada modelo.

Los Cox usan cinco pliegues externos, cinco semillas y tres pliegues internos;
imputación, escalado, PCA y selección se ajustan dentro del entrenamiento.
Hay 19 eventos: los IC son amplios y los remuestreos de predicciones OOF no
incluyen incertidumbre de reentrenamiento. El calibrador usa otro protocolo,
leave-one-CAPRA-score-group-out. El runner `--mode oof` reproduce esas
predicciones para la cohorte medida; `--mode deployed` aplica artefactos finales
a pacientes nuevos. No se presenta el replay como validación externa.

## Orden y magnitud son dos problemas

PANEL-PROTOCOL fija el orden del riesgo. EXPERT-HORIZON fija la magnitud del
horizonte. Para un par comparable según la censura, si `r_i > r_j` y el mapa
`m=f(r)` es estrictamente decreciente, entonces `m_i < m_j`. La concordancia
usa precisamente esa inversión riesgo/tiempo. Si el mapa conserva también
los empates, cada par conserva su contribución (1, 0 o medio punto), y la
media de todas esas contribuciones permanece idéntica.

La precisión «estrictamente» importa: un mapa meramente no creciente puede
introducir empates y cambiar el c-index. Calibradores distintos por pliegue
también podrían cruzar casos. Aquí todos los empates CAPRA-S comparten grupo
excluido y las bandas de los grupos son disjuntas; el modelo desplegado usa
una única curva estrictamente decreciente. La familia es `a·exp(-0,1·CAPRA-S)`.

La invariante de [test_invariantes_t3.py](agent/tests/test_invariantes_t3.py)
fija el resultado de ambos informes:

```text
orden CAPRA-S:       0.7371681415929203
meses tras el mapa:  0.7371681415929203
corrida real:        0.7371681415929203
```

Por tanto, optimizar el horizonte bajo estas restricciones no daña
`ranking_score`. No implica que cualquier calibrador OOF sea monótono ni que
la magnitud actual supere a la constante: el time medido es 0,7540 frente a
0,7590. La elección desplegada de event (CAPRA-S ≥9) procede de comparación
OOF y su rendimiento seleccionado no tiene una evaluación externa adicional.

## En que se diferencia de las tareas 1 y 2

No hay puerta de decisión que anule casos, ni `variable_weights`, ni
`confidence`, ni `reveal_sequence` en Task3Output. **El juez pesa 0,30 y juzga
los 75 casos**. La prosa tiene mayor peso que en T1/T2 (0,20), aunque la
clasificación final de T3 sigue dependiendo únicamente del c-index.

**El número lo produce EXPERT-HORIZON, no el LLM.** En el baseline, T3-038 y
T3-063 resistieron ocho reintentos devolviendo «Cannot be determined»: se le
pedía al modelo una fecha de recurrencia sin explicarle que una observación
censurada representa seguimiento sin evento observado. Repetir el mismo
encargo no resolvía esa contradicción semántica.

Aquí el presidente recibe el horizonte ya fijado y sólo escribe su explicación.
`decide.finish` añade la cifra y la semántica: con event=0 es seguimiento esperado
sin evento, no una fecha conocida de recurrencia; con event=1 es un horizonte
pronosticado, no evidencia de que ya ocurrió. Se rechazan números negativos,
no finitos y event fuera de {0,1}. Si la nota falla las guardias, el respaldo
mantiene el número del experto. Esto elimina por construcción el aborto por
negativa del LLM a producir meses, sin convertir el pronóstico en certeza.

Los dos ficheros del reto son `prostate-time-to-recurrence-or-last-follow-up.json`
con `{event, months_to_recurrence}` y su gemelo `-reasoning.json`, que contiene
**una cadena JSON suelta**. El esquema interno además conserva case_id y task.

## Incertidumbre y censura ganglionar

Sin campo confidence, la incertidumbre se expresa en la nota y en una banda
explícitamente heurística. **43/75 casos no tienen ganglios extraídos**:
`ln_unknown=1` significa pNx, no pN0. CAPRA-S les asigna cero en el componente
ganglionar por convención de cálculo; no se convierte esa convención en una
negación clínica de enfermedad ganglionar.

La semiamplitud base es 0,20·meses. El término de imputación suma
0,15·meses si ln_unknown, más 0,05·meses por documento ausente; el extremo
inferior se trunca en cero. No tiene cobertura validada y se declara así en
la salida. La guardia impide afirmar ausencia de muestreo si sí hubo ganglios
muestreados. Ni la escalera por completitud ni esa banda son probabilidades
calibradas de acierto.

## Ejecución y comprobación

Desde la raíz, con el modelo ya generado y vLLM apagado:

```bash
PYTHONPATH=src:. .venv/bin/python dev/score_local.py --tasks 3 --count-missing \
  --output-root delete_final_versions_task/task_3/runs/labeled/output \
  --json-out delete_final_versions_task/task_3/runs/score_no_judge.json
.venv-eval/bin/python dev/score_with_judge.py --task 3 \
  --output-root delete_final_versions_task/task_3/runs/labeled/output \
  --json-out delete_final_versions_task/task_3/runs/judge/entrega.json
./delete/run_tests.sh
```

Comprobar procesos GPU desde el host antes del juez. Si `gemma4:e4b` ya está
cargado y no hay competidores, conservar esa carga y puntuar todo seguido,
sin descargar ni recargar entre medias (como en esta evaluación autorizada).
El juez no es determinista ni siquiera dentro de una carga; cualquier repetición
se conserva como otra medición, no como sustitución selectiva de la anterior.
Los procesos largos deben lanzarse con `nohup ... & disown` y log persistido.

## Bibliografía

La arquitectura común y su bibliografía se desarrollan en tarea 1. Referencias
específicas comprobadas en las fuentes enlazadas:

- Cooperberg, Hilton y Carroll (2011). *The CAPRA-S score*. Cancer 117(22):5039–5046.
  [DOI 10.1002/cncr.26169](https://pubmed.ncbi.nlm.nih.gov/21647869/).
- Punnen et al. (2014). *Multi-institutional validation of the CAPRA-S score*.
  European Urology 65(6):1171–1177.
  [DOI 10.1016/j.eururo.2013.03.058](https://pubmed.ncbi.nlm.nih.gov/23587869/).
- Tilki et al. (2015). *External validation of the CAPRA-S score ... in a European cohort*.
  Journal of Urology 193(6):1970–1975.
  [DOI 10.1016/j.juro.2014.12.020](https://pubmed.ncbi.nlm.nih.gov/25498570/).
- Stephenson et al. (2005). *Postoperative Nomogram Predicting the 10-Year Probability
  of Prostate Cancer Recurrence After Radical Prostatectomy*. JCO 23(28):7005–7012.
  [DOI 10.1200/JCO.2005.01.867](https://pmc.ncbi.nlm.nih.gov/articles/PMC2231088/).
- Han, Partin, Pound, Epstein y Walsh (2001). *Long-term biochemical disease-free
  and cancer-specific survival following anatomic radical retropubic prostatectomy:
  The 15-year Johns Hopkins experience*. Urol Clin North Am 28(3):555–565.
  [Fuente de los autores, DOI 10.1016/S0094-0143(05)70163-4](https://pure.johnshopkins.edu/en/publications/long-term-biochemical-disease-free-and-cancer-specific-survival-f-4/).
- Cao et al. (2025). *Development of a deep learning system for predicting biochemical
  recurrence in prostate cancer*. BMC Cancer 25:232.
  [DOI 10.1186/s12885-025-13628-9](https://link.springer.com/article/10.1186/s12885-025-13628-9).
  Usa Inception_v3 preentrenado en ImageNet y MIL: **no se cita como validación
  de modelos fundacionales histológicos**. Queda marcado el hueco bibliográfico
  específico de WSI + foundation models + BCR en 2024–2025, sin inventar una referencia.
- Freedland et al. (2005). *Risk of prostate cancer-specific mortality following
  biochemical recurrence after radical prostatectomy*. JAMA 294(4):433–439.
  [DOI 10.1001/jama.294.4.433](https://pubmed.ncbi.nlm.nih.gov/16046649/).
- Harrell, Lee y Mark (1996). *Multivariable prognostic models: issues in developing
  models, evaluating assumptions and adequacy, and measuring and reducing errors*.
  Statistics in Medicine 15(4):361–387.
  [Ficha y DOI verificados](https://pubmed.ncbi.nlm.nih.gov/8668867/).
- Breslow (1974). *Covariance analysis of censored survival data*.
  Biometrics 30(1):89–99. [Registro bibliográfico](https://pubmed.ncbi.nlm.nih.gov/4813387/).
- Cox (1972). *Regression Models and Life-Tables*. JRSS-B 34(2):187–220
  (incluye discusión). [Texto del artículo](https://web.stanford.edu/~lutian/coursepdf/cox1972paper.pdf).
- Pound et al. (1999). *Natural History of Progression After PSA Elevation Following
  Radical Prostatectomy*. JAMA 281(17):1591–1597.
  [DOI 10.1001/jama.281.17.1591](https://jamanetwork.com/journals/jama/fullarticle/189741).

- Uno, Cai, Tian y Wei (2007). *Evaluating Prediction Rules for t-Year Survivors
  With Censored Regression Models*. JASA 102(478):527–537.
  [Artículo, DOI 10.1198/016214507000000149](https://www.tandfonline.com/doi/abs/10.1198/016214507000000149).
  Fundamenta las métricas dependientes del tiempo con censura empleadas por el evaluador.

Auditoría de artefactos: [acceptance_6_2.json](runs/acceptance_6_2.json),
75/75 esquemas y actas, 75/75 con contenido documental real, 43 pNx, seis
notas de respaldo; cero errores y c-index idéntico antes/después.
Las siete suites globales pasan: **202 tests** (92+62+22+4+4+7+11).
