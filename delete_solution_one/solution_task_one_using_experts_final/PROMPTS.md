# Los prompts, uno por uno

Este documento es el análisis de los cinco prompts que llevan a un modelo de
lenguaje en esta solución: qué le pide cada uno, con qué cota, qué se midió que
hacía mal, y qué se cambió. Es la parte del sistema que no se puede leer en el
código sin perder de vista por qué está escrita así.

Un principio recorre los cinco, y es la lección de tres generaciones anteriores:
**un prompt no es una descripción, es un presupuesto**. Le dice al modelo qué
puede decir, en cuántas palabras y con qué material; y todo lo que la instrucción
enuncia y se puede comprobar, se comprueba después en código
([`decide.py`](decide.py)), porque pedirlo por favor no basta.

## Coste, medido con el tokenizador del propio modelo

| prompt de sistema | tokens | palabras | cota que impone |
|---|---:|---:|---|
| cabecera común (quién está en la sala) | 604 | 393 | — |
| EXPERT-EAU | 1 273 | 857 | 200 palabras |
| MODERATOR | 1 154 | 759 | un objeto JSON |
| REGISTRAR | 1 256 | 854 | 320 palabras |
| VERIFIER | 1 140 | 757 | 260 palabras |
| CHAIR | 1 043 | 729 | 40–90 palabras |

Los cuatro primeros incluyen la cabecera común, de ahí que ronden todos los
1 200 tokens. El quinto **no la incluye**, y esa es la corrección principal de
esta versión.

---

## 0. La cabecera común: quién está en la sala

Presenta a los catorce participantes por su papel y en el orden en que hablan, y
fija cinco reglas de conversación: dirígete por su papel al colega que te afecta,
no enuncies un valor que no hayas leído, un precedente es otro paciente, «no lo
sabemos» es un hallazgo, no invadas el turno de otro.

**Por qué existe.** En una pizarra, el valor de una intervención depende de en
calidad de qué se dice. Sin la tabla, el modelo trata igual una probabilidad de
un clasificador con AUC 0.79 que una frase del registrador, y no puede saber a
quién debe rebatir.

**Qué NO hace.** No la ve el presidente. Ver §5.

---

## 1. EXPERT-EAU — el especialista en la guía

**Lo que se le pide.** Una única búsqueda `search_guidelines` *antes* de escribir
una palabra; después, tres apartados en 200 palabras: qué dice la guía (con cita
literal entre comillas), qué es lo que las apuestas de los expertos no zanjan, y
qué falta por establecer.

**Los tres acotamientos, y el fallo que corrige cada uno.**

1. *Recuperar primero, hablar después.* Sin esto el modelo escribe «la guía
   recomienda…» sin haber recuperado nada. El grafo lo comprueba: si no llamó a
   la herramienta se le devuelve el turno (`EAU_NUDGE`), y si aun así no la
   llama, su intervención se anota en el acta con «no recuperó nada, así que
   nada de lo anterior le es atribuible».
2. *La lista de valores que YA se conocen.* Medido en el piloto de la generación
   anterior: el especialista escribía «nos falta la densidad de PSA» y la
   densidad de PSA estaba impresa en la intervención 1. Eso mandaba al
   registrador a abrir un documento para recuperar un número que ya estaba sobre
   la mesa, y cada documento de más se paga en `tool_score`. El prompt enumera
   los nueve valores del panel y dice: si el umbral depende de uno de ellos,
   **léelo tú y di de qué lado cae**.
3. *No recomendar.* Su papel es traer el criterio, no la decisión. Un
   especialista que recomienda arrastra al resto de la sala antes de que se
   hayan abierto los documentos.

**Qué se comprueba en código.** Que llamó a la herramienta. La cita literal no
se puede verificar automáticamente contra el corpus recuperado sin un
alineamiento que produciría más falsos positivos que aciertos; queda anotada la
llamada, que es lo que sí es objetivo.

**Una degeneración medida, y su arreglo.** Con el apartado final redactado como
lista libre («qué necesitamos aún»), **el 40 % de sus líneas pedía un valor que
ya estaba impreso en el panel** —medido con la misma regla que el sistema aplica
para tirar preguntas del moderador—, en forma de plantilla: *«the PI-RADS score is
2, which is a factor the guideline makes decisive»*, *«the months since last PSA
is 2, which is…»*. Es exactamente lo que el propio prompt prohibía tres líneas
más arriba: un modelo pequeño, ante una lista libre, produce una plantilla. El
arreglo es quitarle la libertad de forma: el apartado pasa a ser **una línea por
documento**, con la lista cerrada de los cuatro documentos delante y un ejemplo
de la forma exacta. Las actas de antes del ajuste se conservan en
[`runs/_antes_del_ajuste_prompts/`](runs/_antes_del_ajuste_prompts) para poder
comparar.

