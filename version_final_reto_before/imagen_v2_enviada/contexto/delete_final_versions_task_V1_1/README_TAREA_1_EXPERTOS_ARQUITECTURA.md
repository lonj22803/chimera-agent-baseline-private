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

### Que son A, B y D

Los nombres **A**, **B** y **D** vienen del constructor de matrices de `chimera_experts/dataset.py`. Cada letra es una fuente de variables. El Experto 1 usa solo **A**; el Experto 3 usa **A+B+D**, por eso se llama experto de fusion multi-fuente.

| bloque | origen | que contiene | por que importa |
|---|---|---|---|
| **A** | `structured-prompt.json` | panel estructurado que el reto entrega ya tabulado: edad, PSA, volumen, PSAD, PI-RADS, biopsia previa (`bx`), DRE, comorbilidades, `cspca`, etc. | Es el suelo robusto: esta disponible en todos los casos y permite inferencia aunque no se abra ningun documento. |
| **B** | `prostate-biopsy-decision-clinical-data.json` | analitica/laboratorio, especialmente variables derivadas del PSA libre y otros valores de laboratorio. | Aporta senales pequenas pero utiles; por ejemplo `%PSA libre < 15%` aparece entre las variables importantes del Experto 3. |
| **D** | `prostate-biopsy-decision-clinical-data.json` | informe radiologico de RM procesado con extraccion de conceptos y deteccion de negacion tipo NegEx: restriccion en difusion, severidad DWI/T2, lesion >= 15 mm, extension extracapsular, adenopatias, etc. | Es el bloque que mas se nota en la ablacion: quitar radiologia cuesta alrededor de -0.030 AUC. Lee matices que no estan en el panel estructurado. |

Hay otros bloques, pero no se adoptaron para el Experto 3 final:

| bloque | contenido | decision |
|---|---|---|
| **C** | serie longitudinal de PSA | no mejora al clasificador; se usa aparte en el Experto 2 como proyeccion del PSA |
| **E** | notas previas/familia | en la ablacion restaba ligeramente; se deja para el registrador y para reglas documentales, no como bloque del clasificador |
| **F** | embedding neuronal de RM de 1024 dimensiones | las sondas lineales quedaron por debajo del escalar `cspca`; no se usa |
| **G** | salida del Experto 2 como variables | no mejora sobre ABD; se descarta como entrada del clasificador |

La razon de **ABD** es, por tanto, practica: combina el panel completo (**A**), una senal analitica pequena (**B**) y la informacion radiologica textual que mas aporta (**D**), sin meter fuentes que anaden ruido con solo 91 etiquetas. En la ablacion, **ABD** obtuvo AUC 0.794, mejor que ABCD, ABCDE, AD, ABDE o A solo.

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

## 7. Ejemplo detallado de una inferencia

Este ejemplo es representativo de la ruta dificil, no una promesa clinica. Sirve para ver como se mueve la arquitectura cuando llega un caso que no se resuelve solo con el panel.

### Entrada del caso

Supongamos un paciente con este `structured-prompt.json` simplificado:

```json
{
  "age": 72,
  "bx": "Positive",
  "psa": 9.8,
  "psad": 0.16,
  "vol": 61,
  "pirads": 4,
  "dre": "normal",
  "cspca": 0.42,
  "comorbidity": "controlled hypertension"
}
```

Y con estos documentos disponibles pero todavia cerrados:

```text
radiology_report
psa_trend
previous_notes
laboratory_results
family_history
```

Lo importante de entrada es `bx = Positive`: el paciente ya tiene una biopsia previa positiva. Eso lo mete en el cubo dificil. En un paciente nunca biopsiado, PI-RADS 4 casi bastaria para biopsiar. Aqui no: puede ser vigilancia activa, confirmatoria, progresion ya conocida o indicacion de tratamiento sin repetir biopsia.

### Paso 1: `INTAKE`

La junta primero escribe dos intervenciones de intake:

1. El JSON crudo, campo por campo.
2. El mismo caso renderizado como formulario clinico.

No decide nada. Solo fija el expediente visible. Tambien deja claro que en tarea 1 no hay `pathology_report` separado: si hay grado previo, vive en `previous_notes`.

### Paso 2: `EXPERT-STRUCTURED`, el Experto 1

El Experto 1 lee solo el bloque **A**, es decir, el panel estructurado. No ha visto RM en texto libre, notas previas ni analitica.

Para este ejemplo podria devolver:

```json
{
  "decision": "yes",
  "p": 0.54,
  "tier": "discuss",
  "confidence": "uncertain",
  "sigma": 0.18,
  "variable_weights": {
    "bx": "decisive",
    "pirads": "important",
    "psa": "noted",
    "psad": "noted",
    "age": "noted",
    "dre": "noted"
  }
}
```

