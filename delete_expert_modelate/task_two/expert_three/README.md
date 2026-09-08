# Experto 3 — aptitud para tratamiento radical

Lee el bloque clínico (`A`) y el de comorbilidad y expectativa de vida (`I`).
63 variables. **No mira el grado del tumor**, y eso es deliberado: contesta la
pregunta que separa `watchful_waiting` del resto, que las guías no plantean en
términos oncológicos sino de beneficio esperado —esperanza de vida, carga de
comorbilidad, estado funcional.

Es el único experto del panel construido alrededor de una clase concreta, y el
único cuyo resultado principal es **negativo**.

## Rendimiento

| | valor |
|---|---|
| modelo elegido | `extra_trees_balanced` |
| acierto LOO | 0.6389  IC 95 % [0.528, 0.750] |
| acierto CV 4×5 | 0.6667 |
| F1 macro | 0.5235 |
| acierto equilibrado | 0.5234 |
| Brier | 0.4865 |
| ECE | 0.1069 |
| suelo (regla de guía) | 0.8611 · **Δ = −0.2222, p = 0.001** |
| suelo (prevalencia) | 0.4306 |

Está **significativamente por debajo de la regla de guía** y por encima de la
prevalencia. Es decir: sus variables llevan algo de señal —casi toda del bloque
`A`, que contiene el estado de biopsia—, pero como clasificador de las cuatro
conductas es claramente peor que mirar sólo el grado.

## El resultado que importa es el negativo

La pregunta para la que se diseñó es el nodo 3 de la cascada, *«¿se beneficia
del tratamiento?»*, y ahí la medida honesta es:

| bloque | AUC leave-one-out sobre *«¿se beneficia?»* |
|---|---|
| clínico (A) | 0.758 |
| embeddings (J+K) | 0.645 |
| PCA embeddings (K) | 0.613 |
| grado (G) | 0.516 |
| patología (H) | 0.435 |
| **fragilidad (I)** | **0.194** |
| serie de PSA (C) | 0.000 |

n = 33, con **2 negativos**. Una columna que va de 0.000 a 0.758 sin patrón
interpretable —donde la serie de PSA «predice» perfectamente al revés y el
bloque clínico «gana» al que se diseñó para la tarea— no es un ordenamiento de
fuentes: es la varianza de un AUC estimado sobre 31 contra 2.

**La cohorte no contiene la evidencia para contestar esa pregunta.** Con
`watchful_waiting` en 2 casos de 72, no la va a contener ningún modelo.

## Es el único que se atreve con `watchful_waiting`, y falla

```
                       active_sur  continued_  active_tre  watchful_w     n
active_surveillance            13           1          10           1    25
continued_surveillance          1          13           0           0    14
active_treatment               10           0          20           1    31
watchful_waiting                2           0           0           0     2
pred n                         26          14          30           2
```

Predice `watchful_waiting` dos veces —los otros cuatro expertos, nunca— y las
dos son falsos positivos. Los dos casos reales los manda a
`active_surveillance`. Con `class_weight="balanced"` el modelo aprende a
apostar por la clase rara; con dos ejemplares, apostar no es aprender.

## La escalera tampoco ordena

| tramo | `confidence` | n | acierto | margen medio |
|---|---|---|---|---|
| `firm` | `clear` | 14 | 0.8571 | 0.376 |
| `supports` | `borderline` | 21 | 0.5714 | 0.246 |
| `discuss` | `uncertain` | 37 | 0.6216 | 0.079 |

El tramo alto sí separa (0.857 sobre 14 casos), pero los dos inferiores están
invertidos. Y 37 de 72 casos caen en `discuss`: este experto, medido con
honestidad, declara que no sabe en la mitad de la cohorte.

## Entonces, ¿por qué se queda en el panel?

Por una razón y sólo una: **un experto que mide su propia ignorancia es más útil
que un hueco.** Si la junta recibe un veredicto compuesto por la cascada sin
saber que su tercer paso es un juicio clínico sin respaldo estadístico, tratará
ese paso como informado. Con este experto en la mesa, el `expert-panel.json`
lleva un AUC de 0.194 y 37 casos en `discuss`, y eso es una instrucción legible:
*aquí decide el clínico, no el modelo.*

No se le debe dar voto. `run_experts.elect` lo garantiza: el portavoz se elige
por acierto leave-one-out dentro del tramo más alto, y con 0.6389 este experto
nunca gana a los de 0.8611.

## Cómo entrenarlo

```bash
python train_expert_three.py
python train_expert_three.py --blocks I       # sólo fragilidad, sin el bloque clínico
```
