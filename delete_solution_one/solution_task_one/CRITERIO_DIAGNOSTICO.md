# El criterio de decisión de la tarea 1 — qué decide de verdad, y qué no

> Documento de trabajo. Todo lo cuantitativo está medido sobre los **91 casos
> etiquetados** de `data/task1/ground_truth/`, con los splits de `dev/splits/`
> para separar lo que se ajustó de lo que se comprobó. Cuando algo es una
> suposición, se dice.

## 0. El resumen

La tarea 1 no es **un** problema de clasificación: son **tres**, y sólo dos de
ellos están determinados por el panel visible.

| cubo clínico | n | qué pregunta de verdad | criterio | acierto |
|---|---|---|---|---|
| `bx = None` (sin biopsiar) | 24 | ¿hay lesión que muestrear? | biopsiar si PI-RADS ≥ 3 | **24 / 24** |
| `bx = Negative` (biopsia previa negativa) | 18 | ¿se falló algo la vez anterior? | re-biopsiar si PI-RADS ≥ 4 | **16 / 18** |
| `bx = Positive` (cáncer ya diagnosticado) | 49 | ¿cambiaría el manejo? | **el panel no lo determina** | — |

Tratar los tres como si fueran el mismo problema es exactamente lo que hace
fallar al baseline (recall 0.14 en la clase `no`) y lo que hacía fallar a la
corrida 1 de la pizarra (recall 0.14 en `no`, idéntico).

---

## 1. Cómo se llegó a los tres cubos

Cruzando el estado de biopsia previa con la decisión del urólogo:

```
bx = None       (24)   yes 20 · no 4      PI-RADS 4-5 -> 20/20 yes · PI-RADS 2 -> 3/3 no · PI-RADS NA -> 1 no
bx = Negative   (18)   yes 13 · no 5      PI-RADS 4-5 -> 13/15 yes · PI-RADS 3   -> 3/3 no
bx = Positive   (49)   yes 23 · no 26     PI-RADS 5   -> 10 yes/14 no · PI-RADS 4 -> 11 yes/8 no
```

Los dos primeros cubos se leen solos. El tercero es plano.

### 1.1 Por qué los dos primeros criterios no son un ajuste a los datos

Son la práctica estándar que la propia guía EAU sostiene: mpMRI antes de la
biopsia, biopsia dirigida sobre lesión PI-RADS ≥ 3 en el paciente sin biopsiar,
y re-biopsia dirigida sobre PI-RADS ≥ 4 tras una biopsia negativa. No se
eligieron mirando la tabla: se eligieron porque son el criterio, y **luego** se
comprobó que reproducen al urólogo en 40 de 42 casos. Se sostienen igual en los
dos splits, que es la prueba de que no son memoria (ver §3).

---

## 2. El cubo `Positive` es irreducible con el panel visible

Tres medidas independientes dicen lo mismo.

**(a) Ninguna variable estructurada separa las dos respuestas.** AUC dentro de
los 49 casos, para distinguir `yes` de `no`:

| variable | AUC | | variable | AUC |
|---|---|---|---|---|
| `psa` | 0.472 | | `vol` | 0.457 |
| `age` | 0.548 | | `cspca` | 0.450 |
| `pirads` | 0.475 | | `psav` | 0.524 |
| `psad` | 0.429 | | `months` | 0.545 |

Todas entre 0.43 y 0.55: azar. Y el PSA **sube en los 49 casos** (el último
valor de la serie es mayor que el anterior en 49/49; `psav > 0` en 46/49), así
que "el PSA está subiendo" no distingue nada dentro de este cubo.

**(b) Los propios urólogos discrepan, y lo dicen.** Sus textos de referencia,
literales:

> *"He has a ISUP3 cancer diagnosis already and he should be recommended treatment"* → **no**
> *"Start treating the patient. It does not make sense to not treat this man initially"* (PSA 160) → **no**
> *"All depends if the lesion has grown in size since 2024. If stable no biopsy, if increased in size I will do a biopsy"* → **no**
> *"There is no information on ISUP in the earlier cancer diagnosis and missing also size of earlier PIRADS 4 lesion"* → **yes**
> *"Again, has the lesion grown in size or not in a man on active surveillance"* → **yes**
> *"I need information on initial ISUP and size of P4 lesion in initial scan"* → **yes**

