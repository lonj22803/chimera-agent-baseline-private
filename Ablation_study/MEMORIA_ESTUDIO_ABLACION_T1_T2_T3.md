# Memoria del estudio de ablación: trabajo realizado, resultados y trabajo futuro

**Proyecto:** CHIMERA, arquitectura V4.  
**Periodo documentado:** 21–23 de septiembre de 2026.  
**Alcance:** T1, decisión de biopsia; T2, decisión de tratamiento; T3, pronóstico de recurrencia.  
**Fuentes:** artefactos de `Ablation_study/` y [sesión de trabajo de Codex](codex://threads/01a0c350-d30f-71d3-8fad-711ed0847c24).

El estudio permitió localizar qué partes de la arquitectura sostienen las predicciones, cuáles mejoran el formulario o la explicación y cuáles pueden simplificarse en las condiciones evaluadas. Su resultado principal es una propuesta diferente para cada tarea: **reducir selectivamente T1, mantener una única llamada generativa por caso en T2 y eliminar la generación con LLM en T3**. Las tres propuestas conservan el núcleo de cálculo que corresponde a su tarea.

Esta memoria explica el trabajo y sus implicaciones. Las cifras proceden de los resultados guardados; las propuestas de investigación se identifican como trabajo futuro. Los estudios están cerrados y la V4 permaneció intacta. Las arquitecturas reducidas son candidatas evaluadas internamente, pendientes de validación independiente antes de su adopción.

## 1. Qué se buscaba con el estudio

Una arquitectura con muchos expertos, agentes, herramientas y controles puede funcionar bien sin que todas sus piezas aporten por igual. Un componente puede modificar la predicción; otro, limitarse a redactar información ya calculada; otro, ser necesario para abrir una fuente o impedir afirmaciones sin respaldo. Contar agentes o mirar únicamente la puntuación final no permite distinguir esas funciones.

La pregunta fue: **¿qué ocurre al retirar o sustituir cada intervención, manteniendo el resto del sistema lo más estable posible?** Esa comparación es una ablación. Por ejemplo, se ejecuta la junta completa y después una variante sin verificador, usando los mismos casos, para observar qué cambia y cuánto cuesta cada ejecución.

Se perseguían cuatro objetivos:

1. **Explicar de dónde sale el rendimiento:** atribuir los cambios a reglas, expertos, documentos, controles o generación de texto.
2. **Reducir coste y complejidad:** evitar llamadas, tokens, turnos y dependencias que no aportan valor medido.
3. **Preservar la calidad completa de la salida:** decisión, formulario, explicación e integridad de las afirmaciones.
4. **Definir una arquitectura candidata por tarea:** producir evidencia para una simplificación posterior, conservando una referencia reproducible.

El estudio comenzó con T1. Tras su cierre, en la sesión se solicitó expresamente extenderlo a T2 y T3 para estudiar cómo reducir también esas arquitecturas.

## 2. Qué se evaluó y cómo se hizo

### 2.1. Casos, expertos y modelos

| Tarea | Casos evaluados | Salida principal | Condición de evaluación |
|---|---:|---|---|
| T1 | 91 | Biopsia sí/no, formulario y nota | Modo `honest`, con predicciones de expertos fuera de pliegue, u OOF |
| T2 | 72 | Recomendación de tratamiento, formulario y nota | Expertos congelados; los casos participaron en su desarrollo |
| T3 | 75 | Evento de recurrencia, meses y explicación | Predicciones OOF del motor seleccionado |

Son **238 registros caso-tarea**, sin que ello implique 238 pacientes diferentes. OOF significa que la predicción correspondiente a un caso se obtiene desde un ajuste que excluye ese caso; la selección de reglas, hiperparámetros o sistemas sobre la misma cohorte sigue limitando la independencia de la evaluación.

También es necesario distinguir **experto**, **papel LLM** y **modelo generador**. Los expertos pueden ser modelos predictivos, reglas o lectores de resultados congelados. Moderador, registrador, verificador y presidente son papeles del flujo, que pueden implementarse mediante un LLM o mediante código.

| Uso en las corridas documentadas | Modelo o mecanismo |
|---|---|
| Generación en T1 y T2 | `google/gemma-4-E2B-it`, servido con vLLM, temperatura 0 |
| Presidente de T3 | `gemma4:e4b`, servido con Ollama, temperatura 0 |
| Juez narrativo de las tres tareas | `gemma4:e4b`, mediante el evaluador oficial y Ollama |
| Variantes deterministas | Reglas, predicciones congeladas y plantillas; sin llamada generativa para la nota |

**No se hizo una comparación entre familias de LLM.** Por tanto, los resultados permiten valorar papeles y configuraciones concretas, pero no declarar que un modelo o los LLM en general sean irrelevantes. En T3, además, generador y juez emplearon el mismo identificador de modelo; conviene contrastar las conclusiones narrativas con evaluación humana y otro juez.

Fuentes: [configuración T1](runs/L0/run_config.json), [configuración T2 reducida](T2_T3/runs/T2-Lmin/run_config.json), [manifiesto T3](T2_T3/runs/T3-L0/arm.json) y [registro del juez](results/J_session_before.json). Las carpetas `runs/` son artefactos locales regenerables y no se versionan.

### 2.2. Cuatro dimensiones de evaluación

| Dimensión | Pregunta | Qué se midió |
|---|---|---|
| **D: decisión** | ¿Cambia la predicción y su acierto? | Aciertos, F1 y ranking en T1/T2; discriminación mediante c-index en T3 |
| **F: formulario o salida estructurada** | ¿Se conserva la información que debe entregarse? | Confianza, pesos, factores, herramientas y respaldo documental en T1/T2; evento y tiempo en T3 |
| **N: narrativa** | ¿Se conserva la calidad de la explicación? | `rationale_score` del juez y auditoría de notas |
| **C: coste** | ¿Qué recursos exige producir la salida? | Llamadas, tokens y segundos; telemetría de ejecución |

En T1/T2, equivocarse en la decisión hace que el caso reciba cero en la puntuación correspondiente del evaluador. El análisis narrativo reportado se restringe a **74 casos acertados de T1 y 65 de T2**; en T3 se juzgan los 75 casos. La calidad de las explicaciones de los casos mal clasificados en T1/T2 no queda resumida por esas medias.

El ranking de T1/T2 combina decisión y otros campos. El c-index de T3 mide la ordenación del riesgo. **No son una misma escala de calidad**, y tampoco deben compararse directamente las medias narrativas entre tareas.

### 2.3. Secuencia de trabajo

1. **Fijar la referencia y las reglas de análisis.** Se registraron huellas del código, resultados de referencia, pruebas, hipótesis y márgenes antes de las comparaciones. T1 tuvo fases F0–F8; la extensión T2/T3, F0–F6.
2. **Identificar las dependencias.** Se catalogaron nodos, mecanismos y guardias, distinguiendo qué elementos alimentaban realmente las salidas. Los componentes de contrato y operación necesarios para ejecutar el sistema se conservaron.
3. **Ejecutar ablaciones deterministas en CPU.** T1 incluyó retiradas individuales, reconstrucción progresiva de la cascada, combinaciones factoriales, atribuciones de Shapley, sensibilidad y comprobaciones DEV/VAL. T2 exploró las **32 combinaciones** de presencia/ausencia de sus cinco expertos. T3 comparó **cinco variantes numéricas**, incluidos CAPRA y controles con tiempo o evento constantes.
4. **Ejecutar variantes con generación real.** En T1, el control `L0` debía reproducir exactamente decisión, confianza, pesos y plan del simulador en 91/91 casos antes de continuar. Esa comprobación pasó. Las variantes se implementaron mediante mecanismos reversibles dentro del estudio.
5. **Juzgar la narrativa y auditar integridad.** Se realizaron tres pasadas por brazo, con el modelo juez residente durante cada sesión. En T1 se buscaron también cifras o grados sin fuente y lenguaje de proceso en las notas.
6. **Integrar resultados y verificar el cierre.** Se generaron tablas, informes, figuras y comprobaciones de contratos y huellas. Los cierres registran V4 intacta; T1 recoge 199 pruebas V4 y 37 del estudio superadas, y T2/T3 registra 21 pruebas superadas en las suites de su cierre. Esos recuentos corresponden a verificaciones históricas, no a pruebas nuevas ejecutadas para redactar esta memoria.

Fuentes: [plan T1](PLAN_ABLACION_T1.md), [plan T2/T3](T2_T3/PLAN_ABLACION_T2_T3.md), [catálogo T1](configs/intervenciones_t1.yaml), [cierre T1](results/cierre.json) y [cierre T2/T3](T2_T3/results/cierre.json).

### 2.4. Qué variantes se compararon

| Tarea | Brazos | Intervención |
|---|---|---|
| T1 | `L0` y `L0p` | Junta completa y réplica de referencia |
| T1 | `L1`, `L2`, `L3` | Sin EAU, sin moderador y sin verificador, respectivamente |
| T1 | `L4` | Retirada conjunta de EAU, moderador y verificador |
| T1 | `L5` | Sustitución del presidente por nota determinista |
| T1 | `L6`, `L7` | Retirada conjunta de G1/G2 y retirada de G3, respectivamente |
| T1 | `L9/A_min` | Retirada conjunta de imagen, verificador y G1/G2, derivada de los veredictos |
| T2 | `T2-L0`, `T2-Lmin`, `T2-Ldet` | Junta completa; flujo reducido con presidente; salida sin generación |
| T3 | `T3-L0`, `T3-Lmin`, `T3-Ldet` | Conferencia completa; flujo compacto con presidente; salida determinista |

Los nueve brazos principales de T1 tuvieron **27 evaluaciones narrativas**; los seis de T2/T3, **18**. En total, **45 evaluaciones completas**. `L9` se validó en decisión y formulario, pero no tuvo las tres pasadas narrativas de los otros brazos. Su aceptación no demuestra que su narrativa conjunta sea equivalente.

### 2.5. Cómo se decidió si un componente aportaba valor

Se compararon los mismos casos entre control y variante mediante **bootstrap pareado de 10.000 remuestreos**, obteniendo intervalos de confianza del 95 %. T1 añadió McNemar exacto con corrección Holm para decisiones, Wilcoxon para componentes sobre aciertos comunes y comprobación del signo en DEV/VAL.

Los márgenes principales fijados fueron 0,010 para ranking T1/T2 y componentes del formulario, 0,020 para c-index T3 y un margen narrativo de `máximo(0,030, 2 × error estándar de referencia)`. El margen N resultante fue **0,030 en T1, 0,03487 en T2 y 0,030 en T3**; T1 lo estimó usando su réplica, y T2/T3, la variación entre pasadas del control.

En esta memoria, **Δ = control − variante**: un valor positivo indica una pérdida al simplificar; uno negativo, una mejora observada. Se distinguen tres conclusiones:

- **Aporta valor medido:** retirarlo deteriora alguna dimensión conforme a la regla aplicada.
- **Prescindible en lo evaluado:** se conserva la salida o el intervalo completo queda dentro del margen de equivalencia correspondiente.
- **Indeterminado:** los datos no permiten concluir necesidad, equivalencia o perjuicio con suficiente precisión.

La ausencia de una diferencia significativa no demuestra equivalencia. Asimismo, cero cambios en esta muestra no garantiza cero cambios en futuros casos. El veredicto automático `SOBRA` debe leerse junto con la integridad de las notas y el alcance de la intervención.

Fuentes: [prerregistro T1](PREREGISTRO.md), [prerregistro T2/T3](T2_T3/PREREGISTRO.md), [validación del juez T1](results/J_session_validation.json) y [validación del juez T2/T3](T2_T3/results/J_session_validation.json).

## 3. Resultados de T1: simplificación selectiva

La referencia `honest` obtuvo **74/91 aciertos, 81,32 %**, con ranking **0,7607**. Ninguno de los nueve brazos principales con LLM cambió la decisión. Eso indica estabilidad de la decisión ante esas intervenciones, aunque algunos brazos sí modificaron el formulario o la nota.

### 3.1. Qué sostiene la decisión

La cascada distribuyó los casos de esta manera:

| Mecanismo que decidió | Casos | Aciertos | Lectura |
|---|---:|---:|---|
| Reglas de cohorte | 52 | 49 | Mayor cobertura y elevada exactitud observada |
| Grado documentado | 12 | 10 | Resuelve un segundo conjunto de casos mediante información documental |
| Voto ponderado de E1/E3 | 27 | 15 | Tramo con más margen de mejora |

Las reglas de cohorte y grado resolvieron **64/91 casos, con 59 aciertos**. Son centrales en el funcionamiento observado. Sin embargo, sus ablaciones quedaron **indeterminadas según el criterio confirmatorio completo**: la cohorte perdió 0,0648 de ranking al retirarla, pero no superó el requisito McNemar-Holm; el grado presentó incertidumbre y signos opuestos entre DEV y VAL.

Entre los expertos de voto, **E3/FUSION aportó más que E1/STRUCTURED**: la atribución Shapley de ranking fue 0,0371 frente a −0,0052. Shapley resume la aportación marginal en las combinaciones evaluadas; ese resultado no prueba que E1 sea inútil en cualquier configuración. Las ablaciones individuales de ambos quedaron indeterminadas.

En los 27 casos del tramo de voto, responder siempre «sí» habría acertado 18, frente a 15 del voto. El intervalo de la diferencia cruza cero. Es una señal para investigar ese tramo, no evidencia suficiente para sustituirlo por una constante.

Fuentes: [cascada](results/S_cascade.json), [factorial y Shapley](results/S_factorial.json) y [tabla maestra](results/tabla_maestra.json).

### 3.2. Expertos y papeles más importantes o prescindibles

| Componente | Evidencia | Interpretación y recomendación |
|---|---|---|
| **E4 / EXPERT-TRACE** | Su ablación representativa pierde 0,0634 de ranking; IC95 [0,0559; 0,0708] | **Conservar.** Sostiene pesos y plan documental; su valor principal está en el formulario |
| **REGISTRAR y acceso al plan** | Retirarlo pierde 0,0782 de ranking; IC95 [0,0312; 0,1285] | **Conservar la función de acceso.** La evidencia no atribuye toda esa importancia a su prosa ni demuestra que deba ser generativo |
| **MODERATOR y filtros G6** | Sin moderador cambian plan/pesos en 34 casos y empeora el componente de herramientas | **Conservar la función actual** hasta validar una sustitución que preserve el formulario |
| **VERIFIER / N14** | Cero reaperturas; D/F idénticos; ΔN = −0,00045, IC95 [−0,01126; 0,01036] | **Mejor candidato a retirada en T1.** No mostró aportación adicional en estos casos |
| **EXPERT-IMAGE / N09** | Cero activaciones en 91 casos | **Ruta inactiva en esta ejecución.** Se puede simplificar en este contexto; no se evaluó su utilidad cuando hay imágenes o se activa la ruta |
| **E2 / EXPERT-PSA** | Cero diferencias en D/F con `form_weights=trace`; N no medida | **Redundante para D/F en esta configuración.** Medir narrativa antes de retirarlo por completo |
| **EXPERT-EXPERIENCE / biblioteca kNN** | Cero diferencias en D/F al retirarla; N no medida | **Sin aportación D/F observada.** La hipótesis de que sostenía el formulario fue refutada; falta evaluar N |
| **EXPERT-EAU / RAG** | D/F idénticos; ΔN = −0,0297, IC95 [−0,0676; 0,0081] | **Indeterminado.** La mejora puntual no demuestra equivalencia ni permite declarar inútil la recuperación de guías |
| **CHAIR / presidente** | D/F idénticos sin él; pérdida N = 0,0257, IC95 [−0,0162; 0,0689] | **Mantener por ahora.** El intervalo permite una pérdida superior al margen |

La relevancia de E4 y del acceso documental ilustra por qué «no cambia la decisión» es un criterio insuficiente para eliminar un componente. También debe distinguirse retirar una función de sustituir su implementación por código.

### 3.3. Las guardias aportan algo que la media puede ocultar

Sin G1/G2 aparecieron **tres notas con grados sin fuente**, frente a cero violaciones en el control. Pese a ello, la media narrativa se mantuvo dentro del margen y la clasificación automática marcó ambas guardias como `SOBRA`. Como se retiraron juntas, el experimento tampoco separa completamente sus aportaciones individuales.

Sin G3 aparecieron **dos notas con lenguaje de proceso** y una pérdida narrativa de **0,0441**, IC95 [0,0288; 0,0604]. G3 resultó necesaria para N conforme a la regla del estudio.

La recomendación es **mantener G1/G2/G3 y las comprobaciones de respaldo documental**. `A_min/L9`, que retiró imagen, verificador y G1/G2, conservó D/F, pero no recibió evaluación narrativa conjunta en tres pasadas. Por ello, la candidata conservadora es retirar el verificador y estudiar la simplificación de imagen, conservando las guardias. Esa combinación conservadora todavía necesita una corrida conjunta propia.

Fuentes: [efectos estructurados](results/L_efectos.json), [efectos narrativos](results/J_efectos.json), [auditoría](results/N_audit.json) y [ablación conjunta](results/A_min.json).

## 4. Resultados de T2: conservar el cálculo y una llamada del presidente

La referencia obtuvo **65/72 aciertos, 90,28 %**, y ranking **0,7784**. `T2-Lmin` y `T2-Ldet` conservaron exactamente decisión y formulario en los 72 casos.

| Variante | Llamadas LLM | Narrativa media | Resultado |
|---|---:|---:|---|
| Junta completa, `T2-L0` | 539 | 0,8256 | Referencia |
| Flujo reducido con presidente, `T2-Lmin` | 72 | 0,8451 | D/F idénticos y narrativa dentro del margen de equivalencia |
| Flujo sin generación, `T2-Ldet` | 0 | 0,7385 | D/F idénticos, con pérdida narrativa relevante |

`T2-Lmin` prescinde de EAU como papel generativo y ejecuta las funciones de moderación, registro y verificación mediante código. Mantiene los expertos y el presidente para la nota. La diferencia N fue **−0,0195**, IC95 [−0,0328; −0,0062], dentro del margen de 0,03487.

Al eliminar también al presidente, la pérdida N fue **0,0872**, IC95 [0,0595; 0,1159]. **El presidente es el papel LLM con aportación más clara en T2**, para la calidad de la explicación. El cálculo de la decisión ya estaba resuelto antes de redactarla.

### 4.1. Por qué no se pudieron eliminar sin más los expertos replicados

| Experto | Función en el protocolo | Evidencia e implicación |
|---|---|---|
| **E1 / GRADE** | Referencia inicial de decisión | Fue portavoz en 68/72 casos; alta centralidad operativa |
| **E5 / CASCADE** | Respaldo y cascada alternativa | Fue portavoz en un caso y participa en la condición que habilita aptitud |
| **E3 / FITNESS** | Resuelve casos cuando se cumple la condición de aptitud | Fue portavoz en tres casos; retirarlo reduce los aciertos de 65 a 62 |
| **E2 / PATHOLOGY y E4 / FUSION** | Réplicas de E1 cuyos estados participan en el quorum | No añaden votos independientes, pero retirar cualquiera impide activar la rama de aptitud en tres casos |

Entre las 32 combinaciones, **solo el conjunto completo conservó todas las decisiones del control**. Retirar individualmente E2, E3, E4 o E5 cambió tres decisiones y bajó el ranking de 0,7784 a 0,7431. La pérdida fue 0,0353, IC95 [0,0000; 0,0812]: hay un cambio empírico claro, aunque ese intervalo no acredita por sí solo necesidad estadística concluyente.

La explicación está en el protocolo: la rama de aptitud exige que ciertos expertos estén disponibles y compartan el estado `discuss`. Borrar una réplica modifica esa condición. **Redundancia de información no implica redundancia de control de flujo.**

Existe una excepción importante a cualquier afirmación de que «todos mejoran la exactitud»: retirar E1 también cambia tres decisiones, pero aumenta los aciertos a **66/72**, usando E5 como portavoz en los 72 casos. Su efecto de ranking tiene un intervalo que cruza cero. Es una hipótesis para un estudio nuevo; conservar los cinco expertos aquí responde al objetivo de **paridad con V4**, no a una demostración de optimalidad.

La candidata recomendada es, por tanto, **cinco expertos y protocolo actual + registro y controles deterministas + presidente**. La reducción de EAU/moderador/registrador/verificador se evaluó conjuntamente; el resultado respalda esa sustitución como conjunto, sin aislar el efecto narrativo individual de cada papel.

Fuentes: [factorial T2](T2_T3/results/T2_cpu.json), [protocolo de decisión](../version_final_reto_send_v4/task_2/agent/protocol.py), [D/F y coste](T2_T3/results/D_F_effects.json) y [narrativa](T2_T3/results/J_effects.json).

## 5. Resultados de T3: predicción conservada y explicación determinista

Los tres brazos conservaron exactamente los **75 pares de evento y meses**. El c-index fue **0,8235**, y la exactitud de evento, **58/75, 77,33 %**.

| Variante | Llamadas LLM | Narrativa media | Interpretación |
|---|---:|---:|---|
| Conferencia completa, `T3-L0` | 86 | 0,5404 | Referencia |
| Flujo compacto con presidente, `T3-Lmin` | 83 | 0,4969 | Ahorro escaso de llamadas; equivalencia narrativa indeterminada |
| Flujo determinista, `T3-Ldet` | 0 | 0,6200 | Misma predicción y mejor narrativa según el juez empleado |

En `T3-Ldet`, ΔN fue **−0,0796**, IC95 [−0,1311; −0,0284]. Ese resultado indica una mejora observada de la nota determinista. El intervalo no está dentro de la banda simétrica de equivalencia, porque la comparación favorece a la variante más allá de esa banda; no debe describirse simplemente como equivalencia narrativa.

### 5.1. Qué debe mantenerse y qué puede colapsarse

| Componente | Evidencia | Recomendación |
|---|---|---|
| **Motor seleccionado ASGDE** | c-index 0,8235 frente a 0,7372 de CAPRA | Conservar como referencia de mejor rendimiento puntual; la diferencia de 0,0863 tiene IC95 [−0,0062; 0,2075], sin superioridad concluyente |
| **EXPERT-HORIZON / mapa temporal** | Al sustituir el tiempo por una constante, el c-index cae a 0,5000 | Conservar la información que ordena el riesgo y su transformación temporal |
| **CAPRA y política de evento** | Intervienen en la producción del evento y el horizonte | Conservar el cálculo usado por la candidata |
| **Turnos SURGICAL, DIGITAL y FUSION** | Sus intervenciones asesoras no alimentan la salida numérica final de esta configuración | Colapsar los turnos explicativos; mantener las modalidades y cálculos que alimentan el motor |
| **Moderación, registro y verificación discursivos** | El flujo compacto conserva las salidas estructuradas | Mantener las funciones necesarias mediante digest y controles deterministas |
| **CHAIR / presidente** | Eliminarlo conserva predicción y mejora la N medida | Prescindible en la configuración evaluada; `T3-Ldet` es la candidata preferida |

La conferencia T3 de referencia **ya era determinista salvo el presidente**. Por ello, colapsar varios turnos no representa retirar varios LLM predictivos. Tampoco significa que puedan eliminarse los datos quirúrgicos, digitales o de imagen utilizados por ASGDE.

El experimento con tiempo constante destruye la ordenación temporal; no demuestra que el mapa vigente sea la única calibración posible. También se observó que forzar evento cero conserva el c-index, aunque cambia la exactitud de evento. Hay que seguir por separado **discriminación, clasificación del evento y precisión temporal**. El error absoluto medio del tiempo en los casos con evento fue **27,53 meses** en los tres brazos: preservar la arquitectura numérica conserva también sus limitaciones.

Fuentes: [ablaciones numéricas T3](T2_T3/results/T3_cpu.json), [predicción y coste](T2_T3/results/D_F_effects.json), [narrativa](T2_T3/results/J_effects.json) y [ejecutor T3](T2_T3/harness/run_t3_arm.py).

## 6. Respuesta directa: qué es irrelevante y qué es más importante

**No hay evidencia para declarar un experto o un modelo «completamente irrelevante» fuera del ámbito evaluado.** Dentro de ese ámbito, la clasificación práctica es la siguiente:

| Categoría | Componentes | Por qué |
|---|---|---|
| **Retirada mejor respaldada** | Verificador T1; presidente T3 en `T3-Ldet` | Se conserva la salida estructurada, con narrativa equivalente en T1 y mejor puntuación narrativa en T3 |
| **Implementación generativa sustituible** | EAU/moderador/registrador/verificador T2, como conjunto | `T2-Lmin` preserva D/F y N con una llamada del presidente por caso observado |
| **Sin intervención efectiva observada** | Ruta EXPERT-IMAGE de T1 | Nunca se activó; su valor en una ruta activa no se midió |
| **Redundantes solo para D/F** | E2/PSA y biblioteca kNN de T1 | Cero diferencias estructuradas; falta medir narrativa |
| **Turnos explicativos colapsables** | Asesores SURGICAL/DIGITAL/FUSION de T3 | No determinan evento/meses; se conserva el motor que integra sus fuentes |
| **Contribución importante al formulario e integridad** | E4/TRACE, acceso documental, moderador/filtros y guardias de T1 | Sus retiradas deterioran campos o permiten defectos en la nota |
| **Contribución importante a la explicación** | Presidente T2 y G3 de T1 | Su retirada produce pérdidas narrativas relevantes |
| **Núcleo que debe preservarse en la candidata** | Cascada T1; protocolo y quorum T2; motor, CAPRA y horizonte T3 | Producen las salidas numéricas o controlan qué experto las produce |
| **Evidencia insuficiente para retirar** | E1/E3, EAU y presidente T1; expertos T2 bajo un quorum nuevo | Hay incertidumbre o el rediseño todavía no se ha evaluado |

La importancia depende de la función. En T1 destacan la cascada para decidir y E4/documentos para completar el formulario; en T2, el protocolo de expertos y el presidente para explicar; en T3, el motor y el horizonte. Tener muchos turnos en una conversación no acredita una aportación predictiva adicional.

## 7. Coste de inferencia: qué se ahorró

| Comparación | Llamadas | Tokens de entrada | Tiempo por caso |
|---|---|---|---|
| T1 completa → sin verificador | Una llamada menos por caso | Sin ahorro fiable cuantificado en la síntesis | Ahorro observado de **5,77 s/caso** |
| T2 completa → `T2-Lmin` | **539 → 72; −86,6 %** | **1.708.214 → 93.991; −94,5 %** | **41,43 → 1,53 s; −96,3 %** |
| T3 completa → `T3-Ldet` | **86 → 0; −100 %** | La variante no realiza generación LLM | **1,516 → aproximadamente 0,001 s** |

Los 72 casos T2 suman 2.983,3 segundos en la telemetría del control y 110,3 en la variante reducida. En T3, los 75 casos suman 113,72 segundos en el control y aproximadamente 0,073 en la variante determinista. Son tiempos de los segmentos registrados, separados de carga de modelos, desarrollo y evaluación con el juez.

**El alcance de estos ahorros es limitado por la forma de ejecución.** T2 reutilizó un control histórico de `result_v2/task_2/labeled`, y la variante reducida consulta expertos en caché y documentos locales. T3 utiliza predicciones OOF almacenadas; el tiempo de aproximadamente un milisegundo no incluye recalcular el modelo para un paciente nuevo. Los resultados demuestran reducción de la orquestación medida, pero todavía no cuantifican el ahorro completo de un despliegue comparable de extremo a extremo.

Las llamadas del juez del estudio no están incluidas en esas tablas de inferencia. Tampoco se midieron de forma suficiente euros, energía o capacidad de servicio, por lo que no se deducen ahorros monetarios.

Fuentes: [tabla maestra T1](results/tabla_maestra.json), [costes T2/T3](T2_T3/results/D_F_effects.json), [procedencia del control T2](T2_T3/runs/T2-L0/arm.json) y [ejecutor reducido T2](T2_T3/harness/run_t2_minimal.py).

## 8. Cuánto tiempo tomó el estudio

**El periodo documentado hasta la entrega del informe ejecutivo anterior fue de 43 horas y 17 minutos**, distribuido entre el 21 y el 23 de septiembre de 2026. Es tiempo de calendario: incluye pausas entre solicitudes, preparación, generación, evaluación, incidencias y revisión. No equivale a 43 horas de dedicación humana ni de uso continuo de GPU.

La cronología siguiente se reconstruyó con las marcas de la sesión y los estados de cierre. **Todas las horas de esta tabla están convertidas a Europe/Madrid, UTC+2 en esas fechas.**

| Hito | Fecha y hora local | Fuente |
|---|---|---|
| Solicitud inicial de ejecutar T1 | 21/09, 11:34:14 | Mensaje del usuario en la sesión |
| Inicio registrado de `L0` T1 | 22/09, 14:23:29 | `runs/L0/arm.json` |
| Final del último brazo principal, `L0p` | 22/09, 21:37:53 | `logs/f5-resume.log` |
| Cierre automático T1, incluidas síntesis y pruebas | 23/09, 02:11:58 | `results/guardian_status.json` |
| Solicitud de extensión a T2/T3 | 23/09, 02:19:40 | Mensaje del usuario en la sesión |
| Cierre automático T2/T3 | 23/09, 06:22:10 | `T2_T3/results/guardian_status.json` |
| Entrega del resultado T2/T3 tras revisión | 23/09, 06:42:35 | Mensaje final en la sesión |
| Entrega del informe ejecutivo de las tres tareas | 23/09, 06:51:31 | Mensaje final en la sesión |

De esas marcas se obtienen estos intervalos:

- **T1, desde solicitud hasta cierre:** aproximadamente **38 h 38 min**.
- **Ventana de los nueve brazos principales T1:** aproximadamente **7 h 14 min**, incluidas interrupciones y reanudación. No es una medición de utilización efectiva de GPU.
- **Corrida conjunta `L9`:** aproximadamente **29 min**, desde su manifiesto de inicio hasta el final registrado en el log del guardián.
- **Extensión T2/T3, desde solicitud hasta cierre automático:** **4 h 2 min 30 s**; hasta el mensaje de entrega revisado, aproximadamente **4 h 23 min**.
- **Proceso completo, desde solicitud inicial hasta informe ejecutivo:** **43 h 17 min 17 s**.

Estos intervalos se solapan y **no deben sumarse**. Los tiempos del plan, como «45 minutos por brazo» o «4 horas de juez», eran previsiones; esta memoria utiliza marcas registradas para describir el tiempo transcurrido. No existe aquí una contabilidad completa y homogénea de horas-persona o GPU-hora.

### 8.1. Incidencias y trabajo operativo realizado

Durante T1 se corrigió el lanzador para rechazar argumentos accidentales antes de reservar GPU. Un caso de `L5` agotó su tiempo de espera tras aproximadamente 914 segundos; se reanudó conservando los 90 casos válidos y completando el faltante. Se utilizó `tmux` para mantener los procesos y un guardián para encadenar evaluación, síntesis, ablación conjunta y cierre.

También se corrigió el recuento previsto del juez T1: nueve brazos por tres pasadas son **27**, no 24. En la extensión T3 se restauró en el resumen compacto la información explícita sobre muestreo ganglionar, evitando una omisión que generaba contradicciones narrativas y reintentos. Esa corrección forma parte de la variante final; las conclusiones se apoyan en los resultados finales, no en la versión preliminar archivada.

Los avisos de datos clínicos ausentes en `ground_truth` se revisaron en la sesión: el evaluador adaptado incorporaba el contexto desde `agent_input`. El aviso no significaba por sí solo que el juez recibiera la nota sin contexto. Los artefactos finales validaron los recuentos esperados de casos juzgados.

Fuentes: [sesión de trabajo](codex://threads/01a0c350-d30f-71d3-8fad-711ed0847c24), [bitácora](BITACORA_ABLACION.md), [estado T1](results/guardian_status.json), [estado T2/T3](T2_T3/results/guardian_status.json), [log de reanudación T1](logs/f5-resume.log) y [log del guardián T1](logs/guardian.log). Los logs son evidencia local y pueden no estar disponibles en otro checkout.

## 9. Qué queda demostrado y qué sigue abierto

El trabajo deja una infraestructura reproducible de ablación, resultados por caso, comparaciones estadísticas, auditorías y tres propuestas concretas de arquitectura. También muestra que una simplificación puede mantener la predicción y mejorar el coste sin preservar necesariamente todos los aspectos de la salida.

Hay cinco límites principales para interpretar la evidencia:

1. **Evaluación interna.** T1/T3 usan OOF, pero sus cohortes influyeron en decisiones de desarrollo; T2 utiliza casos conocidos durante el desarrollo de los expertos. No se ha medido generalización independiente. En T1, la diferencia entre ranking `deployed` 0,8390 y `honest` 0,7607 muestra la importancia de distinguir estas condiciones.
2. **Muestras pequeñas e incertidumbre.** Varios cambios afectan a pocos casos. Un resultado indeterminado debe seguir abierto, y un intervalo [0; 0] sobre salidas idénticas no garantiza invariancia universal.
3. **Narrativa medida por un juez automático.** Tres pasadas permiten observar variación, pero no sustituyen una revisión humana. Las guardias T1 muestran que una media equivalente puede coexistir con errores concretos de integridad.
4. **Intervenciones conjuntas y sustituciones.** Retirar varios componentes a la vez no identifica necesariamente su efecto individual. La reducción T2 conserva funciones mediante código; eliminar esas funciones sería otro experimento.
5. **Comparabilidad operativa limitada.** Cachés, control histórico y predicciones almacenadas impiden atribuir toda la diferencia de tiempo exclusivamente a retirar papeles LLM.

Conservar resultados tampoco corrige los errores del control: permanecen 17 decisiones incorrectas en T1, 7 en T2 y 17 eventos incorrectos en T3. La siguiente etapa debe abordar tanto eficiencia como calidad predictiva.

## 10. Recomendaciones y trabajo futuro

### 10.1. Prioridades de implementación y validación

| Prioridad | Trabajo | Por qué | Criterio de finalización propuesto |
|---|---|---|---|
| **1** | Validar `T2-Lmin` y `T3-Ldet` con casos independientes y ejecuciones comparables | Son las candidatas con reducción operativa más clara | Márgenes de calidad fijados antes de medir, integridad revisada y coste de extremo a extremo registrado |
| **2** | Ejecutar la candidata conservadora T1: sin verificador, guardias intactas y simplificación de imagen evaluada por separado y conjuntamente | Evita adoptar `L9` como si tuviera validación narrativa completa | Paridad D/F, evaluación N repetida y auditoría; incluir casos que activen la ruta de imagen |
| **3** | Revisar notas con especialistas humanos y un juez adicional | Comprueba si la preferencia automática corresponde a utilidad y fidelidad del contenido | Revisión ciega por caso, afirmaciones verificables y desacuerdos documentados; incluir casos con decisión incorrecta |
| **4** | Probar datos faltantes, fallos de herramientas, reintentos y tiempos límite | La equivalencia de la muestra puede depender de que todas las fuentes estén disponibles | Contratos válidos, comportamiento de respaldo definido y fallos visibles |
| **5** | Integrar las candidatas que superen los criterios con configuración reversible y telemetría | Permite comparar el comportamiento real y volver a la referencia | Regresiones controladas, trazabilidad de versiones y seguimiento de calidad, latencia y consumo |

Estas prioridades son propuestas derivadas del estudio; no indican que ya se haya realizado esa validación o adoptado las reducciones en V4.

### 10.2. Preguntas de investigación abiertas por los resultados

**T1: mejorar el tramo de voto y cerrar las ablaciones incompletas.** Comparar E3 solo, E1/E3 y alternativas sencillas con validación anidada o externa, concentrándose en los casos que no resuelven cohorte y grado. Medir la narrativa al retirar PSA y biblioteca. Diseñar una sustitución determinista del registrador que mantenga exactamente el acceso documental y comprobar su efecto completo. El estudio actual no permite trasladar automáticamente a T1 la reducción de orquestación lograda en T2.

**T2: desacoplar el quorum de la presencia de réplicas.** Sustituir la dependencia de «cuatro objetos disponibles en `discuss`» por una condición explícita de incertidumbre podría permitir eliminar representaciones duplicadas. Habría que comparar el protocolo actual con el nuevo y medir decisiones, confianza, formulario y notas. La mejora puntual al retirar E1 justifica estudiar E5 como referencia alternativa, sin asumir que un acierto adicional en esta muestra se reproducirá fuera de ella.

**T3: evaluar calibración temporal y dependencia de las modalidades.** Comparar ASGDE y CAPRA con más casos independientes, analizar el error temporal y la calibración, y mantener métricas de evento separadas del c-index. Si se quiere reducir el modelo predictivo, hace falta una ablación de sus entradas y entrenamiento correspondiente: colapsar turnos asesores no contesta qué modalidades son necesarias.

**Evaluación de LLM: separar modelo, prompt y función.** Repetir las comparaciones generativas con otros modelos y un juez independiente permitiría comprobar si las conclusiones dependen del modelo elegido, del resumen proporcionado o de la plantilla. Registrar carga, extracción de datos, inferencia de expertos, herramientas, generación y evaluación por separado permitiría calcular coste real, además de llamadas y tokens.

El siguiente resultado esperado es una comparación prospectiva y reproducible de las tres candidatas frente a sus controles, con criterios de aceptación definidos y datos nuevos. Esa evidencia permitiría decidir qué simplificaciones integrar y qué componentes seguir investigando.

## 11. Material de respaldo para presentar el trabajo

| Material | Utilidad |
|---|---|
| [Informe ejecutivo final](reports/INFORME_EJECUTIVO_FINAL_T1_T2_T3.md) | Síntesis de decisiones y límites |
| [Informe técnico T1](reports/INFORME_ABLACION_T1.md) | Intervenciones, hipótesis y veredictos detallados |
| [Informe técnico T2/T3](T2_T3/reports/INFORME_ABLACION_T2_T3.md) | Arquitecturas y resultados de la extensión |
| [Tabla maestra T1](results/tabla_maestra.csv) | Consulta y reutilización de efectos por intervención |
| [Efectos estructurados y coste T2/T3](T2_T3/results/D_F_effects.json) | Evidencia numérica de identidad y ahorro |
| [Efectos narrativos T2/T3](T2_T3/results/J_effects.json) | Medias, intervalos y márgenes de N |
| [Escalera de construcción T1](reports/figuras/escalera_construccion.png) | Presentar cómo cambia el rendimiento al construir la arquitectura |
| [Atribución Shapley T1](reports/figuras/shapley_decision.png) | Ilustrar la aportación relativa de los mecanismos estudiados |
| [Coste frente a efecto T1](reports/figuras/coste_efecto.png) | Relacionar ahorro y cambio de rendimiento |

Para una exposición oral, el orden sugerido es: pregunta de investigación → diseño de comparación → resultados por tarea → componentes prescindibles y necesarios → coste y duración → límites → validación e investigación futuras.
