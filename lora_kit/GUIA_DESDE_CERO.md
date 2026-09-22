# Guía desde cero: entrenar con LoRA el agente CHIMERA para las tres tareas

Todo lo que hay que hacer, en orden, desde una máquina vacía hasta una tabla de
resultados y un modelo listo para Grand Challenge. Cada paso dice **qué hacer**, **el
comando** y **cómo saber que ha ido bien**. El *porqué* de cada decisión está en
[`PLAN_FINETUNING_LORA.md`](PLAN_FINETUNING_LORA.md). Las particularidades de cada
tarea están en `tasks/task{1,2,3}/README.md`.

**Qué se mide:** Gemma 4 E2B-it + un adaptador LoRA, dentro del agente del reto sin
tocar (bucle ReAct + herramientas + formulario final), frente al mismo agente con el
modelo sin entrenar. Sin expertos, sin reglas.

**Tiempo aproximado** en una GPU de 24 GB: 1 h de preparación, ~1 h de entrenamiento
por semilla (5 pliegues) y ~25 min de evaluación por brazo y pliegue. La validación
cruzada completa (B0 + L1 con 3 semillas) lleva ~10–12 h de GPU, sin vigilancia.

---

## Paso 0 — Requisitos de la máquina

| Qué | Mínimo | Cómo comprobarlo |
|---|---|---|
| Linux x86_64 | — | `uname -m` → `x86_64` |
| GPU NVIDIA | **24 GB** (RTX 4090, A10G, L4, A5000…) | `nvidia-smi` |
| Driver compatible con CUDA 12.9 (lo usa la rueda de vLLM) | driver ≥ 575 | `nvidia-smi` (arriba a la derecha) |
| Docker + NVIDIA Container Toolkit | — | `docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi` |
| Python 3.11 | — | `python3.11 --version` |
| Disco libre | ~120 GB (pesos base 10 GB + un fusionado por pliegue ~10 GB + imagen ~20 GB) | `df -h .` |
| Cuenta de Hugging Face con la licencia de Gemma 4 aceptada | — | abrir https://huggingface.co/google/gemma-4-E2B-it y aceptar |

---

## Paso 1 — Montar el repositorio limpio

```bash
cd ~/repo-limpio                    # tu repositorio con los datos
# 1) copia aquí la carpeta lora_kit/ entera (de la rama claude/practical-thompson-gx0yal)
# 2) deja los datos con ESTA estructura (la del reto):
#    data/task1/agent_input/<case>/structured-prompt.json
#    data/task1/agent_input/<case>/prostate-biopsy-decision-clinical-data.json
#    data/task1/ground_truth/<case>/prostate-biopsy-decision.json
#    data/task1/ground_truth/<case>/prostate-biopsy-decision-reasoning.json
#    data/task2/...  (prostate-treatment-decision-*)
#    data/task3/...  (prostate-time-to-recurrence-or-last-follow-up-*)
```

El nombre de la carpeta de cada caso tiene que ser su `case_id`, en `agent_input` y en
`ground_truth`. Mira `lora_kit/fixture_data/` si dudas: es exactamente esta estructura.

**Comprobación:**

```bash
for t in 1 2 3; do echo "task$t: $(ls data/task$t/agent_input | wc -l) entradas, $(ls data/task$t/ground_truth | wc -l) con GT"; done
# esperado: task1 195/91 · task2 153/72 · task3 75/75
```

Añade a `.gitignore`: `model/`, `runs/`, `CHIMERA-agent/`, `.venv-train/`.

---

## Paso 2 — Descargar los pesos

```bash
python3.11 -m pip install --user "huggingface_hub[cli]"
huggingface-cli login                                   # pega tu token (lectura)
huggingface-cli download google/gemma-4-E2B-it --local-dir model/gemma-4-E2B-it
# opcional, solo si quieres que search_guidelines funcione (el experimento no lo necesita):
huggingface-cli download google/embeddinggemma-300m --local-dir model/embedding_model
```

**Comprobación:** `ls model/gemma-4-E2B-it` muestra `config.json`, `*.safetensors`,
`tokenizer.json` y la plantilla de chat (`chat_template.jinja` o dentro de
`tokenizer_config.json`).

---

## Paso 3 — El evaluador oficial

```bash
git clone https://github.com/DIAGNijmegen/CHIMERA-agent.git
git -C CHIMERA-agent checkout 92365b9       # el commit con el que se probó el kit
```

Fijar el commit importa: si cambian los pesos de las métricas, los números dejan de
ser comparables entre corridas.

---

## Paso 4 — Entorno de entrenamiento y prueba de humo

```bash
python3.11 -m venv .venv-train && source .venv-train/bin/activate
pip install --upgrade pip
pip install -r lora_kit/requirements-train.txt
lora_kit/pipeline/selftest.sh CHIMERA-agent
```