Su confianza declarada lo confirma: en este cubo pusieron `uncertain` 11 veces
y `borderline` 13, frente a 2 `borderline` y ningún `uncertain` en el cubo de
los no biopsiados.

**(c) Toda regla ajustada en una mitad falla en la otra.** La mejor regla que
se encontró para este cubo (PSA ≥ 100 → no; grado ISUP/Gleason documentado en
los textos → no; en otro caso → sí) da **0.647 en `dev` y 0.467 en `val`** —
peor que la moneda al aire en el split que no se usó para construirla. Es
sobreajuste, y se descartó.

### 2.1 Lo que sí se puede sacar del cubo `Positive`

Lo que los urólogos dicen no está en el panel: está en los **documentos**. Sus
razonamientos se reducen a cuatro preguntas, y las cuatro se contestan leyendo
lo que las herramientas MCP devuelven:

1. **¿Consta el grado de la biopsia previa** (ISUP o Gleason) en algún sitio?
   Un cáncer ya graduado es un problema de *tratamiento*; un cáncer sin grado
   documentado es un problema de *caracterización*, y ahí la biopsia es lo que
   permite elegir tratamiento.
2. **¿Compara el informe de MRI con un estudio anterior, y la lesión es nueva,
   estable o mayor?** Una lesión estable en un cáncer conocido no es
   información nueva.
3. **¿Está el paciente en vigilancia activa y le toca biopsia de protocolo?**
4. **¿Hay ya un tratamiento, una prueba de estadificación o un procedimiento
   acordado o rechazado?**

Esas cuatro preguntas son ahora el checklist explícito del investigador (L2) y
el marco de decisión del presidente (L3) cuando `bx = Positive`.

---

## 3. Cuánto vale la mejora, medido

Cinco políticas sobre los mismos 91 casos. "protocolo" = los criterios de los
cubos `None` y `Negative`; en `Positive` el protocolo se abstiene y decide
quien se indique.

| política | acc `dev` | acc `val` | acc total | F1(`yes`) |
|---|---|---|---|---|
| agente solo (corrida 1) | 0.672 | 0.667 | 0.670 | 0.789 |
| prior kNN solo | 0.719 | 0.630 | 0.692 | 0.767 |
| **protocolo + agente** | 0.703 | **0.741** | **0.714** | **0.812** |
| protocolo + prior | 0.734 | 0.741 | 0.736 | 0.793 |
| protocolo + "siempre no" | 0.734 | 0.704 | 0.725 | 0.725 |

Dos lecturas:

* **`protocolo + agente` es la mejor combinación para lo que ranquea.** El
  `ranking_score` de la tarea 1 es `(mean_case_score + F1(yes)) / 2`, y esta
  política tiene a la vez la mejor exactitud y el mejor F1. `protocolo + prior`
  acierta más casos pero pierde F1 porque el prior dice `no` más a menudo, y en
  T1 el F1 se calcula sólo sobre la clase positiva.
* **La mejora generaliza.** Es la única política cuyo `val` (0.741) no cae por
  debajo de su `dev` (0.703). La del prior sí cae (0.719 → 0.630).

Estimación del efecto sobre el `ranking_score`, con el resto de componentes
congelados en lo medido en la corrida 1: puerta 0.670 → 0.714,
`mean_case_score` ≈ 0.545, F1 0.812 → **ranking ≈ 0.68**, frente a 0.650 de la
corrida 1 y 0.643 del baseline a la misma temperatura.

---

## 3bis. El criterio que más acierta NO es el que más puntúa

Esto es lo más contraintuitivo de la tarea 1, y es fácil optimizar el número
equivocado. El `ranking_score` es `(mean_case_score + F1(yes)) / 2`, y el F1 se
calcula **sólo sobre la clase positiva**: una predicción `no` correcta no suma
nada al F1, sólo evita restar. Con `mean_case_score ≈ 0.763 · exactitud`
(el 0.763 es el componente medio entre los casos que pasan la puerta, medido en
la corrida 1), las políticas se ordenan así:

| política en el cubo indeterminado | exactitud | F1(`yes`) | `ranking` estimado |
|---|---|---|---|
| protocolo + `no` por defecto | **0.725** | 0.725 | 0.6393 |
| protocolo + `yes` por defecto | 0.692 | 0.800 | 0.6641 |
| protocolo + el agente de la corrida 1 | 0.714 | 0.812 | **0.6783** |
| baseline (`yes` a todo) | 0.615 | 0.762 | 0.6157 |

