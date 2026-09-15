# Bitácora V1.1 — por qué Development se pasó de tiempo, y qué se cambió

La V1.1 no cambia ninguna decisión, ningún prompt y ningún modelo. Cambia
**cuándo** se hace el trabajo que no necesita el LLM, y añade un reloj que
garantiza que el contenedor escriba antes de que lo maten.

## 1. El diagnóstico

El correo de los organizadores dice «Time limit exceeded» con la inferencia
corriendo con normalidad, y la página de la fase dice **15 minutos por caso**,
A10G de 24 GiB o T4 de 16, y 32 GB de DRAM.

Dos sospechas se descartan con el propio log del correo:

* **No fue una T4.** `Maximum concurrency for 32,768 tokens per request: 31.59x`
  son ~1,035 M tokens de caché KV ≈ 9,1 GiB. Con `gpu_memory_utilization: 0.9`
  eso sólo cuadra con 24 GiB (9,9 de pesos + 9,1 de KV + ~1,2 de activaciones
  ≈ 0,9 × 22,5). En una T4 el KV habría salido ~2,6 GiB → 9x.
* **No fueron los tokens.** 32 768 es la ventana que se pide, no lo que se
  gasta: sobre los 195 casos de T1 el prompt más largo de una llamada es ~7 k y
  el total por caso ~45 k repartido en 7 llamadas.

Lo que sí dice el log, en sus dos marcas de tiempo:

```
21:37:54  init engine (profile, create kv cache, warmup model) took 21.77 s
21:43:02  Detected the chat template content format to be 'openai'
```

Ese tramo —vLLM ya listo, primera llamada al modelo todavía no— son **308 s** en
GC. Aquí son 38 s. Y ese tramo es exactamente el trabajo de CPU que no necesita
el modelo: arrancar el servidor MCP y el servicio de embeddings, y puntuar el
caso con los expertos entrenados.

### El coste que ninguna medición anterior incluía

`panel_cache.json` trae los 195 casos de T1 y los 153 de T2 del dev. **Todos**
los smokes y la corrida de cobertura entraron por la rama cacheada. En el test
real ningún caso está en la caché, así que cada caso paga la puntuación en vivo,
y eso nunca se había cronometrado.

Medido con un `case_id` inventado y 4 núcleos reales (la A10G trae 4 vCPU):

| | V1, caso cacheado | V1, caso nuevo |
|---|---|---|
| T1 (interf0) | 112 s | **267,8 s** |
| T2 (interf1) | 128 s | 127,3 s |

T2 no cambia porque su `ExpertReader` nunca usó la caché: puntúa siempre en
vivo. T1 sí: 189,4 s de grafo frente a 37,3 s, es decir ~140 s de puntuación.

Desglose de esos 141 s, proceso nuevo, sin perfilador:

| variante | segundos |
|---|---|
| `structured` | 29,4 |
| `fusion_full` | 38,7 |
| `fusion_nolab` | **73,2** |
| `psa`, `trace` | ~0 |

`fusion_nolab` es la más cara porque quitar la analítica mete NaN donde no los
había y dispara las diez imputaciones. Y es **monohilo**: el load average se
queda en 0,98 durante toda la puntuación, que es la razón de que 28 núcleos no
fueran más rápidos que 4.

## 2. Lo que se cambió

Todo lo de abajo o no toca el resultado, o sólo actúa cuando el caso no cabría
en el límite.

### `common/warmup.py` — solapar, no acelerar

Hilos demonio que arrancan, en cuanto el caso está leído y **antes** de cargar
vLLM: la puntuación de los expertos, el servicio de embeddings y la propia carga
del modelo. La sesión MCP se abre en el bucle de eventos mientras el modelo
carga en su hilo. El mismo cálculo con los mismos ficheros, sólo antes.

Demonios a propósito: los hilos de `ThreadPoolExecutor` no lo son y el
intérprete los espera al salir, así que un caso cortado por el reloj dejaría el
proceso colgado **después** de escribir la salida, que es el fallo que se está
arreglando.

Si un precalentamiento falla, no se propaga: `warmup.result` reconstruye en el
camino crítico y sólo se pierde el solape.

### `common/serial_predict.py` — `n_jobs=1` en los bosques

Los expertos se entrenaron con `RandomForestClassifier(n_estimators=1000,
n_jobs=-1)` y ese ajuste viaja en el pickle. Puntuando **una fila**, cada
`predict_proba` monta y desmonta un pool de joblib; un caso de T2 encadena 104
bosques. Medido: 10,3 s → 5,0 s por caso. En T1 son 64 estimadores.

