# Experimento: ¿sirve de algo el predictor sobre embeddings?

Prueba **temporal y aislada**. Enciende las dos piezas que el baseline trae apagadas
(`features.FeatureStore` + `tools.predictor.run_predictor`) y mide si el agente se comporta
distinto y si la puntuación mejora. **El repo queda exactamente como estaba**; todo lo que
produjo el experimento vive aquí.

El análisis completo, con gráficas, está en **`exploratory_analysis.ipynb`**.

## Respuesta corta

**No mejora la línea base.** El delta global (+0,033) no se distingue del ruido: 84 casos
suben y 77 bajan (prueba de signos, p = 0,64).

| | control `off` | tratamiento `on_prompt` | delta |
|---|---|---|---|
| T1 · biopsia | 0,6428 | 0,6387 | −0,0041 |
| T2 · tratamiento | 0,3485 | 0,4476 | +0,0991 |
| T3 · recurrencia | 0,4650 | 0,4381 | −0,0270 |
| **OVERALL (2:2:1)** | **0,4895** | **0,5221** | **+0,0326** |

Tres hallazgos, en orden de importancia:

1. **Con el prompt intacto, la herramienta no existe para el agente: 0 llamadas en 30 casos.**
   El prompt de sistema es un protocolo de coste que enumera siete herramientas; una
   herramienta MCP registrada pero no anunciada ahí es una herramienta muerta.
2. **Anunciada, se usa poco y al revés de como convendría:** 38 % en T1 (donde la cabeza tiene
   AUC 0,43, peor que el azar), 14 % en T2 (donde tiene 0,76) y ~1 % en T3. El agente ignora
   el campo `reliability` que la propia herramienta le entrega.
3. **La subida de T2 no es de la herramienta.** El 85 % del delta viene de casos en los que el
   predictor nunca se llamó: la adenda cambió el prompt de los 72 y reordenó sus trayectorias.
   Por caso, los que la llamaron mejoran +0,084 y los que no, +0,075.

**Lo que sí vale:** la cabeza sobre MRI+biopsia es lo único medido que predice
`continued_surveillance` (16) y `watchful_waiting` (3), las dos clases que el agente nunca
emite. Ese activo se desperdicia entregándolo como un número en una herramienta opcional.

## Diseño

| Brazo | predictor | prompt | casos |
|---|---|---|---|
| `on` (sonda) | ✔ | intacto | 30 (10/tarea) |
| `off` (control) | ✘ | intacto | 238 etiquetados |
| `on_prompt` (tratamiento) | ✔ | + adenda de 1045 chars | 238 etiquetados |

`temperature=0`, modelo cargado una sola vez para los tres brazos, mismo orden de casos.
Predicciones **out-of-fold** (`StratifiedKFold(5)`): la cabeza nunca vio la etiqueta del caso
que puntúa. Evaluador oficial, juez de razonamiento desactivado, casos sin salida contados
como fallo.

## Ficheros

| | |
|---|---|
| `exploratory_analysis.ipynb` | el análisis completo (34 celdas, 7 gráficas) |
| `train_head.py` | entrena las cabezas out-of-fold sobre los embeddings |
| `run_experiment.py` | runner de dos brazos (no toca `run.py`; try/except por caso, trazas) |
| `comparar.py` | puntuación con el evaluador oficial + trazas + oráculo |
| `_build_notebook.py` | genera el `.ipynb` |
| `artifacts/predictor_oof.json` | la tabla out-of-fold que consume la herramienta |
| `artifacts/head_metrics.json` | métricas de validación cruzada de las cabezas |
| `artifacts/predictor.py.orig` | `tools/predictor.py` original (el del repo) |
| `artifacts/predictor.py.experimento` | `tools/predictor.py` parcheado (para reproducir) |
| `output_{off,on,on_prompt}/` | salidas GC por caso |
| `traces/{off,on,on_prompt}/` | traza por caso: llamadas, salidas, avisos, duración |
| `resumen_*.jsonl` · `experimento.log` | progreso y fallos |

## Reproducir

```bash
cp delete_test/artifacts/predictor.py.experimento src/chimera_agent_baseline/tools/predictor.py
python delete_test/train_head.py
python delete_test/run_experiment.py --arms off on_prompt --temperature 0.0
python delete_test/_build_notebook.py
git checkout -- src/chimera_agent_baseline/tools/predictor.py
```

## Nota sobre las cifras absolutas

El control de aquí (0,4895) **no** es el 0,5651 de `dev/baseline_reference.json`: aquel se
midió a `temperature=1.0`. Fijar la temperatura a 0 hace el A/B limpio pero baja el número
absoluto — sobre todo en T3, donde el `form_fill` pierde 9 casos de forma determinista
(el fallo de censura ya conocido, ahora reproducible en vez de enmascarado por el muestreo).
La comparación válida es `on_prompt` contra `off`, no contra aquella cifra.
