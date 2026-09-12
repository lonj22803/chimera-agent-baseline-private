# CHIMERA V2_2 — ejecución del PLAN, resultados y veredictos

**Fecha: 12 de septiembre de 2026.** Todo lo de aquí está medido con el
evaluador oficial y las particiones anidadas por grupo de este directorio.
Ningún número viene de una corrida anterior ni de la documentación de V1.

## Resumen en una tabla

| Exp. | Hipótesis | Veredicto | Evidencia |
|---|---|---|---|
| **E00** | Reproducir H0, construir B0 | ✅ **exacta** | H0 OVERALL 0,82360, al quinto decimal |
| **E01** | Negación, tiempo y fuente mejoran extracción | ⚠️ **parcial** | 16 contradicciones corregidas; cronología: 0 casos |
| **E02** | El panel de T2 evita consultas rutinarias | ✅ **sí** | panel 0,8287 vs completo 0,8472 |
| **E03** | Consultas por duda > plan fijo | ❌ **no** | 95,83% de decisiones no cambian; basta 1 documento |
| **E04** | Los conceptos verificados aportan señal | ❌ **no** | nada bate al ancla en T1 ni en T2 |
| **E05** | Mapa continuo evita pérdida en exportación | ✅ **sí** | 31 empates → 0; time_score +0,0172 |
| **E06** | Ancla clínica + residuo mejora T3 | ✅ **sí** | 0,73717 → 0,82832 |
| **E07** | La curva mejora la interpretación temporal | ✅ **sí** | time_score +0,0188, c-index −0,0031 |
| **E08** | Formulario y explicación desde hechos | ⛔ **no ejecutado** | exige GPU y juez pareado |
| **E09** | Conceptos multimodales compartidos | ⛔ **bloqueado por el PLAN** | «no ejecutar antes de validar E01/E04»; E04 falló |
| **E10** | Junta completa sobre B0 y H0 | ⛔ **no ejecutado** | exige la tubería completa en GPU |
| **E11** | Arquitectura completa en 16 GB | ✅ **ensayo superado** | 13 332 MiB; ver `../delete_final_versions_task_V2/` |

---

## E00 — Las dos referencias

H0 se reproduce **exactamente**:

| | T1 | T2 | T3 | OVERALL |
|---|---:|---:|---:|---:|
| H0 | 0,83903 | 0,77839 | 0,88319 | **0,82360** |
| B0 | 0,83903 | 0,77252 | 0,88319 | **0,82126** |

B0 declara las lecturas que el protocolo hizo de verdad. Cuesta **−0,00235** de
OVERALL, todo en T2, donde los 72 casos declaraban `reveal_sequence: []`
mientras abrían seis secciones.

### La discrepancia que E00 encontró

La corrida de cobertura de T3 (11-sep 00:35) da **0,73717**, no el 0,88319 que
documenta V1. Causa comprobada: de los 126 ficheros del árbol congelado de esa
corrida, **6 difieren** del árbol entregado, y uno es
`task_3/agent/protocol.py` — el que elige el portavoz. La cobertura llevaba el
portavoz viejo. Y 0,73717 es exactamente el `baseline_c_index` de
`survival_total.json`, lo que cierra el círculo.

**Las tres cifras de T3 no se deben mezclar:** 0,88319 desplegada **dentro de
muestra**, 0,82345 anidada fuera de muestra, 0,73717 el portavoz anterior.

---

## Grupos y particiones — lo que había que hacer antes de entrenar

Los 423 casos son **199 grupos**, y **170 abarcan más de una tarea**; 54 grupos
tienen un miembro en cada una. Criterio único y declarado: igualdad exacta de un
vector de modalidad, union-find sobre las tres tareas.

Hallazgo que simplifica el resto: **dentro de cada tarea, los casos etiquetados
están todos en grupos distintos** (91/91, 72/72, 75/75). La agrupación sólo
muerde en la rama compartida —que no se ejecuta— y en comparaciones entre
tareas. Para las cabezas por tarea, partir por grupo equivale a partir por caso.

