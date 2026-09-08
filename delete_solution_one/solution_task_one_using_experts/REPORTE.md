# Reporte de entrega — junta con expertos, tarea 1

Fecha: 7 de septiembre de 2026. Corrida: `runs/all` (195 casos en modo
`deployed`: los 91 etiquetados más los **104 sin etiqueta**, que son la prueba
honesta gratis — ahí no puede haber precedente idéntico, así que el sistema
corre exactamente como correría en el test del reto).

Lo que este reporte responde, en orden: qué pasó sobre los 104 casos nuevos
(§1), qué hay que cambiar para que esto corra en Grand Challenge (§2), qué
conviene que ajustes tú a mano y por qué no lo decidí yo (§3), cómo abordar las
tareas 2 y 3 con la misma arquitectura (§4), y qué es mejor entregar (§5).

## 1. Lo que pasó sobre los 104 casos sin etiqueta

Cifras completas en `runs/all/informe_sin_etiqueta.md`; los 91 etiquetados de
la misma corrida vuelven a dar 0,9765, así que mezclar los 195 no cambió nada.

| comprobación | resultado | lectura |
|---|---|---|
| casos entregados | **104/104**, 0 fallos, 0 reaperturas | la red de seguridad funciona; ningún caso se pierde |
| precedente idéntico | **0** | correcto: fuera de muestra el peldaño 1 no existe |
| tiempo por caso | 30 s de media, 43 s máximo (modelo ya cargado) | ver §2 para el coste por contenedor |
| respaldo determinista del presidente | **2/104** (el JSON no validó tras 3 intentos) | la decisión y la traza no dependen del presidente; sólo la prosa de esos 2 casos es la del respaldo, que es correcta pero seca |
| lo abierto ≠ el plan | **0/104** | el arreglo del plan vacío y el plan fijo funcionan |
| documentos abiertos | imagen 100 %, PSA 100 %, notas 100 %, laboratorio **44 %**, antecedentes 0 % | idéntico al urólogo en la serie (97 / 87 / 85 / 45 / 0 %): el Experto 4 generaliza |
| decisión «sí» | **72 %** (urólogo en la serie: 62 %) | ver hallazgo 1 |
| «sí» en el cubo positivo | **48/67 = 72 %** (urólogo: 47 %) | ver hallazgo 1 |
| grado documentado leído | 18/67 casos positivos (7 GG1, 7 GG2, 4 GG3) | 49 casos positivos van al voto ponderado, donde el acierto esperado es 0,63 |
| confianza entregada | **`clear` en 104/104** | ver hallazgo 2 |
| el presidente disintió | 32/104 (31 %); se entregó el protocolo en todos | en `honest` el protocolo tenía razón en 14 de 22 disidencias; no hay motivo para dejarle votar |
| valores sin fuente en el registrador | 16 retos, 5 sin resolver | son umbrales de la guía (0,15 ng/mL²), no valores del paciente; ver §3.5 |

**Hallazgo 1 — el cubo positivo se inclina a «sí» más que el urólogo.** El
72 % frente al 47 % de la serie tiene dos causas que se suman: (a) el umbral
de carga de la prueba (p ≥ 0,40) del voto ponderado, elegido porque sube la
F1(yes), y (b) que el conjunto sin etiqueta tiene más cubo positivo (67 de 104)
y menos grado documentado (27 % frente al 24 % de la serie, similar). Si el
test se parece a la serie etiquetada, la F1(yes) lo agradece y la exactitud lo
paga; es el ajuste 3.1 y es tuyo.

**Hallazgo 2 — la confianza es constante fuera de muestra.** La política
`trace` entrega la moda por cubo, que es `clear` en los tres cubos. Sobre la
serie eso puntúa 0,736 de `confidence_score`, mejor que la política por
acuerdo (0,789 frente a 0,803 en el conjunto honesto), pero es una salida sin
información. Lo honesto es decirlo: hoy el sistema no sabe cuándo el urólogo
dudaría, y lo que más se le parece es «casi siempre está seguro».

**Hallazgo 3 — el presidente falla el JSON 3 veces de 104.** Dos acaban en
respaldo. La causa visible en las actas es un preámbulo largo antes del objeto
con el tope de 1200 tokens del papel. Cambio barato: subir `chair` a 1600 en
`sampling.VOICES` o añadir al reintento «start your answer with `{`».

**Hallazgo 4 — la prosa nombra la maquinaria.** Igual que en `deployed`: «the
panel protocol was triggered by…», «the cohort criterion». Cuando no la nombra
(caso `8f4e08`) la prosa es exactamente la de un urólogo. Es §3.5.

### Cambios que se derivan, en orden de coste