**Y el arreglo es parcial, que es lo que hay que decir.** Con el formato cerrado
el 40 % baja al **12 %**, pero no a cero: algunas líneas siguen apoyándose en un
valor del panel (*«laboratory_results - the PSA density…»*). El cuaderno mide las
dos cifras y publica la tabla. No se ha insistido más porque el residuo no cuesta
puntuación: desde que el plan lo fija el Experto 4, ese apartado ya no manda a
abrir ningún documento.

Merece decirse por qué el fallo no costaba puntuación: desde que el plan de
documentos lo fija el Experto 4, un «lo que falta» mal escrito ya no manda a
nadie a abrir nada. El diseño contenía el daño. Se corrigió porque el acta es un
entregable que alguien lee, no porque restara.

---

## 2. MODERATOR — las preguntas, no los documentos

**Lo que se le pide.** Un objeto JSON con: dos a cuatro preguntas abiertas, una
pregunta por cada documento que EXPERT-TRACE haya listado, y si conviene llamar
al experto de imagen.

**El cambio de fondo respecto a las generaciones anteriores: ya no elige los
documentos.** Antes el moderador componía el plan y el código lo recortaba a
posteriori. Ahora el plan lo fija el Experto 4 —el modelo entrenado sobre las 91
trazas del urólogo lector— y el moderador sólo le adjunta a cada documento la
pregunta que tiene que contestar.

**Por qué.** `tool_score` es **precisión** contra las secciones que abrió el
urólogo: abrir de menos es gratis, abrir de más se paga. Predecir lo que ese
urólogo abre es un problema supervisado con 91 ejemplos, y un modelo entrenado
lo hace mejor que un LLM razonando sobre el caso. La corrida completa lo
confirma: la frecuencia con que esta solución abre cada sección coincide con la
del urólogo dentro del ruido (§3 del README).

**Los dos acotamientos.**

1. *Nunca pedir un valor del panel.* Misma razón que en el EAU, y aquí además
   hay una regla mecánica: `roster.drops_panel_question` tira la pregunta que
   pide un valor impreso, y distingue «¿cuál es la densidad de PSA?» (se cae) de
   «¿comparan las notas el grado previo?» (se queda), porque la segunda pide algo
   que sólo vive dentro de un documento.
2. *Qué buscar en las notas cuando hay biopsia previa positiva.* El prompt
   nombra las cuatro cosas: grado, número y fechas de las sesiones, protocolo de
   vigilancia, tratamiento ya acordado. No es un detalle: es el cubo donde se
   decide la tarea.

---

## 3. REGISTRAR — el único que abre documentos

**Lo que se le pide.** Llamar a las herramientas del plan *antes* de escribir
una palabra, y después un informe de 320 palabras en cuatro apartados: qué
encontré, qué no abrí, qué apoya cada cosa, y hacia dónde se inclina.

**Las líneas obligatorias.** Para las notas previas tiene que emitir, cada una en
su línea y citando las palabras de la nota:

```
PRIOR GRADE: <Gleason o ISUP tal como está escrito, o "not recorded">
BIOPSY SESSIONS: <cuántas, con fechas, o "not recorded">
SURVEILLANCE: <en protocolo / biopsia confirmatoria pendiente / not recorded>
TREATMENT: <acordado, rechazado, o ninguno>
```

y para la resonancia, `COMPARISON:` y `LESION:`. Es el formato lo que hace que el
informe sea legible por el resto de la sala y por el parte del presidente.

**El acotamiento que más vale.** *La primera acción del turno es una llamada, no
prosa.* Un modelo pequeño, si se le deja, anuncia lo que va a hacer y se queda
sin turno. Y: *cada número, fecha y frase tiene que aparecer en un resultado de
herramienta o en el panel*, que es lo que comprueba `decide.unsourced_values`.

**Dos degeneraciones medidas.** En **el 31 % de las actas** el registrador pegaba
el JSON crudo de la serie de PSA —`{"date": "Feb 2022", "val": 4.2}, …`— pese a
la prohibición, porque «no pegues JSON» no le dice qué hacer en su lugar. Ahora el
prompt le da la forma: primer valor con su fecha, último valor con su fecha, y la
forma de la curva en palabras: el JSON crudo **desaparece por completo**. Y en el
3 % ponía el mismo hallazgo a favor y en contra; ahora se le dice que un hallazgo
va en un solo lado y que, si corta por los dos, elija el más fuerte y lo
justifique en la misma línea. También **cae a cero**.