`watchful_waiting` (2 etiquetas) falta en **3 de los 5 pliegues** en las tres
semillas. Se registra, no se esconde.

---

## E01 — Extracción: un acierto, una corrección sin efecto

5 385 hechos sobre 228 casos con informe. **100% con cita que cuadra con su
fuente** en la posición declarada.

| Corrección | Alcance real |
|---|---|
| Alcance de negación | **16 casos** en los que V1 activaba «estable» y «progresión» a la vez |
| Orden cronológico | **0 casos.** El desorden existe como mecanismo, pero no ocurre en este corpus |
| `unknown` ≠ `false` | **468 negativas documentadas** frente a 3 717 ausencias, que V1 colapsaba en 0 |

La segunda línea es importante y es negativa: la corrección de cronología está
demostrada con una prueba sintética y **no cambia ni un delta de ISUP real**. Se
conserva como guardia, no se cuenta como mejora.

**Lo que E01 no puede cerrar:** el PLAN §10.2 exige que las anotaciones de
conceptos «las revisa **una persona** sin ver la etiqueta de decisión». Eso no lo
puede hacer una máquina. Aquí se mide mecanismo, no verdad clínica.

---

## E02 — El panel de T2 basta casi del todo

Bajo la misma validación anidada por grupo:

| política | exactitud | F1 pond. | F1 macro |
|---|---:|---:|---:|
| **ancla ISUP** (mapeo aprendido en train) | **0,86111** | **0,84896** | **0,66089** |
| panel (A,G,J) · bosque pequeño | 0,82870 | 0,82418 | 0,64430 |
| completo (los 6 documentos) · bosque | 0,84722 | 0,84109 | 0,65594 |

Dos lecturas, las dos incómodas:

1. El panel llega a **1,8 puntos** del recorrido completo. Abrir seis documentos
   en todos los casos compra muy poco.
2. **Ningún modelo aprendido bate a la regla de grado.** El listón de T2 no es
   0,847: es **0,861**, y sólo necesita `bx_isup`, un campo del panel.

Nota metodológica: escribir el mapeo grado→clase a mano da 0,306. La regla sólo
vale si su mapeo se aprende en train, como el PLAN exige.

---

## E03 — Consultar aporta poco, y se concentra en un documento

V1 abre seis secciones en los 72 casos. Resultado:

- **69 de 72 decisiones (95,83%) no cambian** al abrirlas.
- De las 3 que cambian: **2 arregladas, 0 rotas**, balance +2.

Utilidad marginal de cada sección sobre el panel:

| sección | Δ F1 ponderado | decisiones cambiadas |
|---|---:|---:|
| `pathology_report` | **+0,01417** | 2 |
| `previous_notes` | 0,00000 | 0 |
| `psa_trend` | −0,00016 | 1 |
| `radiology_report` | −0,00016 | 1 |
| `laboratory_results` | −0,01462 | 1 |
| `family_history` | −0,01462 | 1 |

**Veredicto:** la salida que el PLAN prevé para E03 —«Plan fijo pequeño y
explícito»— es la que sostiene la evidencia. Un plan de **un documento**
(`pathology_report`) captura todo el beneficio. No hace falta un planificador
adaptativo, y montarlo sería complejidad sin retorno medible.

---

## E04 — Los conceptos verificados no aportan señal

Ésta era la apuesta central de V2. Sale que no.

**Tarea 1** (F1 de `yes`, 91 casos):

| política | métrica | Δ ancla |
|---|---:|---:|
| ancla (cascada V1) | **0,93103** | — |
| conceptos solos | 0,00000 | −0,93103 |
| panel + conceptos | 0,68936 | −0,24167 |
| **residual: ancla + conceptos** | **0,93103** | **+0,00000** |