1. **Subir el tope de tokens del presidente** (hallazgo 3): 1 línea.
2. **Quitar los nombres de regla de `chair_standing()`** y dejar decisión +
   evidencia (hallazgo 4): 10 líneas de prompt; medir con 30 casos en
   `honest` antes de fijarlo.
3. **Decidir el umbral** (hallazgo 1, §3.1): 1 flag.
4. **Decidir si una confianza constante es aceptable** (hallazgo 2): si no,
   `--confidence-policy agreement` cuesta 0,001 en la serie y devuelve una
   señal por caso (acuerdo de los expertos y tramo).
5. **Integración en el contenedor** (§2): es lo único que impide subir.


---

## 2. Cambios obligatorios para que corra en Grand Challenge

En el reto **cada caso es un contenedor**: `inference.py` recibe en `/input`
los tres ficheros de un solo paciente, arranca el modelo, corre el agente y
escribe dos ficheros en `/output`. Esta solución se desarrolló con un runner
por lotes sobre `data/`, y hay cinco cosas que no sobreviven a ese cambio de
forma. Las dos primeras ya están hechas; las otras tres son tuyas.

| # | qué falla | estado | qué hacer |
|---|---|---|---|
| 1 | **Un caso nuevo no está en `panel_cache.json`** y los cuatro expertos se abstenían en silencio (medido: "No trained classifier scored this case" en las cuatro intervenciones, y la traza caía a la moda por cubo) | **hecho**: `Panel.ensure()` puntúa el caso en vivo con los artefactos cuando no está en el caché; verificado que reproduce el caché (p 0,7437 y 0,7766 idénticas). Cuesta 30–80 s por caso | nada; en el contenedor el caché puede ir vacío |
| 2 | **Con plan vacío el registrador abría documentos igualmente** (2 casos de 91) | **hecho**: sin plan no se le enlazan herramientas de documento | nada |
| 3 | **`inference.py` llama al ReAct del baseline** (`run_baseline_for_gc_interface`) | pendiente | añadir `run_junta_for_gc_interface(task=1, …)`: escribir los tres ficheros en un `tempdir/agent_input/<case_id>/`, arrancar el MCP sobre ese dir, construir el grafo con `create_conference_graph(tools, model, feature_store, Panel(cache), Library(labelled_root), mode="deployed")`, invocar, y escribir `prostate-biopsy-decision.json` y `…-reasoning.json` con `decide.to_gc_outputs`. Es el mismo bucle que `run_task1._run_queries` para un solo caso |
| 4 | **La imagen no lleva lo que la junta necesita**: `Dockerfile_Baseline` copia sólo `src/`, `templates/`, `resources/`, `configs/`; `.dockerignore` excluye `data/` | pendiente | empaquetar (a) `delete_solution_one/solution_task_one_using_experts/` y `delete_expert_modelate/chimera_experts/` en `/opt/app/`; (b) los cuatro `.joblib` (80 MB) en el **tarball del modelo** (`/opt/ml/model/experts/`) y apuntar `experts/panel.ARTIFACT` ahí; (c) **los 91 casos etiquetados** (`agent_input` + `ground_truth`, ~3 MB) en el mismo tarball, porque la biblioteca de precedentes y la moda por cubo los leen en tiempo de ejecución. Son datos de entrenamiento que el organizador entrega; empaquetarlos es lo mismo que empaquetar un modelo entrenado con ellos |
| 5 | **Versiones**: los artefactos se deserializan con scikit-learn 1.9.0 / numpy 2.3.5 (el venv). `requirements.txt` del contenedor no fija scikit-learn | pendiente | fijar `scikit-learn==1.9.0`, `scipy`, `joblib` en `requirements.txt`; comprobar con `do_test_run.sh` que `joblib.load` no avisa de versión |

Dos avisos más del mismo bloque:

* **Tiempo por caso.** Localmente: carga del modelo ~90 s + servicio de
  embeddings ~30 s + expertos en vivo 30–80 s + junta 33 s ≈ **3–4 min por
  contenedor**. Comprueba el límite de tiempo por job del reto antes de subir.
  Si aprieta, la palanca es `--max-passes 1` (ya no reabre nunca) y bajar
  `n_imputations` del `UncertaintyExpert` de 10 a 3 en inferencia (la varianza
  entre imputaciones sólo importa con valores ausentes).
* **`CHIMERA_EMBED_SOCKET`**: en el contenedor sólo corre un proceso, así que
  el socket por defecto vale. Sólo importa en local con dos corridas a la vez.

---

## 3. Lo que conviene que ajustes tú, y por qué no lo cerré yo

Son decisiones de criterio, no de código. Cada una tiene el número que la
sostiene y el sitio donde se toca.

### 3.1 Qué versión de la decisión entregar

