# PLAN V4 — bajar el tiempo por caso sin tocar la arquitectura ni los resultados

**16 de septiembre de 2026.** La V3 (supervisor + sombra) **volvió a ser rechazada
por tiempo** en la fase Test. El correo **no da ningún número** y **no hay logs**.
Todo lo que sigue se diseña a ciegas sobre lo único medible aquí.

Trabaja **sólo dentro de `version_final_reto_send_v4/`** (y, si una fase lo pide,
en `Dockerfile_final` / `.dockerignore` / los scripts de la raíz, con el diff
mínimo). `version_final_reto` es un **enlace simbólico** a esta carpeta: los
imports y las pruebas usan ese nombre.

## La regla que manda sobre todas

**Ningún cambio puede mover un byte de las salidas.** La compuerta de identidad
(F6-A) compara los seis ficheros contra la V3 con el mismo `case_id`. Si una fase
no puede pasarla, se revierte esa fase, no se negocia el criterio.

Concretamente, **prohibido**: tocar prompts, decisiones, protocolo, expertos,
umbrales, `n_imputations`, `max_new_tokens`, número de llamadas al LLM, el
troceado del prefill (8192) y el contexto (32 768). Todo eso cambia la salida.

**Medido y ya descartado, no repetir** (está en `BITACORA_V1_1.md` y
`BITACORA_TEST.md`):
- repartir el ensemble entre **hilos**: >4 min frente a 146 s (el GIL);
- `VLLM_ENABLE_V1_MULTIPROCESSING=0`: 211 s frente a 154 s;
- bajar `n_imputations` o el prefill: cambian la salida.

## Lo que sabemos, con números

Contenedor, imagen sin montar, `--cpuset 0-3`, caso no cacheado:

| tarea | total V3 | `model_load` | expertos (`warm_prewarm`) | grafo (LLM) |
|---|---:|---:|---:|---:|
| T1 | 150,9 s | 117,0 | 110,4 | 26,5 |
| T2 | 124,7 s | 82,9 | 22,1 | 34,6 |
| T3 | 70,4 s | 59,8 | — | 4,1 |

Con 2 núcleos, T1 sube a 210,0 s. La sombra deja la decisión de los expertos
lista a los 79 s (4 núcleos) y 195 s (2 núcleos).

Dentro de los 146 s de expertos de T1 (medido el 16-sep, 4 núcleos):
`cargar artefactos` 6,3 · `structured` 29,2 · `fusion_full` 38,5 ·
`fusion_nolab` 72,1 · `trace` y `psa` ≈ 0.

La imagen pesa 33,6 GB: 13,4 GB la instalación de vLLM, 7,2 GB el entorno base,
810 MB `requirements.txt`, 656 MB `apt`, 483 MB el paquete.

## La hipótesis que ordena el plan

El reloj duro de la V3 corta a **720 s desde que arranca nuestro proceso** y en
local funciona (F6-C de `BITACORA_TEST.md`: murió a los 135,3 s en mitad de una
generación). Si aun así el job se pasó de 900 s, **hay tiempo que nuestro reloj
no ve**: arranque del contenedor, descarga de la imagen y, sobre todo, la
extracción de `model.tar.gz` (8,9 GB comprimidos) que Grand Challenge hace en
`/opt/ml/model`. Aquí el modelo se monta ya extraído y ese tramo **nunca se ha
medido**.

De ahí el orden: primero medir lo invisible (F1), después garantizar salida
temprana pase lo que pase (F2), después bajar el reloj con lo medido (F3), y sólo
entonces acelerar de verdad (F4, F5).

---

## F1 · Medir el arranque invisible

**Objetivo:** que el log diga cuánto tiempo se consumió antes de nuestra primera
línea, para poder ajustar el reloj con datos en vez de con miedo.

Al arrancar `common/supervisor.py`, antes de lanzar nada, escribir en stderr una
línea `{"kind": "gc_arranque", ...}` con:
- `ahora`: `time.time()`.
- `uptime`: primer campo de `/proc/uptime` (edad de la máquina; en una VM recién
  creada para el job, es el tiempo desde que arrancó).
