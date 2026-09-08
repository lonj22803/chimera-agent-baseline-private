# Experto 1 — grado, estadio y grupo de riesgo de guía

**El ancla del panel.** Lee sólo el bloque `G`: las cuatro variables de las que
la etiqueta se derivó retrospectivamente —`bx_isup`, `bx_gl_prim`, `bx_gl_sec`,
`ct`— más el PSA, la densidad y las reglas EAU/NCCN calculadas como variables.

Es el experto barato: no depende de que el informe de patología venga bien
redactado, ni de que existan las representaciones neuronales. Sigue en pie
cuando falta todo lo demás.

## Rendimiento

Leave-one-out sobre los 72 casos etiquetados, 28 variables:

| | valor |
|---|---|
| modelo elegido | `random_forest` |
| **acierto LOO** | **0.8611**  IC 95 % [0.778, 0.944] |
| acierto CV 4×5 | 0.8611 |
| F1 macro | 0.6609 |
| acierto equilibrado | 0.6679 |
| **Brier** | **0.2619** |
| **ECE** | **0.0425** |
| suelo (regla de guía) | 0.8611 · Δ = +0.0000 |

**Empata a la regla en decisión y la bate en probabilidad.** El Brier baja de
0.2781 a 0.2619 y el ECE de 0.1152 a 0.0425 —casi un tercio—. Ese es el único
argumento defendible para preferir el modelo aprendido, y es el argumento que
importa para una junta: predice la misma conducta, pero dice mucho mejor cuánto
se fía.

## La escalera de fiabilidad

Fuera de muestra, reentrenando el ensemble completo en cada iteración:

| tramo | `confidence` | n | acierto | margen medio |
|---|---|---|---|---|
| `firm` | `clear` | 56 | **0.875** | 0.741 |
| `supports` | `borderline` | 12 | 0.833 | 0.466 |
| `discuss` | `uncertain` | 4 | 0.750 | 0.224 |

Cae de forma monótona. Si no cayera, la incertidumbre no estaría midiendo nada.
El tramo alto cubre 56 de 72 casos, así que la abstención informada es barata:
sólo 4 casos llegan a `discuss`.

## Matriz de confusión

```
                       active_sur  continued_  active_tre  watchful_w     n
active_surveillance            21           1           3           0    25
continued_surveillance          1          13           0           0    14
active_treatment                3           0          28           0    31
watchful_waiting                0           0           2           0     2
pred n                         25          14          33           0
```

`watchful_waiting` no se predice nunca. Con 2 casos de 72 es la respuesta
correcta bajo una métrica de acierto exacto, y por eso esa clase se aborda en el
[Experto 5](../expert_five/), que la saca de una pregunta con 33 casos en vez de
2 — y que mide honestamente que tampoco ahí hay evidencia.

## Cómo entrenarlo

```bash
python train_expert_one.py                    # selección entre la lista corta
python train_expert_one.py --model extra_trees --blocks GH
```
