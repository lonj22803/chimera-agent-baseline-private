# Lista de entrega — V1.1

Cada línea se marca sólo con evidencia en disco. Lo que no se ha comprobado, se dice.

## Contrato de salida

| regla | estado | evidencia |
|---|---|---|
| Slugs exactos de los seis sockets | **✅** | página del algoritmo; `contrato.py::GC_OUTPUTS` + test |
| Exactamente **dos** ficheros por interfaz | **✅** | `CHIMERA_SLUG_STRICT=canonical` por defecto; smoke 3/3 |
| T3 decisión `{event, months_to_recurrence}` | **✅ 75/75** | validación estricta, 0 incumplimientos |
| T3 razonamiento = cadena JSON suelta | **✅ 75/75** | el socket declara *Kind: String* |
| `variable_weights` completo en T1 y T2 | **✅ 0 incompletos** | 348 casos; era la causa del fallo anterior |
| Valida contra `Task{1,2,3}Output` | **✅ 423/423** | `verification/contrato_423.json` |
| `output/schema.py` intacto | **✅** | único fichero bloqueado del reto |

## Recursos y ejecución

| regla | límite | medido |
|---|---|---|
| VRAM (A10G 24 GB) | < 24 GB | **21 502 MiB** sostenido 3 h 30 min |
| RAM | 32 GB | **5,9 GiB** pico |
| Tiempo por caso | 15 min | **T1 154 s · T2 122 s · T3 74 s** — un contenedor por caso, 4 núcleos, caso no cacheado |
| Sin red | `--network none` | ✅ en cobertura y smoke |
| Cobertura completa | 423 casos | **✅ 423/423**, exit 0, sin OOM |
| Smoke de entrega, imagen tal cual | 3 interfaces | **✅ exit 0, 2 ficheros cada una** |

### El renglón del tiempo, y por qué el de la V1 engañaba

La V1 puso en esta casilla «T1 27 s · T2 46 s · T3 4 s». Son ciertos y son **la
medida equivocada**: salen de la corrida de cobertura, donde un solo vLLM sirve
195 casos y los expertos vienen de `panel_cache.json`. Grand Challenge no hace
eso: levanta **un contenedor por caso** y ningún caso del test está en la caché.
Medido como corre allí, la V1 tarda **274 s** en la tarea 1, no 27.

El renglón sólo se puede marcar con el perfilador, que reproduce las dos cosas
—4 núcleos reales y un `case_id` que la caché no conoce—:

```
python3 delete_final_versions_task_V1_1/verification/gc_profile.py \
    --cpuset 0-3 --interfaces 0,1,2 --image chimera_agent_baseline_v1_1 \
    --package delete_final_versions_task_V1_1 --tag entrega
```

Y hay que mirar `fallback: false` en la línea `gc_delivery` de cada interfaz: un
caso que cae al respaldo escribe salida válida y puntúa peor, así que «exit 0 y
dos ficheros» no basta como prueba.

### Smoke de la imagen que se sube — 2026-09-11 19:58:58, `chimera_agent_baseline_v1_1` (`31ffdd434e70`)

**Sin montar código**: sólo `/input`, `/output` y el modelo, con el `ENTRYPOINT` de la
imagen y `--network none` — el `docker run` de Grand Challenge. Y con `--cpuset-cpus 0-3`
más un `case_id` que `panel_cache.json` no contiene: las dos condiciones que la V1 nunca
reprodujo y que escondían el fallo de tiempo.

| interfaz | tarea | exit | ficheros | segundos | respaldo | llamadas LLM | VRAM MiB |
|---|---|---:|---|---:|---|---:|---:|
| 0 | biopsia | **0** | los 2 canónicos | **133.1** | `false` | 7 | 21502 |
| 1 | tratamiento | **0** | los 2 canónicos | **124.3** | `false` | 7 | 21502 |
| 2 | recurrencia | **0** | los 2 canónicos | **76.9** | `false` | 2 | 21502 |