La lección de las tres es la misma y vale para cualquier prompt: **prohibir no
basta, hay que dar la forma**. «No pegues JSON» no le dice qué escribir en su
lugar; «primer valor con su fecha, último con la suya, y la forma de la curva en
palabras» sí.

**Y un fallo que sólo aparece corriendo los 195.** El registrador **inventa el
grado de la biopsia previa en el 6.7 % de los informes**, entrecomillado como si
lo citara de la nota: `PRIOR GRADE: "Gleason 3+4 focus"` en un caso cuyo fichero
clínico no menciona «Gleason» ni «ISUP» ni una sola vez. Es la peor alucinación
posible en esta tarea, porque el grado es lo que decide si el hombre se
re-biopsia o se trata. La guardia de valores no lo cazaba: mira números con
decimales o de tres cifras, e ignora a propósito los enteros de una cifra. Ahora
hay una guardia específica (`decide.unsourced_grades`) en las tres capas por las
que puede colarse, y el reto al registrador le dice, con todas las letras, que
`PRIOR GRADE: not recorded` es la línea honesta y que esa ausencia es en sí misma
un hallazgo que la sala necesita.

**Corrección de esta versión.** La guardia de procedencia marcaba dieciséis veces
el umbral 0.15 ng/mL² como valor sin fuente. No era una alucinación: está en la
intervención del especialista en la guía. Un falso positivo repetido enseña a
ignorar la guardia, así que ahora el pajar incluye el acta entera, no sólo los
resultados de herramienta y el panel.

**Lo que se le impide en vez de pedírselo.** `get_family_history` no se le enlaza
—el urólogo la pidió 0 de 91 veces— y, cuando el plan está vacío, no se le
enlaza ninguna herramienta de documento. Esto último corrige un fallo medido: con
el plan vacío y la instrucción «no hagas llamadas», el modelo abría tres o cuatro
documentos igualmente, en los dos únicos casos de 91 donde el urólogo no abrió
nada.

---

## 4. VERIFIER — ¿se puede decidir ya?

**Lo que se le pide.** Cuatro comprobaciones en 260 palabras —suficiencia,
alineamiento con la posición del panel, las preguntas abiertas una a una, y qué
variables pesan según la guía— y una línea mecánica de cierre:

```
VERDICT: <ready | not-ready> | SUGGEST: <biopsy | defer> | MISSING: <documento | none>
```

**Por qué la línea.** Huang et al. (ICLR 2024) miden que un LLM no juzga con
fiabilidad si su propio trabajo necesita corrección, y en la generación v2 se
observó en directo: devolvía «no reabrir» en el 100 % de los casos, incluidos
los que tenían dos posturas opuestas. La solución no es pedirle que se esfuerce
más: es que escriba una línea parseable y que **el grafo aplique la regla**. Si
no la escribe, la sesión se cierra: reabrir tiene que costar una afirmación
explícita.

**Simplificación de esta versión.** El prompt anterior dedicaba doce líneas a
explicar por qué no debía pedir el laboratorio («la trampa»). Ya no hace falta:
como el plan lo fija el Experto 4 y nada fuera del plan se abre nunca, lo único
que el verificador puede declarar ausente es un documento que estaba en el plan y
que el registrador no abrió. Doce líneas menos de prompt y una condición menos
que puede fallar.

---

## 5. CHAIR — la nota clínica

Éste es el prompt que se reescribió entero, y conviene explicar el porqué con el
caso que lo motivó. En la corrida de 195 casos de la generación anterior, el
presidente escribió esto:

> *The decision to defer biopsy is supported by the cohort criterion and the
> EXPERT-LIBRARY precedent, which indicates deferral for this exact panel
> configuration. While the PI-RADS 2 score and the prior positive biopsy status
> weigh against immediate intervention, the VERIFIER noted that the GRADE of the
> prior biopsy result remains unanswered, introducing uncertainty. Therefore,
> the evidence converged on deferral…*

Y el urólogo, para ese mismo paciente, había escrito:

> *Priads 2 with only sightly elevated PSA*

El texto libre que el reto puntúa es **la traza de razonamiento de un clínico**.
El de arriba describe cómo se produjo el dictamen, no al paciente. Medido sobre
los 195 casos de esa corrida: **187 notas (96 %) nombraban un participante o un
mecanismo**.

**La causa no era el modelo. Era el prompt.** Al presidente se le entregaban tres
cosas que garantizaban ese resultado:

1. la cabecera común, que **enumera a los catorce participantes por su nombre**;
2. el acta entera —unos 5 650 tokens de media— con los nombres en cada cabecera
   de intervención;
