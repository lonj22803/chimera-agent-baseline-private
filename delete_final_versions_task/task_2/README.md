# Junta clínica con expertos entrenados — tarea 2

La corrida completa posterior al arreglo MCP contiene **153/153 casos**: 72
etiquetados y 81 sin etiqueta, sin documentos abiertos vacíos. Las cinco salidas
anteriores defectuosas se conservan sólo como evidencia en
`runs/labeled_BROKEN_no_documents/` y no forman parte de estas métricas.

## 1. Resultado y límites de la medición

| Referencia | Decisión | Weighted F1 | Ranking sin juez | Ranking con juez |
|---|---:|---:|---:|---:|
| Baseline histórico | 41/72 = 0,5694 | 0,5224 | 0,4457 | no disponible aquí |
| Regla ISUP | 62/72 = 0,8611 | 0,8490 | — | — |
| Junta, corrida completa | 65/72 = 0,9028 | 0,8898 | **0,7784** | **0,8031 / 0,8150** |
| Techo de consistencia del perfil | 0,931 | — | — | — |

Fuentes: [sin juez](runs/score_no_judge.json), [segundo pase con juez](runs/judge/entrega.json)
y [registro del primer pase](../../delete/HANDOFF.md). El primer pase terminó
la evaluación pero falló al guardar por ausencia del directorio padre; el arreglo
ya está aplicado. El JSON persistido corresponde al segundo pase por ese motivo,
no porque sea una medición más fiable.

Los dos pases consecutivos se hicieron **SIN recargar el modelo** y dieron
0,8031 y 0,8150. El juez **no es determinista ni sin recarga**; la recarga añade
variación. Son mediciones puntuales, no un intervalo de confianza ni una selección
del mejor resultado. `rationale_score` fue 0,7108 y 0,8431, respectivamente.
No se ajustan prompts para perseguir una nota previa.

La corrida real reproduce exactamente la simulación sin juez (0,7783863062).
Los expertos de entrega se entrenaron sobre estos 72 casos: esta concordancia
verifica la ejecución, pero no demuestra generalización. Los 81 sin etiqueta
verifican cobertura y formato, no exactitud. El baseline conserva el artefacto
histórico de `tool_score=0`; véase `runs/baseline_no_judge.json`.

### Por qué el grounding bajo es deliberado

`section_grounding=0,2171` responde a la compuerta 4.2: **no silenciar casillas**
y entregar `reveal_sequence=[]`. Los documentos sí se abren internamente; el
campo entregado vacío no representa ausencia de lectura. `tool_score=1,0000`.
Los otros componentes son variable_weight 0,8382, confidence 0,9000 e
important_decisive 0,6732.

Sin juez, grounding pesa 0,175 (aporta 0,0380); con juez pesa 0,05 (aporta
0,0109) y rationale pesa 0,20. El ranking sube **+0,025 / +0,037** respecto
al modo sin juez. Esto confirma la mejora al encender el juez para esta política;
no constituye por sí solo una comparación causal con una variante que silencie
casillas. La decisión de conservarlas procede de la compuerta medida de 4.2.

## 2. La sesión, intervención por intervención

```text
Entrada estructurada
  -> E1 grado -> E2 anuncia lectura pendiente -> E5 cascada
  -> TRACE fija formulario y plan interno
  -> EAU recupera guía -> moderador formula preguntas
  -> registrador abre las seis secciones previstas
  -> E2 patología + E4 fusión + E5 actualizado
  -> [E3 aptitud si los cuatro primarios están en discuss]
  -> protocolo elige portavoz -> verificador
  -> [reapertura acotada] -> presidente redacta -> guardias -> entrega
```

