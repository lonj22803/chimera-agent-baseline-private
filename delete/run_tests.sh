#!/usr/bin/env bash
# Corre TODAS las suites, no solo la que recoge `pytest -q`.
#
# Por que existe: pyproject.toml fija `testpaths = ["tests"]`, asi que un
# `pytest -q` a secas colecciona 92 tests y NINGUNO de delete_final_versions_task.
# Usar ese 92 como verificacion de un paso del plan es enganoso: pasa igual
# aunque el trabajo nuevo este roto o ni siquiera exista.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONPATH=src:.
PY=.venv/bin/python
fail=0

run() {  # run <etiqueta> <ruta...>
  local label=$1; shift
  if [ ! -e "$1" ]; then printf "  %-34s (no existe, se salta)\n" "$label"; return; fi
  local out; out=$($PY -m pytest -q "$@" 2>&1 | tail -1)
  printf "  %-34s %s\n" "$label" "$out"
  echo "$out" | grep -qE "error|failed" && fail=1
  return 0
}

echo "=== suites del proyecto ==="
run "upstream (tests/)"            tests
run "common"                       delete_final_versions_task/common/tests
run "task_1 agent"                 delete_final_versions_task/task_1/agent/tests
run "task_2 agent"                 delete_final_versions_task/task_2/agent/tests
run "task_2 expertos"              delete_final_versions_task/task_2/experts_2/tests
run "task_3 agent"                 delete_final_versions_task/task_3/agent/tests
  run "task_3 expertos"              delete_final_versions_task/task_3/experts_3

echo
if [ $fail -ne 0 ]; then echo "RESULTADO: HAY FALLOS"; exit 1; fi
echo "RESULTADO: todo en verde"
