# Los prompts de la tarea 2, uno por uno

Este documento es el hermano de [`../task_1/PROMPTS.md`](../task_1/PROMPTS.md).
No repite lo que allí está: se centra en **qué cambia respecto a la tarea 1 y por
qué**, porque la arquitectura es la misma y la diferencia es deliberada.

## Coste, medido con el tokenizador del propio modelo

`gemma-4-E2B-it`, longitud del *system prompt* de cada papel:

| papel | tarea 2 | tarea 1 | diferencia |
|---|---:|---:|---:|
| cabecera `CONFERENCE` | 247 | 742 | −495 |
| `EXPERT-EAU` | 351 | 1537 | −1186 |
| `MODERATOR` | 342 | 1336 | −994 |
| `REGISTRAR` | 374 | 1546 | −1172 |
| `VERIFIER` | 339 | 1365 | −1026 |
| `CHAIR` | 128 | 1080 | −952 |

La tarea 2 gasta **una cuarta parte** de instrucción que la tarea 1. No es
descuido: es el criterio del paso 4.1 llevado al prompt.

## Por qué son más cortos

| | tarea 1 | tarea 2 |
|---|---|---|
| dónde está la dificultad | el cubo `bx=Positive`, 49/91 casos que ninguna variable determina | en ningún sitio: la etiqueta es casi función de `bx_isup` (0,8611) |
| qué aporta el LLM | **recupera el grado documentado** de las notas, y eso decide el caso | casi nada de decisión: el grado ya viene estructurado |
| a qué dedica la sala el tiempo | **encontrar evidencia** | **justificar y calibrar** |

En la tarea 1 el registrador tiene que arrancar un grado de la prosa de notas
antiguas, y ahí cada línea de instrucción se paga sola. En la tarea 2 el grado
llega en el `structured-prompt`: pedirle al modelo que lo busque es pedirle que
repita algo que ya sabe. De ahí la frase que sí está, y que es nueva:

> *The structured values are already known. Ask documents for additional
> findings, not for a value printed at INTAKE. Missing information is a finding.*

## Lo que la cabecera declara y la tarea 1 no necesitaba

Tres hechos medidos entran en el prompt porque, si no, la sala razona sobre una
ficción:

1. **Las réplicas.** *"Experts 1, 2 and 4 made identical historical decisions:
   confirmatory replicas, not independent votes."* Emiten las mismas 72
   decisiones: una votación entre ellos tiene resultado conocido de antemano.
2. **El nodo de aptitud.** *"The fitness node AUC is 0.500, not informed
   discrimination."* Con 2 casos de `watchful_waiting` frente a 31, la cohorte no
   contiene la evidencia. Declararlo es lo que impide tratar como informado un
   veredicto que no lo es.
3. **Nadie vota.** *"Do not vote: the written consolidation decides."* La decisión
   sale de la cascada y del portavoz por fiabilidad, en `protocol.py`.

> **Nota de exactitud (corregida).** El prompt decía `AUC is 0.500`, copiado del
> texto del plan; el artefacto entrenado mide **0,5645**
> (`experts_2/reports/expert_five_report.json`). Sigue siendo azar —su acierto,
> 0,9394, es exactamente el suelo de la moda— pero el número redondo no era el
> medido. Ahora **el acta y el prompt leen los dos de `protocol.NODE_AUC`**, así
> que si el experto se reentrena cambian a la vez y no se desincronizan.

## CHAIR: 128 tokens, y por qué es un riesgo abierto

El presidente de la tarea 2 cabe en 128 tokens frente a los 1080 de la tarea 1.
Le pide cuatro cosas: describir al paciente, explicar el compromiso, no inventar,
y no contar cómo se produjo la decisión.

Es el papel que redacta el `free_text` entregado, y ese texto es lo que puntúa
`rationale_score` — **0,20 del `case_score` con el juez encendido**, el mismo peso
que la confianza. Que sea ocho veces más corto que el de la tarea 1 no está
justificado por el criterio de 4.1: ese criterio explica por qué el *registrador*
necesita menos instrucción, no por qué el *redactor* la necesita.

**Está sin medir.** La simulación (`analysis/simulate.py`) corre sin LLM, así que
no toca al presidente: su `free_text` es un marcador y `rationale_score` no
interviene. Hasta que no haya una corrida con juez sobre los 72, no sabemos si
esta brevedad cuesta puntos. Es lo primero que hay que mirar cuando 4.3 tenga
número, y si cuesta, el arreglo es traer las guardias de prosa de la tarea 1, que
ya están escritas y medidas.

## El digest: evidencia cruda, no el resumen del registrador

`clinical_digest` no le pasa al presidente lo que el registrador *dijo*, sino los
documentos recuperados, filtrados línea a línea con `process_language`. Dos
motivos, los dos de la tarea 1: un resumen intermedio es una oportunidad más de
alucinar, y el lenguaje de proceso (*"the panel agreed…"*) se cuela en la nota si
no se corta antes de que el presidente lo lea.

La guardia se verificó antes de activarla, como exige el paso 4.2: **0 falsos
positivos sobre los 72 `free_text` reales** del urólogo. El test que lo fija está
en `agent/tests/test_guards_task2.py`, para que no regrese en silencio si alguien
añade un patrón.

## Qué se le pide a un LLM y qué no

| | quién | por qué |
|---|---|---|
| decidir la acción | **el código** (`protocol.consolidate`) | los expertos entrenados baten al LLM; el portavoz se elige por fiabilidad medida |
| rellenar `variable_weights` | **el código** (moda) | la compuerta 1.2 mide que ninguna política aprendida bate al suelo en esta tarea |
| `confidence` | **el código** (constante `clear`) | 0,9028 y ningún modelo la bate bajo LOO |
| `reveal_sequence` | **el código** (lista vacía) | los 72 patrones la traen vacía; declarar secciones pone `tool_score` a 0 |
| abrir documentos | LLM + MCP (REGISTRAR) | hace falta el informe de patología para que hable el Experto 2 |
| criticar a los expertos | LLM (EXPERT-EAU, VERIFIER) | señalar dónde la regla está en su límite |
| **redactar la nota** | **LLM (CHAIR)** | es lo único entregado que el código no puede escribir |
