# Informe ejecutivo final: ablacion de T1, T2 y T3

**Fecha de corte:** 23 de septiembre de 2026.

**Estado:** estudios cerrados; arquitecturas reducidas evaluadas como candidatas, sin adopcion en V4.

## 1. Conclusion ejecutiva

**La arquitectura puede reducirse, pero la reduccion adecuada depende de la tarea.**
El estudio distingue el calculo de la decision, la fidelidad de los campos de salida,
la calidad de la explicacion y el coste de ejecucion. Conservar la decision no basta
para justificar la eliminacion de un componente.

| Tarea | Hallazgo principal | Recomendacion ejecutiva |
|---|---|---|
| **T1: decision de biopsia** | Retirar el verificador mantiene decision/formulario y narrativa equivalente; otros componentes sostienen el formulario o la integridad de la nota. | Priorizar la variante sin verificador. Considerar desactivar el experto de imagen no activado, conservando las guardias de integridad. |
| **T2: decision de tratamiento** | El brazo reducido conserva las salidas estructuradas y pasa de 539 a 72 llamadas LLM en 72 casos. La nota completamente determinista pierde calidad. | Priorizar `T2-Lmin`: expertos y reglas existentes, controles deterministas y una llamada del presidente por caso observado. |
| **T3: pronostico de recurrencia** | El brazo sin LLM conserva todos los pares evento/meses y mejora la puntuacion narrativa del juez. | Priorizar `T3-Ldet`: motor seleccionado, politica de evento, horizonte y nota determinista. |

Estas recomendaciones son **candidatas para validacion posterior**, no una demostracion
de equivalencia en pacientes nuevos ni una autorizacion de uso clinico. El estudio
identifica simplificaciones compatibles con los casos medidos; no demuestra una
arquitectura minima universal.

## 2. Alcance y resultados comparables

Se evaluaron **91 casos T1, 72 T2 y 75 T3**: 238 registros caso-tarea, no necesariamente
238 pacientes distintos. La evaluacion narrativa cerro 27/27 ejecuciones en T1 y
18/18 en T2/T3, con tres pasadas por brazo incluido. Hubo bootstrap pareado de
10.000 remuestreos para los efectos reportados.

En este informe, **D/F** significa decision y campos estructurados; **N**, puntuacion
narrativa del juez. Los deltas e intervalos se expresan como **control menos variante**:
positivo indica perdida al simplificar, negativo indica mejora observada.

| Tarea y comparacion | Casos | Rendimiento estructurado del control | Conservacion por la variante | N: control -> variante |
|---|---:|---|---|---:|
| T1: `L0` -> `L3`, sin verificador | 91 | 74/91 aciertos (81.32%); ranking 0.7607 | D/F identicos | 0.7959 -> 0.7964 |
| T2: `T2-L0` -> `T2-Lmin` | 72 | 65/72 aciertos (90.28%); ranking 0.7784 | D/F identicos | 0.8256 -> 0.8451 |
| T3: `T3-L0` -> `T3-Ldet` | 75 | c-index 0.8235; evento correcto 58/75 (77.33%) | 75/75 pares evento/meses identicos | 0.5404 -> 0.6200 |

Los rankings de T1/T2 son los agregados **sin juez narrativo**; el ranking T3 es el
c-index. No son metricas intercambiables ni deben promediarse entre tareas. N se
evalua en los 74 aciertos T1, los 65 aciertos T2 y los 75 casos T3: sus medias tampoco
constituyen una comparacion directa de calidad entre tareas.

Fuentes: [efectos T1](../results/L_efectos.json), [narrativa T1](../results/J_efectos.json),
[D/F y coste T2/T3](../T2_T3/results/D_F_effects.json),
[narrativa T2/T3](../T2_T3/results/J_effects.json).

## 3. Hallazgos por tarea

### T1: reducir selectivamente, preservando formulario e integridad

