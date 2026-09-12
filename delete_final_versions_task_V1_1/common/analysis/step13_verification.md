# Paso 1.3 — aceptación incompleta

Implementado el techo task2: cancer=clear, treat=borderline, fit=uncertain.
Los tests ejercitan el mecanismo con acierto 0.94 y 1.0, presupuestos nulos
y positivos, y cuantiles 0 e infinito; fit permanece uncertain.

No se generaron los dos cachés de confianza ni se ejecutó la aceptación con
`--confidence-input`: falta el LOO anidado real. La ejecución siguiente es
un diagnóstico sin cachés, no un sustituto de esa aceptación.
`confidence_from_rung` sigue NO MEDIDO en ambas tareas.
El mensaje histórico de task2 en measure_forms menciona que falta protocolo;
la cascada sí existe y ahora tiene sus techos. Lo pendiente son sus veredictos
y presupuestos LOO con calibración interior.

Se conserva forms_report.json y no se adopta ninguna política nueva.
La comparación de B/C con el informe original devolvió:
```text
Compuerta B/C conservada: True
confidence_from_rung: {'task1': None, 'task2': None}
```

No se modificaron delete_solution_one/ ni delete_expert_modelate/.
`git diff --name-only -- delete_solution_one delete_expert_modelate` no produjo salida.
No se instalaron dependencias. El benchmark utiliza sklearn/joblib ya presentes
para reentrenar las recetas originales exigidas en el paso. No invoca al juez.

## Tests de incertidumbre

```sh
.venv/bin/python -m pytest -q delete_final_versions_task/common/tests/test_uncertainty_forms.py
```

Código de salida: 0. Salida real:

```text
...........................                                              [100%]
27 passed in 0.06s
```

## Tests de common

```sh
.venv/bin/python -m pytest -q delete_final_versions_task/common/tests
```

Código de salida: 0. Salida real:

```text
............................................                             [100%]
=============================== warnings summary ===============================
delete_final_versions_task/common/tests/test_measure_forms.py::test_numpy_heads_match_existing_model[2]
delete_final_versions_task/common/tests/test_measure_forms.py::test_numpy_heads_match_existing_model[3]
delete_final_versions_task/common/tests/test_measure_forms.py::test_numpy_heads_match_existing_model[4]
  /home/jjlondono/PycharmProjects/chimera-agent-baseline/.venv/lib/python3.12/site-packages/sklearn/linear_model/_logistic.py:1403: FutureWarning: 'penalty' was deprecated in version 1.8 and will be removed in 1.10. To avoid this warning, leave 'penalty' set to its default value and use 'l1_ratio' or 'C' instead. Use l1_ratio=0 instead of penalty='l2', l1_ratio=1 instead of penalty='l1', l1_ratio set to a float between 0 and 1 instead of penalty='elasticnet', and C=np.inf instead of penalty=None.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
44 passed, 3 warnings in 1.71s
```

## Suite existente

```sh
.venv/bin/python -m pytest -q
```

Código de salida: 0. Salida real:

```text
........................................................................ [ 78%]
....................                                                     [100%]
92 passed in 0.47s
```

## Diagnóstico de medición sin cachés

```sh
.venv/bin/python -m delete_final_versions_task.common.analysis.measure_forms --output delete_final_versions_task/common/analysis/forms_report_step13.json
```

Código de salida: 2. Salida real:

