# Experto 5 — el estratificador: cascada de guía de tres nodos

No mejora el acierto de nadie. **Descompone** el 0.8611 en las tres preguntas
que EAU y NCCN encadenan, y mide cada una por separado:

```
1. ¿Hay cáncer confirmado?      GH    ->  no: continued_surveillance
2. ¿Está indicado tratar?       AGH   ->  no: active_surveillance
3. ¿El paciente se beneficia?   AGI   ->  no: watchful_waiting
                                          sí: active_treatment
```

Cada nodo ve **su** bloque y sólo el suyo: el que decide si el paciente se
beneficiaría de un tratamiento radical no ve el grado del tumor, porque ésa no
es la pregunta que contesta. La composición es la regla de la cadena, así que la
salida sigue siendo una distribución sobre las cuatro conductas, no una
etiqueta.

## Por qué existe

Un clasificador plano de cuatro salidas tiene que aprender, con 72 casos, una
frontera para `watchful_waiting` a partir de **2 ejemplares**. No hay forma de
que salga bien: el modelo aprende a no predecir nunca esa clase, que es la
respuesta óptima bajo acierto exacto y la respuesta inútil bajo cualquier otro
criterio.

La alternativa no es reponderar; es descomponer la etiqueta por la costura que
la guía ya tiene. Así `watchful_waiting` sale de una pregunta con **33 casos** en
vez de 2.

## Los tres nodos, medidos por separado

Leave-one-out, `extra_trees`:

| nodo | pregunta | n | positivos | AUC | acierto | suelo |
|---|---|---|---|---|---|---|
| 1 (GH) | ¿hay cáncer confirmado? | 72 | 58 | **0.957** | 0.972 | 0.806 |
| 2 (AGH) | ¿está indicado tratar? | 58 | 33 | **0.874** | 0.897 | 0.569 |
| 3 (AGI) | ¿se beneficia del tratamiento? | 33 | **31** | **0.565** | 0.939 | 0.939 |

**Éste es el resultado del experto.** El mismo 0.8611 que dan los otros cuatro
se abre en dos preguntas bien contestadas —0.957 y 0.874, muy por encima de sus
suelos— y una que la cohorte no puede contestar: AUC 0.565 sobre 33 casos con
**dos negativos**, y un acierto de 0.939 que es exactamente el de decir «apto»
siempre.

Publicar ese 0.565 es el propósito del experto. Una junta que recibe un
veredicto compuesto sin sus partes no puede saber que el tercer paso es un
juicio clínico sin respaldo estadístico; con las partes, sí. El
`expert-panel.json` lleva las tres probabilidades intermedias en `nodes`.

## La cascada compuesta

| | valor |
|---|---|
| **acierto LOO** | **0.8611**  IC 95 % [0.778, 0.944] |
| F1 macro | 0.6609 |
| Brier | 0.2842 |
| ECE | 0.0857 |
| suelo (regla de guía) | 0.8611 · Δ = +0.0000, p = 1.000 |

Es el peor Brier de los cuatro expertos empatados en acierto (0.2842 frente a
0.2619 del [Experto 1](../expert_one/)). Componer tres probabilidades por la
regla de la cadena multiplica sus errores de calibración, y con un nodo que está
en el azar el producto arrastra ese ruido. Se conserva igualmente porque su
aportación no es la probabilidad final sino las tres intermedias.

```
                       active_sur  continued_  active_tre  watchful_w     n
active_surveillance            21           1           3           0    25
continued_surveillance          1          13           0           0    14
active_treatment                3           0          28           0    31
watchful_waiting                0           0           2           0     2
pred n                         25          14          33           0
```

## Nota de implementación

Los miembros del envoltorio de incertidumbre llevan el bosque adelgazado a 200
árboles, igual que los de los otros cuatro expertos. El bagging ya aporta la
dispersión entre modelos; mantener 1000 árboles por cabeza dentro de una cascada
de tres nodos multiplica el coste por quince sin añadir desacuerdo, y deja la
escalera fuera de muestra —72 reentrenamientos del ensemble completo— fuera de
cualquier tiempo razonable.

## Cómo entrenarlo

```bash
python train_expert_five.py
python train_expert_five.py --model random_forest --members 15
```