Límite de la fase: **900 s por caso**. `respaldo: false` en las tres, así que estos
tiempos son de la junta completa y no de la salida degradada — que es la comprobación que
«exit 0 y dos ficheros» no da.

La primera imagen **no pasó** esta compuerta: la tarea 3 caía al respaldo por un pickle
que pedía el paquete con su nombre antiguo. Ver la sección 3.bis de
[BITACORA_V1_1.md](BITACORA_V1_1.md).

Comando:

```
python3 delete_final_versions_task_V1_1/verification/gc_profile.py \
    --cpuset 0-3 --interfaces 0,1,2 --image chimera_agent_baseline_v1_1 --no-mount --case-id ENTREGA
```

### Smoke final — 11-sep-2026 08:19, imagen `chimera_agent_baseline_v1`

Sin montar código: sólo `/input`, `/output` y el modelo, como hará Grand Challenge.

| interfaz | tarea | exit | ficheros | segundos |
|---|---|---|---|---:|
| 0 | biopsia | **0** | los 2 canónicos | 118 |
| 1 | tratamiento | **0** | los 2 canónicos | 133 |
| 2 | recurrencia | **0** | los 2 canónicos | 74 |

Contenido verificado contra `contrato.py::GC_OUTPUTS`: T1 con **10** claves de
`variable_weights`, T2 con **11** —el fallo que tumbó Development, cerrado— y T3 con su
razonamiento como **cadena JSON suelta**.

## Artefactos

### Lo que se sube — 11-sep-2026

| qué | fichero | tamaño | sha256 |
|---|---|---:|---|
| Container Image | `chimera_agent_baseline_v1_1_2026-09-11_19-58-58.tar.gz` | 10 727 580 462 B | `c8eae1729acc0fafe9425625dff59d2feeb5a12588320928f8e89537913ade4a` |
| Model | `model.tar.gz` (**sin cambios**) | 8,3 GB | el mismo que ya está subido |

`gzip -t` pasa, así que el tarball no está truncado — que con el disco al 98% no era
gratis. El modelo no se ha tocado desde el 9-sep, así que **no hace falta volver a
subirlo**: la entrada Model que ya existe sirve.

Imagen `31ffdd434e70`, creada 2026-09-11 19:58:58, construida con `./do_build_v1_1.sh`
(`Dockerfile_V1_1`). La imagen de la V1 sigue existiendo como tag aparte, así que volver
atrás es reenviar la anterior.


- **Imagen**: entra por `inference_v1_1.py`, que importa el `inference.py` real y sustituye
  una sola función. Lleva **sólo V1.1**; la V1 no viaja dentro y sigue existiendo como tag
  aparte, así que volver atrás es reenviar su imagen. Se construye con
  `./do_build_v1_1.sh` (Dockerfile_V1_1).
- **Modelo aparte**: `model.tar.gz` se sube como *Model* independiente; GC lo extrae en
  `/opt/ml/model`.

## Pendiente del usuario, no del código

- [ ] **Revocar el `HF_TOKEN` de `.env`**. No entra en la imagen —la auditoría no halló
      credenciales— pero sigue vivo en la cuenta de Hugging Face.
- [ ] Declarar **Gemma-4-E2B** y **EmbeddingGemma** en el Algorithm.
- [ ] Elegir **A10G, ≤32 GB RAM** y las tres interfaces.
- [ ] **Cuota: 5 envíos en validación** (cuenta el mejor), **1 solo en test**.

## Lo que la entrega NO demuestra

- La cobertura de 423 casos es **contrato, no calidad**: incluye casos sin etiqueta.
- Los expertos de T1 y T2 se ajustaron sobre la cohorte etiquetada; el techo honesto de
  T1 fuera de muestra es 0,7607 frente al 0,8390 desplegado.
- El c-index de T3 en modo `deployed` (0,8832) es **dentro de muestra**. El defendible
  es el anidado, **0,8235**.
- El Debug anterior dio 0,8406 sobre **12 casos**: ni comparable ni un objetivo.
