# CHIMERA V1

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