| Quién | Función | Autoridad sobre la entrega |
|---|---|---|
| E1 | Grado y riesgo, 28 variables; ECE histórico 0,0425 | Portavoz por defecto |
| E2 | Segunda lectura de patología | Réplica confirmatoria de E1 |
| E3 | Aptitud, comorbilidad y beneficio | Excepción cuando los cuatro primarios dudan |
| E4 | Fusión tras recuperar documentos | Réplica confirmatoria de E1 |
| E5 | Cascada cáncer / tratar / beneficio | Sustituye a E1 si éste duda y la cascada es más firme |
| TRACE | Casillas y plan de fuentes | Moda congelada por compuerta 1.2 |
| EAU | Recuperación de pasajes de guía | Aporta contexto, no vota |
| Moderador | Preguntas por documento | No cambia el plan fijo |
| Registrador | Abre fuentes mediante MCP | Documenta qué se obtuvo |
| Verificador | Comprueba las secciones pendientes | Puede pedir reapertura |
| Presidente | Redacta `free_text` | Decisión y formulario los fija el código |

## En qué se diferencia de la tarea 1

En T1 la dificultad está en el grupo `bx=Positive` (49/91): ninguna variable
del panel determina por sí sola la respuesta. El LLM recupera el grado
documentado en las notas y esa evidencia puede decidir el caso. En T2 el grado
ya viene estructurado y la etiqueta es casi función de `bx_isup`.

Por eso el margen señalado por el plan está en el 82,5 % del `case_score`
que no es decisión, y la sesión dedica su trabajo a justificar y calibrar.
Ese porcentaje describe la descomposición indicada por el plan; no elimina
la puerta multiplicativa ni permite compensar una decisión errónea con prosa.

E1, E2 y E4 dieron las mismas 72 decisiones históricas. Se sientan como
réplicas para comprobar fuentes, no como tres votos independientes: el hallazgo
es la redundancia de la información disponible para esta etiqueta.

El plan citaba AUC 0,500 en aptitud. El artefacto entrenado actual informa
**0,5645** (cáncer 0,9569; tratar 0,8739); el protocolo lee esos valores del
informe y no copia las cifras antiguas. Se publica la limitación del nodo:
su exactitud no mejora el suelo mayoritario y sólo hay dos `watchful_waiting`
entre 72 casos. No se presenta como un predictor de beneficio individual validado.

## 3. Protocolo: cómo se decide

E1 habla por defecto. E5 puede sustituirlo si E1 no está disponible, o si E1
está en `discuss` y E5 dispone de un peldaño más firme. E3 sólo entra cuando
E1/E2/E4/E5 están disponibles y todos en `discuss`. Si el portavoz no produce
una acción válida, el respaldo usa grado ≤0: `continued_surveillance`, grado
1: `active_surveillance`, grado superior: `active_treatment`.

La cascada, las réplicas, el portavoz y el techo de consistencia quedan en el
acta. El diagnóstico de confianza por peldaño lleva `validated=false` y
`adopted=false`. La entrega conserva `clear` y `reveal_sequence=[]`.

## 4. Incertidumbre, confianza y pesos

Se distinguen importancia atributiva (qué mueve al modelo), normativa (qué
exige revisar una guía) y conductual (qué casillas marcó el urólogo). El
formulario puntuado representa esta última. La compuerta 1.2 no admite ninguna
política aprendida sobre el suelo en T2: se entrega la moda.

La metodología común separa dispersión entre modelos, entre imputaciones y
entre expertos (`VarianceBudget`), y registra la entropía aparte. Esto no
convierte automáticamente un peldaño en confianza validada ni supone que las
réplicas aporten evidencia independiente. El diagnóstico actual del protocolo
usa un presupuesto nulo y carece de comparables; no es una estimación clínica
de incertidumbre individual.

La medición honesta `nested_stratified_cv_10x9` confirma `clear`: **0,9028**,
frente a **0,4306** de `agreement` y **0,3611** de `confidence_from_rung`.
No se adopta ninguna alternativa. En tarea 1 sí gana `agreement` (0,7582 frente
a 0,7363 constante); `confidence_from_rung` no se adopta en ninguna tarea.
La confianza media entre quienes pasan la puerta en esta corrida es 0,9000;
es una agregación distinta de la medición de políticas.

Pesos modales: `pirads`, `psa`, `age`, `bx_isup` son `important`; `ct`, `fh`,
`comorbidity`, `psad`, `cspca`, `bx_gl_prim`, `bx_gl_sec` son `noted`. Sin grado
positivo se omiten las casillas `bx_*`. La guardia rebaja `fh` si no se reconoce
su fuente. No se adopta la política de silenciar casillas para mejorar grounding.