El residual **reproduce el ancla exactamente**. Con regularización fuerte, el
modelo concluye por sí mismo que los conceptos no añaden nada.

**Tarea 2** (F1 ponderado, 72 casos): ancla 0,84896; el mejor candidato,
0,80063. Ninguno se acerca.

**Veredicto del PLAN para E04: «Ancla sin corrector».** Y de §15: «Si la
representación nueva no mejora decisiones, conservarla sólo donde corrija
errores demostrados o mejore fidelidad».

---

## E05, E06, E07 — Supervivencia: aquí sí hay ganancia

**E06, el riesgo** (c-index, anidado por grupo, 3 semillas):

| composición | c-index | grados de libertad |
|---|---:|---:|
| ancla CAPRA-S sola | 0,73717 | 1 |
| + conceptos clínicos | 0,79440 | 4 |
| **+ residuo de modalidades** | **0,82832** | 4 |

Reproduce el hallazgo de V1 (0,82345 anidado) bajo una validación más estricta.

**E05 y E07, la exportación** — que es lo que puntúa de verdad:

| exportador | c-index | time_score | valores distintos |
|---|---:|---:|---:|
| CDF escalonada (V1) | **0,82994** | 0,71407 | 43,3 (**32 empates**) |
| mapa continuo | 0,82655 | 0,72230 | 75 |
| **curva de supervivencia** | 0,82684 | **0,73288** | 75 |

La CDF empírica colapsa 75 casos en ~43 valores. Los otros dos exportadores
eliminan **todos** los empates. La curva gana **+0,0188 de `time_score`**
perdiendo 0,0031 de c-index: dentro de la tolerancia de 0,01 que fija §7.4.

**Pero no es una mejora de ranking.** El ranking de T3 *es* el c-index, y ahí no
gana nadie por el margen de 0,005 que exige §10.5. Es una mejora de **fidelidad
temporal a coste de ranking nulo**, y así hay que venderla.

---

## Qué se adoptaría, y cuánto vale

Siguiendo las compuertas del propio PLAN:

| pieza | ¿pasa? | qué aporta |
|---|---|---|
| Extracción con negación | sí, como corrección | 16 casos; fidelidad, no ranking |
| `unknown` ≠ `false` | sí, como representación | no mejora decisiones |
| Plan fijo de 1 documento en T2 | sí, operativo | 6 consultas → 1, traza verdadera |
| Corrector sobre conceptos | **no** | nada que adoptar |
| Curva de supervivencia en T3 | sí, como fidelidad | +0,0188 time_score, ranking plano |
| Perfil de 16 GB | sí | 21 502 → 13 332 MiB |

**Estimación honesta del efecto en OVERALL: cercano a cero, y posiblemente
negativo.** Declarar la traza real de T2 cuesta −0,00235 medidos. Nada de lo que
pasó sus compuertas lo compensa en ranking, porque las dos ganancias reales
—fidelidad temporal en T3 y menos consultas en T2— no mueven el c-index ni el F1.

El PLAN pedía «+0,010 de OVERALL frente a B0» como cierre mínimo de calidad.
**No se alcanza.** Decirlo es el resultado.

---

## Lo que no se ejecutó, y por qué

- **E08 y E10** exigen la tubería completa en GPU y el juez pareado en dos pases.
  No se han ejecutado. Sin E08 no hay medición de explicación ni de formulario.
- **E09** lo bloquea el propio PLAN: «No ejecutar E09 antes de resolver la
  agrupación y validar E01/E04». E04 salió negativo, así que no procede.
- **La revisión humana ciega de conceptos** (§10.2) no la puede hacer una
  máquina. E01 queda abierto por ese lado.
- **El cierre físico de E11** exige una GPU de 16 GB identificada. Aquí hay una
  RTX 5090. Estado: pendiente de validación física.
- **La confirmación externa** sólo llega de la fase oficial. No es código.
