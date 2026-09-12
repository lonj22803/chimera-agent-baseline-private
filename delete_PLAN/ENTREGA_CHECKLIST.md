# Lista de entrega — V1

Cada línea se marca sólo con evidencia en disco. Lo que no se ha comprobado, se dice.

## Contrato de salida

| regla | estado | evidencia |
|---|---|---|
| Slugs exactos de los seis sockets | **✅ confirmado** | página del algoritmo; `contrato.py::GC_OUTPUTS` + test |
| Exactamente **dos** ficheros por interfaz | **✅** | `CHIMERA_SLUG_STRICT=canonical` es el defecto |
| T3 decisión `{event, months_to_recurrence}` | **✅ 75/75** | validación estricta, 0 incumplimientos |
| T3 razonamiento = cadena JSON suelta | **✅ 75/75** | ídem; el socket declara *Kind: String* |
| `variable_weights` completo en T1 y T2 | **✅ 0 incompletos** | 348 casos; era la causa del fallo anterior |
| Valida contra `Task{1,2,3}Output` | **✅ 423/423** | `verification/contrato_423.json` |
| `output/schema.py` intacto | **✅** | único fichero bloqueado del reto |

## Recursos y ejecución

| regla | límite | medido |
|---|---|---|
| VRAM (A10G 24 GB) | < 24 GB | **21 502 MiB** sostenido 3 h 30 min |
| RAM | 32 GB | **5,9 GiB** pico |
| Tiempo por caso | 15 min | T1 27 s · T2 46 s · T3 4 s |
| Sin red | `--network none` | ✅ en cobertura y smoke |
| Cobertura completa | 423 casos | **✅ 423/423**, exit 0, sin OOM |

## Artefactos

- **Imagen**: `chimera_agent_baseline_v1`. Entra por `inference_v1.py`, que importa el
  `inference.py` real y sustituye una sola función. `output/schema.py` no se toca.
- **Modelo aparte**: `model.tar.gz` se sube como *Model* independiente; GC lo extrae en
  `/opt/ml/model`. El contenedor lo da por hecho.

## Pendiente del usuario, no del código

- [ ] **Revocar el `HF_TOKEN` de `.env`** (`GC_PACKAGING.md:73`). No entra en la imagen
      —la auditoría no halló credenciales— pero sigue vivo en la cuenta.
- [ ] Declarar los modelos **Gemma-4-E2B** y **EmbeddingGemma** en el Algorithm.
- [ ] Elegir **A10G, ≤32 GB RAM** y las tres interfaces.
- [ ] **Cuota: 5 envíos en validación** (cuenta el mejor), **1 solo en test**.

## Lo que la entrega NO demuestra

- La cobertura de 423 casos es **contrato, no calidad**: incluye casos sin etiqueta.
- Los expertos de T1 y T2 se ajustaron sobre la cohorte etiquetada; el techo honesto de
  T1 medido fuera de muestra es 0,7607 frente al 0,8390 desplegado.
- El c-index de T3 en modo `deployed` (0,8832) es **dentro de muestra**. El número
  defendible es el anidado, **0,8235**.
- El Debug anterior dio 0,8406 sobre **12 casos**; no es comparable ni un objetivo.