```text
Midiendo task1: 91 casos, LOO anidado...
Midiendo task2: 72 casos, LOO anidado...

task1: n=91
A confidence_score
politica                 metrica    delta  sube baja        p adoptar
clear                    0.736264 +0.000000    0    0 1.000000 False
agreement                NO MEDIDO: El caché honest de task1 usa 5 folds y la corrida final usa expertos ajustados con los etiquetados; faltan veredictos LOO y calibración interior sin fuga.
confidence_from_rung     NO MEDIDO: El caché honest de task1 usa 5 folds y la corrida final usa expertos ajustados con los etiquetados; faltan veredictos LOO y calibración interior sin fuga.
B variable_weight_score
politica                 metrica    delta  sube baja        p adoptar
moda                     0.849451 +0.000000    0    0 1.000000 False
aprendido_entero         0.863248 +0.013797   47   27 0.026517 True
arbitrate_cells          0.877981 +0.028531   60    7 0.000000 True
B important_decisive_factor_score
politica                 metrica    delta  sube baja        p adoptar
moda                     0.752645 +0.000000    0    0 1.000000 False
aprendido_entero         0.723160 -0.029485   27   39 0.175286 False
arbitrate_cells          0.766811 +0.014166   27   14 0.059584 True
C important_decisive_factor_score
politica                 metrica    delta  sube baja        p adoptar
moda                     0.752645 +0.000000    0    0 1.000000 False
umbral_0.5               0.724078 -0.028567   27   38 0.214539 False
expected_f1_set          0.736210 -0.016435   27   38 0.214539 False
Contraste expected_f1_set vs umbral_0.5: {"delta": 0.012131946197880257, "n_sube": 20, "n_baja": 18, "n_empata": 53, "p": 0.8714146793645341}
Escalera de fiabilidad: null

task2: n=72
A confidence_score
politica                 metrica    delta  sube baja        p adoptar
clear                    0.902778 +0.000000    0    0 1.000000 False
agreement                NO MEDIDO: No hay protocolo por peldaños de task2 especificado ni veredictos LOO con varianzas y calibración interior para ese protocolo.
confidence_from_rung     NO MEDIDO: No hay protocolo por peldaños de task2 especificado ni veredictos LOO con varianzas y calibración interior para ese protocolo.
B variable_weight_score
politica                 metrica    delta  sube baja        p adoptar
moda                     0.841340 +0.000000    0    0 1.000000 False
aprendido_entero         0.805913 -0.035427   13   42 0.000114 False
arbitrate_cells          0.840520 -0.000821   13   15 0.850554 False
B important_decisive_factor_score
politica                 metrica    delta  sube baja        p adoptar
moda                     0.675555 +0.000000    0    0 1.000000 False
aprendido_entero         0.619020 -0.056536   15   36 0.004601 False
arbitrate_cells          0.661563 -0.013992    1    6 0.125000 False
C important_decisive_factor_score
politica                 metrica    delta  sube baja        p adoptar
moda                     0.675555 +0.000000    0    0 1.000000 False
umbral_0.5               0.621462 -0.054093   14   29 0.031539 False
expected_f1_set          0.631251 -0.044304   19   40 0.008641 False
Contraste expected_f1_set vs umbral_0.5: {"delta": 0.009788359788359778, "n_sube": 15, "n_baja": 21, "n_empata": 36, "p": 0.40503224614076316}
Escalera de fiabilidad: null

Informe: delete_final_versions_task/common/analysis/forms_report_step13.json
Aceptación completa: False
```

## Coste medido y motivo de pausa

```sh
.venv/bin/python -m delete_final_versions_task.common.analysis.benchmark_nested_confidence
```

Código de salida: 0. Salida real:

```text
structured: fit 90 cases, excluded [0]
{"expert": "structured", "fit_seconds": 23.128393135000806, "predict_seconds": 41.2296309609992, "total_seconds": 64.35802409600001}
structured: fit 89 cases, excluded [0, 1]
{"expert": "structured", "fit_seconds": 21.95042595799896, "predict_seconds": 40.12896223200005, "total_seconds": 62.07938818999901}
fusion: fit 90 cases, excluded [0]
{"expert": "fusion", "fit_seconds": 38.98903201199937, "predict_seconds": 45.10085724400051, "total_seconds": 84.08988925599988}
fusion: fit 89 cases, excluded [0, 1]
{"expert": "fusion", "fit_seconds": 38.5837838059997, "predict_seconds": 45.33954461199755, "total_seconds": 83.92332841799725}
Report: /home/jjlondono/PycharmProjects/chimera-agent-baseline/delete_final_versions_task/common/analysis/nested_confidence_cost.json
```

El benchmark conserva el esquema histórico de columnas para estimar coste;
no es un caché LOO honesto. El generador definitivo debe seleccionar columnas
y ajustar imputadores sólo en cada entrenamiento. No se reutilizan las
predicciones del modelo entrenado: se clona y reajusta su receta.

Son 91 folds exteriores, cada uno con 90 casos interiores. Para que cada
predicción interior excluya ambos casos, los modelos se ajustan sobre 89.
La implementación directa permite reutilizar el ajuste del par {i,j}
para los dos folds exteriores: 91 ajustes exteriores + C(91,2)=4095 ajustes
interiores por receta. No se cuentan 91² folds exteriores.

Extrapolación serial a partir de una muestra por tamaño: estructurado 72.24 h; fusión 97.59 h; suma 169.83 h.
No es un tiempo total medido ni una cota mínima inevitable: los tiempos
varían entre folds y una implementación optimizada puede reducirlos.
La suma no incluye traza, variante de fusión sin laboratorio ni task2.
Dividir por trabajadores sería sólo un ideal, no una aceleración medida.

El paso 1.3 de delete/PLAN_CODEX.md exige medir antes de descartar el LOO
y «repórtalo con el tiempo medido y decide con el usuario si se aproxima».
Se pausa en ese punto, pendiente de decidir entre ejecución larga exacta
o una aproximación explícitamente autorizada. No se ha implementado ni
publicado una aproximación como honest. No se avanzó al paso siguiente.