- `edad_proceso_s`: desde `/proc/self/stat` (campo 22, en jiffies) y
  `/proc/uptime`.
- `modelo_mtime_s`: `time.time() - max(mtime)` de los ficheros de
  `/opt/ml/model` (dos o tres, no recorrer los 10 GB). **Si GC extrae el tarball
  justo antes de arrancarnos, esto mide la extracción.**
- `cpus`: `os.cpu_count()` y `len(os.sched_getaffinity(0))`.
- `ram_mb`, `gpu`: nombre y memoria por NVML si está.

**Gate F1:** la línea aparece en `container.log` de una corrida local y todos sus
campos tienen valores plausibles. Sin coste medible en tiempo.

## F2 · Salida publicada en cuanto existe ("anytime")

**Objetivo:** que `/output` tenga una salida válida desde el minuto dos, no sólo
al final. Hoy el supervisor publica **una vez**, al terminar; si GC mata el
contenedor antes, `/output` está vacío.

Cambio en `common/supervisor.py`: en cuanto la sombra publica su etapa
(`0-respaldo` primero, `1-expertos` después), copiarla ya a `/output`; cuando la
junta entregue, sobrescribir con sus bytes. Cada fichero con `os.replace`
(atómico), y el par completo antes de considerar publicada una etapa.

**Gate F2:** en una corrida normal de T1, `/output` tiene los dos ficheros antes
de los 120 s (comprobable con un `ls` en bucle desde el arnés) y, al terminar,
son **byte a byte los de la junta**.

## F3 · Reloj más conservador y adaptado a lo medido

**Objetivo:** que el proceso termine con margen aunque el arranque invisible se
haya comido varios minutos.

- `CHIMERA_HARD_SECONDS` baja de 720 a **600** por omisión.
- Si F1 estima un arranque invisible de `X` segundos (por `modelo_mtime_s`, con
  un tope prudente), el corte efectivo pasa a `min(600, 840 - X)`, nunca menos de
  240. Registrar el valor elegido y por qué en la línea `gc_supervisor`.
- El reloj interno de la junta sigue contando hacia el corte menos 25 s.

**Gate F3:** tres corridas forzadas (reloj interno apagado con
`CHIMERA_CASE_BUDGET_SECONDS=0` y `CHIMERA_HARD_SECONDS` a 130) terminan a los
~130 s con salida válida, como en `BITACORA_TEST.md`; y una corrida con
`CHIMERA_SIM_ARRANQUE_S=300` (variable nueva, sólo para probar) elige 540 s.

## F4 · Los expertos de T1, en procesos paralelos

**Objetivo:** 146 s → ~110 s de puntuación, sin mover un número.

La ruta crítica es la cadena de fusión (`fusion_full` 38,5 s y luego
`fusion_nolab` 72,1 s), que **no se puede partir**: comparten el mismo experto y
su `RandomState` avanza con cada pasada, así que `fusion_nolab` sólo sale igual
si se calcula **después** de `fusion_full`, en el mismo objeto.

Lo que sí es independiente es `structured` (29,2 s): es otro artefacto, con su
propio `RandomState`. Sacarlo a un proceso hijo lo solapa con la fusión.

Cómo, en `task_1/experts_1/panel.py::ensure`:
- lanzar `structured.report([case])` en un proceso con
  `multiprocessing.get_context("forkserver")` (**no hilos**, y no `fork` a secas:
  el proceso ya tiene hilos vivos del precalentamiento);
- calcular en el proceso principal `fusion_full` y, aplazado como hoy,
  `fusion_nolab`;
- recoger el veredicto del hijo (un dict, picklable) y montar el caché igual que
  ahora;
- si el hijo falla o tarda más que el principal, calcular en línea como hoy: un
  fallo aquí es más lento, nunca incorrecto.
- `CHIMERA_EXPERTOS_PARALELOS=0` lo apaga (brazo de control para el A/B).