| opción | dónde | ranking honesto (91) | qué significa |
|---|---|---|---|
| **A. la cascada tal cual** (cohorte → grado → voto ponderado con umbral 0,40) | `protocol.PARAMS` | **0,7807** | diferir necesita razón positiva; el sistema dice «sí» en el 66 % del cubo positivo frente al 47 % del urólogo |
| B. umbral 0,50 | `--threshold 0.5` | 0,7390 | mejor calibrado, 4 puntos menos de F1(yes) |
| C. sin regla del grado | `--no-grade-rule` | 0,7077 | si desconfías del parser regex |

Recomiendo **A**. Pero el umbral 0,40 se eligió sobre los mismos 91 casos
(§4 del README), y es la clase de número que un revisor te va a preguntar.
Si prefieres defender el 0,50 «por principio», el coste está medido: −0,04.

### 3.2 La biblioteca de precedentes: con o sin el propio caso

`--library self` (por defecto en `deployed`) es lo que da 0,9765 sobre los 91:
memorización explícita. En el test **no cambia nada** (el caso nunca está).
Lo que sí cambia es el **acta**: en `deployed` sobre los 91 el presidente lee
las palabras del urólogo sobre ese mismo paciente y su prosa se parece a
ellas. Si vas a enseñar actas de casos etiquetados, enséñalas de `runs/honest`,
no de `runs/deployed`. Y si prefieres que ni siquiera exista la opción,
`Library(exclude_self=True)` fijo en `run_task1.py` y se acabó: el número
sobre los 91 pasa a ser 0,8215 (expertos memorizados, biblioteca LOO).

### 3.3 Las tres reglas de panel del cubo positivo

`experts/cohort.POSITIVE_PANEL_RULES`: PSA ≥ 20, edad ≥ 78, PI-RADS ≤ 2 →
diferir. Se apoyan en 6, 2 y 2 casos. Son criterio de guía (alto riesgo →
estadificar; expectativa de vida; sin lesión), pero **los umbrales son tuyos
de revisar**: un urólogo puede preferir PSA ≥ 20 → «estadificar antes de
decidir» en vez de «no biopsiar». El caso `0169468160c6` (PSA 187, el urólogo
biopsió) es el que la regla falla.

### 3.4 El parser del grado (`decide.documented_grade`)

Cubre `ISUP n`, `grade group n`, `GG n`, `Gleason a+b`, `Gleason 6–10`. No
cubre «favorable intermediate risk», «low-risk disease» ni «Gleason 7» sin
patrón (que asigna GG 2 por convención). Revisa con tu criterio: (a) si «Gleason
7» sin patrón debe ser GG 2 o «no determinado»; (b) si «low-risk» en las notas
debe contar como GG 1. Cada caso que añadas cambia la regla GG ≥ 2 / GG 1.

### 3.5 Los prompts del presidente y del registrador

Dos cosas que un modelo de 2B no hace bien y que sólo se arreglan escribiendo:

* el presidente **nombra la maquinaria** («supported by the cohort criterion»,
  «the panel protocol») pese a la instrucción de no hacerlo. Con el juez de
  razonamiento del reto activo (peso 0,20) eso es prosa peor que la de un
  urólogo. Es el `CHAIR_SYSTEM` de `prompts.py`, bloque «HOW TO WRITE
  `reasoning`». Prueba a quitar de `chair_standing()` los nombres de regla y
  dejar sólo la decisión y la evidencia;
* el registrador escribe a veces un **umbral de la guía** (0,15 ng/mL²) que la
  guardia de procedencia marca como valor sin fuente (16 de 91 retos, 10 sin
  resolver). No es alucinación —está en la intervención del EAU— pero la
  guardia sólo mira herramientas y panel. Si te molesta el aviso, añade la
  intervención del EAU al «haystack» en `graph.registrar_post`.

### 3.6 Lo que NO conviene tocar

* `enforce_grounding` y la decisión de pesar `bx` aunque no aterrice: medido
  dos veces, sale a cuenta (+0,03 neto).
* que el LLM no vote: medido tres veces (registrador 0,47, verificador 0,49,
  presidente 0,36 cuando disiente en `honest`).
* la temperatura: ya está en 0.

---

## 4. Cómo abordar las tareas 2 y 3 con esta arquitectura

La junta es reutilizable tal cual: cambia el catálogo de herramientas (sale
de la lista MCP viva), los expertos, las reglas del protocolo y el esquema de
salida. Lo que hay que saber de cada tarea ya está medido en sesiones
anteriores; lo pongo con la palanca que implica.

### 4.1 Tarea 2 — decisión de tratamiento (`ranking` baseline 0,4457; pesa lo mismo que la 1)