**Comprobación:** termina con `== OK` y antes imprime `paridad ... argmax igual=1.000`
(o ≥ 0,98) y `OVERALL=1.0000`. Esto prueba, **sin GPU**, que la cadena funciona:
datos de las 3 tareas → máscara → LoRA → fusión → evaluador. Si falla aquí, no sigas.

Comprueba también la GPU desde este entorno:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

---

## Paso 5 — Imagen de inferencia (la pila exacta del reto)

La evaluación y la verificación de la plantilla **tienen que** ejecutarse con vLLM
0.25.0, como en Grand Challenge. Se hace con la imagen Docker del propio kit:

```bash
docker build --platform=linux/amd64 -t chimera-lora-infer lora_kit/agent_baseline
```

(unos 15–25 min la primera vez). Para ejecutar cualquier cosa dentro de la imagen,
con el repositorio montado:

```bash
lora_kit/pipeline/in_container.sh python3 -c "import vllm, transformers; print(vllm.__version__, transformers.__version__)"
# esperado: 0.25.0 5.12.1
```

---

## Paso 6 — Construir los datos de entrenamiento (las tres tareas)

```bash
source .venv-train/bin/activate
mkdir -p runs
python lora_kit/pipeline/make_folds.py --data-root data --out runs/folds.json --k 5
python lora_kit/pipeline/build_sft.py  --data-root data --out runs/sft.jsonl --folds runs/folds.json
python lora_kit/pipeline/dump_examples.py --sft runs/sft.jsonl --out runs/ejemplos
```

**Comprobaciones** (esto es el inventario del plan, §5):

1. `make_folds.py` imprime la tabla pliegue × clase de cada tarea. Cada pliegue tiene
   que tener casos de todas las clases grandes (`watchful_waiting`, con 2 casos, solo
   cae en 2 pliegues: es normal).
2. `runs/sft.stats.json`:
   - `taskN:casos_etiquetados` = 91 / 72 / 75;
   - `taskN:descartado:*` debería ser 0; si no, el error sale por pantalla con el caso;
   - `fh_ponderada_sin_family_history`, `pesos_no_elegibles_descartados`,
     `reasoning_ampliado_a_40` y `seccion_invalida_descartada` cuentan las
     incoherencias del GT que se han corregido. Apúntalas: son parte del informe.
3. **Lee** `runs/ejemplos/task{1,2,3}/sft_react.txt` y `sft_form_fill.txt` de principio
   a fin. Es exactamente lo que el modelo va a aprender. Si algo no tiene sentido
   clínico (un razonamiento que contradice la decisión, un documento vacío), se arregla
   ahora en `build_sft.py`, no después de entrenar.

---

## Paso 7 — Verificar la plantilla contra vLLM (obligatorio)

```bash
lora_kit/pipeline/in_container.sh python3 lora_kit/pipeline/check_template.py \
    --model model/gemma-4-E2B-it --sft runs/sft.jsonl --n 30
```

**Comprobación:** termina en `OK -> usa --tool-content string` (o `blocks`). **Apunta
ese valor**: lo usarás en todos los entrenamientos.

Si falla:

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| `prompt_identico` con 0 en los dos modos | La plantilla de HF y vLLM renderizan distinto | Imprime ambos prompts decodificados para un ejemplo y localiza la diferencia (suele estar en los mensajes `tool` o en los argumentos). Ajusta `normalise_messages` en `render.py` |
| `el tramo no acaba en token de parada` | El modelo no aprendería a terminar el turno | Revisa qué token pone la plantilla de Gemma 4 al final del turno y añádelo en `_eos_ids` de `render.py` |
| `parser devuelve [...] en vez de [...]` | vLLM no leería las llamadas que el modelo aprende | Compara el texto del tramo con el formato que espera `vllm/tool_parsers/gemma4_utils.py` |
| `plantilla inestable` | El prompt de un turno no es prefijo de la conversación | La plantilla reescribe turnos anteriores (p. ej. borra razonamientos); hay que trocear de otra forma |

No entrenes hasta que esto diga `OK`.

---

## Paso 8 — Primer entrenamiento corto (para medir memoria y tiempo)

```bash
source .venv-train/bin/activate
TC=string        # el valor del paso 7
python lora_kit/pipeline/train_lora.py --model model/gemma-4-E2B-it --sft runs/sft.jsonl \
    --fold 0 --epochs 1 --out runs/prueba --tool-content $TC
```

**Comprobaciones** en `runs/prueba/train.log`:

- `LoRA sobre N módulos (p. ej. ...language_model...)`: N > 0 y los nombres son del
  **decodificador de texto**. Si sale `--target-regex no casa`, el script lista los
  nombres reales: ajusta `--target-regex` a ellos (solo `q/k/v/o/gate/up/down_proj`
  del modelo de lenguaje, nunca visión ni audio).