**Gate F4:** (a) los **195 casos de T1** dan salida idéntica a `result_v2/` salvo
`free_text` — reutiliza el arnés de la sombra; (b) la compuerta de identidad
byte a byte; (c) `warm_prewarm` baja de ~110 s a ~75-85 s con 4 núcleos.

## F5 · Imagen más ligera — SÓLO si F1 dice que compensa

**Condición de entrada:** que F1 muestre un arranque invisible grande, o que
lleguen los logs y confirmen que la descarga o la extracción cuentan dentro del
límite. Si no, **no se toca**: cada capa que se mueve es riesgo sobre una imagen
ya verificada.

Candidatos, por orden de seguridad:
1. `build-essential` y `ffmpeg` (656 MB de `apt`): comprobar que nada los usa en
   ejecución y quitarlos, o instalarlos y borrarlos en la misma capa.
2. Duplicados de CUDA: el entorno base trae torch cu126 y encima se instala torch
   cu129. Ver si quedan las dos copias de `nvidia/*` y eliminar la que no carga.
3. Cachés y `__pycache__` de site-packages.

**Gate F5:** las seis salidas byte a byte iguales, `pip freeze` sin paquetes que
falten respecto a `version_final_reto_send/imagen/pip_freeze_imagen_v3.txt` salvo
los retirados a propósito (lista explícita), y el nuevo tamaño registrado.

## F6 · Compuertas finales (todas obligatorias antes de entregar)

Con la imagen **tal cual, sin montar código** (`--no-mount`), `--cpuset 0-3`, y
el mismo `case_id` que la referencia:

- **A · identidad:** las tres interfaces, 6/6 ficheros byte a byte iguales a
  `version_final_reto_send/verification/gc_profile_20260915_201106_v3_idle`
  (T1) y `..._202124_v3_final_t2t3` (T2 y T3).
- **B · cortes:** la junta cae a su respaldo (`CHIMERA_CASE_BUDGET_SECONDS=60`)
  → publica la sombra; y corte duro en mitad de una generación
  (`CHIMERA_CASE_BUDGET_SECONDS=0`, `CHIMERA_HARD_SECONDS=130`) → el contenedor
  sale a los ~130 s, con salida válida y la GPU liberada.
- **C · estrés:** T1 con `--cpuset 0-1` termina con salida idéntica, y la sombra
  llega a tiempo.
- **D · máquina lenta simulada:** T1 con `--cpuset 0-1` y
  `CHIMERA_SIM_ARRANQUE_S=300`: el proceso termina antes de 600 s y `/output`
  tiene salida válida.
- **E · pruebas:** `PYTHONPATH=src:. .venv/bin/python -m pytest -q
  version_final_reto` — las 195 actuales más las nuevas de cada fase.

## Cómo se construye y se mide

```bash
CODE_DIR=version_final_reto_send_v4 DOCKER_IMAGE_TAG=chimera_agent_baseline_v4 ./do_build_final.sh
python3 version_final_reto/verification/gc_profile.py --cpuset 0-3 --interfaces 0,1,2 \
    --image chimera_agent_baseline_v4 --no-mount --tag v4_identidad
python3 version_final_reto/verification/compare_outputs.py <ref> <nueva>
```

Variables extra al contenedor: `CHIMERA_PROFILE_ENV="A=1,B=2"`.

## Cuatro trampas que ya costaron tiempo

1. **Una sola GPU.** Nunca dos contenedores a la vez; las corridas van en serie.
2. **Mismo `case_id` en los dos brazos.** Va dentro del prompt (`Board.HEAD`),
   así que cambiarlo cambia la trayectoria y la comparación no vale.
3. **Un caso por proceso.** Los imputadores llevan `RandomState` dentro del
   pickle y avanzan con cada `transform`.
4. **Montar código sobre otra imagen no comprueba la entrega.** Siempre
   `--no-mount`, y mirar `fallback: false`: un caso real nunca tarda menos de
   ~70 s; tiempos de segundos son un crash con exit 0.

## Registro de avance

