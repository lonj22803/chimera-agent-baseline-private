# Experto 2 — patología digital y riesgo de *upgrade*

Lee el bloque de grado (`G`) más el informe de anatomía patológica en texto
libre (`H`) y las dos modalidades de representaciones neuronales (`J`, `K`).
86 variables.

Su pregunta propia no es la conducta sino **si el grado de la biopsia se queda
corto**: la discrepancia entre el ISUP clínico y el `AI-predicted ISUP grade
group` que cierra el informe (`path_ai_gap`), la presencia de patrones
cribiforme e intraductal, y la trayectoria entre *timepoints*.

## Rendimiento

| | valor |
|---|---|
| modelo elegido | `extra_trees` |
| **acierto LOO** | **0.8611**  IC 95 % [0.778, 0.944] |
| acierto CV 4×5 | 0.8611 |
| F1 macro | 0.6609 |
| Brier | 0.2733 |
| ECE | 0.0627 |
| suelo (regla de guía) | 0.8611 · Δ = +0.0000 |

Mismo acierto y **misma matriz de confusión** que el [Experto 1](../expert_one/)
y que la regla. Con 86 variables en vez de 28, y peor calibrado (Brier 0.2733
frente a 0.2619; ECE 0.0627 frente a 0.0425).

**Conclusión honesta: este experto no aporta decisión.** Ver el informe de
patología y las preparaciones no cambia ni un caso respecto de leer sólo el
grado. Se mantiene en el panel por dos motivos concretos, no por completitud:

1. **Contesta el primer nodo mejor que nadie.** AUC 0.979 en *«¿hay cáncer
   confirmado?»* frente a 0.920 del bloque de grado. Cuando la junta necesita
   separar `continued_surveillance` del resto, es el que sabe.
2. **Es el único que ve el riesgo de *upgrade*.** `path_ai_gap` no está en
   ninguna otra parte, y es el argumento que un deliberador puede usar para
   discutir un ISUP 1 con PI-RADS 5.

## La escalera **no** ordena bien, y hay que decirlo

| tramo | `confidence` | n | acierto | margen medio |
|---|---|---|---|---|
| `firm` | `clear` | 52 | 0.8462 | 0.680 |
| `supports` | `borderline` | 18 | **0.9444** | 0.366 |
| `discuss` | `uncertain` | 2 | 0.5000 | 0.212 |

El tramo medio acierta **más** que el alto. Con n = 18 frente a n = 52 la
diferencia cabe dentro del ruido, pero la propiedad que justifica una escalera
—que el acierto caiga de forma monótona— **no se cumple aquí**, mientras que en
el [Experto 1](../expert_one/) sí (0.875 → 0.833 → 0.750).

Consecuencia para la junta: **la confianza de este experto no es de fiar como
criterio de abstención.** Si el portavoz se elige por tramo, el Experto 1 debe
tener prioridad sobre éste, que es exactamente lo que hace `run_experts.elect`
al desempatar por acierto leave-one-out dentro del tramo.

## Matriz de confusión

```
                       active_sur  continued_  active_tre  watchful_w     n
active_surveillance            21           1           3           0    25
continued_surveillance          1          13           0           0    14
active_treatment                3           0          28           0    31
watchful_waiting                0           0           2           0     2
pred n                         25          14          33           0
```

## Cómo entrenarlo

```bash
python train_expert_two.py
python train_expert_two.py --blocks GH        # sin las representaciones neuronales
```