- `longitudes: p50=… p95=… max=…`: si `max` > `--max-len` (10240), algunos ejemplos se
  descartan (lo dice el log). Sube `--max-len` si la memoria lo permite.
- `max_mem_gb` en la línea de la época: por debajo de ~22 GB.

Si da **OOM**, en este orden:

1. `--max-len 8192`;
2. `--qlora` (necesita `pip install bitsandbytes`);
3. si el error menciona `logits_to_keep`, `--no-logits-to-keep` (más memoria; combínalo con 1 o 2).

---

## Paso 9 — Validación cruzada: entrenar, fusionar y evaluar

Un bucle por semilla y pliegue. Déjalo corriendo (por ejemplo con `nohup` o `tmux`).

```bash
source .venv-train/bin/activate
TC=string
for SEED in 0 1 2; do
  for F in 0 1 2 3 4; do
    R=runs/r16_s$SEED/fold$F
    python lora_kit/pipeline/train_lora.py --model model/gemma-4-E2B-it --sft runs/sft.jsonl \
        --fold $F --seed $SEED --out $R --tool-content $TC --eval-generate
    E=$(cat $R/BEST_EPOCH)
    python lora_kit/pipeline/merge_export.py --base model/gemma-4-E2B-it \
        --adapter $R/adapter_epoch$E --out $R/merged --check-sft runs/sft.jsonl --tool-content $TC
    lora_kit/pipeline/in_container.sh lora_kit/pipeline/eval_fold.sh \
        $R/merged $R/split.json data $R/eval CHIMERA-agent
    rm -rf $R/merged            # ~10 GB por pliegue; el adaptador se queda
  done
done

# brazo de referencia B0: el modelo SIN entrenar, en los mismos pliegues (una vez basta)
for F in 0 1 2 3 4; do
  lora_kit/pipeline/in_container.sh lora_kit/pipeline/eval_fold.sh \
      model/gemma-4-E2B-it runs/r16_s0/fold$F/split.json data runs/B0/fold$F CHIMERA-agent
done
```

Opcional, brazo **L1-T** (temperatura 0,2): repite la evaluación de la semilla 0
añadiendo `0.2` como sexto argumento de `eval_fold.sh` y con `$R/eval_t02` como salida
(hay que volver a fusionar, porque el bucle borra `merged`).

**Comprobaciones por pliegue** (lo imprime `eval_fold.sh`):

- `task1/2/3: ranking=…` y `sin_salida=0`. Un `sin_salida` > 0 son casos en los que el
  agente no escribió salida: mira `agent.log` (suele ser el form-fill agotando los 3
  reintentos).
- `herramientas inexistentes: 0` y `reintentos form_fill` bajos. El baseline sin
  entrenar sí tiene ambos; el LoRA debería reducirlos.
- `run_info.json` → `seconds` / nº de casos: tiene que quedar muy por debajo de 780 s
  por caso.

---

## Paso 10 — La tabla de resultados

```bash
source .venv-train/bin/activate
python lora_kit/pipeline/report.py --eval-repo CHIMERA-agent --ref B0 \
    --arm B0="runs/B0/fold*/score.json" \
    --arm L1_s0="runs/r16_s0/fold*/eval/score.json" \
    --arm L1_s1="runs/r16_s1/fold*/eval/score.json" \
    --arm L1_s2="runs/r16_s2/fold*/eval/score.json" \
    --out runs/REPORT.md
```

**Cómo leerla:**

- Primera tabla: `ranking_score` por tarea y OVERALL (`(2·T1 + 2·T2 + T3)/5`), media ±
  desviación entre pliegues, y el agregado de todas las predicciones fuera de pliegue.
- Segunda tabla: diferencia con B0 e IC al 95 % (bootstrap pareado por caso), más
  McNemar sobre la puerta de decisión de T1 y T2.
- **El LoRA funciona** si el ΔOVERALL tiene un IC que no cruza 0 **en las tres
  semillas**. Si solo gana en una, es ruido.
- Referencias: el baseline sin entrenar da 0,635 / 0,446 / 0,664 en T1/T2/T3. La
  solución entregada da 0,839 / 0,778 / 0,883, pero **dentro de muestra**. Su estimación
  honesta ronda 0,76 en T1 y 0,82 en T3. Compara con la honesta.
- Mira aparte el recall de `no` en T1 y el de `continued_surveillance` en T2 (en
  `score.json` → `tasks.N.decision_classification_report`): es donde falla el baseline.

Si quieres ablaciones (rango, épocas, `--permute-tools`, solo T1+T2): §11 del plan.
Cada una es otro bucle del paso 9 con otro `--out`.

---

## Paso 11 — Modelo final

Con la configuración ganadora, entrena con **todos** los casos y un número de épocas
**fijo**: la mediana de los `BEST_EPOCH` de los pliegues.

