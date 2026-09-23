# Bitacora de la ablacion T1

Registro append-only de incidencias y desviaciones observadas durante la ejecucion.

## 2026-09-22

- L0 supero la compuerta de identidad Tier S con 91/91 casos y `accepted: true`.
- La primera ejecucion secuencial recibio un argumento accidental `source` despues de L0. El
  lanzador ahora valida todos los brazos antes de reservar la GPU.
- L5 registro un `TimeoutError` en `PT-pseudo_c39e94a13920`. La reanudacion conservo 90 casos y
  completo el caso faltante; `summary.jsonl` conserva ambas entradas y el validador usa la ultima
  por `case_id`.
- Los nueve brazos L tienen 91/91 salidas y `accepted: true`.
- Correccion aritmetica no sustantiva del PASO 6.2: la lista pre-registrada contiene L0, L0p y
  L1-L7, es decir, nueve brazos. Tres pasadas producen 27 ficheros, no los 24 escritos en la
  compuerta original. No cambia ningun brazo, metrica, hipotesis ni regla de decision.

## Cierre automatico F6-F8

- Fecha: 2026-09-23. Sesion del juez: 27/27; `delta_N=0.030000`.
- Tabla maestra: 29 filas; indeterminadas: N03, N04, N07, N12, N15, M1, M2, M3, M4, M5, M6, M8.
- A_min: brazo `L9`, aceptada=True, delta ranking=0.000000, H16=confirmada.
- Cierre: V4 intacta=True, suites equivalentes=True, pruebas del estudio=37.
