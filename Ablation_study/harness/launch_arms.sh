#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${repo_root}/.venv/bin/python"
resume=0

if [[ "${1:-}" == "--resume" ]]; then
  resume=1
  shift
fi

if [[ "$#" -eq 0 ]]; then
  requested_arms=(L0 L1 L2 L3 L4 L5 L6 L7 L0p)
else
  requested_arms=("$@")
fi
readonly -a requested_arms

is_known_arm() {
  case "$1" in
    L0|L1|L2|L3|L4|L5|L6|L7|L0p) return 0 ;;
    *) return 1 ;;
  esac
}

# Validate the complete request before starting any expensive GPU work.
for requested_arm in "${requested_arms[@]}"; do
  if ! is_known_arm "$requested_arm"; then
    echo "Brazo desconocido: ${requested_arm}. Validos: L0 L1 L2 L3 L4 L5 L6 L7 L0p" >&2
    exit 2
  fi
done

gpu_is_free() {
  local active
  active="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null || true)"
  [[ -z "${active//[[:space:]]/}" ]]
}

cd "$repo_root"
export PYTHONPATH="$repo_root:$repo_root/src"

for requested_arm in "${requested_arms[@]}"; do
  if [[ "$resume" -eq 1 ]] && "$python_bin" -m Ablation_study.harness.run_arm --arm "$requested_arm" --check-complete; then
    echo "[$requested_arm] 91 salidas validas; se omite por --resume"
    continue
  fi
  while ! gpu_is_free; do
    echo "[$requested_arm] GPU ocupada por procesos de computo; nueva comprobacion en 15 s"
    sleep 15
  done
  echo "[$requested_arm] inicio"
  "$python_bin" -m Ablation_study.harness.run_arm --arm "$requested_arm"
  echo "[$requested_arm] terminado"
done