Cada fase cerrada se escribe **aquí**, con la ruta de la evidencia en disco.
Lo que no tenga evidencia no se marca como hecho.

| fase | estado | evidencia |
|---|---|---|
| F1 | cerrada | `version_final_reto_send_v4/verification/plan_v4_f1_f4_evidence/telemetry_extract.log`; corridas `gc_profile_20260916_090039_v4_f1_f2_f3_f4_t1_fixed`, `gc_profile_20260916_090338_v4_f1_f2_f3_f4_t2t3` |
| F2 | cerrada | `version_final_reto_send_v4/verification/plan_v4_f1_f4_evidence/telemetry_extract.log`; early publish T1 a 3.0 s y 71.6 s, salida final idéntica en `compare_t1_vs_v3.json` |
| F3 | cerrada | `version_final_reto_send_v4/verification/plan_v4_f1_f4_evidence/telemetry_extract.log`; `CHIMERA_SIM_ARRANQUE_S=300` eligió `hard_seconds=540.0`, T3 idéntico en `compare_f3_sim300_t3_vs_v3.json`. **Reabierta y corregida 2026-09-16:** el suelo `MIN_HARD_SECONDS=240` se aplicaba también a lo pedido a mano y convertía `CHIMERA_HARD_SECONDS=130` en 240 (F6-B2 acababa sola a 164 s). `supervisor.py` pasa a `min(requested, max(240, 840 − penalty))`: igual en producción (600), simulación 300 (540) y caso patológico (240). El reloj adaptativo sigue inerte en corridas reales (`startup_mtime_stale=true`); la ganancia real de F3 es 720→600. |
| F4 | cerrada, **sin ganancia** | `version_final_reto_send_v4/verification/plan_v4_f1_f4_evidence/compare_t1_vs_v3.json`; T1 byte a byte idéntico, sombra de expertos T1 en 71.38 s. A/B 2026-09-16 (T1, brazos alternados): `CHIMERA_EXPERTOS_PARALELOS=0` 157,4 · 161,9 s; `=1` 159,9 · 163,4 s; expertos 78,5–82,8 s en ambos. El 71,38 s era ruido. No se cumplió la compuerta (a) de 195 casos ni la (c). Se deja activado: idéntico byte a byte. Corridas `gc_profile_*_ab_f4_par{0,1}_r{1,2}`. |
| F5 | omitida (condicionada) | F1 local no mostró arranque invisible grande medible: `modelo_mtime_s` correspondía a modelo montado viejo y quedó marcado `startup_mtime_stale=true`; no se tocó imagen |
| F6 | A, B y E cerradas; C y D sin correr | **A:** 6/6 byte a byte con el cierre forzado incluido, `version_final_reto_send_v4/verification/gc_profile_*_cierre_ident` (0 cierres forzados). **B1:** `CHIMERA_CASE_BUDGET_SECONDS=60` → sombra publicada, 75,4 s, `gc_profile_*_f6b1_respaldo`. **B2:** corte duro a 130,3 s, `reason: hard_deadline`, 2 ficheros, `gc_profile_*_fix_b2` (tras corregir F3). **E:** 199 tests pasan. Cara a cara del mismo día: V3 170,9 s sin publicación temprana; V4 162,9 s, publica a 3,3 s. |
| F7 | cerrada (añadida 2026-09-16) | **Cierre forzado de la junta.** `deadline.must_close()`: cuando sólo quedan 90+90 s (verificador + presidente), o pasado `CHIMERA_CIERRE_FORZADO_S`, T1 salta de los bucles de herramientas a `*_finalize`, T2 rechaza herramientas en `speak`, y en ambas se sueltan empujones y segunda vuelta: el verificador decide y el presidente redacta. Un disparo fijo a 14 min no actuaría nunca (el supervisor corta a 600 s). Compuerta con `CHIMERA_CIERRE_FORZADO_S=0`: T1 157,7 s y T2 130,1 s, `source: board`, `fallback: false`, 2 ficheros cada una, `version_final_reto_send_v4/verification/gc_profile_*_cierre_forzado`. Identidad en A. |