- **El verificador es el candidato mejor respaldado para retirada.** No hubo reaperturas ni cambios D/F. La diferencia N fue -0.00045, IC95 [-0.01126, 0.01036], dentro del margen de equivalencia de 0.03. Su retirada ahorro una llamada y 5.77 segundos por caso en la comparacion medida.
- **El experto de imagen no se activo en ninguno de los 91 casos.** Puede simplificarse esa ruta en la configuracion observada, pero el resultado no demuestra que las imagenes carezcan de valor en otras poblaciones o rutas de ejecucion.
- **El formulario tiene dependencias reales aunque la decision no cambie.** Retirar EXPERT-TRACE/E4 produjo una perdida de ranking de 0.0634, IC95 [0.0559, 0.0708]; retirar REGISTRAR, de 0.0782, IC95 [0.0312, 0.1285]. Sin moderador cambiaron el plan/pesos de 34 casos y empeoro el componente de herramientas. Estos componentes no son prescindibles por el mero hecho de que la decision sea estable.
- **Las guardias no deben juzgarse solo por la media del juez.** Sin G1/G2 aparecieron tres notas con grados sin fuente, frente a cero violaciones en el control. Sin G3 aparecieron dos notas con lenguaje de proceso y una perdida N de 0.0441, IC95 [0.0288, 0.0604]. Se recomienda mantener estas protecciones.
- **No hay evidencia suficiente para retirar el presidente.** La perdida N estimada fue 0.0257, pero su IC95 [-0.0162, 0.0689] excede el margen de equivalencia. Que la estimacion puntual sea pequena no demuestra equivalencia.

**Precaucion con la ablacion conjunta:** `L9/A_min` retiro N09, N14, G1 y G2, y fue
aceptado por conservar D/F y ranking. Sin embargo, no figura entre los brazos con
tres pasadas narrativas. Su aceptacion no acredita la integridad narrativa conjunta.
La recomendacion ejecutiva es mas conservadora: mantener G1/G2 y G3, priorizar la
retirada del verificador y comprobar conjuntamente cualquier simplificacion adicional.
La combinacion conservadora propuesta no tiene una evaluacion conjunta propia.

Fuentes: [tabla maestra](../results/tabla_maestra.json), [auditoria narrativa](../results/N_audit.json),
[A_min](../results/A_min.json), [brazos juzgados](../results/J_session_validation.json).

### T2: una llamada generativa aporta mejor equilibrio que cero

- **`T2-Lmin` conserva exactamente D/F en 72/72 casos.** Prescinde del papel generativo EAU y sustituye moderador, registrador y verificador por codigo determinista. Mantiene el protocolo de cinco expertos y la redaccion del presidente.
- **La narrativa se conserva dentro del margen predefinido.** N pasa de 0.8256 a 0.8451; delta -0.0195, IC95 [-0.0328, -0.0062], dentro del margen de 0.0349. La pequena mejora medida no exige asumir una mejora clinica.
- **Eliminar tambien el presidente tiene un coste narrativo claro.** `T2-Ldet` mantiene D/F, pero N cae a 0.7385: perdida de 0.0872, IC95 [0.0595, 0.1159], superior al margen. No es la opcion recomendada cuando la explicacion importa.
- **Un experto puede influir sin emitir el voto final.** Las 32 combinaciones CPU muestran que retirar individualmente E2, E3, E4 o E5 altera tres decisiones por dependencias del quorum de aptitud. Los aciertos bajan de 65 a 62; la perdida de ranking es 0.0353, IC95 [0.0000, 0.0812]. Solo el conjunto completo conserva todas las decisiones.

Conservar los cinco expertos es una recomendacion de **paridad con el control**, no
prueba de que todos sean indispensables para maximizar exactitud: retirar E1 cambia
tres decisiones y eleva los aciertos a 66, pero el intervalo de efecto en ranking
cruza cero. Redisenar expertos o quorum seria un experimento nuevo.