3. la decisión, redactada como *«PANEL-PROTOCOL ANSWERED NO BIOPSY by the rule
   cohort criterion (pirads_le_2), carried by EXPERT-COHORT»*.

Con eso delante, copiar los nombres es lo que se le pidió.

**Los cuatro cambios.**

1. **El presidente no ve el acta ni la lista de participantes.** Recibe un
   *parte clínico* construido en código (`prompts.clinical_digest`): la ficha del
   paciente, lo que dijeron los documentos —el informe del registrador, filtrado
   línea a línea de cualquier mención a un colega—, la cita de la guía, y la
   valoración con su justificación **en palabras clínicas**
   (`protocol.clinical_reason`), no por el nombre de la regla. El acta sigue
   existiendo entera y es la traza auditable; lo que cambia es que el modelo que
   redacta no la tiene delante. Coste del prompt: **de ~7 800 tokens a ~2 100**.
2. **Una lista negra explícita** de lo que no puede escribir: protocolo, panel,
   criterio, regla, modelo, clasificador, probabilidad, tramo, experto, revisor,
   registrador, moderador, colega, junta, acta, intervención, precedente, serie,
   consenso, «la evidencia convergió», «apoyado por el».
3. **Ejemplos reales del urólogo lector**, elegidos por cubo de biopsia previa y
   excluyendo el caso que se decide. Un modelo pequeño imita un registro mucho
   mejor de lo que sigue una descripción de él.
4. **La alternativa clínica sale del código, no del criterio del modelo.** En la
   primera prueba, con la instrucción «cierra con la alternativa si la hay», el
   presidente la ofrecía en casi todas las notas, incluida la de un hombre con
   PSA 187 al que acababa de mandar a estadificación: *«podría igualmente
   retrasarse un año»* detrás de *«el PSA obliga a tratar»* no es una
   alternativa, es una contradicción. Ahora `clinical_reason` decide si el caso
   admite una, y la línea **sólo aparece en el parte cuando existe**. Que
   apareciera con un «no hay ninguna» tampoco servía: el modelo escribía «No
   alternative plan exists» dentro de la nota clínica.

**Qué se comprueba en código.** `decide.process_language` busca los patrones
prohibidos en la nota entregada. La lista está curada, no es una lista de
palabras sueltas: en prosa clínica legítima aparecen «laboratory panel»,
«surveillance protocol», «PI-RADS score» y «high probability of undetected
cancer», y marcarlas enseñaría a ignorar la guardia. Verificación: **0 falsos
positivos sobre los 91 textos reales del urólogo**, y caza los seis fragmentos
del ejemplo de arriba.

Si la nota los contiene, se le devuelve el turno una vez con la lista delante. Si
reincide, la nota se redacta de forma determinista (`decide.clinical_note`) con
los valores del caso y los hechos recuperados, en el mismo registro. Así, **la
nota entregada no puede describir el procedimiento**, la decida quien la decida.

**Lo que el presidente ya no hace: votar.** En las generaciones anteriores podía
disentir y se le retaba. Medido: en el modo honesto disintió en 22 de 91 casos y
el protocolo tenía razón en 14 de ellos; el mecanismo de reto costaba hasta dos
llamadas extra por caso para acabar imponiendo la decisión del protocolo. Aquí el
presidente firma la valoración y escribe por qué. Es más rápido, puntúa mejor, y
—esto importa— es lo honesto: si la decisión la toma una cascada de reglas
medidas, el acta debe decir eso y no simular una deliberación que no decide.

---

## 6. Qué se le pide a un LLM y qué no, en una tabla

| tarea | ¿la hace el modelo? | por qué |
|---|---|---|
| recuperar la guía y citarla | **sí** | es texto libre sobre un corpus; no hay alternativa |
| leer un documento y resumir lo que dice | **sí** | ídem, y es lo que alimenta la decisión |
| formular las preguntas abiertas del caso | **sí** | requiere entender el caso; y sus errores son baratos |
| decidir qué documentos abrir | no | modelo entrenado sobre 91 trazas; `tool_score` es precisión |
| decidir la biopsia | no | medido en el azar en el cubo difícil (0.47–0.49) |
| fijar confianza y pesos | no | modelo entrenado contra las trazas del urólogo |
| declarar qué secciones se abrieron | no | se deriva de las llamadas reales |
| leer el grado de la biopsia previa | no | expresión regular sobre el texto crudo: el modelo lo copia mal |
| **escribir la nota clínica** | **sí** | es exactamente para lo que sirve, y es lo que el juez puntúa |
