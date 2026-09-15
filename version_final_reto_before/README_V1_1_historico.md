# CHIMERA V1.1

La V1 con una sola cosa arreglada: **el reloj**. Development no falló por el contrato de
salida ni por los tokens, sino por tiempo — 15 minutos por caso, y el trabajo de CPU que no
necesita el LLM corría en serie detrás de la carga de vLLM. La [BITACORA V1.1](BITACORA_V1_1.md)
tiene el diagnóstico con las mediciones y el desglose de los 141 s que costaba puntuar un caso
de la tarea 1 con los expertos entrenados.

Ninguna decisión, ningún prompt y ningún modelo cambian. Lo que cambia:

| pieza | qué hace |
|---|---|
| `common/warmup.py` | los expertos, el servicio de embeddings y la carga del modelo arrancan a la vez, en hilos demonio, en cuanto el caso está leído |
| `common/serial_predict.py` | `n_jobs=1` en los bosques: puntuando una fila, el pool de joblib cuesta más que el bosque |
| `task_1/experts_1/panel.py` | `fusion_nolab` (73 s de 141) sólo se calcula si alguien la lee |
| `common/deadline.py` | 780 s de los 900: suelta lo opcional y, en el límite, cierra con el respaldo determinista en vez de dejar que GC mate el contenedor |

Medido en contenedor con `--cpuset-cpus 0-3` (la A10G del reto trae 4 vCPU) y un `case_id`
que la caché de expertos no conoce, que es la única ruta que existe en el test real:

| interfaz | V1 | V1.1 | salida |
|---|---|---|---|
| task 1 | 274,4 s | **154,1 s** (−43,8%) | idéntica byte a byte |
| task 2 | 128,2 s | 122,2 s (−4,7%) | idéntica byte a byte |
| task 3 | 76,6 s | 77,3 s (+0,9%) | idéntica byte a byte |

La tarea 1 es la que estaba en riesgo: es la única con puntuación en vivo aparte
(~140 s), y la única que baja. En la 2 el precalentamiento esconde los 16,5 s de
expertos y `n_jobs=1` quita 14 s del grafo, pero la carga del modelo sube otros
tantos al competir por los 4 núcleos.

Verificación de que los números no se mueven, en dos niveles:

* **salida contra salida**, mismo `case_id` en los dos brazos: los dos JSON de
  Grand Challenge son idénticos byte a byte (`verification/compare_outputs.py`);
* **números de los expertos**, un proceso por caso y por brazo, con y sin
  `n_jobs=1`: `verification/compare_experts_task{1,2}.json`. En la tarea 2, seis
  casos, peor diferencia 3,6e-16. En la tarea 1, cuatro de seis idénticos y los
  otros dos con 3,6e-12. Ninguna decisión, peldaño ni confianza se mueve, y los
  flotantes que llegan al prompt se escriben con dos o tres decimales.

Implementación y experimentos del [PLAN](PLAN.md). La versión original permanece intacta.

> **Estado, 11-sep-2026 · Fase 1 CERRADA.** La compuerta de entrega pasa entera:
> **423/423 casos válidos** en contenedor real (exit 0, sin OOM, pico 21 502 MiB < 22 GiB),
> **0 errores de contrato**, **0 formularios incompletos** y los slugs confirmados contra la
> página del algoritmo. Los tres motivos por los que la entrega anterior no pasó Development
> están medidos y resueltos. 160 tests en verde.
>
> **Una mejora adoptada:** el portavoz de la tarea 3 pasa de CAPRA-S a la selección anidada,
> c-index **0,7372 → 0,8235** (+0,0173 de OVERALL). Dieciséis candidatos más se midieron y se
> rechazaron; la [BITACORA](BITACORA.md) explica por qué cada uno.

- [BITACORA.md](BITACORA.md): mediciones, candidatos rechazados y estado de adopción.
- [ENTREGA.md](ENTREGA.md): contrato, slugs y recursos.
- [ARQUITECTURA.md](ARQUITECTURA.md): estructura compartida y diferencias justificadas.
- `tasks_complete/`: orquestación — un runner, la evaluación, el ciclo de experimentos y la compuerta.
- `verification/`: tests, snapshots de ejecución, smoke de contenedor y cobertura real.
- `experiments/results/`: comparaciones DEV/VAL/total y auditoría de actas.
- `baseline_scores/`: scores históricos congelados; no son nuevas mediciones.

Los candidatos no sustituyen automáticamente la entrega. Los cambios de prosa requieren dos pases
pareados del juez dentro de una misma carga; las mejoras numéricas conservan su protocolo de
validación. La fase 7 permanece condicionada a sus criterios de cierre.