**La política más exacta es la peor de las tres primeras.** Diferir por defecto
en el cubo indeterminado gana 3 puntos de exactitud y pierde 7 de F1. Es
exactamente el error que estuvo a punto de colarse: la primera versión del
marco clínico para `bx = Positive` estaba escrita en negativo (*"answer NO
when..."* cinco veces seguidas), el modelo se llevó el cubo entero hacia `no`
—de 24 `yes` a 11 en los primeros 25 casos— y la exactitud **no** mejoró,
porque el cubo es una moneda al aire. Lo único que habría cambiado es el F1, a
peor.

### Cómo se corrigió sin optimizar contra la métrica

No se le dice al modelo nada sobre F1. Se le da el principio clínico correcto,
que resulta ser el que apunta en la misma dirección: **diferir exige una razón
positiva; proceder no.** Un hombre con cáncer conocido y un PSA en movimiento
que se queda sin muestrear es una decisión tomada sobre información que no se
tiene, y eso hay que justificarlo con algo que el registro diga. El silencio del
registro —sin ISUP previo, sin comparación con una MRI anterior, sin nota de lo
que mostró la biopsia— **no es** prueba de que diferir sea seguro; es la razón
por la que la biopsia sería informativa. Que es, literalmente, lo que escriben
los urólogos en los casos `yes` de este cubo (§2b).

### Una regla que se probó y se descartó

"Grado ISUP/Gleason documentado en los textos → no; en otro caso → sí" da
exactitud 0.747 y F1 0.819 (`ranking` estimado 0.6945), el mejor número de
todos... en `dev` 0.766 y en `val` **0.704**, por debajo de la regla simple
(`val` 0.741). Son 13 casos con grado documentado: no hay con qué sostenerla.
Se descartó por la misma razón que la de §2(c), y no está implementada.

---

## 4. Cómo está implementado, y qué se decidió NO hacer

**Implementado** como un participante más de la pizarra:
[`experts/protocol.py`](experts/protocol.py) escribe, antes de que hable ningún
LLM, la situación clínica del paciente, el criterio que le corresponde, el
veredicto que implica y **su acierto medido**. El presidente recibe además ese
criterio en su propio mensaje con una regla de standing explícita: *"submit
that answer unless a document the conference actually retrieved contradicts it,
and if you depart from it, name that document and that finding"*. En el cubo
`Positive` el experto escribe explícitamente que **no** da respuesta, para que
nadie lea su silencio como un "no".

**No se hizo un router determinista que sobrescriba al agente.** Habría dado
los mismos puntos en los cubos `None` y `Negative`, pero convierte la
conferencia en un sello de goma en 42 de los 91 casos y deja sin justificar la
decisión —que es la mitad de la nota del reto—. La versión implementada deja al
presidente la última palabra y le exige nombrar la evidencia con la que se
aparta; si no la nombra, se queda con el criterio.

**No se ajustó el cubo `Positive`.** La regla que funcionaba en `dev` se
descartó por lo que dice §2(c). Lo que se le da al agente ahí no es una
respuesta, son las cuatro preguntas de §2.1.

**No se tocó el peso de `bx`.** Marcarlo por encima de `not_used` cuesta
`section_grounding_score` siempre en T1 (su sección es `pathology_report`, que
no está en el vocabulario de `Task1Output.reveal_sequence`), pero lo que gana
en `variable_weight_score` y en `important_decisive_factor_score` lo compensa
de sobra, y con el juez del reto activo el grounding sólo pesa 0.05.

---

## 5. Cómo volver a medir esto

```bash
# los tres cubos, las AUC del cubo Positive y la tabla de políticas
python delete_solution_one/solution_task_one/analysis/criterio.py

# el comportamiento de una corrida (incluye acierto por cubo)
python delete_solution_one/solution_task_one/analysis/diagnose.py runs/run2

# la nota oficial
python dev/score_local.py --tasks 1 --count-missing \
    --output-root delete_solution_one/solution_task_one/runs/run2/output
```

Si aparecen más casos etiquetados, lo primero que hay que rehacer es la tabla
de §3 con los splits nuevos: los criterios de los cubos `None` y `Negative` son
clínicos y deberían aguantar, pero el número de aciertos que se le declara al
presidente (24/24 y 16/18) sale de estos 91 casos y hay que actualizarlo.