La diferencia numérica está en el bit 16 (`margin` 0,8315283228871304 →
...303): el bosque promedia sus árboles y en paralelo esa suma la acumulan
varios hilos, así que el orden **ya** era no determinista entre corridas.
`CHIMERA_SERIAL_PREDICT=0` lo desactiva, que es el brazo de control de la
verificación.

### `task_1/experts_1/panel.py` — `fusion_nolab` aplazado

`experts_1/fusion.render` lee **una** de las dos variantes: `fusion_full` si el
registrador abrió la analítica, `fusion_nolab` si no. En los 195 casos de la
cobertura la abrió en el 42%, así que cuatro de cada diez casos pagaban 73 s por
un número que nadie mira. Ahora es un `dict` con `__missing__`.

`fusion_full` se sigue calculando siempre y antes, aunque no se lea: las dos
variantes comparten el mismo experto y su imputador sortea con un `RandomState`
que avanza en cada pasada. Saltarse la primera le daría a la segunda los sorteos
de la primera y el número cambiaría. Así, cuando `fusion_nolab` hace falta, sale
idéntico a la V1.

### `common/deadline.py` — el seguro

780 s de los 900. Suelta, de menos a más valioso: los empujones a un papel que
no llamó a su herramienta, la segunda vuelta de la junta, y por último el caso
entero, que `dispatch` cierra con el respaldo determinista. Un caso que se pasa
no puntúa bajo: puntúa cero y no escribe nada.

En un caso que va a tiempo no cambia nada. `CHIMERA_CASE_BUDGET_SECONDS=0` lo
desactiva, y es lo que usan las comparaciones byte a byte.

### Medido y descartado

* **Repartir los miembros del ensemble entre hilos.** Cada miembro tiene su
  propio `RandomState`, así que sería neutro; pero el trabajo es Python con el
  GIL cogido y con 4 hilos tardó **más** que en serie (>4 min frente a 146 s).
* **`VLLM_ENABLE_V1_MULTIPROCESSING=0`.** Quitar el subproceso `EngineCore`
  parecía ahorro seguro —no re-importar torch en un intérprete nuevo— y sale
  **peor**: 211,3 s frente a 154,1 s, con `warm_model` de 115 s a 165 s. La
  razón es justo el solape: como subproceso, el motor tiene su propio intérprete
  y su propio núcleo, y no pelea por el GIL con el hilo que puntúa los expertos.
* **Bajar `n_imputations`.** Cambia `epistemic`, `aleatoric` y `ci95`, y con
  ellos `confidence`. No es neutro.

### Dos trampas de medición, para quien venga después

1. **Un caso por proceso.** Los imputadores de la tarea 1 llevan
   `sample_posterior=True` y su `RandomState` viaja dentro del pickle, así que
   avanza con cada `transform`. Puntuar el mismo caso dos veces en un intérprete
   da números distintos —lo vimos con `ci95 [0,0658, 0,5956]` pasando a
   `[0,0663, 0,592]` sin cambiar nada—. En GC no importa, porque cada caso llega
   en su propio contenedor; en una comparación, lo invalida todo.
2. **El `case_id` está en el prompt.** `Board.HEAD` lo imprime en la cabecera
   del acta, así que dos `case_id` distintos son dos prompts distintos y dos
   trayectorias distintas. Con tres identificadores inventados distintos vimos
   la tarea 2 hacer 12, 12 y 7 llamadas al LLM, y estuvo a punto de parecer un
   cambio de comportamiento de la V1.1. No lo era. Las comparaciones usan
   `--case-id` fijo en los dos brazos.

## 3. Resultado

Los dos brazos con el **mismo** `case_id`, contenedor, `--cpuset-cpus 0-3`, caso
que la caché de expertos no tiene:

| | V1 | V1.1 | salida |
|---|---|---|---|
| T1 (interf0) | 274,4 s | **154,1 s** (−43,8%) | **idéntica byte a byte** |
| T2 (interf1) | 128,2 s | 122,2 s (−4,7%) | **idéntica byte a byte** |
| T3 (interf2) | 76,6 s | 77,3 s (+0,9%) | **idéntica byte a byte** |

Los seis ficheros de Grand Challenge salen iguales carácter a carácter. En T1
eso son 120 segundos menos por la misma decisión (`no`), la misma confianza
(`clear`) y el mismo texto.

