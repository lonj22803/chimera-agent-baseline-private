# Tarea 1: expertos, cubo clinico, arquitectura y decision final

Este documento explica la solucion de la **tarea 1** de `delete_final_versions_task_V1_1`: decidir si un paciente necesita biopsia de prostata. La idea central es sencilla: el LLM no decide la biopsia. El LLM recupera documentos, contrasta guia, resume y redacta; la decision la toma una cascada escrita en codigo a partir de expertos entrenados y reglas medidas.

La implementacion viva esta en `task_1/agent/graph.py`, `task_1/agent/protocol.py`, `task_1/agent/decide.py` y `task_1/experts_1/`. La historia de entrenamiento viene de `../delete_expert_modelate/task_one/` y sus artefactos se consumen desde el panel de expertos de esta version.

## 1. De donde viene esta version

Antes de esta entrega hubo varias generaciones de la tarea 1. Las versiones anteriores mejoraban el baseline, pero seguian fallando en el mismo sitio: los casos con **biopsia previa positiva**. En los 91 casos etiquetados, el problema se parte naturalmente en tres cubos por `bx`:

| cubo | n | problema clinico | resultado final |
|---|---:|---|---:|
| `bx = None` | 24 | paciente sin biopsia previa | 1.000 |
| `bx = Negative` | 18 | biopsia previa negativa | 0.889 |
| `bx = Positive` | 49 | cancer ya conocido / vigilancia / tratamiento | 0.878 |
| total | 91 | todos los casos etiquetados | 0.912 |

Las generaciones anteriores ya iban razonablemente bien en los dos primeros cubos. El salto real sale del tercero: `bx = Positive` pasa de alrededor de 0.59 a 0.878. Ese cubo no se arregla con mas texto del LLM, sino separando tres preguntas:

1. Que dice el panel estructurado.
2. Que documentos abre el urologo lector y que hechos viven en esos documentos.
3. Cuando un paciente ya tiene diagnostico tisular, si toca re-biopsiar, confirmar vigilancia o pasar a tratamiento.

Por eso la arquitectura final es una junta: varios expertos hablan, pero el voto final esta reglado.

## 2. Como se entrenaron los expertos

Los expertos entrenados nacen en `delete_expert_modelate/task_one`. Alli se entrenaron sobre los **91 casos con ground truth** de CHIMERA para tarea 1 y se evaluaron con validacion cruzada, leave-one-out u out-of-fold segun el componente.

El entrenamiento no fue "un clasificador y ya". La carpeta de modelado hizo un bakeoff de modelos y bloques de informacion:

| experto | objetivo | datos que usa | modelo | medicion principal |
|---|---|---|---|---|
| Experto 1, estructurado | biopsia si/no | bloque A, `structured-prompt.json` | Extra-Trees con bagging e imputacion multiple | AUC CV 0.758 |
| Experto 2, PSA | trayectoria futura del PSA | serie longitudinal de PSA | Extra-Trees regressor + jackknife+ | cobertura conforme de la proyeccion |
| Experto 3, fusion | biopsia si/no | A + B + D: panel, documentos clinicos abiertos y RM/lab utiles | Extra-Trees con incertidumbre | AUC CV 0.794 |
| Experto 4, traza | que abre y que pesa el urologo | trazas reales del formulario | modelos logisticos por casilla + moda por cubo | solo conserva casillas que baten a la moda en LOOCV |

La razon para elegir Extra-Trees fue empirica: en el bakeoff ganaba o empataba a modelos razonables, tenia mejor comportamiento leave-one-out que alternativas cercanas y permitia calcular importancias por permutacion out-of-fold. Con solo 91 etiquetas, el README de modelado insiste en la limitacion: los intervalos de AUC son anchos y hay sesgo de seleccion. Por eso la version final distingue tres numeros:

| cifra | valor | que significa |
|---|---:|---|
| entrega | 0.8390 | corrida final sobre los 91 etiquetados, optimista porque los expertos vieron esas etiquetas |
| techo | 0.9469 | biblioteca con precedente identico, imposible en test |
| honesto | 0.7607 | simulacion out-of-fold/leave-one-out, cota mas realista de generalizacion |

En V1.1 no se cambiaron las decisiones ni los modelos respecto a V1: se arreglo el reloj. Los expertos se precalientan en paralelo, los bosques puntuan con `n_jobs=1` para evitar overhead en una sola fila, y algunos calculos caros se hacen perezosos.

## 3. Que hace cada experto en la junta

La junta esta en `task_1/agent/graph.py`. Tiene intervenciones numeradas y persistidas en JSON/Markdown. El orden importa porque algunos expertos solo pueden hablar despues de que el registrador abra documentos.

