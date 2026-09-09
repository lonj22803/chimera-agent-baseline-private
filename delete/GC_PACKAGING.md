# Empaquetado de las tres tareas — 2026-09-09

El entrypoint `inference.py` selecciona `gc_entry.dispatch` por defecto.
`USE_MERGED_SOLUTION = False` restaura la ruta upstream. No se han modificado
`src/`, el esquema oficial, la configuración del modelo ni las zonas intocables.

La imagen incluye los expertos, las dos cachés, informes requeridos y exactamente
91 precedentes etiquetados de tarea 1. El árbol local tiene 195 entradas: la lista
explícita de `.dockerignore` deja pasar solo las 91 con ground truth. Si cambia la
biblioteca, actualizar esa lista y el contador de `verify_gc_image.py` juntos.
Se excluyen embeddings de precedentes, datos de tareas 2-3, runs, análisis,
notebooks, entornos y `.env`/variantes. Las fixtures locales son T2-001 y T3-001;
el slug de tarea 3 sigue truncado y su nombre de archivo sigue completo.

## Verificación CPU

`./delete/run_tests.sh`: 208 tests pasan (92 upstream, 68 common, 22 task1 agent,
4 task2 agent, 4 task2 expertos, 7 task3 agent, 11 task3 expertos). Incluye ocho
pruebas del seam y seis del router/puente, con backend sustituido explícitamente.
Esto no demuestra inferencia LLM ni calidad clínica.

Auditoría de imagen, sin red ni GPU, desde la raíz del repo:

```bash
docker run --rm --network none --entrypoint python3 \
  -v "$PWD/delete/verify_gc_image.py:/tmp/verify_gc_image.py:ro" \
  chimera_agent_baseline_debug /tmp/verify_gc_image.py
```

Comprueba artefactos y exclusiones, 91 pares de precedentes, flags offline,
patrones de credenciales sin imprimir valores y deserialización de modelos.
El escaneo de patrones no constituye una garantía universal de ausencia de secretos.

`test_gc_entry.py` requiere datos y salidas de referencia excluidos de la imagen.
Para correrlo dentro del contenedor, montar `data/` en `/opt/app/data:ro` y los
`task_{1,2,3}/runs/` locales en sus mismas rutas bajo `/opt/app/`, además de disponer
de pytest. No añadir esos datos de evaluación a la imagen de entrega.

## Pendiente de ejecución en host con GPU

AGENTS.md prohíbe intentar las corridas GPU desde el sandbox. Ejecutar en el host:

```bash
./do_test_run.sh
```

El arnés construye `chimera_agent_baseline_debug` y ejecuta las tres interfaces con
`--network none` y modelos montados de solo lectura. Revisar stderr: retorno cero
y esquema válido también pueden significar que se activó el respaldo determinista.
Validar los dos archivos planos por tarea contra Task1Output/Task2Output/Task3Output.
Registrar tiempos por caso, memoria con `docker stats` y VRAM con herramientas NVIDIA
en el host (docker stats no mide VRAM). Límites objetivo: 15 min, 32 GB RAM, A10G 24 GB.
No ejecutar vLLM y el juez Ollama simultáneamente en la RTX 5090. Cualquier evaluación
con juez debe usar `.venv-eval/bin/python`.

Mantener `gpu_memory_utilization=0.9`; cambiar a 0.80 en el override de `gc_entry`
solo si Debug demuestra OOM. No se ha medido rendimiento A10G en esta sesión.

## Entrega privada y plataforma

Después de validar la imagen, `make gc-save` produce `chimera-agent-baseline.tar.gz`
y `model.tar.gz`; usa otro tag que `do_build.sh`, aunque el Dockerfile es el mismo.
Comprobar que el tar de modelos contiene `gemma-4-E2B-it/` y `embedding_model/` en
la raíz. Mantener datos del challenge fuera de repositorios públicos (`data/` ya
está ignorado); las fixtures reales también requieren revisión DUA antes de publicar.

Subir ambos artefactos al Algorithm privado con las tres interfaces y elegir A10G,
≤32 GB RAM. Declarar los modelos Gemma y EmbeddingGemma. Validar primero en Debug.
Las fechas y cuotas del plan, así como la interpretación MCP para tarea 3 y la
admisibilidad DUA de precedentes, requieren confirmación en la plataforma/reglas;
esta implementación mantiene la decisión acordada de MCP solo en tareas 1-2.

Revocar/rotar el HF_TOKEN de `.env` desde la cuenta Hugging Face. No se ha leído ni
mostrado su valor, ni se ha revocado desde esta sesión. Excluirlo del contenedor no
revoca la credencial. No se ha realizado ninguna submission.

## Resultado observado de la imagen

Build auditado correcto: `chimera_agent_baseline_debug`, manifest
`sha256:f98a3a17bab0f41c2745419f4b741a0a8e38b79cfe52f23d5c81d7c3d14593b8`.
La auditoría CPU sin red ha pasado: 33 artefactos, 91 precedentes,
393.449.487 bytes de joblibs requeridos, cero coincidencias de credenciales en
`/opt/app` con el patrón revisado y deserialización correcta de todos los modelos.
Se añadió `train/__init__.py`, que el plan daba por existente pero faltaba.

Dentro de la imagen: **14 tests pasan** (`test_gc_entry.py` y
`test_gc_inference.py`, 4,24 s). Se montaron pytest y sus dependencias Python puras
desde `/tmp/chimera-gc-testdeps`, fixtures y referencias de solo lectura;
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`, sin red ni GPU.
No se instalaron dependencias de prueba en la imagen de entrega.

El escaneo del historial completo de instrucciones de Docker también terminó sin
coincidencias de patrones de credenciales ni asignaciones de HF_TOKEN/API keys.
No se ha efectuado un escaneo exhaustivo del contenido de todas las capas base.

Imagen exportada: `chimera_agent_baseline_debug_2026-09-09T23-29-35.836477594+02-00.tar.gz`
(10.724.640.009 bytes). `verify_gc_archives.py` ha comprobado sus 34 miembros,
manifest, referencias a capas e integridad gzip. El rebuild de exportación
produjo el manifest `sha256:9e358793725759d450968ac584d8dc358e886a2b92382ba2283da2ea532dd578`.

Modelos exportados: `model.tar.gz` (8.890.092.117 bytes, 57 miembros).
Verificación completa correcta: integridad gzip, rutas seguras, ausencia de archivos
.env, `gemma-4-E2B-it/config.json` y `embedding_model/config.json`, pesos safetensors
y tamaños de todos los archivos cotejados con `model/`. Ambos tarballs están listos
para transferir; su exportación no sustituye la aceptación GPU/Debug pendiente.
