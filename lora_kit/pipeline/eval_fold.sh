#!/usr/bin/env bash
# Ejecuta el agente baseline SIN CAMBIOS con un modelo (base o fusionado) sobre los casos
# de test de un pliegue y lo puntúa con el evaluador oficial. Va en el entorno de
# inferencia (el del contenedor: vLLM 0.25.0).
#
#   pipeline/eval_fold.sh <model_dir> <split.json> <data_root> <out_dir> <eval_repo> [temperatura]
#
#   # brazo B0 (modelo base) y brazo L1 (LoRA fusionado) en el pliegue 0:
#   pipeline/eval_fold.sh ../model/gemma-4-E2B-it runs/r16/fold0/split.json ../data runs/B0/fold0 ../CHIMERA-agent
#   pipeline/eval_fold.sh runs/r16/fold0/merged   runs/r16/fold0/split.json ../data runs/r16/fold0/eval ../CHIMERA-agent
#   # lo mismo a temperatura 0,2 (brazo L1-T):
#   pipeline/eval_fold.sh runs/r16/fold0/merged   runs/r16/fold0/split.json ../data runs/r16/fold0/eval_t02 ../CHIMERA-agent 0.2
set -euo pipefail

MODEL_DIR=$(realpath "$1")
SPLIT=$(realpath "$2")
DATA_ROOT=$(realpath "$3")
OUT=$(realpath -m "$4")
EVAL_REPO=$(realpath "$5")
TEMP=${6:-1.0}

KIT=$(cd "$(dirname "$0")/.." && pwd)
PIDS=$(python3 -c "import json,sys; print('[' + ','.join(repr(c) for c in json.load(open(sys.argv[1]))['test']) + ']')" "$SPLIT")
mkdir -p "$OUT"

cd "$KIT/agent_baseline"
START=$(date +%s)
python3 -m chimera_agent_baseline.run \
    paths.data_root="$DATA_ROOT" \
    paths.output_dir="$OUT/output" \
    paths.model_dir="$MODEL_DIR" \
    "agent.pids=$PIDS" \
    generation.temperature="$TEMP" \
    2>&1 | tee "$OUT/agent.log"
END=$(date +%s)
echo "{\"seconds\": $((END - START)), \"temperature\": $TEMP, \"model_dir\": \"$MODEL_DIR\"}" > "$OUT/run_info.json"

python3 "$KIT/pipeline/score_fold.py" \
    --data-root "$DATA_ROOT" --output-root "$OUT/output" --split "$SPLIT" \
    --eval-repo "$EVAL_REPO" --out "$OUT/score.json"

# Señales operativas: herramientas inexistentes y reintentos del form-fill.
echo "herramientas inexistentes: $(grep -c 'is not a valid tool' "$OUT/agent.log" || true)"
echo "reintentos form_fill:      $(grep -c 'form_fill parse failed' "$OUT/agent.log" || true)"
