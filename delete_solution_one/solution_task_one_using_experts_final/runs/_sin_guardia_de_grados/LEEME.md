# Corrida completa anterior a la guardia de grados

Los 195 casos corridos antes de añadir la tercera capa de la guardia de
procedencia, la que comprueba **los grados de la biopsia previa** y no sólo los
valores numéricos. Se conserva porque es la evidencia del fallo que la motivó y
permite medir el antes y el después.

| medida sobre estos 195 casos | |
|---|---|
| informes del registrador que afirman un grado ausente del fichero clínico | **13 (6.7 %)**, varios entrecomillados como si lo citaran |
| de ésos, invenciones que llegaron a la nota entregada | **5 (2.6 % de las notas)** |
| decisiones afectadas | **0** — `documented_grade` lee el texto crudo de la herramienta, no el resumen del registrador, así que el protocolo nunca se dejó engañar |
| `ranking_score` | 0.8390 |

El caso que lo destapó es `PT-pseudo_d217629c323a`: el registrador escribió
`PRIOR GRADE: "Gleason 3+4 focus"` y el fichero clínico no menciona «Gleason» ni
«ISUP` ni una sola vez. La nota entregada quedó además internamente
contradictoria — *«on surveillance for prior Gleason 3+4 focus … Lack of prior
biopsy grade necessitates sampling»* — porque el parte del presidente contenía a
la vez la invención del registrador y la línea correcta que el código construye
(«las notas no recogen el grado»).
