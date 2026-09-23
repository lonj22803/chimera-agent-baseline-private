#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python="${repo_root}/.venv/bin/python"
study="${repo_root}/Ablation_study/T2_T3"
logs="${study}/logs"
results="${study}/results"
ollama_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
judge_model="${JUDGE_MODEL:-gemma4:e4b}"
gpu_util="${GPU_UTIL:-0.9}"

mkdir -p "$logs" "$results"
cd "$repo_root"
export PYTHONPATH="$repo_root:$repo_root/src"
export PYTHONNOUSERSITE=1
exec > >(tee -a "$logs/guardian.log") 2>&1

status() { "$python" -m Ablation_study.T2_T3.harness.guardian_status "$1" "$2" "${3:-}"; }
stage=init
on_error() {
  local code="$1" line="$2"
  trap - ERR
  status failed "$stage" "codigo ${code}, linea ${line}" || true
  exit "$code"
}
trap 'on_error "$?" "$LINENO"' ERR
exec 9>"$results/guardian.lock"
flock -n 9 || { echo "Ya existe otro guardian T2/T3." >&2; exit 2; }

stage=cpu
status running "$stage" "huella y ablaciones deterministas"
"$python" -m Ablation_study.T2_T3.harness.fingerprint
"$python" -m Ablation_study.T2_T3.harness.t2_cpu > "$logs/t2-cpu.log" 2>&1
"$python" -m Ablation_study.T2_T3.harness.t3_cpu > "$logs/t3-cpu.log" 2>&1

stage=t2_baseline
status running "$stage" "importando control V4 completo"
"$python" -m Ablation_study.T2_T3.harness.run_t2_arm --arm T2-L0

stage=unload_ollama
status running "$stage" "liberando residencia antes de vLLM"
curl -sf "$ollama_url/api/generate" -H 'Content-Type: application/json' \
  -d "{\"model\":\"${judge_model}\",\"keep_alive\":0}" >/dev/null || true

stage=t2_min
status running "$stage" "T2 reducida con una llamada LLM por caso"
"$python" -m Ablation_study.T2_T3.harness.run_t2_arm --arm T2-Lmin --gpu-util "$gpu_util"

stage=t2_det
status running "$stage" "derivando T2 determinista"
"$python" -m Ablation_study.T2_T3.harness.derive_t2_deterministic

stage=ollama
status running "$stage" "preparando una residencia Ollama"
if ! curl -sf "$ollama_url/api/tags" >/dev/null; then
  nohup ollama serve > "$logs/ollama.log" 2>&1 &
  for _ in $(seq 1 60); do curl -sf "$ollama_url/api/tags" >/dev/null && break; sleep 1; done
fi
curl -sf "$ollama_url/api/generate" -H 'Content-Type: application/json' \
  -d "{\"model\":\"${judge_model}\",\"prompt\":\"Reply OK.\",\"stream\":false,\"keep_alive\":\"12h\",\"options\":{\"num_predict\":1}}" \
  > "$results/generation_warmup.json"

stage=t3_l0
status running "$stage" "T3 conferencia completa"
"$python" -m Ablation_study.T2_T3.harness.run_t3_arm --arm T3-L0 --ollama-url "$ollama_url" --model "$judge_model"
stage=t3_min
status running "$stage" "T3 arquitectura minima"
"$python" -m Ablation_study.T2_T3.harness.run_t3_arm --arm T3-Lmin --ollama-url "$ollama_url" --model "$judge_model"
stage=t3_det
status running "$stage" "T3 determinista"
"$python" -m Ablation_study.T2_T3.harness.run_t3_arm --arm T3-Ldet

stage=score
status running "$stage" "validando contratos, identidad y coste"
"$python" -m Ablation_study.T2_T3.harness.score_runs

stage=judge
status running "$stage" "18 evaluaciones narrativas"
bash "$study/harness/judge_session.sh"
"$python" -m Ablation_study.T2_T3.harness.judge_analysis

stage=report
status running "$stage" "sintesis e informe"
"$python" -m Ablation_study.T2_T3.harness.report

stage=closure
status running "$stage" "huella y suites"
"$python" -m Ablation_study.T2_T3.harness.closure
"$python" -m Ablation_study.T2_T3.harness.finalize_plan

stage=complete
status complete "$stage" "F0-F6 cerradas; informe disponible"
echo "Guardian completo: Ablation_study/T2_T3/reports/INFORME_ABLACION_T2_T3.md"