| intervencion | nombre | naturaleza | que lee | que aporta |
|---:|---|---|---|---|
| 3 | `EXPERT-STRUCTURED` | Experto 1 entrenado | panel estructurado | probabilidad de biopsia, incertidumbre y variables que movieron el modelo |
| 4 | `EXPERT-COHORT` | reglas medidas | panel estructurado | criterio por cubo clinico |
| 5 | `EXPERT-EXPERIENCE` | biblioteca kNN | 91 casos etiquetados | precedentes parecidos dentro del mismo cubo |
| 6 | `EXPERT-TRACE` | Experto 4 entrenado | panel + trazas etiquetadas | plan de documentos y pesos del formulario |
| 7 | `EXPERT-EAU` | LLM + RAG | guia EAU | contraste normativo con citas |
| 8 | `MODERATOR` | LLM | acta hasta el momento | preguntas concretas para documentos |
| 10 | `REGISTRAR` | LLM + herramientas | documentos del plan | hechos clinicos recuperados |
| 11 | `EXPERT-PSA` | Experto 2 entrenado | serie de PSA abierta | trayectoria y banda conforme |
| 12 | `EXPERT-FUSION` | Experto 3 entrenado | documentos abiertos + panel | mejor probabilidad entrenada si hay fuentes |
| 13 | `PANEL-PROTOCOL` | codigo | todos los anteriores | decision final por cascada |
| 14 | `VERIFIER` | LLM + RAG | acta y guia | comprueba si falta algo |
| 15 | `CHAIR` | LLM | parte clinico sin maquinaria | nota clinica y formulario final |

Hay una regla importante: los expertos que dependen de documentos solo hablan sobre documentos abiertos. Si no se abrio la serie de PSA, el Experto 2 se abstiene. Si falta laboratorio o RM, el Experto 3 lo refleja en su variante y en su incertidumbre. Esto evita que un experto "lea por debajo de la mesa".

## 4. El cubo clinico

El cubo es la particion por biopsia previa (`bx`). No es un adorno: cambia la pregunta clinica.

### `bx = None`: nunca biopsiado

Aqui la regla medida y clinicamente natural es:

```text
PI-RADS >= 3 -> biopsiar
PI-RADS <= 2 -> diferir
```

En la serie etiquetada acierta 24/24. Por eso el protocolo deja que el criterio de cohorte decida estos casos salvo que algo documentado contradiga claramente el panel.

### `bx = Negative`: biopsia previa negativa

Aqui la regla se endurece:

```text
PI-RADS >= 4 -> repetir biopsia
PI-RADS <= 3 -> no repetir por defecto
```

Acierta 16/18. Un PI-RADS 3 despues de una biopsia negativa no tiene el mismo peso que en un paciente nunca biopsiado.

### `bx = Positive`: biopsia previa positiva

Este es el cubo dificil. El paciente ya tiene diagnostico de cancer o una historia oncologica previa, asi que una RM sospechosa o un PSA alto no significan automaticamente "hacer otra biopsia". A veces significan tratamiento, estadificacion o vigilancia.

Leyendo los `free_text` del urologo en los 49 casos positivos se extrajeron reglas concretas:

| patron encontrado | regla | n | acierto |
|---|---|---:|---:|
| "start treatment and do a PSMA-PET" | PSA >= 20 -> no re-biopsiar | 6 | 5 |
| "stop checking PSA, no need for diagnostics" | edad >= 78 -> no mas diagnostico | 2 | 2 |
| "now normal MRI" | PI-RADS <= 2 -> no hay lesion que muestrear | 2 | 2 |
| grado previo documentado alto | GG >= 2 -> tratar, no re-biopsiar | 8 | 7 |
| vigilancia con GG 1 | GG 1 -> biopsia confirmatoria | 4 | 3 |

El grado previo no vive en el panel: vive en `previous_notes`. Por eso el Experto 4 fija si hay que abrir notas previas y el registrador las abre. Luego `decide.documented_grade()` extrae el grado con expresiones regulares del texto crudo de la herramienta, no del resumen del LLM. Esto evita errores como copiar "ISUP 2" cuando el documento realmente decia "Gleason 3+4".

## 5. La arquitectura completa

El flujo de la tarea 1 es:

```text
INTAKE
  -> EXPERT-STRUCTURED
  -> EXPERT-COHORT
  -> EXPERT-EXPERIENCE
  -> EXPERT-TRACE fija el plan
  -> EXPERT-EAU consulta guia
  -> MODERATOR formula preguntas
  -> REGISTRAR abre exactamente el plan
  -> EXPERT-PSA, si hay serie abierta
  -> EXPERT-FUSION, si hay documentos abiertos
  -> PANEL-PROTOCOL decide
  -> VERIFIER comprueba si falta algo
  -> CHAIR redacta nota clinica y salida Grand Challenge
```

La pizarra no es solo logging: es la memoria estructurada de la deliberacion. Cada intervencion tiene `speaker`, texto, datos y numero global. El protocolo puede mirar datos estructurados de los expertos, y el presidente final no ve la maquinaria completa: recibe un parte clinico ya traducido para que la nota final hable del paciente, no del sistema.

Hay guardias en codigo porque los fallos se midieron:

