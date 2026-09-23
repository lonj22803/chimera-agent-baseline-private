# Runbook GPU - Ablacion Tarea 1

Ejecutar desde la raiz del repositorio, en la rama `ablation_study_final_version`. Las corridas
usan los 91 casos etiquetados, modo `honest`, temperatura 0, k=3 y el mismo perfil vLLM. No editar
la V4 ni cambiar argumentos entre brazos.

## 1. Preparacion

```bash
cd /home/jjlondono/PycharmProjects/chimera-agent-baseline
export PYTHONPATH="$PWD:$PWD/src"
git branch --show-current
.venv/bin/python -m pytest -q -p no:cacheprovider Ablation_study/ablacion_tests
nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv
```

La rama debe ser `ablation_study_final_version` y la suite debe quedar verde. No debe haber otro
proceso de computo en la GPU. El lanzador vuelve a comprobarlo antes de cada brazo.

## 2. Regla de VRAM

vLLM ocupa aproximadamente 28,2 GiB con `gpu-util=0.9`; el juez Ollama `gemma4:e4b`, unos 6,5
GiB. Juntos superan los 32,6 GiB de la RTX 5090. Generar primero todos los brazos, liberar vLLM y
solo despues iniciar la sesion de juez. Antes de generar, descargar cualquier juez residente:

```bash
curl -s localhost:11434/api/generate -d '{"model":"gemma4:e4b","keep_alive":0}'
nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv
```

No cambiar modelo, `gpu-util`, plantilla, temperatura ni limites de tokens entre brazos. A T=0 un
cambio del perfil vLLM puede cambiar la prosa y deja de ser una comparacion controlada.

## 3. L0 y compuerta obligatoria

```bash
Ablation_study/harness/launch_arms.sh L0
.venv/bin/python -m Ablation_study.harness.run_arm --arm L0 --check-complete
.venv/bin/python -m Ablation_study.harness.validate_arm --arm L0
```

Tiempo esperado: unos 45 minutos. `--check-complete` debe devolver codigo 0 y
`Ablation_study/results/L_L0.json` debe contener `"accepted": true`. La validacion exige 91/91,
contrato valido e identidad de decision, confianza, pesos y `reveal_sequence` con S-A0 honest.
Tambien registra imagen, reaperturas, nudges, planes vacios y concordancia plan-registrador.

Si L0 no es aceptado, detenerse. No lanzar L1-L7: hay que investigar el `blocker` de `L_L0.json`.

## 4. Resto de brazos

Solo tras aceptar L0:

```bash
Ablation_study/harness/launch_arms.sh --resume L1 L2 L3 L4 L5 L6 L7 L0p
for arm in L1 L2 L3 L4 L5 L6 L7 L0p; do
  .venv/bin/python -m Ablation_study.harness.validate_arm --arm "$arm"
done
```

Orden fijo: L1 sin EAU; L2 sin moderador; L3 sin verificador; L4 sala LLM minima; L5 presidente
determinista; L6 sin G1-G2; L7 sin G3; L0p replica de referencia. Presupuestar unos 45 minutos
por brazo, aproximadamente seis horas adicionales. `--resume` omite solamente directorios con
91 pares de salida. Un brazo rechazado se relanza de forma aislada despues de leer su `blocker`.

No hace falta un proceso por caso: los expertos salen de la cache y son deterministas. Si es
obligatorio conservar el mismo `case_id` entre brazos; el runner lo lee de los directorios de
entrada y nunca lo inventa.

## 5. Comprobacion y entrega

Cada `Ablation_study/runs/<brazo>/` debe contener:

- `arm.json` y `run_config.json`;
- 91 directorios bajo `output/task1/`, cada uno con decision y razonamiento;
- 91 actas JSON bajo `boards/`;
- `summary.jsonl` y `telemetry.jsonl`.

Comprobar el conjunto:

```bash
for arm in L0 L1 L2 L3 L4 L5 L6 L7 L0p; do
  test -f "Ablation_study/results/L_${arm}.json"
  .venv/bin/python -m Ablation_study.harness.run_arm --arm "$arm" --check-complete
done
```

Las corridas permanecen en `Ablation_study/runs/` y no se versionan. Para devolver el trabajo a
Codex basta indicar que los nueve brazos y sus `results/L_*.json` ya existen en este workspace.
No copiar `data/`, textos clinicos sueltos ni notas a otra ubicacion.

## 6. Juez, despues de liberar vLLM

Confirmar que vLLM ya no aparece en `nvidia-smi`. Mantener Ollama cargado durante las 27
evaluaciones; no descargar ni reiniciar el modelo entre pasadas. La cifra correcta es 27: nueve
brazos (L0, L0p y L1-L7) por tres pasadas. La discrepancia 24/27 esta registrada en la bitacora.

Comprobar primero el calendario sin usar GPU:

```bash
Ablation_study/harness/judge_session.sh --plan
```

Para proteger la sesion frente a una desconexion SSH:

```bash
tmux new-session -s ablation-juez
cd /home/jjlondono/PycharmProjects/chimera-agent-baseline
Ablation_study/harness/judge_session.sh
```

Separarse con `Ctrl+b`, `d`; volver con `tmux attach-session -t ablation-juez`. El script omite
cualquier `J_<brazo>_p<pase>.json` completo al reanudarse, registra el orden fijo aleatorizado y
guarda `api/ps` antes y despues. Ollama debe estar respondiendo en `localhost:11434`.

Al terminar la sesion de juez, liberar el modelo:

```bash
curl -s localhost:11434/api/generate -d '{"model":"gemma4:e4b","keep_alive":0}'
```
