# Experto 4 — fusión multi-fuente

El único que ve el expediente entero: prompt estructurado, serie de PSA, informe
radiológico, grado, patología, fragilidad y las dos modalidades de
representaciones neuronales. **184 variables.**

Su papel en el panel no es ganar —no gana— sino ser el **control**: la
comprobación de que ninguna fuente aporta algo cuando se la deja competir con
todas las demás en igualdad de condiciones.

## Rendimiento

| | valor |
|---|---|
| modelo | `extra_trees` (fijado, ver más abajo) |
| **acierto LOO** | **0.8611**  IC 95 % [0.778, 0.944] |
| acierto CV 4×5 | 0.8611 |
| F1 macro | 0.6609 |
| Brier | 0.2652 |
| ECE | 0.0760 |
| suelo (regla de guía) | 0.8611 · Δ = +0.0000, p = 1.000 |

**184 variables producen exactamente la misma matriz de confusión que 28.** No
un acierto parecido: las mismas 72 predicciones, caso a caso, que el
[Experto 1](../expert_one/) sobre el bloque de grado y que la regla de guía de
un solo predictor.

Es el resultado que cierra la cuestión de las fuentes, y coincide con lo que la
ablación ya decía por separado: retirar cualquier bloque salvo el de grado deja
el acierto intacto, y el bloque de grado solo es indistinguible del conjunto
completo (p = 0.735).

## Matriz de confusión

```
                       active_sur  continued_  active_tre  watchful_w     n
active_surveillance            21           1           3           0    25
continued_surveillance          1          13           0           0    14
active_treatment                3           0          28           0    31
watchful_waiting                0           0           2           0     2
pred n                         25          14          33           0
```

## La escalera tampoco ordena aquí

| tramo | `confidence` | n | acierto | margen medio |
|---|---|---|---|---|
| `firm` | `clear` | 55 | 0.8545 | 0.599 |
| `supports` | `borderline` | 11 | **0.9091** | 0.303 |
| `discuss` | `uncertain` | 6 | 0.8333 | 0.175 |

Como en los [Expertos 2](../expert_two/) y [3](../expert_three/), el tramo medio
acierta más que el alto. De los cinco expertos, **sólo el Experto 1 tiene una
escalera monótona** (0.875 → 0.833 → 0.750), y por eso es el que debe llevar la
voz cuando el panel elige portavoz por tramo.

Es una observación incómoda y conviene no adornarla: con 72 casos repartidos en
tres tramos, la ordenación de la escalera es en sí misma una cantidad ruidosa.
Que se cumpla en uno de cinco expertos no es evidencia de que ese experto tenga
una incertidumbre mejor calibrada; es compatible con el azar. Lo que sí está
medido con más muestra es su ECE (0.0425, el mejor del panel), y ése es el
motivo defendible para darle prioridad.

## Por qué el modelo va fijado

`--model` tiene por defecto `extra_trees` en lugar de seleccionar entre la lista
corta. La etapa 1 ya ordenó los 17 candidatos y la ablación ya mostró que
ninguno de los siete bloques adicionales mueve una predicción: gastar cinco
validaciones cruzadas completas para reelegir sobre un superconjunto redundante
no cambia la conclusión, sólo el reloj. Con `--model <otro>` se puede comprobar.

## Cómo entrenarlo

```bash
python train_expert_four.py
python train_expert_four.py --model random_forest
```
