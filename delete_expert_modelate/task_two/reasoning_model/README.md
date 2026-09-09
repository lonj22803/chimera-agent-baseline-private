# El formulario de razonamiento

Pasada la puerta de la decisión, **el 82.5 % restante del `case_score` sale de
aquí**: `confidence`, `variable_weights` y `reveal_sequence`, puntuados contra
la traza que rellenó el urólogo.

No es un experto más del panel: no clasifica la conducta. Es el que redacta el
segundo de los dos ficheros que el reto exige.

## Tres hechos de esta cohorte que cambian cómo se rellena

**1. `reveal_sequence` está vacío en los 72 casos.** En la tarea 2 el clínico
recibe el expediente completo, no lo va destapando. El `tool_score` premia la
*precisión* de las herramientas declaradas —`|agente ∩ patrón| / |agente|`— de
modo que declarar cualquier sección cuando el patrón no declaró ninguna lo pone
a cero. **La predicción correcta de este campo es la lista vacía**, y no hay
nada que aprender.

**2. `confidence` sólo toma dos valores:** `clear` (58) y `borderline` (14).
`uncertain` no aparece nunca. Emitirlo cuesta el componente entero, porque la
distancia a `clear` es 2 sobre 2.

**3. Tres de las once casillas están condicionadas.** `bx_isup`, `bx_gl_prim` y
`bx_gl_sec` aparecen en 52 de las 72 trazas, y aparecen exactamente cuando la
biopsia dio grado. Emitirlas de más **no** penaliza el `variable_weight_score`
—ese recorre las claves del patrón— pero sí el
`important_decisive_factor_score`, que es un F1 de conjuntos y cuenta como falso
positivo toda variable marcada *important* o *decisive* de más. De ahí la puerta
`bx_isup > 0`, que acierta 66 de 72.

## La puerta usa la métrica del reto, no el acierto exacto

El evaluador puntúa cada casilla por **distancia ordinal**,
`1 − |W(patrón) − W(predicho)| / 3`: fallar un *decisive* por *important* cuesta
un tercio de lo que cuesta fallarlo por *not_used*. Un modelo puede acertar más
casillas exactas y aun así puntuar peor.

Por eso cada casilla se compara con la constante que **minimiza esa distancia**
—que en esta cohorte coincide con la moda en las once, pero eso es un hecho
medido, no una suposición— y el modelo aprendido se adopta sólo si la bate bajo
leave-one-out:

| casilla | LOO aprendido | mejor constante | valor | adoptado |
|---|---|---|---|---|
| `bx_isup` | **0.8718** | 0.8462 | `important` | **sí** |
| `psa` | **0.8657** | 0.8611 | `important` | **sí** |
| `fh` | 0.8843 | 0.8981 | `noted` | no |
| `confidence` | 0.8958 | 0.9028 | `clear` | no |
| `age` | 0.8056 | 0.8565 | `important` | no |
| `comorbidity` | 0.8102 | 0.8519 | `noted` | no |
| `psad` | 0.8009 | 0.8519 | `noted` | no |
| `cspca` | 0.7810 | 0.8476 | `noted` | no |
| `ct` | 0.7778 | 0.8102 | `noted` | no |
| `pirads` | 0.7546 | 0.8194 | `important` | no |
| `bx_gl_sec` | 0.7308 | 0.7756 | `noted` | no |
| `bx_gl_prim` | 0.7244 | 0.7756 | `noted` | no |

**Dos de doce.** El resto se queda en su constante, que es lo que impide que el
formulario empeore por añadir parámetros. Un modelo por casilla sobre 72 trazas
tiene poco que ganar y mucho que sobreajustar.

## Lo que produce

| componente | valor | peso sin juez |
|---|---|---|
| `confidence_score` | 0.9028 | 0.225 |
| `variable_weight_score` | 0.8545 | 0.275 |
| `important_decisive_factor_score` | 0.6798 | 0.175 |
| `tool_score` | **1.0000** | 0.150 |
| `section_grounding_score` | 0.2154 | 0.175 |
| **suma ponderada** | **0.7448** | |

Ese 0.7448 es el techo del formulario. El `case_score` real lo multiplica por la
puerta de la decisión: un caso con la conducta equivocada puntúa **cero** aunque
el formulario sea perfecto.

## Una trampa del evaluador local, documentada y no explotada

El `section_grounding_score` penaliza toda variable pesada por encima de
`not_used` cuya sección de origen no aparezca en el `reveal_sequence`. Con la
lista vacía que esta tarea exige, sólo `psa` y `age` quedan ancladas
(`comorbidity` es *ungradable* y se excluye). Se puede subir ese componente a
1.0 silenciando las otras nueve casillas:

| política | `var_weight` | F1 factores | *grounding* | sin juez | **con juez** |
|---|---|---|---|---|---|
| plantilla completa | 0.8413 | 0.6582 | 0.2000 | 0.7347 | **0.7696** |
| silenciar lo no anclable | 0.6574 | 0.4608 | 1.0000 | **0.7896** | 0.7340 |

La segunda gana **sólo porque el juez de razonamiento está desactivado**, lo que
redistribuye el peso del *grounding* de 0.05 a 0.175. Con la configuración real
del leaderboard pierde 0.036. **No se adopta**, y cualquier número medido aquí
con `USE_RATIONALE_JUDGE=0` que dependa del *grounding* no es comparable con el
leaderboard.

## Cómo entrenarlo

```bash
python train_reasoning_model.py
```