Lectura humana: el panel se inclina levemente a biopsia porque hay PI-RADS 4 y PSAD algo elevada, pero el propio experto sabe que en `bx = Positive` su senal es debil. Por eso el tramo es `discuss`: habla, pero no puede cerrar el caso.

### Paso 3: `EXPERT-COHORT`, el criterio por cubo

El experto de cohorte mira primero el cubo:

```text
bx = Positive
```

Luego prueba sus reglas fuertes para biopsia previa positiva:

```text
PSA >= 20       ? no, PSA = 9.8
edad >= 78      ? no, edad = 72
PI-RADS <= 2    ? no, PI-RADS = 4
```

Como ninguna dispara, se abstiene:

```json
{
  "bucket": "prior positive biopsy",
  "verdict": null,
  "fired": null,
  "confidence": "uncertain",
  "rule": "the visible panel does not determine this decision"
}
```

Esto es crucial. El sistema no interpreta "no hay regla" como "no biopsiar". Lo interpreta como "el panel no alcanza; hay que leer las notas previas para saber grado, vigilancia y contexto".

### Paso 4: `EXPERT-EXPERIENCE`, biblioteca de precedentes

La biblioteca busca los `k=3` casos mas parecidos dentro del mismo cubo `Positive`, usando variables estructuradas estandarizadas: PI-RADS, log(PSA), log(PSAD), volumen, edad, DRE y `cspca`.

Podria recuperar:

| vecino | distancia | decision real | confianza | resumen |
|---|---:|---|---|---|
| caso A | 0.42 | yes | borderline | vigilancia con sospecha persistente |
| caso B | 0.58 | no | clear | grado alto previo, paso a tratamiento |
| caso C | 0.77 | yes | uncertain | lesion persistente sin grado inicial claro |

La moda ponderada podria quedar cerca de empate:

```json
{
  "answer": "yes",
  "p_yes": 0.56,
  "confidence": "uncertain",
  "self_match": false
}
```

Pero en `bx = Positive` esta biblioteca acierta 0.47 leave-one-out. Por eso en la decision final **no vota**. Aun asi su turno sirve: muestra precedentes, que documentos abrio el urologo en situaciones parecidas y que variables solian aparecer en la traza.

### Paso 5: `EXPERT-TRACE`, el Experto 4 fija el plan

El Experto 4 no decide biopsia. Predice que abriria y que pesaria el urologo lector.

Para este caso podria decir:

```json
{
  "source": "trace model + bucket mode",
  "reveal_sequence": [
    "radiology_report",
    "previous_notes",
    "laboratory_results"
  ],
  "confidence": "borderline",
  "variable_weights": {
    "bx": "decisive",
    "pirads": "important",
    "psa": "important",
    "psad": "noted",
    "dre": "noted",
    "age": "noted",
    "fh": "not_used"
  }
}
```

Esta salida tiene dos efectos:

1. Fija el `reveal_sequence` candidato del formulario.
2. Fija el plan operativo del registrador: abrir exactamente radiologia, notas previas y laboratorio.

No se abre `family_history` porque en esta tarea penaliza mas de lo que aporta y el urologo casi nunca la abria. Tampoco se abre `psa_trend` si el modelo de traza no lo pidio.

### Paso 6: `EXPERT-EAU` y `MODERATOR`

El experto EAU consulta guia y recuerda el criterio general:

```text
En cancer ya diagnosticado, una nueva biopsia solo tiene sentido si cambia manejo:
confirmatoria en vigilancia, sospecha de reclasificacion o informacion histologica
insuficiente. Si ya hay grado alto documentado, el siguiente paso suele ser tratamiento
o estadificacion, no repetir tejido.
```

El moderador convierte la incertidumbre en preguntas concretas:

```text
radiology_report: confirmar PI-RADS, tamano de lesion, restriccion DWI y extension extracapsular.
previous_notes: buscar grado ISUP/Gleason de la biopsia previa, fechas y si esta en vigilancia activa.
laboratory_results: confirmar PSA, PSA libre o datos que apoyen riesgo actual.
```

### Paso 7: `REGISTRAR` abre los documentos del plan

El registrador llama herramientas reales y solo para las secciones previstas. Supongamos que recupera:

```text
radiology_report:
  Lesion periferica izquierda PI-RADS 4, 12 mm, restriccion en difusion moderada,
  sin extension extracapsular ni adenopatias.

previous_notes:
  Biopsia previa hace 14 meses: Gleason 3+3, Grade Group 1.
  Paciente en vigilancia activa. Se recomienda biopsia confirmatoria si persiste lesion en RM.

laboratory_results:
  PSA 9.8 ng/mL, porcentaje PSA libre 12%, creatinina normal.
```