**Limite operativo importante:** el control T2 se importo de una corrida historica;
el brazo reducido consulta resultados de expertos en cache y lee documentos locales.
Lo demostrado es la reduccion de la orquestacion sobre esos artefactos, no la
inferencia completa para pacientes nuevos. Los tiempos no aislan exclusivamente
el efecto causal de retirar papeles LLM.

Fuentes: [factorial T2](../T2_T3/results/T2_cpu.json),
[efectos D/F](../T2_T3/results/D_F_effects.json), [efectos N](../T2_T3/results/J_effects.json),
[procedencia del control](../T2_T3/harness/run_t2_arm.py),
[ejecutor reducido](../T2_T3/harness/run_t2_minimal.py).

### T3: separar prediccion numerica de redaccion permite eliminar el LLM

- **`T3-Ldet` conserva toda la prediccion evaluada.** Los 75 pares evento/meses son identicos al control, con c-index 0.8235 y la misma exactitud de evento. Mantiene el motor seleccionado ASGDE, CAPRA para la politica de evento y el mapa de horizonte.
- **La nota determinista supera al presidente segun este juez.** N sube de 0.5404 a 0.6200; delta -0.0796, IC95 [-0.1311, -0.0284]. Es una mejora observada, no equivalencia dentro de una banda simetrica ni superioridad clinica demostrada.
- **Retener al presidente en el flujo reducido no ofrece una ventaja acreditada.** `T3-Lmin` baja solo de 86 a 83 llamadas y su perdida N de 0.0436 tiene IC95 [-0.0089, 0.0951]. La equivalencia narrativa queda indeterminada.
- **El horizonte temporal sigue siendo esencial para ordenar riesgo.** Sustituirlo por un valor constante lleva el c-index a 0.5000. CAPRA solo obtiene 0.7372 frente a 0.8235 del seleccionado, pero el IC95 de la diferencia [-0.0062, 0.2075] cruza cero: no demuestra superioridad concluyente del motor seleccionado.

La conferencia T3 de referencia **ya era determinista salvo el presidente**. Reducir
turnos asesores no equivale a eliminar varios agentes LLM predictivos ni justifica
suprimir las modalidades que alimentan ASGDE. Ademas, el c-index no basta: forzar
evento cero conserva ese ranking y cambia la exactitud de evento. Deben seguirse
por separado discriminacion, evento y error temporal.

Fuentes: [ablaciones CPU T3](../T2_T3/results/T3_cpu.json),
[efectos D/F](../T2_T3/results/D_F_effects.json), [efectos N](../T2_T3/results/J_effects.json),
[ejecutor T3](../T2_T3/harness/run_t3_arm.py).

## 4. Impacto operativo medido

| Candidata | Llamadas LLM | Tokens de entrada | Tiempo por caso | Lectura correcta |
|---|---:|---:|---:|---|
| T1 sin verificador (`L3`) | -1 por caso | Sin ahorro fiable cuantificado | -5.77 s respecto al control | Ahorro local del componente retirado. |
| T2 reducida (`T2-Lmin`) | 539 -> 72; **-86.6%** | 1,708,214 -> 93,991; **-94.5%** | 41.43 -> 1.53 s; **-96.3%** | Comparacion con control historico y expertos reutilizados; no promesa de latencia productiva. |
| T3 determinista (`T3-Ldet`) | 86 -> 0; **-100%** | Sin consumo LLM en la variante | 1.516 -> aproximadamente 0.001 s | Reproduccion con predicciones OOF almacenadas; no incluye recalcular el modelo para un caso nuevo. |

Las llamadas y tokens corresponden a los brazos de inferencia, no al coste adicional
del juez del estudio. No se estiman ahorros monetarios, energia o capacidad de servicio:
faltan mediciones homogeneas de extremo a extremo. Tampoco se suman estos tiempos
como si fueran un unico flujo ejecutado bajo condiciones identicas.

