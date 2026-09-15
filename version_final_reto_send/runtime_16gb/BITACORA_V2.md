# Bitácora V2 — Fase A y E11 (perfil obligatorio de 16 GB)

Lo que hay aquí es **una fase del PLAN, no el PLAN entero**. El plan estima
8–14 jornadas de núcleo más cómputo; esta entrada cubre la Fase A en lo que
toca a E11 y deja intactas las fases B a E.

## 0. Por qué esta fase y no otra

La entrega de Development del 10-sep-2026 no cayó por memoria. El correo de
Grand Challenge lo dice sin ambigüedad:

> La evaluación se interrumpió porque excedió el límite de tiempo. No se generó
> ninguna excepción. El registro muestra que la inferencia seguía ejecutándose
> con normalidad cuando se detuvo el proceso.

Y su propio log lo confirma: `Maximum concurrency for 32,768 tokens per
request: 31.59x` sólo cuadra con una A10G de 24 GiB. **Allí sobraba memoria.**
El agujero está entre `21:37:54 init engine ... 21.77 s` y `21:43:02 chat
template content format` — 308 s con el motor ya cargado y sin generar nada.
Eso es CPU: MCP, el servicio de embeddings y la puntuación en vivo de los
expertos. La V1.1 ya atacó ese tramo (274 → 154 s) y es de fecha posterior al
correo, así que **todavía no ha sido evaluada**.

Entonces, ¿por qué el perfil de 16 GB? Porque es requisito obligatorio del PLAN
(§13.1) y porque la V1 **no puede** correr en una tarjeta de 16 GiB: eso se
midió aquí y se documenta abajo. No porque arregle el tiempo. Confundir las dos
cosas sería justo el error que el PLAN pide evitar.

## 1. Lo que se ha cambiado

| Fichero | Estado | Qué hace |
|---|---|---|
| `runtime/resources.py` | nuevo | El perfil de §13.1: inventario NVML, techo, presupuesto y opciones efectivas |
| `verification/inference_v2.py` | nuevo | Entrada de V2: la tubería de la V1.1 con `gc_entry.configure` sustituido |
| `verification/e11_motor.py` | nuevo | E11 tramo 1: el perfil por la ruta real de carga, con lastre de VRAM |
| `verification/e11_contenedor.py` | nuevo | E11 tramo 2: las tres interfaces en contenedor con la tarjeta recortada |
| `verification/test_perfil.py` | nuevo | 7 pruebas, sin GPU; la principal comprueba que el perfil **llega** al motor |
| `../Dockerfile_V2`, `../do_build_v2.sh` | nuevos | Imagen de V2; calcados de los de la V1.1 |
| `../.dockerignore` | modificado | Deja fuera de la imagen planes, bitácoras, auditorías, pruebas y bancos de medida de V2 |
| `../src/chimera_agent_baseline/models/__init__.py` | **modificado** | Único fichero de código tocado fuera de V2: +16 líneas, −1 |

El cambio en `models/__init__.py` es aditivo y está justificado por el PLAN:
«Añadir variables de entorno sin conectarlas no cumple el requisito». Es el
constructor real de `vllm.LLM`. Si `cfg.generation` no trae las claves nuevas,
el motor arranca **exactamente** igual que en V1 y V1.1; con ellas, pasa
`max_num_seqs`, `max_num_batched_tokens`, `kv_cache_memory_bytes` y
`limit_mm_per_prompt`. No se ha tocado `output/schema.py` ni el árbol de la
V1.1.

En esta fase V2 **no cambia ni una decisión clínica**: mismos runners, mismos
prompts, mismos expertos, misma pizarra. E11 lo exige así — «variando primero
sólo gestión de memoria».


