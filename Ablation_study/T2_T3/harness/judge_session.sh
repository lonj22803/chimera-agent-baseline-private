#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
eval_python="${repo_root}/.venv-eval/bin/python"
score_script="${repo_root}/dev/score_with_judge.py"
study="${repo_root}/Ablation_study/T2_T3"
results="${study}/results"
logs="${study}/logs"
ollama_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
judge_model="${JUDGE_MODEL:-gemma4:e4b}"
eval_repo="${CHIMERA_EVAL_REPO:-${HOME}/PycharmProjects/CHIMERA-agent-eval}"

orders=(
  "T2-L0 T3-Lmin T2-Ldet T3-L0 T2-Lmin T3-Ldet"
  "T3-Ldet T2-Lmin T3-L0 T2-Ldet T3-Lmin T2-L0"
  "T2-Ldet T3-L0 T2-L0 T3-Ldet T2-Lmin T3-Lmin"
)

mkdir -p "$results" "$logs"
cd "$repo_root"
export PYTHONPATH="$repo_root:$repo_root/src"
export OLLAMA_BASE_URL="$ollama_url"
export JUDGE_MODEL="$judge_model"
export DEEPEVAL_TELEMETRY_OPT_OUT=YES
exec > >(tee -a "$logs/judge-session.log") 2>&1

if ! curl -sf "$ollama_url/api/tags" >/dev/null; then
  nohup ollama serve > "$logs/ollama.log" 2>&1 &
  for _ in $(seq 1 60); do
    curl -sf "$ollama_url/api/tags" >/dev/null && break
    sleep 1
  done
fi
curl -sf "$ollama_url/api/generate" -H 'Content-Type: application/json' \
  -d "{\"model\":\"${judge_model}\",\"prompt\":\"Reply OK.\",\"stream\":false,\"keep_alive\":\"12h\",\"options\":{\"num_predict\":1}}" \
  > "$results/J_session_warmup.json"
curl -sf "$ollama_url/api/ps" > "$results/J_session_before.json"

judge_complete() {
  local file="$1" task="$2" expected eligible
  expected=72; [[ "$task" == 3 ]] && expected=75
  "$eval_python" -c '
import json, math, sys
from pathlib import Path
p, task, expected = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
if not p.is_file(): raise SystemExit(1)
rows = json.loads(p.read_text()).get("rows") or []
eligible = rows if task == 3 else [r for r in rows if r.get("decision_score") == 1.0]
scores = [r.get("rationale_score") for r in eligible]
ok = len(rows) == expected and scores and all(isinstance(v, (int,float)) and math.isfinite(v) for v in scores)
raise SystemExit(0 if ok else 1)
' "$file" "$task" "$expected"
}

for pass in 1 2 3; do
  for arm in ${orders[$((pass - 1))]}; do
    task=2; [[ "$arm" == T3-* ]] && task=3
    target="$results/J_${arm}_p${pass}.json"
    if judge_complete "$target" "$task"; then
      echo "[p${pass} ${arm}] completo; se omite"
      continue
    fi
    echo "[p${pass} ${arm}] inicio"
    "$eval_python" "$score_script" --task "$task" \
      --data-root "$repo_root/data/task${task}" \
      --eval-repo "$eval_repo" \
      --output-root "$study/runs/${arm}/output" \
      --json-out "$target"
    judge_complete "$target" "$task"
    echo "[p${pass} ${arm}] terminado"
  done
done
curl -sf "$ollama_url/api/ps" > "$results/J_session_after.json"
echo "Sesion completa: 18/18 evaluaciones."