## 5. Solidez de la evidencia y limites

1. **T1 y T3 son evaluaciones internas OOF, no validacion externa.** En T1 tambien se eligieron reglas e hiperparametros sobre la cohorte; su ranking `deployed` de 0.8390 frente a 0.7607 `honest` ilustra el optimismo de evaluar sobre datos usados en desarrollo. T3 tambien tiene seleccion informada por su cohorte.
2. **T2 es una evaluacion sobre datos usados para desarrollar los expertos.** Sus 90.28% de aciertos describen estos 72 casos y no deben extrapolarse a nuevos pacientes.
3. **Identidad empirica no significa equivalencia universal.** Cero cambios y un intervalo [0, 0] sobre una muestra no garantizan invariancia fuera de ella. Las ablaciones individuales tampoco descartan interacciones al combinar retiradas.
4. **El juez narrativo es una medida automatica condicionada al contexto disponible.** Tres pasadas y bootstrap mejoran la estimacion interna, pero no sustituyen auditoria humana de afirmaciones, completitud y relevancia. T1 demuestra que una media equivalente puede ocultar errores de integridad.
5. **Reproducir artefactos no valida el despliegue.** Cache, control historico T2 y predicciones OOF T3 limitan las conclusiones sobre coste real y comportamiento ante datos faltantes, fallos o cambios de distribucion.

## 6. Decision y trabajo posterior

**El plan experimental esta cerrado; la adopcion de las reducciones no.** Ambos
[cierres T1](../results/cierre.json) y [T2/T3](../T2_T3/results/cierre.json) registran
estudio completo y V4 intacta. Este informe consolida e interpreta los resultados;
no introduce nuevas corridas ni cambios en la arquitectura de produccion.

| Prioridad | Trabajo recomendado | Criterio de salida |
|---|---|---|
| 1 | Validar `T2-Lmin` y `T3-Ldet` en casos independientes, recalculando los modelos necesarios y ejecutando control y variante bajo las mismas condiciones. | Calidad, integridad y latencia de extremo a extremo aceptables con margenes fijados antes de medir. |
| 2 | Evaluar conjuntamente la reduccion conservadora T1: sin verificador y con ruta de imagen simplificada, manteniendo G1/G2/G3. | Paridad D/F, equivalencia narrativa y auditoria de afirmaciones; incluir casos que puedan activar la ruta de imagen. |
| 3 | Revisar las notas T2/T3 con evaluacion humana y comprobar datos ausentes, reintentos y respuestas de respaldo. | Sin degradacion relevante de contenido ni aumento de afirmaciones sin respaldo. |
| 4 | Tras superar esas validaciones, integrar variantes con opcion de reversibilidad y telemetria. | Pruebas de regresion, trazabilidad y capacidad de volver al control. |

**Balance final:** la oportunidad mas clara es reducir la orquestacion generativa en
T2 y eliminarla en T3 dentro del flujo evaluado. En T1, la evidencia respalda una
reduccion selectiva, no un desmantelamiento general. El objetivo debe ser conservar
la calidad de todas las salidas y su integridad, no minimizar el numero de agentes
como fin en si mismo.

## 7. Documentacion de respaldo

- [Informe tecnico completo T1](INFORME_ABLACION_T1.md).
- [Informe tecnico completo T2/T3](../T2_T3/reports/INFORME_ABLACION_T2_T3.md).
- [Plan T1](../PLAN_ABLACION_T1.md) y [plan T2/T3](../T2_T3/PLAN_ABLACION_T2_T3.md).
- [Prerregistro T1](../PREREGISTRO.md) y [prerregistro T2/T3](../T2_T3/PREREGISTRO.md).
- [Validacion de las pasadas narrativas T1](../results/J_session_validation.json) y [T2/T3](../T2_T3/results/J_session_validation.json).
