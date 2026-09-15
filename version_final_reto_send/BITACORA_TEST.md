# Fase Test: el límite de 15 minutos, garantizado fuera de la junta

**15 de septiembre de 2026.** Grand Challenge rechazó el envío
`28f1d855-1779-41d2-8b38-14f95357a56c` de la fase Test: «many of the algorithm
jobs exceeded the 15-minute time limit per case. One of the affected jobs ran for
approximately 1291 seconds». La misma V2 había pasado Debug y Development.

No hay log de esos jobs: sólo el correo. Así que la corrección no puede apuntar a
una causa medida allí. Tiene que garantizar el límite **pase lo que pase dentro de
la junta**, sin cambiar la arquitectura ni los resultados.

## Qué se sabía y qué se midió

**1. El reloj que había no garantizaba nada.** `common/deadline.py` cortaba a los
780 s, pero **dentro** del proceso que trabaja: `asyncio.wait_for` sólo dispara si
el bucle está libre, y cancelar la junta no para una llamada síncrona al LLM que
ya corre en un hilo. Además, Python 3.11 espera sin límite a esos hilos al cerrar.

**2. El respaldo al que cortaba no era la decisión de los expertos.**
`run_task1.fallback_case` decide sólo por la cohorte: **71/91** frente a **83/91**
de la entrega. El de T2 consolida sin leer a los expertos.

**3. La parte de la salida que puntúa sin juez no la decide el LLM.** La
simulación sin LLM coincide con `result_v2/` en decisión, confianza, pesos y
revelaciones:

| tarea | coincide con la entrega | cómo se midió |
|---|---|---|
| T1 | **91/91** etiquetados | `task_1/analysis/simulate.py` |
| T2 | **72/72** etiquetados | `task_2/analysis/simulate.py` |
| T3 | **75/75** (evento y meses, fichero entero) | `run_task3.fallback_case` |

El LLM sólo redacta el texto libre: el presidente de T1 y T2 ya tenía una rama
determinista (`clinical_note` / `build_output(note=None)`) para cuando no redacta.

## La técnica

Tres procesos, ninguno cambia la junta:

```
inference_final.py  ─►  common/supervisor.py   (reloj duro, no calcula nada)
                         ├─ trabajador: inference_final.py con CHIMERA_WORKER=1
                         │    la V2 intacta; escribe en un directorio privado
                         └─ sombra: common/shadow.py, prioridad SCHED_IDLE
                              etapa 0: fallback_case          (~3 s)
                              etapa 1: decisión de los expertos (T1 ~80 s, T2 ~30 s)
```

- Si la junta entrega a tiempo (`fallback: false`), el supervisor publica **sus**
  ficheros, byte a byte.
- Si no llega, cae al respaldo, o se cuelga al cerrar, el supervisor mata su
  **grupo de procesos** entero (vLLM, MCP y embeddings) y publica la mejor etapa
  de la sombra.
- El corte duro es `CHIMERA_HARD_SECONDS` = **720 s** desde que arranca el
  contenedor. El reloj interno de la junta cuenta hacia ese corte menos 25 s
  (`CHIMERA_HARD_DEADLINE_EPOCH`), para soltar empujones y segunda vuelta a tiempo.
- `CHIMERA_SUPERVISOR=0` vuelve al arranque directo de la V2.

La sombra corre en **su propio proceso** a propósito. Adelantar el cálculo dentro
de la junta habría tocado el `RandomState` de los imputadores y los lectores de T2,
que se llaman en un orden fijo. En otro proceso, cada uno desunpickla sus
artefactos y sortea desde el mismo estado.

**Qué cuesta:** en los casos cortados, el texto libre lo escribe el código y no el
presidente. Decisión, confianza, pesos y revelaciones son los mismos. El juez de
razonamiento puntúa ese texto y **no se ha medido** sobre la nota determinista.

## Cambios en el código