Sobre el `.dockerignore`: al principio el Dockerfile copiaba el árbol de V2
entero, así que **corregir una frase de esta bitácora invalidaba la imagen ya
comprobada**. En ejecución la imagen sólo necesita `runtime/` y la entrada; todo
lo demás sale fuera. Es también lo que pide el PLAN §13: «El Docker futuro usa
una lista explícita de artefactos […] No copiar `data/task1/` entero por
comodidad, ground truth, reports con tablas OOF, el evaluador, datos de
validación ni el árbol de experimentos».

## 2. De dónde salían los 21,5 GiB

No del modelo. De cómo se repartía lo que sobraba.

Este modelo tiene **1 KV head**, `head_dim` 256 y 28 de sus 35 capas con
ventana deslizante de 512. Un contexto completo de 32 768 tokens ocupa
**0,29 GiB de KV** — medido, no estimado: a 12 GiB de presupuesto vLLM reporta
`GPU KV cache size: 106,443 tokens` con `Maximum concurrency ... 3.25x`, y
0,93/3,25 = 0,286.

La V1 reservaba ~9,1 GiB de KV (31,59×) porque `gpu_memory_utilization` se
queda con todo lo libre de la tarjeta. El contenedor atiende **un paciente por
arranque**: esa concurrencia no compraba absolutamente nada.

El perfil de V2 fija el KV en 1 GiB —3,4 contextos completos— y con eso el pico
**deja de depender del tamaño de la tarjeta**. En una A10G de 24 GiB este mismo
perfil también se queda en ~12 GiB en vez de subir a 21,5.

Una advertencia que hay que registrar, porque vLLM la emite: al fijar
`kv_cache_memory_bytes` el motor **se salta el perfilado** y `gpu_memory_utilization`
deja de gobernar. El presupuesto pasa a imponerse por el KV fijado, no por la
fracción. Está medido en ambas formas y las dos caben, pero la fracción queda
como declaración, no como límite efectivo.

## 3. Medición, tramo 1: el motor por la ruta real

`verification/e11_motor.py` no simula el constructor: compone la misma
configuración de Hydra que `gc_entry`, aplica el perfil y llama a
`chimera_agent_baseline.models.load_model`. Un lastre en otro proceso ocupa la
diferencia para que la tarjeta ofrezca de verdad el espacio de una de 16 GiB.

RTX 5090, driver 595.84, vLLM 0.25.0, torch 2.11.0+cu129, bf16, contexto 32 768.

| Perfil | VRAM ofrecida | Resultado | Pico neto |
|---|---:|---|---:|
| V1.1 (`common/runtime.py`, tope 19 GiB) | 14,52 GiB | **no arranca** | — |
| V2 (§13.1) | 15,51 GiB | arranca y genera | **12 573 MiB** |

El fallo de la V1.1 es literal:

```
ValueError: Free memory on device cuda:0 (14.52/31.36 GiB) on startup is less
than desired GPU memory utilization (0.6059, 19.0 GiB).
```

En el contenedor eso no sería un crash ruidoso: caería al respaldo determinista
y **todos los casos puntuarían con la salida de emergencia**. Es exactamente lo
que el PLAN prohíbe llamar cumplimiento: «no declarar cumplimiento mediante
respaldos».

El pico de V2, 12 573 MiB = 12,28 GiB, queda bajo el techo de 14 GiB de §13.1.
Repetido en dos corridas independientes dio el mismo valor al MiB.

**Aviso de lectura:** este tramo se midió con el prefill en 4096, que era el
valor por omisión del perfil en ese momento. La sección 5 explica por qué acabó
subiendo a 8192 y la 7 da la cifra de la configuración entregada: 13 332 MiB.
Lo que este tramo demuestra —que la V1.1 no arranca en 16 GiB y V2 sí— no
depende de ese ajuste.

## 4. Ensayo preliminar, no cierre

El lastre recorta una tarjeta de 32 GiB; **no es una GPU física de 16 GB**. El
PLAN es explícito: «Limitar memoria en una tarjeta mayor sirve como ensayo
preliminar; el cierre exige una GPU física de 16 GB identificada. Si no está
disponible, el estado es **pendiente de validación física**, nunca cumplido».

