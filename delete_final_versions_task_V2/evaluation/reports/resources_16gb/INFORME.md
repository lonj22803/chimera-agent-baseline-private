# E11 — Arquitectura completa en 16 GB

**Estado: ensayo preliminar superado. Validación física pendiente.**
Fecha: 11–12 de septiembre de 2026. PLAN §13.1 y §11 (E11).

## Qué se pedía

> «Superar E11 en una GPU real de 16 GB con la ruta completa, sin OOM ni
> respaldos provocados por falta de memoria. Una configuración que requiere
> 24/32 GB no es entregable V2.» — PLAN §10.5

Y con una condición que es la mitad del ejercicio: **sin quitar nada**.
«"Funcionar tal cual" significa conservar especialistas, pizarra, consultas,
contraste, protocolo, presidente, modalidades necesarias y contratos
oficiales.»

## El diagnóstico: el consumo no era del modelo

Los 21 502 MiB del smoke de la V1 no los pedía el modelo. Salían de cómo se
repartía lo que sobraba en la tarjeta.

`gemma-4-E2B-it` tiene **1 KV head**, `head_dim` 256, y 28 de sus 35 capas usan
ventana deslizante de 512. Eso hace que un contexto **completo** de 32 768
tokens ocupe **0,29 GiB de KV**. Medido, no estimado: con 12 GiB de presupuesto
vLLM reporta `GPU KV cache size: 106,443 tokens` y `Maximum concurrency for
32,768 tokens per request: 3.25x`; 0,93 ÷ 3,25 = 0,286 GiB.

La V1 reservaba ~9,1 GiB de KV —los `31.59x` que aparecen en el log de Grand
Challenge— porque `gpu_memory_utilization` se queda con todo lo libre. El
contenedor atiende **un paciente por arranque**. Esa concurrencia no compraba
nada: era memoria reservada para secuencias simultáneas que nunca existen.

## Qué se cambió

Nada de la arquitectura. Sólo el reparto:

| Ajuste | V1 / V1.1 | V2 | Por qué |
|---|---|---|---|
| Tope del motor | 19 GiB, fracción sobre el total | `min(12, min(14, total−1)−2)` GiB | Techo de §13.1 |
| KV | lo que sobre (~9,1 GiB) | **fijo en 1 GiB** | 3,4 contextos completos; el pico deja de seguir al tamaño de la tarjeta |
| `max_num_seqs` | por omisión | **1** | Un paciente por contenedor |
| Prefill troceado | 8192 | **8192, sin tocar** | Ver abajo: 4096 ahorra 0,73 GiB pero cambia la prosa |
| Ranuras de imagen | por omisión | **0** | No se envía ninguna imagen al LLM en ninguna ruta |
| Contexto | 32 768 | **32 768** | Sin recortar |
| Precisión | bf16 | **bf16** | Sin cuantizar |
| Expertos, pizarra, MCP, embeddings | — | **iguales** | Ninguno eliminado |

No se ha llegado a necesitar el paso 4 de §13.1 (`cpu_offload_gb`) ni el 5
(contexto compacto) ni el 6 (cuantización). El perfil cabe con las entradas y
la precisión originales, que es el orden que el PLAN exige.

**Advertencia registrada:** al fijar `kv_cache_memory_bytes`, vLLM **se salta el
perfilado** y `gpu_memory_utilization` deja de gobernar —lo dice él mismo en el
log—. El límite efectivo pasa a ser el KV fijado más pesos y activaciones. La
fracción queda como declaración, no como tope. Ambas formas se midieron y las
dos caben, pero conviene no confundirlas.

## Tramo 1 — el motor por la ruta real

`verification/e11_motor.py` compone la misma configuración de Hydra que
`gc_entry`, aplica el perfil y llama a `models.load_model`. Un proceso lastre
ocupa la diferencia para que la tarjeta ofrezca de verdad el espacio de una de
16 GiB.

RTX 5090 (sm120), driver 595.84, vLLM 0.25.0, torch 2.11.0+cu129.

| Perfil | VRAM ofrecida | ¿Arranca? | Pico neto |
|---|---:|---|---:|
| V1.1 `common/runtime.py` | 14,52 GiB | **No** | — |
| V2 §13.1 | 15,51 GiB | Sí, y genera | **12 573 MiB** |

```
ValueError: Free memory on device cuda:0 (14.52/31.36 GiB) on startup is less
than desired GPU memory utilization (0.6059, 19.0 GiB).
```