| fichero | cambio |
|---|---|
| `common/supervisor.py` | **nuevo**: el reloj duro |
| `common/shadow.py` | **nuevo**: la salida de los expertos sin LLM, siguiendo los nodos del grafo en su orden |
| `inference_final.py` | arranca el supervisor; en modo trabajador escribe donde se le dice |
| `common/gc_entry.py` | escribe el registro `gc_delivery` en `CHIMERA_DELIVERY_RECORD` si existe |
| `common/deadline.py` | cuenta hacia `CHIMERA_HARD_DEADLINE_EPOCH` si existe |
| `common/tests/test_supervisor.py` | **nuevo**: 6 pruebas |
| `verification/gc_profile.py` | no aborta al imprimir fases `None` de un caso cortado |

`Dockerfile_final` no cambia: el `ENTRYPOINT` sigue siendo `inference_final.py`.

## Evidencia

**Sombra frente a la entrega, un proceso por caso, todos los casos del dev:**
T1 **195/195** y T2 **153/153** idénticos en todo salvo `free_text`.

**Pruebas:** 195 pasan (189 previas + 6 nuevas).

Compuertas con la imagen tal cual, **sin montar código**, `--cpuset-cpus 0-3`,
casos `UNSEEN-*` que la caché no tiene. Referencia: `gc_profile_20260912_212149_final`.

| compuerta | qué fuerza | resultado | carpeta en `verification/` |
|---|---|---|---|
| A · identidad | nada | **6/6 ficheros byte a byte iguales**, `source: board` | `gc_profile_20260915_200323_v3_identidad` |
| A · imagen final, T1 | nada | 2/2 byte a byte, 150,9 s | `gc_profile_20260915_201106_v3_idle` |
| A · imagen final, T2 y T3 | nada | **4/4 byte a byte**, `source: board`, 124,7 y 70,4 s | `gc_profile_20260915_202124_v3_final_t2t3` |
| C · la junta cae al respaldo | `CHIMERA_CASE_BUDGET_SECONDS=60` | publica `shadow:1-expertos`; T1 y T2 **iguales a la junta** en decisión, confianza, pesos y revelaciones | `gc_profile_20260915_201403_v3_C_respaldo` |
| D · corte duro en mitad del LLM | reloj interno apagado, corte a 135 s | `hard_deadline` a **135,3 s**, trabajador `-9` durante una generación, publica la sombra, GPU liberada | `gc_profile_20260915_201850_v3_D_duro135_sinreloj` |
| estrés · 2 núcleos | `--cpuset-cpus 0-1` | T1 en 210,0 s, **byte a byte igual**; la sombra con `SCHED_IDLE` termina la etapa 1 a los 195 s | `gc_profile_20260915_202439_v3_estres_2nucleos` |

La imagen de las filas «imagen final» y siguientes es `chimera_agent_baseline_v3`
(`4e725e4fafd0`). La primera fila A se corrió con la versión anterior del supervisor
(`nice 10`), que sólo difiere en la prioridad de la sombra.

**Tiempos con la sombra al lado (T1, 4 núcleos):** 138,8 s sin sombra → 169,9 s
con `nice 10` → **150,9 s con `SCHED_IDLE`**. La sombra sigue lista a los 79 s.
La prioridad no cambia los números: los hilos de BLAS quedan como estaban.

## Lo que esto NO demuestra

- **Por qué la máquina de Test tardó 1291 s.** Sin log no se sabe si fue la GPU,
  la CPU o el disco. La técnica garantiza el límite igualmente, pero no hace que
  la junta entregue en más casos.
- **La nota del juez sobre el texto determinista.** Medible con
  `dev/score_with_judge.py`.
- **Un corte duro con la sombra aún sin terminar.** Se publicaría la etapa 0 (el
  respaldo de cohorte, 71/91 en T1). Sólo ocurre si la etapa 1 no ha acabado en
  720 s: aquí tarda 80 s en T1.
