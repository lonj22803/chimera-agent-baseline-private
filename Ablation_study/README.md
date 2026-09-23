# Ablation_study: estudio de ablación de las tareas 1, 2 y 3

Qué intervenciones de la V4 (`version_final_reto_send_v4`) son necesarias para la exactitud de
la inferencia, cuáles sólo para la forma del formulario o la nota, y cuáles sobran.

| Fichero | Qué es |
|---|---|
| [Memoria del estudio T1/T2/T3](MEMORIA_ESTUDIO_ABLACION_T1_T2_T3.md) | Exposición del trabajo: objetivos, metodología, relevancia de expertos y LLM, resultados, duración y trabajo futuro |
| [Informe ejecutivo final T1/T2/T3](reports/INFORME_EJECUTIVO_FINAL_T1_T2_T3.md) | Hallazgos principales, reducciones candidatas, costes, límites y siguientes pasos |
| [PLAN_ABLACION_T1.md](PLAN_ABLACION_T1.md) | **Plan T1**: diseño, catálogo, hipótesis y los pasos para Codex. Fuente de verdad del avance T1 |
| [Extensión T2/T3](T2_T3/README.md) | Plan, ejecutores, resultados e informe técnico de tratamiento y recurrencia |
| `PREREGISTRO.md` | Hipótesis y regla de veredicto, congeladas antes de medir (PASO 0.3) |
| `BITACORA_ABLACION.md` | Decisiones, desviaciones y bloqueos |
| `RUNBOOK_GPU.md` | Lo que ejecuta el humano con vLLM/Ollama (PASO 4.3) |
| `harness/` · `configs/` · `ablacion_tests/` | Código del estudio (nada se toca fuera de esta carpeta) |
| `results/` · `reports/` | Agregados y el informe final |
| `runs/` | Salidas de los brazos con LLM (no se versionan) |

**Regla de oro:** `version_final_reto_send_v4/` es de sólo lectura. Todo el código nuevo vive aquí.

Arrancar a Codex con un paso: ver §10 del plan.