En el contenedor ese fallo **no es un crash**: `gc_entry` lo captura y escribe
el respaldo determinista. Todos los casos puntuarían con la salida de
emergencia. El PLAN lo prohíbe expresamente como forma de cumplir E11.

Ficheros: `e11_motor_v2.json`, `e11_motor_v1_1.json`, `e11_motor_v1_1_fallo.log`.

## Tramo 2 — las tres interfaces, en contenedor, sin montar código

`verification/e11_contenedor.py` pone el lastre y delega en el perfilador de la
V1.1, que es quien ya sabe fijar los 4 núcleos de la A10G e inventar un
`case_id` que la caché de expertos no conoce —la única ruta que existe en el
test real—. Imagen `chimera_agent_baseline_v2` **tal cual, con su propio
ENTRYPOINT**: montar el árbol sobre otra imagen comprueba el código, no la
entrega.

Tarjeta ofrecida: 15 882 MiB. `--cpuset 0-3`, `--memory 32g`, `--network none`.

| Interfaz | Segundos | Salida | Ficheros | Pico neto VRAM | RSS |
|---|---:|---:|---:|---:|---:|
| 0 — biopsia | 133,9 | 0 | 2/2 | 13 332 MiB | 3 367 MiB |
| 1 — tratamiento | 121,9 | 0 | 2/2 | 13 154 MiB | 3 382 MiB |
| 2 — recurrencia | 72,4 | 0 | 2/2 | 13 154 MiB | 2 865 MiB |

Cero OOM, cero respaldos, cero expertos omitidos. RSS muy por debajo de los
32 GiB de RAM.

**La cifra operativa es la de una interfaz: 13 332 MiB**, porque Grand Challenge
arranca un contenedor por paciente. El muestreo de toda la corrida marca 13 828
MiB, pero eso incluye el solape al encadenar tres contenedores en la misma
tarjeta, que allí no ocurre. Contra el techo de 14 336 MiB quedan 1 004 MiB por
interfaz; contra una tarjeta de 16 384 MiB, 3 052.

Que el perfil estaba activo **dentro** de la imagen lo dice su propio log:

```
reserved 1.0 GiB memory for KV Cache as specified by kv_cache_memory_bytes config
GPU KV cache size: 136,184 tokens
Maximum concurrency for 32,768 tokens per request: 4.16x
```

4,16× frente a los 31,59× del log que Grand Challenge devolvió.

## Igualdad de contrato, decisión y texto

Comparado con la misma imagen de la V1.1 corrida con el **mismo `case_id`**
(`gc_profile_20260912_000200_v11_unseen`, corrida de referencia; ese identificador viaja en la cabecera
del acta, así que compararlo con otro no mide nada):

**Las seis salidas son idénticas byte a byte.** Decisiones, meses, evento,
confianza, `reveal_sequence`, los 10 y 11 pesos y toda la prosa.

Ninguna corrida cayó al respaldo (`"fallback": false`, `"cut": false`).

Y la imagen reconstruida desde el árbol actual reproduce las seis salidas byte a
byte: dentro de una misma configuración el motor es determinista.

### Lo que costó conseguir esa igualdad

La primera versión del perfil acotaba el prefill a 4096 tokens. Con eso T2 y T3
salían idénticas, pero **la prosa de T1 cambiaba** —misma decisión, misma
confianza, mismas consultas, mismos pesos—. Mover las fronteras del troceado
cambia el orden de reducción en coma flotante y, a temperatura 0, eso basta para
cambiar un token. Comprobado:

| Prefill | Pico neto (interf 0) | Margen al techo | Salida frente a V1.1 |
|---|---:|---:|---|
| 4096 | 12 584 MiB | 1 752 MiB | prosa de T1 distinta |
| **8192 (elegido)** | 13 332 MiB | 1 004 MiB | **byte a byte idéntica** |

Se eligió 8192. Para un cambio que sólo debe tocar la gestión de memoria, poder
demostrar salida idéntica vale más que 0,73 GiB de margen que no se necesitan.
`CHIMERA_PREFILL_TOKENS=4096` recupera el margen si hiciera falta; la decisión y
los pesos no cambian en ninguno de los dos casos.

## Coste temporal: neutral

Misma imagen sin montar, mismo `case_id`, `--cpuset 0-3`:

