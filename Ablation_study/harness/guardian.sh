#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python="${repo_root}/.venv/bin/python"
logs="${repo_root}/Ablation_study/logs"
results="${repo_root}/Ablation_study/results"
ollama_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
judge_model="${JUDGE_MODEL:-gemma4:e4b}"
gpu_util="${GPU_UTIL:-0.9}"

mkdir -p "$logs" "$results"
cd "$repo_root"
export PYTHONPATH="$repo_root:$repo_root/src"
exec > >(tee -a "$logs/guardian.log") 2>&1

status() {
  "$python" -m Ablation_study.harness.guardian_status "$1" "$2" "${3:-}"
}

on_error() {
  local code="$1"
  local line="$2"
  trap - ERR
  status failed "${stage:-unknown}" "fallo con codigo ${code} en linea ${line}" || true
  echo "Guardian detenido en ${stage:-unknown}, linea ${line}, codigo ${code}." >&2
  exit "$code"
}
trap 'on_error "$?" "$LINENO"' ERR

exec 9>"$results/guardian.lock"
if ! flock -n 9; then
  echo "Ya existe otro guardian activo." >&2
  exit 2
fi

stage="wait_judge"
status running "$stage" "esperando 27 artefactos validos"
"$python" -m Ablation_study.harness.judge_analysis --wait --interval 30

stage="synthesis"
status running "$stage" "construyendo tabla maestra y A_min"
"$python" -m Ablation_study.harness.synthesize

read -r requires_l9 accepted < <(
  "$python" -c 'import json; from pathlib import Path; p=json.loads(Path("Ablation_study/results/A_min.json").read_text()); print(str(bool(p["requires_l9"])).lower(), str(bool(p["accepted"])).lower())'
)
if [[ "$requires_l9" == "true" && "$accepted" != "true" ]]; then
  stage="unload_judge"
  status running "$stage" "liberando Ollama antes de L9"
  curl -sf "$ollama_url/api/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"${judge_model}\",\"keep_alive\":0}" >/dev/null || true

  stage="wait_gpu"
  status running "$stage" "esperando que la GPU quede libre"
  for _ in $(seq 1 120); do
    processes="$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null || true)"
    [[ -z "$processes" ]] && break
    sleep 5
  done
  processes="$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null || true)"
  if [[ -n "$processes" ]]; then
    echo "La GPU no quedo libre tras 10 minutos:" >&2
    echo "$processes" >&2
    false
  fi

  stage="run_l9"
  status running "$stage" "ejecutando ablacion conjunta A_min"
  "$python" -m Ablation_study.harness.run_amin --gpu-util "$gpu_util"

  stage="resynthesis"
  status running "$stage" "validando L9 y recalculando A_min"
  "$python" -m Ablation_study.harness.synthesize
fi

"$python" -c 'import json; from pathlib import Path; p=json.loads(Path("Ablation_study/results/A_min.json").read_text()); raise SystemExit(0 if p.get("accepted") else 1)'

stage="report"
status running "$stage" "generando informe, extension y figuras"
"$python" -m Ablation_study.harness.report

stage="closure"
status running "$stage" "verificando huella y ejecutando suites"
"$python" -m Ablation_study.harness.closure

stage="finalize"
status running "$stage" "cerrando plan y bitacora"
"$python" -m Ablation_study.harness.finalize_plan

stage="complete"
status complete "$stage" "F0-F8 cerradas; informe final disponible"
echo "Guardian completo. Informe: Ablation_study/reports/INFORME_ABLACION_T1.md"