```bash
cat runs/r16_s*/fold*/BEST_EPOCH | sort -n | awk '{a[NR]=$1} END{print "mediana:", a[int((NR+1)/2)]}'
EPOCHS=3         # la mediana anterior
python lora_kit/pipeline/train_lora.py --model model/gemma-4-E2B-it --sft runs/sft.jsonl \
    --fold -1 --epochs $EPOCHS --seed 0 --out runs/final --tool-content $TC
python lora_kit/pipeline/merge_export.py --base model/gemma-4-E2B-it \
    --adapter runs/final/adapter_epoch$EPOCHS --out runs/final/merged --check-sft runs/sft.jsonl --tool-content $TC
```

Revisa `runs/final/merged/MERGE_REPORT.json`: `config_diffs` debería estar vacío.

**No publiques un número de este modelo:** ha visto las 238 etiquetas. El número válido
es el del paso 10.

---

## Paso 12 — Empaquetar y probar como en Grand Challenge

Grand Challenge monta el tarball del modelo en `/opt/ml/model/`, y el agente busca
`/opt/ml/model/gemma-4-E2B-it` y `/opt/ml/model/embedding_model`.

```bash
mkdir -p model_gc
cp -r runs/final/merged model_gc/gemma-4-E2B-it
[ -d model/embedding_model ] && cp -r model/embedding_model model_gc/embedding_model

# prueba: un caso por tarea, sin red, en el formato plano de GC (una ejecución por caso)
for i in 0 1 2; do
  rm -rf runs/gc_test/interf$i && mkdir -p runs/gc_test/interf$i && chmod 777 runs/gc_test/interf$i
  CASE=$(ls -d lora_kit/fixture_data/task$((i+1))/agent_input/*/)
  time docker run --rm --gpus all --network none \
      -v "$PWD/$CASE:/input:ro" -v "$PWD/runs/gc_test/interf$i:/output" \
      -v "$PWD/model_gc:/opt/ml/model:ro" chimera-lora-infer
  ls runs/gc_test/interf$i
done
```

**Comprobaciones:**

- Cada ejecución escribe los **dos** ficheros de su tarea en `/output`.
- El tiempo por caso (arranque en frío incluido) queda muy por debajo de 15 min.
- Si la tarjeta de Grand Challenge es de 16 GB, baja `generation.gpu_memory_utilization`
  en `lora_kit/agent_baseline/configs/config.yaml` (por ejemplo a 0.80), reconstruye la
  imagen (paso 5) y repite esta prueba con `nvidia-smi` abierto para ver el pico.

Tarballs para subir:

```bash
docker save chimera-lora-infer | gzip -c > chimera-lora-infer.tar.gz     # imagen (Algorithm → Containers)
tar -czf model.tar.gz -C model_gc .                                     # modelo (Algorithm → Models)
```

---

## Paso 13 — Qué entregar del experimento

1. `runs/REPORT.md` (la tabla del paso 10).
2. `runs/sft.stats.json` (correcciones del GT) y `runs/folds.json` (pliegues).
3. `runs/*/fold*/history.json` (curvas y época elegida por pliegue).
4. La versión de todo: commit del evaluador, `pip freeze` del entorno de entrenamiento
   y `docker image inspect chimera-lora-infer`.
5. Qué se declara: `--fh-policy`, `--oversample`, `--tool-content`, rango, épocas, y que
   T3 escribe `event: 0` siempre (lo explica `tasks/task3/README.md`).

---

## Resumen en una lista

- [ ] 0. GPU ≥ 24 GB, Docker con GPU, Python 3.11, licencia de Gemma aceptada
- [ ] 1. `lora_kit/` copiado y `data/` con la estructura del reto (91/72/75 con GT)
- [ ] 2. `model/gemma-4-E2B-it` descargado
- [ ] 3. `CHIMERA-agent` clonado en `92365b9`
- [ ] 4. `.venv-train` + `selftest.sh` → `== OK`
- [ ] 5. imagen `chimera-lora-infer` construida (vLLM 0.25.0, transformers 5.12.1)
- [ ] 6. `folds.json`, `sft.jsonl`, `sft.stats.json` revisados; ejemplos leídos
- [ ] 7. `check_template.py` → `OK -> usa --tool-content …`
- [ ] 8. entrenamiento corto: módulos LoRA correctos, memoria < 22 GB
- [ ] 9. 3 semillas × 5 pliegues entrenados y evaluados + B0 evaluado
- [ ] 10. `REPORT.md`: ΔOVERALL con IC, en las tres semillas
- [ ] 11. modelo final con épocas fijas, `config_diffs` vacío
- [ ] 12. prueba GC sin red: dos ficheros por caso, < 15 min
- [ ] 13. informe + versiones + decisiones declaradas