T2 y T3 no bajan, y tiene explicación: T3 no tiene expertos que puntuar y su
reloj es casi todo carga del modelo; en T2 el precalentamiento esconde los 16,5 s
de expertos y `n_jobs=1` quita 14 s del grafo, pero la carga del modelo sube
otros tantos al competir por los 4 núcleos. T1 era la que estaba en riesgo y es
la que baja.

Evidencia agregada: `verification/resumen_v1_1.json`, que empareja los brazos
por `case_id`, compara los ficheros byte a byte y recoge lo que midieron las
comparaciones de expertos.

Fases. V1: `model_load` 76,9 + `mcp` 8,3 + `graph` 181,4. V1.1: `warm_model`
115,4 y `warm_prewarm` 116,5 corriendo **a la vez**, `mcp` 7,1 escondido del
todo, y el grafo reducido a 31,0 s de puro LLM. La contención entre la carga del
modelo y la puntuación se paga —el modelo pasa de 77 a 115 s— y aun así el
solape gana 120 s.

Y el aplazamiento se ve en el mismo T1 medido antes de aplicarlo: 211,5 s con
las tres variantes, 154,1 s calculando sólo las dos que se leen.

### El seguro, probado y no sólo escrito

Un seguro sin probar no cuenta. Con `CHIMERA_CASE_BUDGET_SECONDS=60` en un caso
que necesita 154 s:

```
"fallback": true, "cut": true, "budget_spent": 60.4, "budget_left": -0.4
```

Contenedor fuera en **63,9 s con exit 0** y los dos ficheros escritos y válidos.
Es lo que habría pasado en Development en vez de perder el caso entero.

El corte sale con `os._exit(0)` en cuanto la salida está en disco. No es
brusquedad gratuita: al cancelar la junta quedan hilos demonio donde estaban —uno
de ellos cargando vLLM—, y desmontar CUDA por debajo de ellos puede acabar en un
exit distinto de 0 con los ficheros ya escritos, que para Grand Challenge es un
caso perdido igual que si no hubiéramos escrito nada.

## 3.bis El fallo que sólo apareció al construir la imagen

La primera imagen de la V1.1 **no pasó** su propia compuerta: la tarea 3 se fue
al respaldo con

```
Task 3 case ENTREGA-2 failed; writing fallback
ModuleNotFoundError: No module named 'delete_final_versions_task_V1'
```

`task_3/experts_3/train/artifacts/spokesperson_candidate.joblib` —el portavoz
adoptado el 11-sep, volcado desde `experiments/survival_total.py` con
`pickle.dumps`— guarda su clase bajo la ruta **completa** del paquete de
entonces. Los cinco expertos de la tarea 3 guardan el módulo pelado `protocol`,
que `ModelReader.find_class` ya traducía; el portavoz, no.

**Por qué ninguna prueba lo cazó.** El árbol de la V1 sigue en el repo, así que
`pytest` lo importa sin problema. Y todas las corridas del perfilador montaban
el árbol de la V1.1 **dentro de la imagen de la V1**, que lleva
`/opt/app/delete_final_versions_task_V1/` cocido. El nombre viejo se resolvía
solo, en los dos sitios. Sólo al correr la imagen de la V1.1 —que no lo lleva— y
**sin montar código** apareció.

Es el mismo problema que el repo ya había resuelto una vez un nivel más abajo:
`common/chimera_experts/__init__.py` registra `sys.modules["chimera_experts"]`
porque los bundles guardan las clases con el nombre histórico del paquete. El
renombrado V1 → V1.1 lo reprodujo arriba.

Arreglado en `ModelReader.find_class`, comparando por el final de la ruta y no
por el nombre exacto del paquete, para que el próximo renombrado no lo rompa
otra vez. Y con dos pruebas que sí lo cazan
(`common/tests/test_reloj_v1_1.py`): una esconde
`delete_final_versions_task_V1` del intérprete con un `meta_path` que lanza el
mismo `ModuleNotFoundError` —y comprueba primero que el pickle **revienta** con
el desempaquetador estándar, para que la prueba no pase por vacía—, y la otra
recorre todos los binarios del árbol y falla si algún artefacto más pide el
nombre viejo.

**La lección para la próxima entrega:** la compuerta tiene que correr
`--no-mount` sobre la imagen construida. Montar código encima de otra imagen
comprueba el código, no la entrega.

## 4. Lo que hay que comprobar en la página del algoritmo

Fijar **A10G de 24 GiB**. La V1 capa la fracción de VRAM en `min(0,80, 19 GiB)`,
que en una T4 de 16 GiB deja al KV sin sitio para 32 k de contexto y manda todos
los casos al respaldo.
