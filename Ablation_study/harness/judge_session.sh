#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
eval_python="${repo_root}/.venv-eval/bin/python"
score_script="${repo_root}/dev/score_with_judge.py"
results="${repo_root}/Ablation_study/results"
logs="${repo_root}/Ablation_study/logs"
ollama_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
judge_model="${JUDGE_MODEL:-gemma4:e4b}"
eval_repo="${CHIMERA_EVAL_REPO:-${HOME}/PycharmProjects/CHIMERA-agent-eval}"
plan_only=0

if [[ "${1:-}" == "--plan" ]]; then
  plan_only=1
  shift
fi
if [[ "$#" -ne 0 ]]; then
  echo "Uso: $0 [--plan]" >&2
  exit 2
fi

orders=(
  "L7 L3 L2 L0p L6 L0 L4 L1 L5"
  "L0p L0 L4 L7 L1 L6 L2 L3 L5"
  "L5 L7 L1 L3 L0p L6 L4 L2 L0"
)

print_plan() {
  local pass arm
  for pass in 1 2 3; do
    for arm in ${orders[$((pass - 1))]}; do
      echo "p${pass} ${arm} results/J_${arm}_p${pass}.json"
    done
  done
}

if [[ "$plan_only" -eq 1 ]]; then
  print_plan
  exit 0
fi

cd "$repo_root"
export PYTHONPATH="$repo_root:$repo_root/src"
export OLLAMA_BASE_URL="$ollama_url"
export JUDGE_MODEL="$judge_model"
mkdir -p "$results" "$logs"
exec > >(tee -a "$logs/judge-session.log") 2>&1

if [[ ! -x "$eval_python" ]]; then
  echo "No existe el interprete del juez: $eval_python" >&2
  exit 1
fi
if [[ ! -f "$eval_repo/evaluation/evaluate.py" ]]; then
  echo "No existe el evaluador oficial en $eval_repo/evaluation" >&2
  exit 1
fi

gpu_processes="$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null)" || {
  echo "nvidia-smi no pudo consultar la GPU." >&2
  exit 1
}
if grep -Eiq 'python|vllm' <<<"$gpu_processes"; then
  echo "Hay un proceso Python/vLLM usando la GPU; libera vLLM antes del juez:" >&2
  echo "$gpu_processes" >&2
  exit 1
fi

if ! curl -sf "$ollama_url/api/tags" >/dev/null; then
  if ! command -v ollama >/dev/null; then
    echo "Ollama no responde en $ollama_url y no existe el comando 'ollama'." >&2
    exit 1
  fi
  echo "Ollama no responde; iniciando 'ollama serve'."
  nohup ollama serve > "$logs/ollama-judge.log" 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf "$ollama_url/api/tags" >/dev/null && break
    sleep 1
  done
  if ! curl -sf "$ollama_url/api/tags" >/dev/null; then
    echo "Ollama no estuvo listo tras 30 segundos; revisa $logs/ollama-judge.log." >&2
    exit 1
  fi
fi

curl -sf "$ollama_url/api/generate" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${judge_model}\",\"prompt\":\"Reply OK.\",\"stream\":false,\"keep_alive\":\"8h\",\"options\":{\"num_predict\":1}}" \
  > "$results/J_session_warmup.json"
curl -sf "$ollama_url/api/ps" > "$results/J_session_before.json"
print_plan > "$results/J_session_schedule.txt"

judge_complete() {
  "$eval_python" -c '
import json, math, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.is_file():
    raise SystemExit(1)
data = json.loads(p.read_text())
rows = data.get("rows") or []
judged = [row.get("rationale_score") for row in rows if row.get("decision_score") == 1.0]
ok = len(rows) == 91 and judged and all(isinstance(value, (int, float)) and math.isfinite(value) for value in judged)
raise SystemExit(0 if ok else 1)
' "$1"
}

for pass in 1 2 3; do
  for arm in ${orders[$((pass - 1))]}; do
    target="$results/J_${arm}_p${pass}.json"
    if judge_complete "$target"; then
      echo "[p${pass} ${arm}] resultado completo; se omite"
      continue
    fi
    echo "[p${pass} ${arm}] inicio"
    "$eval_python" "$score_script" \
      --task 1 \
      --data-root "$repo_root/data/task1" \
      --eval-repo "$eval_repo" \
      --output-root "$repo_root/Ablation_study/runs/${arm}/output" \
      --json-out "$target"
    judge_complete "$target"
    curl -sf "$ollama_url/api/ps" >/dev/null
    echo "[p${pass} ${arm}] terminado"
  done
done

curl -sf "$ollama_url/api/ps" > "$results/J_session_after.json"
echo "Sesion completa: 27/27 evaluaciones."