## 5. Guardias y verificación de artefactos

El código valida la salida, comprueba lenguaje de proceso y valores o grados
sin fuente, y mantiene constantes las políticas de entrega. La lectura interna
de documentos es distinta del `reveal_sequence` entregado vacío.

El defecto de transporte MCP está corregido mediante `_mcp_payload()`:
normaliza listas de bloques, cadenas y diccionarios antes del registrador.
La corrida completa posterior abrió documentos en los 153 casos. Las salidas
antiguas defectuosas no se usan para aceptar la entrega.

`analysis/accept_run.py` comprueba cobertura exacta de ambos splits, esquema,
políticas, actas JSON/MD, una fila de resumen por caso, presencia de telemetría
y hashes de los archivos. También exige verificador listo para aceptar.

Las siete suites de `./delete/run_tests.sh` pasaron: **202 tests** (92+62+22+4+4+7+11). Esto no
sustituye la comprobación de la corrida.

## 6. Cómo se corre

Desde Codex, solicitar al puente autorizado:

```bash
./delete/gpu_bridge/request.sh ".venv/bin/python -m delete_final_versions_task.task_2.agent.run_task2 --all-cases --split all --out-root delete_final_versions_task/task_2/runs" 9000
```

Tras finalizar generación y comprobar que vLLM ha liberado la GPU, puntuar
con `dev/score_local.py` usando `.venv/bin/python` y con
`dev/score_with_judge.py --task 2` usando **`.venv-eval/bin/python`**, mediante
el puente. No caben simultáneamente vLLM y el juez de Ollama.

```bash
PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.task_2.analysis.accept_run
./delete/run_tests.sh
```

## 7. Mapa de ficheros

| Ruta | Contenido |
|---|---|
| `agent/` | Grafo, protocolo, prompts, guardias y runner |
| `experts_2/` | Cinco modelos, caché histórico e informes |
| `PROMPTS.md` | Prompts y coste histórico |
| `analysis/simulate.py` | Simulación dentro de muestra, sin LLM ni juez |
| `analysis/accept_run.py` | Auditoría de los artefactos de la corrida |
| `runs/labeled/` | 72 etiquetados: salidas, actas, resumen, telemetría |
| `runs/unlabeled/` | 81 sin etiqueta, mismo formato |
| `runs/acceptance_4_3.json` | Auditoría aceptada: 153/153 y cero errores |

## 8. Bibliografía

La bibliografía de arquitectura de pizarra, recuperación, ensembles,
incertidumbre y calibración se comparte con [la tarea 1](../task_1/README.md#11-bibliografía).
Referencias adicionales requeridas por el plan:

- Cooperberg et al. (2011). [The CAPRA-S score](https://pubmed.ncbi.nlm.nih.gov/21647869/). Cancer 117(22). Paralelo con la tarea 3.
- EAU-EANM-ESTRO-ESUR-ISUP-SIOG. [Guidelines on Prostate Cancer, archivo de ediciones](https://nl.patients.uroweb.org/guidelines/archive/prostate-cancer) (2024).
- NCCN. *Clinical Practice Guidelines in Oncology: Prostate Cancer* (2024). [Publicación asociada: Insights, versión 3.2024](https://pubmed.ncbi.nlm.nih.gov/38626801/).
- Kweldam et al. (2015). [Cribriform growth is highly predictive for postoperative metastasis and disease-specific death in Gleason score 7 prostate cancer](https://pubmed.ncbi.nlm.nih.gov/25189638/). Modern Pathology 28(3).
- van Leenders et al. (2020). [The 2019 ISUP Consensus Conference on Grading of Prostatic Carcinoma](https://pubmed.ncbi.nlm.nih.gov/32459716/). American Journal of Surgical Pathology 44(8).
- Barry et al. (1992). [The American Urological Association symptom index for benign prostatic hyperplasia](https://pubmed.ncbi.nlm.nih.gov/1279218/). Journal of Urology 148(5).
- Chapman et al. (2001). [A simple algorithm for identifying negated findings and diseases in discharge summaries](https://pubmed.ncbi.nlm.nih.gov/12123149/). Journal of Biomedical Informatics 34(5).