| Interfaz | V1.1 | V2 (16 GiB) | Δ |
|---|---:|---:|---:|
| 0 — biopsia | 136,2 s | 133,9 s | −2,3 |
| 1 — tratamiento | 125,9 s | 121,9 s | −4,0 |
| 2 — recurrencia | 77,1 s | 72,4 s | −4,7 |

Consistente en dirección pero pequeño. La explicación plausible es que asignar
1 GiB de KV cuesta menos que 9, pero **no se ha aislado** y con una sola corrida
por brazo no se distingue de la variación entre arranques. No se reclama como
mejora de latencia, y desde luego **no es la solución al problema temporal**.
Nótese además que V2 corrió con la tarjeta recortada y V1.1 no podía: la
comparación es en igualdad de CPU, no de VRAM ofrecida.

## Lo que este informe NO demuestra

1. **No es una GPU física de 16 GB.** El recorte es por lastre en una RTX 5090
   de 32 GiB. El PLAN: «el cierre exige una GPU física de 16 GB identificada.
   Si no está disponible, el estado es pendiente de validación física, nunca
   cumplido». Ese es el estado.
2. **No cubre una T4.** Si la tarjeta de 16 GB fuese Turing (sm75), no tiene
   bf16 nativo ni los mismos kernels que Blackwell. Caber en memoria no
   demuestra que arranque allí.
3. **No arregla el límite de tiempo.** El rechazo de Development del 10-sep fue
   temporal, no de memoria: el propio `31.59x` de su log prueba que había una
   A10G de 24 GiB con memoria de sobra. Este perfil es neutral en tiempo —y así
   debe ser—. El riesgo temporal sigue vivo y es asunto de otra fase.
4. **No mejora la puntuación.** No cambia ni una decisión clínica. Es un cambio
   operativo, y el PLAN §10.5 es explícito: «Eficiencia: mismas decisiones y
   fidelidad con menor latencia/coste puede justificar un cambio operativo,
   pero no se vende como mejora estadística».

## Artefactos

Imagen comprobada: `chimera_agent_baseline_v2`, `sha256:f9a2e4819b5518f52425f96d057ac1ba108f72c1385dc2032c8a1940683a9326`. Reconstruible con
`./do_build_v2.sh`; la compuerta con
`python3 delete_final_versions_task_V2/verification/e11_contenedor.py --interfaces 0,1,2`.

La imagen contiene de V2 **sólo** `runtime/` y `verification/inference_v2.py`.
Planes, bitácoras, auditorías, pruebas y bancos de medida se quedan fuera por
`.dockerignore`: no se usan en ejecución, y si viajasen, editar una frase de
documentación invalidaría la imagen ya comprobada.

| Fichero | Qué es |
|---|---|
| `e11_motor_v2.json` | Tramo 1, perfil V2 por la ruta real de carga (medido con prefill 4096) |
| `e11_motor_v1_1.json` + `.log` | Tramo 1, perfil V1.1: el `ValueError` que impide arrancar en 16 GiB |
| `e11_contenedor_v2_definitiva.json` + `gc_profile_..._v2_definitiva/` | **La compuerta que vale**: imagen final, tres interfaces, sin montar código |
| `e11_contenedor_v2_prefill8192.json` + su `gc_profile_...` | El experimento que fijó el prefill en 8192 |
| `e11_contenedor_v2_e11.json`, `..._e11_final.json`, `..._entrega.json` y sus `gc_profile_...` | Corridas intermedias; se conservan como traza, no como resultado |

La referencia V1.1 con el mismo `case_id` vive en
`../../../../delete_final_versions_task_V1_1/verification/gc_profile_20260912_000200_v11_unseen/`.

## Cómo repetirlo

```bash
# Tramo 1: el motor por la ruta real, con la tarjeta recortada a 16 GiB
.venv/bin/python delete_final_versions_task_V2/verification/e11_motor.py --perfil v2
.venv/bin/python delete_final_versions_task_V2/verification/e11_motor.py --perfil v1_1   # falla, a propósito

# Tramo 2: las tres interfaces en contenedor, sin montar código
./do_build_v2.sh
.venv/bin/python delete_final_versions_task_V2/verification/e11_contenedor.py --interfaces 0,1,2

# Las pruebas del perfil, sin GPU
PYTHONPATH=.:src .venv/bin/python -m pytest delete_final_versions_task_V2/verification/test_perfil.py -q
```