| guardia | fallo que evita |
|---|---|
| `process_language` | que la nota diga "el protocolo decidio" o "el experto X..." en vez de razonar como clinico |
| `unsourced_values` | numeros inventados o no respaldados |
| `unsourced_grades` | grados ISUP/Gleason sin documento |
| `documented_grade` | depender del resumen del LLM para un dato decisivo |
| `enforce_grounding` | marcar una variable como importante sin haber abierto su fuente |
| `validate_output` | entregar JSON que no cumple `Task1Output` |

## 6. Como se toma la decision final

La decision final vive en `task_1/agent/protocol.py`. No es mayoria simple, ni promedio de opiniones, ni voto del LLM. Es una cascada:

```text
1. precedente identico, solo si se permite self-match
2. criterio de cohorte por cubo
3. grado documentado en notas abiertas
4. voto ponderado de expertos entrenados
5. respaldo determinista si no hay experto disponible
```

En la entrega, el precedente identico va apagado para medir algo parecido al test. Si el caso etiquetado se deja buscarse a si mismo en la biblioteca, el resultado local es memorizacion.

El peldaño 4 se usa cuando no decide ni la cohorte ni el grado documentado. La formula es:

```text
p = sum(p_i * w_i) / sum(w_i)
biopsia si p >= 0.45
```

Los pesos vienen de la fiabilidad medida:

| tramo | peso |
|---|---:|
| `firm` | 3.0 |
| `supports` | 2.0 |
| `discuss` | 1.0 |

El Experto 3 tiene multiplicador 1.5 porque su AUC es mejor que el Experto 1. La biblioteca tiene peso 0 fuera del precedente identico: sigue hablando como evidencia, pero no vota, porque en el cubo `bx = Positive` su acierto leave-one-out es 0.47, practicamente azar.

El umbral 0.45 no es casual. En estos casos, especialmente con cancer ya conocido, diferir una biopsia exige una razon positiva. La rejilla medida mostro que 0.45 daba mejor ranking que 0.50 o 0.40 en la configuracion de entrega.

## 7. Que se entrega al formulario

El formulario de Grand Challenge no solo pide `biopsy_decision`: tambien pide `confidence`, `variable_weights`, `reveal_sequence` y `free_text`.

La solucion separa tres tipos de "importancia":

| tipo | que mide | se entrega? |
|---|---|---|
| atributiva | que variable mueve la prediccion del modelo | no directamente |
| normativa | que exige la guia o la regla clinica | alimenta la explicacion |
| conductual | que peso marco el urologo lector en su traza | si |

Se entrega la importancia conductual del Experto 4 porque el evaluador compara contra la traza del urologo, no contra lo que el modelo considera causal. Se probo subir variables por acuerdo del panel y bajo el score, asi que no se adopto.

La confianza final tampoco sale simplemente de `p`. Sale del acuerdo y del peldaño que decidio. Una probabilidad 0.52 no significa lo mismo si viene de una regla que acierta 24/24 que si viene de expertos en desacuerdo.

## 8. Resultado y lectura honesta

Resultado principal de la tarea 1 con juez de razonamiento apagado:

| metrica | valor |
|---|---:|
| `ranking_score` | 0.8390 |
| `mean_case_score` | 0.7470 |
| puerta de decision | 0.9121 |
| F1(`yes`) | 0.9310 |
| `variable_weight_score` | 0.8506 |
| `important_decisive_factor_score` | 0.7723 |
| `tool_score` | 0.8685 |

La lectura honesta es:

- La mejora fuerte viene del cubo `bx = Positive`.
- El LLM no era fiable como votante en ese cubo: registrador y verificador estaban alrededor del azar.
- El LLM si es util recuperando informacion, consultando guia y redactando.
- Los expertos entrenados aportan probabilidad, incertidumbre y trazas; el protocolo decide con reglas medibles.
- La cifra 0.8390 es optimista para test porque hay seleccion y entrenamiento sobre 91 etiquetas; la cifra honesta publicada alrededor de 0.7607 es la referencia de generalizacion.

## 9. Por que esta es la decision final

La decision final de arquitectura fue esta:

1. **No dejar votar al LLM.** Se midio que falla justo donde importa.
2. **Usar expertos entrenados como instrumentos, no como autoridad absoluta.** Aportan probabilidades, tramos de fiabilidad e importancia, pero el protocolo puede abstenerlos o ponderarlos.
3. **Dividir por cubo clinico.** La variable `bx` cambia la tarea: no es lo mismo diagnosticar de cero que repetir una biopsia o manejar cancer ya conocido.
4. **Leer documentos solo cuando el plan lo exige.** Mejora precision de herramientas y evita abrir secciones que penalizan.
5. **Extraer el grado documentado en codigo.** Es demasiado decisivo para confiarlo al resumen de un modelo.
6. **Hacer que la nota final sea clinica.** El presidente no debe explicar la junta; debe explicar al paciente.
7. **Publicar tambien la cifra honesta.** La entrega local gana mucho, pero el diseño reconoce el sesgo de seleccionar parametros sobre los mismos 91 casos.

En resumen: la tarea 1 quedo como una junta clinica instrumentada. Los modelos entrenados y el LLM producen evidencia; la decision sale de una cascada transparente, escrita y medida.
