# Lista de entrega — V2 (perfil de 16 GB)

Cada línea se marca sólo con evidencia en disco. Lo que no se ha comprobado, se dice.

## Qué es esta entrega, y qué no

V2 es, **en esta fase, la V1.1 con la gestión de memoria sustituida**. No cambia
decisiones, prompts, expertos ni el grafo: E11 lo exige así —«variando primero
sólo gestión de memoria»—. Las fases B a E del PLAN (representación verificable,
corrector, supervivencia, rama multimodal) **no están implementadas**.

Por tanto: **no se espera que puntúe distinto de la V1.1.** Lo que aporta es
poder correr en una tarjeta de 16 GB, donde la V1.1 no arranca.

## Contrato de salida

| regla | estado | evidencia |
|---|---|---|
| Slugs exactos de los seis sockets | **✅** | heredado de V1.1; mismo `gc_entry` y mismo `contrato.py` |
| Exactamente **dos** ficheros por interfaz | **✅ 3/3** | compuerta de entrega, imagen sin montar |
| Salidas idénticas a la V1.1 | **✅ 6/6 byte a byte** | mismo `case_id`, ver INFORME |
| `output/schema.py` intacto | **✅** | único fichero bloqueado del reto |
| Forma de los seis JSON | **✅** | idéntica a la entrega V1.1 que pasó Debug |

**Lo que NO se ha vuelto a medir:** la cobertura de 423 casos. Se corrió para la
V1.1, no para V2. El argumento de que se hereda es fuerte —salida byte a byte
idéntica en las tres interfaces y ni una línea de decisión tocada— pero **es un
argumento, no una medición**. Si hay tiempo antes de enviar, vale la pena
repetirla.

## Recursos y ejecución

| regla | límite | medido |
|---|---|---|
| VRAM | 16 GB (requisito §13.1) | **13 332 MiB** pico por contenedor |
| Techo interno §13.1 | 14 336 MiB | ✅ 1 004 MiB de margen |
| RAM | 32 GB | **3,4 GiB** pico |
| Tiempo por caso | 900 s | **T1 133,9 s · T2 121,9 s · T3 72,4 s** |
| Sin red | `--network none` | ✅ |
| Respaldos por memoria | 0 | ✅ `fallback: false` en las tres |
| Contexto y precisión | sin degradar | **32 768 y bf16**, sin cuantizar |

### Compuerta de entrega — imagen `chimera_agent_baseline_v2` (`f9a2e4819b55`)

**Sin montar código**: sólo `/input`, `/output` y el modelo, con el `ENTRYPOINT` de
la imagen y `--network none`. Con `--cpuset-cpus 0-3` y un `case_id` que
`panel_cache.json` no contiene. Y con la tarjeta recortada por lastre a
**15 882 MiB**, el espacio de una de 16 GiB.

| interfaz | tarea | exit | ficheros | segundos | respaldo | VRAM neta MiB |
|---|---|---:|---|---:|---|---:|
| 0 | biopsia | **0** | los 2 canónicos | **133,9** | `false` | 13 332 |
| 1 | tratamiento | **0** | los 2 canónicos | **121,9** | `false` | 13 154 |
| 2 | recurrencia | **0** | los 2 canónicos | **72,4** | `false` | 13 154 |

```
python3 version_final_reto/runtime_16gb/e11_contenedor.py --interfaces 0,1,2
```

Y el contraste que justifica la entrega: con esa misma tarjeta recortada, el
perfil de la V1.1 **no arranca el motor** —`ValueError`, pide 19 GiB— y todos los
casos caerían al respaldo determinista.

## Artefactos

### Lo que se sube — 12-sep-2026

| qué | fichero | tamaño | sha256 |
|---|---|---:|---|
| Container Image | `chimera_agent_baseline_v2_2026-09-12_00-28-50.tar.gz` | 10 727 605 884 B | `70cfec356170ff994791997db0d4babc2708c458497434f62e0421bac6d44b5b` |
| Model | `model.tar.gz` (**sin cambios**) | 8,3 GB | el mismo que ya está subido |

Comprobado **dentro del tarball**, no sólo en el Docker local:

- `gzip -t` pasa: no está truncado —con el disco al 98% eso no era gratis—.
- `manifest.json` declara `chimera_agent_baseline_v2:latest`, 25 capas.
- La config lleva `ENTRYPOINT ["python3", "inference_v2.py"]`, `WorkingDir
  /opt/app`, `User user`, `PYTHONPATH=/opt/app:/opt/app/src` y
  `VLLM_USE_FLASHINFER_SAMPLER=0`, creada `2026-09-12T00:28:50` — la misma
  imagen que pasó la compuerta, no otra.

De V2 la imagen lleva **sólo** `runtime/` y `verification/inference_v2.py`:
planes, bitácoras, auditorías, pruebas y bancos de medida quedan fuera por
`.dockerignore`. Se construye con `./do_build_v2.sh` (`Dockerfile_V2`) y se
empaqueta con `./do_save_v2.sh`, que ahora aborta si no hay 12 GiB libres.

Las imágenes y los tarballs de la V1 y la V1.1 siguen donde estaban: volver
atrás es reenviar el anterior y nada más.

## Pendiente del usuario, no del código

- [ ] **Decidir la instancia.** Si sigue siendo **A10G de 24 GiB**, la V1.1 vale
      igual y la V2 no aporta nada que no sea margen. La V2 es lo que hace falta
      si la tarjeta es de **16 GB**.
- [ ] **Si la tarjeta de 16 GB fuese una T4**: es Turing (sm75), sin bf16 nativo.
      Este ensayo corrió en Blackwell (sm120). Caber en memoria **no demuestra**
      que arranque allí. Habría que probarlo antes de gastar un envío.
- [ ] **Revocar el `HF_TOKEN` de `.env`** (sigue pendiente desde la V1.1).
- [ ] Declarar **Gemma-4-E2B** y **EmbeddingGemma** en el Algorithm.
- [ ] **Cuota: 5 envíos en validación** (cuenta el mejor), **1 solo en test**.
- [ ] El **modelo no cambia**: la entrada *Model* ya subida sirve tal cual.

## Lo que esta entrega NO resuelve

- **El rechazo de Development fue por tiempo, no por memoria.** El correo lo dice
  y el `31.59x` de su log prueba que había una A10G de 24 GiB con VRAM de sobra.
  El perfil es **neutral en tiempo**. Quien espere que esto cierre el timeout se
  va a llevar el mismo rechazo.
- **Validación física pendiente.** El recorte a 16 GiB es por lastre en una RTX
  5090 de 32 GiB, no una GPU de 16 GB identificada. El PLAN es explícito: eso es
  **ensayo preliminar**, nunca cierre.
- **No mejora la puntuación.** Ni pretende: no cambia una sola decisión. Las
  limitaciones de calidad de la V1.1 siguen todas vigentes —techo honesto de T1
  fuera de muestra 0,7607 frente al 0,8390 desplegado; c-index de T3 defendible
  0,8235, no 0,8832—.
- **La cobertura de 423 casos no se ha repetido** para V2. Ver arriba.
