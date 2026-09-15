# Dónde está cada pizarra, y por qué no están en el mismo sitio

Las **tres** tareas escriben acta. Lo que cambia es dónde, y eso me hizo decir
—mal— que T3 no tenía pizarra:

| tarea | ruta | formato |
|---|---|---|
| T1 | `task_1/{labeled,unlabeled}/boards/<caso>.json` y `.md` | una por caso |
| T2 | `task_2/{labeled,unlabeled}/boards/<caso>.json` y `.md` | una por caso |
| T3 | `task_3/output/task3/<caso>/acta.json` y `acta.md` | **junto a la salida del caso** |

Buscar las de T3 en `boards/` da cero y parece que no existen. Existen: son 75,
con **once intervenciones** cada una.

## La junta de T3, intervención a intervención

`Task3Board` en `task_3/agent/graph.py` — «once intervenciones secuenciales, acta
inmutable y fuentes explícitas»:

| # | interviene | qué aporta |
|---|---|---|
| 1 | `INTAKE` | lee el expediente en voz alta y no interpreta nada |
| 2 | `EXPERT-CAPRA` | CAPRA-S con su referencia publicada y su c-index |
| 3 | `EXPERT-SURGICAL` | grado, estadio, márgenes, vesículas, ganglios |
| 4 | `EXPERT-DIGITAL` | log-riesgo del modelo, declarado como **advisory** |
| 5 | `MODERATOR` | qué documentos hay que abrir y con qué pregunta |
| 6 | `REGISTRAR` | lo que se abrió de verdad, con su texto |
| 7 | `EXPERT-FUSION` | el portavoz seleccionado de forma anidada |
| 8 | `PANEL-PROTOCOL` | la regla que decide, no una opinión |
| 9 | `EXPERT-HORIZON` | riesgo → meses, con su calibración completa |
| 10 | `VERIFIER` | qué falta, qué no está respaldado |
| 11 | `CHAIR` | redacta; no vota |

## Lo que la pizarra deja comprobar del cambio de V2_2

`EXPERT-HORIZON` registra la sustitución del exportador de forma auditable,
incluyendo **el valor que habría dado la CDF empírica**:

```json
{
  "months_to_recurrence": 30.87229814780193,
  "calibration": {
    "exportador": "cdf_suave_v1",
    "months_map": "90 exp(-0.1 * 12 * (1 - CDF_normal_train(raw)))",
    "sustituye": "percentil por CDF empírica de 75 valores",
    "meses_cdf_empirica": 29.838803290639163,
    "nota": "El orden del riesgo se conserva exactamente..."
  }
}
```

Así se compara caso a caso el mapa viejo y el nuevo **sin volver a correr nada**.

**Corrección registrada:** en la primera corrida el acta declaraba `a: 93.67`,
heredado de la rama original del método, cuando el mapa aplicado usa `a: 90`. Los
meses eran correctos, pero un acta que declara parámetros distintos de los
aplicados no sirve como evidencia. Corregido en `task_3/policy.py`; T3 se vuelve
a correr al cerrar la cobertura.