El registrador puede resumir, pero la decision no confia ciegamente en su resumen para el grado. `decide.documented_grade()` escanea el texto crudo y extrae:

```json
{
  "gg": 1,
  "quote": "Gleason 3+3",
  "on_surveillance": true,
  "biopsy_mentions": 1
}
```

La traduccion es mecanica: Gleason 3+3 equivale a Grade Group 1. Ademas detecta vigilancia activa.

### Paso 8: `EXPERT-PSA`

En este ejemplo no se abrio `psa_trend`, asi que el Experto 2 se abstiene:

```json
{
  "available": false,
  "reason": "psa_trend not opened"
}
```

Esto es deliberado. No proyecta el PSA a partir del valor suelto del panel, porque su contrato es leer la serie abierta. Si no esta sobre la mesa, no inventa trayectoria.

### Paso 9: `EXPERT-FUSION`, el Experto 3 con A+B+D

El Experto 3 ahora si puede leer sus bloques:

- **A**: panel estructurado.
- **B**: laboratorio abierto.
- **D**: radiologia abierta procesada con NegEx.

Sus variables internas incluirian cosas como:

```text
A:
  bx_positive = 1
  pirads = 4
  log_psa = log(9.8)
  psad = 0.16
  dre_suspicious = 0

B:
  fpsa_lt15 = 1

D:
  rad_dwi_restriction = 1
  rad_dwi_severity = 2
  rad_lesion_ge15mm = 0
  rad_epe = 0
  rad_nodes = 0
```

Podria devolver:

```json
{
  "decision": "yes",
  "p": 0.62,
  "tier": "supports",
  "confidence": "borderline",
  "available": true,
  "variant": "fusion_full",
  "variable_weights": {
    "bx": "decisive",
    "pirads": "important",
    "psa": "important",
    "psad": "noted",
    "dre": "noted"
  }
}
```

Lectura humana: la RM y el PSA libre bajo empujan hacia biopsia/confirmacion, pero no es un caso `firm` porque `bx = Positive` sigue cambiando la pregunta.

### Paso 10: `PANEL-PROTOCOL` aplica la cascada

La cascada revisa los peldaños:

```text
1. precedente identico?
   no, self-match apagado / test no puede tenerlo

2. criterio de cohorte?
   no, en bx Positive no disparan PSA >= 20, edad >= 78 ni PI-RADS <= 2

3. grado documentado?
   si: GG 1 ("Gleason 3+3") y vigilancia activa
```

Como hay grado documentado GG 1 en vigilancia, dispara la regla documental:

```text
GG 1 en vigilancia activa -> biopsia confirmatoria
```

La decision queda:

```json
{
  "decision": "yes",
  "who": "documented grade",
  "rule": "documented prior grade GG 1 (Gleason 3+3)",
  "confidence": "clear",
  "track": "A documented GG 1 in a man under surveillance is what a confirmatory biopsy is for..."
}
```

Observa algo importante: aunque el Experto 1 y el Experto 3 tambien sugerian `yes`, aqui **no hace falta llegar al voto ponderado**. El caso lo decide un hecho documental con regla escrita.

Si no hubiese grado documentado, entonces si entraria el voto ponderado:

```text
Experto 1: p = 0.54, tier discuss  -> peso 1.0
Experto 3: p = 0.62, tier supports -> peso 2.0 * 1.5 = 3.0
Biblioteca: p = 0.56              -> peso 0.0

p_final = (0.54*1.0 + 0.62*3.0 + 0.56*0.0) / (1.0 + 3.0 + 0.0)
        = (0.54 + 1.86) / 4.0
        = 0.60

0.60 >= 0.45 -> biopsia yes
```

En esta ruta alternativa tambien habria salido `yes`, pero por otro motivo: masa ponderada de expertos, no regla documental.

### Paso 11: pesos de variables y grounding

El formulario final necesita `variable_weights`. No se copian sin mas las importancias del Experto 3. Se parte del Experto 4 porque predice la traza del urologo:

```json
{
  "bx": "decisive",
  "pirads": "important",
  "psa": "important",
  "psad": "noted",
  "dre": "noted",
  "age": "noted",
  "fh": "not_used"
}
```

Luego `enforce_grounding` comprueba que las variables importantes esten aterrizadas:

| variable | nivel | fuente necesaria | se abrio? | queda |
|---|---|---|---|---|
| `bx` | decisive | panel / no aterrizable por diseno | si | decisive |
| `pirads` | important | `radiology_report` | si | important |
| `psa` | important | panel/lab | si | important |
| `psad` | noted | radiologia/panel | si | noted |
| `fh` | not_used | `family_history` | no | not_used |