Ese es el estado: **pendiente de validación física**.

Hay además un riesgo que el ensayo no cubre y conviene no tapar: si la tarjeta
de 16 GB fuese una **T4**, es Turing (sm75) y no tiene bf16 nativo ni los
mismos kernels. Este ensayo corre en Blackwell (sm120). Caber en memoria no
demuestra que el mismo modelo arranque en esa arquitectura.

## 5. El prefill, y por qué la salida acabó siendo idéntica

La primera versión del perfil acotaba el prefill troceado a 4096 tokens. Ahorra
~0,73 GiB de activaciones y parecía gratis: el contexto no se toca y la decisión
tampoco.

No era gratis. Con `case_id` idéntico, T2 y T3 salían byte a byte iguales a la
V1.1, pero en T1 **cambiaba la prosa** —misma decisión `no`, misma confianza,
mismas consultas, los 10 pesos iguales, otro texto—:

- V1.1: «Stable MRI finding and low PSA density argue against repeat biopsy.»
- V2 con 4096: «Decision is no biopsy as PI-RADS 2 and PSAD 0.14 align with
  low-risk profile. The prior biopsy grade is not recorded…»

La hipótesis era que mover las fronteras del troceado cambia el orden de
reducción en coma flotante y, a temperatura 0, eso basta para cambiar un token.
Se comprobó corriendo la interfaz 0 con `CHIMERA_PREFILL_TOKENS=8192`:

| Prefill | Pico neto | Margen al techo | Salida frente a V1.1 |
|---|---:|---:|---|
| 4096 | 12 584 MiB | 1 752 MiB | prosa de T1 distinta |
| 8192 | 13 332 MiB | 1 004 MiB | **byte a byte idéntica** |

Hipótesis confirmada, y con ella la decisión: **el perfil se queda en el 8192
por omisión de vLLM**. Para un cambio que sólo debe tocar la gestión de memoria,
poder demostrar salida idéntica vale más que 0,73 GiB de margen que no se
necesitan. `CHIMERA_PREFILL_TOKENS=4096` lo recupera si algún día el margen
manda.

Merece la pena registrar el orden en que salió esto, porque es el que hay que
repetir: primero se comparó con el `case_id` equivocado (`ENTREGA2-*` contra
`UNSEEN-*`) y la prosa difería en T1 **y** en T3. Ese identificador viaja dentro
de la cabecera del acta, así que cambia el prompt: la comparación no medía nada.
Repetida con el mismo `case_id`, T3 resultó idéntica y sólo quedó T1 por
explicar.

## 6. Reproducibilidad

La imagen reconstruida desde el árbol actual devuelve las **seis salidas byte a
byte iguales** a la corrida anterior. Dentro de una misma configuración el
motor es determinista; lo que no es comparable son dos configuraciones de
troceado distintas, como acaba de verse.

## 7. Resultado de la compuerta de entrega

Imagen `chimera_agent_baseline_v2` reconstruida desde el árbol final y corrida
**sin montar código**, con la tarjeta recortada a 15 882 MiB y `--cpuset 0-3`:

| Interfaz | Segundos | Salida | Pico neto | Ficheros |
|---|---:|---:|---:|---:|
| 0 | 133,9 | 0 | 13 332 MiB | 2/2 |
| 1 | 121,9 | 0 | 13 154 MiB | 2/2 |
| 2 | 72,4 | 0 | 13 154 MiB | 2/2 |

**Las seis salidas son byte a byte idénticas** a las de la V1.1 con el mismo
`case_id`. Cero OOM, cero respaldos, cero expertos omitidos, RSS ≤ 3,4 GiB.

Frente al smoke de la V1: **21 502 → 13 332 MiB**, sin recortar contexto, sin
cuantizar y sin quitar una sola pieza de la junta.