Es donde más margen hay: la puerta falla el 43 % y la F1 es ponderada sobre
cuatro clases, de las que el baseline **nunca emite dos**
(`continued_surveillance`, 14 casos; `watchful_waiting`, 2).

1. **Expertos**: entrena `expert_modelate/task_two` con la misma receta
   (bloques A + patología + RM; aquí sí existe `get_pathology_report`). La sonda
   medida dice que **los embeddings congelados de RM + biopsia separan
   `active_treatment` del resto con AUC 0,76–0,80**; en la tarea 1 no valían y
   aquí sí, así que el Experto F (bloque F) entra en el bakeoff.
2. **Protocolo por cubo**: el cubo aquí es el **ISUP** (GG 1 → vigilancia
   activa o continuada; GG ≥ 3 → tratamiento; GG 2 es el indeterminado), con
   la edad y la comorbilidad decidiendo `watchful_waiting`. Lee los `free_text`
   del urólogo de los 72 casos igual que hice con los 49 de la tarea 1: ahí
   está el criterio de «continued vs active surveillance», que es la clase que
   nadie emite.
3. **Traza**: entrena el modelo de traza sobre las 72 (`reasoning_model`
   admite las 11 variables de la tarea 2 cambiando `TASK1_VARIABLES`).
   `tool_score` aquí es artefacto en local (el ground truth trae
   `reveal_sequence` vacío) — no optimices contra ese cero.
4. **Protocolo de decisión**: la cascada con umbral por clase. La F1 ponderada
   premia acertar la clase mayoritaria (`active_treatment`, 31/72), así que la
   carga de la prueba aquí es «tratar salvo razón documentada para vigilar».

### 4.2 Tarea 3 — meses a recurrencia (`ranking` baseline 0,6636; pesa la mitad)

Tres hechos medidos que cambian el orden de trabajo:

1. **El `ranking_score` es sólo el c-index.** La magnitud no rankea; ordenar
   el riesgo sí. Predecir 60 meses a todos da `mean_case_score` 0,75 pero
   c-index 0,50.
2. **El prompt nunca explica la censura** y el 75 % de los casos son
   censurados: por eso el `form_fill` se planta con «Cannot be determined» y
   el baseline pierde casos. Un caso perdido no es un cero: es un caso menos
   en el c-index.
3. **`event` se escribe constante a 0** (`Task3Output` no tiene el campo).

Palancas, por orden de coste: (a) un respaldo determinista que nunca deje un
caso sin número (una cabeza de Cox sobre patología quirúrgica: ISUP, márgenes,
pT, PSA prequirúrgico), que también ordena el riesgo mejor que el LLM
(c-index de la cabeza sobre embeddings medido 0,60–0,65; con las variables
tabulares de patología debería subir); (b) que el LLM sólo escriba el
razonamiento y el número salga de la cabeza — exactamente el papel que el
presidente tiene aquí; (c) el prompt de censura, que sólo importa para la
prosa.

### 4.3 Lo común a las tres

* **Una junta por tarea, un protocolo por tarea, un mismo grafo.** El grafo ya
  lee el catálogo de la lista MCP; lo que cambia por tarea es `experts/`,
  `protocol.py`, el esquema (`build_dynamic_model(task, …)`) y el «marco»
  clínico del presidente.
* **Simula antes de correr.** `analysis/simulate.py` evalúa cualquier
  protocolo en segundos con el evaluador oficial; el LLM no movió la nota en
  ninguna de las dos corridas de la tarea 1. Elige parámetros sobre la cifra
  honesta y corre el LLM una vez.
* **Cada regla con su número.** Todo lo que entra en la cascada lleva su
  acierto medido en la serie etiquetada y se escribe en el acta.

---

## 5. Qué es mejor entregar

**Entregar el modo `deployed` tal cual (expertos entrenados sobre los 91 +
biblioteca con los 91), con los cambios 3–5 del §2.** Razones:

1. Sobre el test es idéntico a `honest` (0,7807 estimado sobre los 91, +0,14
   sobre el baseline y +0,07 sobre la mejor generación anterior) y usa toda la
   información etiquetada disponible.
2. Es determinista en todo lo que puntúa: la decisión, la confianza, los
   pesos y las revelaciones las fija el código, y el LLM sólo aporta la prosa.
   Un fallo del modelo de lenguaje no puede perder un caso.
3. Lo que queda por ganar está localizado: el cubo positivo sin grado
   documentado (27 casos de 91, acierto 0,63) y la prosa del presidente para
   el juez. Lo primero necesita más datos o al urólogo; lo segundo, §3.5.

Lo que **no** conviene entregar como resultado: el 0,9765. Es el techo de
copiar la traza, y así hay que presentarlo si se muestra — como la
comprobación de que el mecanismo de traza funciona, no como rendimiento.