Si el formulario intentara marcar `fh = important` sin abrir `family_history`, la guardia lo bajaria.

### Paso 12: `VERIFIER`

El verificador comprueba si falta algun documento del plan. Aqui se abrieron los tres:

```text
radiology_report: abierto
previous_notes: abierto
laboratory_results: abierto
```

Tambien contrasta que la regla tenga sentido con la guia: en vigilancia activa con GG 1 y lesion persistente, la confirmatoria es defendible. Por tanto cierra:

```text
VERDICT: ready
```

### Paso 13: `CHAIR` redacta la nota clinica

El presidente no recibe "el Experto 3 dijo..." ni "el protocolo disparo...". Recibe un parte clinico limpio. Una nota final aceptable podria ser:

```text
72-year-old man on active surveillance after prior Gleason 3+3 prostate cancer.
Current MRI shows a persistent PI-RADS 4 lesion without extracapsular extension
or nodal disease. PSA is 9.8 ng/mL with PSA density 0.16 and low free PSA.
Because the prior documented grade is Grade Group 1 and the lesion persists on
surveillance imaging, confirmatory biopsy is appropriate. Biopsy.
```

Luego las guardias revisan:

| comprobacion | resultado |
|---|---|
| no menciona "experts", "protocol", "panel decision" | pasa |
| no inventa numeros | pasa: edad, PSA, PSAD y PI-RADS vienen del panel/documentos |
| no inventa grado | pasa: `Gleason 3+3` esta en `previous_notes` |
| JSON valida contra `Task1Output` | pasa |

### Salida Grand Challenge

La salida final tendria dos ficheros. El de decision:

```json
"yes"
```

Y el de razonamiento, esquematicamente:

```json
{
  "confidence": "clear",
  "variable_weights": {
    "bx": "decisive",
    "fh": "not_used",
    "age": "noted",
    "dre": "noted",
    "psa": "important",
    "vol": "noted",
    "psad": "noted",
    "cspca": "not_used",
    "pirads": "important",
    "comorbidity": "not_used"
  },
  "reveal_sequence": [
    "radiology_report",
    "previous_notes",
    "laboratory_results"
  ],
  "free_text": "72-year-old man on active surveillance after prior Gleason 3+3 prostate cancer..."
}
```

La idea completa se ve ahi: el LLM ayudo a recuperar y redactar, pero la decision no dependio de una intuicion generativa. Dependio de cubo clinico, grado documentado, plan de documentos y reglas medidas.

## 8. Que se entrega al formulario

El formulario de Grand Challenge no solo pide `biopsy_decision`: tambien pide `confidence`, `variable_weights`, `reveal_sequence` y `free_text`.

La solucion separa tres tipos de "importancia":

| tipo | que mide | se entrega? |
|---|---|---|
| atributiva | que variable mueve la prediccion del modelo | no directamente |
| normativa | que exige la guia o la regla clinica | alimenta la explicacion |
| conductual | que peso marco el urologo lector en su traza | si |

Se entrega la importancia conductual del Experto 4 porque el evaluador compara contra la traza del urologo, no contra lo que el modelo considera causal. Se probo subir variables por acuerdo del panel y bajo el score, asi que no se adopto.

La confianza final tampoco sale simplemente de `p`. Sale del acuerdo y del peldaño que decidio. Una probabilidad 0.52 no significa lo mismo si viene de una regla que acierta 24/24 que si viene de expertos en desacuerdo.

## 9. Resultado y lectura honesta

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

## 10. Por que esta es la decision final

La decision final de arquitectura fue esta:

1. **No dejar votar al LLM.** Se midio que falla justo donde importa.
2. **Usar expertos entrenados como instrumentos, no como autoridad absoluta.** Aportan probabilidades, tramos de fiabilidad e importancia, pero el protocolo puede abstenerlos o ponderarlos.
3. **Dividir por cubo clinico.** La variable `bx` cambia la tarea: no es lo mismo diagnosticar de cero que repetir una biopsia o manejar cancer ya conocido.
4. **Leer documentos solo cuando el plan lo exige.** Mejora precision de herramientas y evita abrir secciones que penalizan.
5. **Extraer el grado documentado en codigo.** Es demasiado decisivo para confiarlo al resumen de un modelo.
6. **Hacer que la nota final sea clinica.** El presidente no debe explicar la junta; debe explicar al paciente.
7. **Publicar tambien la cifra honesta.** La entrega local gana mucho, pero el diseño reconoce el sesgo de seleccionar parametros sobre los mismos 91 casos.

En resumen: la tarea 1 quedo como una junta clinica instrumentada. Los modelos entrenados y el LLM producen evidencia; la decision sale de una cascada transparente, escrita y medida.
