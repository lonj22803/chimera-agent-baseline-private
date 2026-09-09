#!/usr/bin/env bash
# Vigilante del puente de GPU. Corre EN EL HOST (fuera del sandbox de Codex).
#
# Codex no ve /dev/nvidia*: su sandbox monta un /dev minimo. Este puente le deja
# pedir las operaciones de GPU que el plan necesita, y solo esas: cada peticion
# se valida contra una LISTA BLANCA antes de ejecutarse. No es un escape general
# del sandbox, es un agujero con forma concreta.
#
#   ./delete/gpu_bridge/watcher.sh          (dejar corriendo en el host)
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
REPO=$PWD
B=delete/gpu_bridge

# Lista blanca: expresiones regulares ancladas. Si una peticion no casa con
# NINGUNA, se rechaza y se registra. Ampliar aqui a proposito, nunca al vuelo.
ALLOW=(
  '^nvidia-smi( --[a-z-]+(=[A-Za-z0-9_,.:%-]+)?)*$'
  '^curl -s http://localhost:11434/api/generate -d .\{1,200\}$'
  '^\.venv/bin/python -m delete_final_versions_task\.task_[123]\.agent\.run_task[123]( --[a-z-]+( [A-Za-z0-9_/.,=-]+)?)*$'
  '^\.venv/bin/python dev/score_local\.py( --[a-z-]+( [A-Za-z0-9_/.,=-]+)?)*$'
  '^\.venv-eval/bin/python dev/score_with_judge\.py( --[a-z-]+( [A-Za-z0-9_/.,=-]+)?)*$'
  '^\.venv/bin/python -m delete_final_versions_task\.task_[123]\.analysis\.[a-z_]+( --[a-z-]+( [A-Za-z0-9_/.,=-]+)?)*$'
)

allowed() {
  local cmd=$1 rx
  for rx in "${ALLOW[@]}"; do
    if printf '%s' "$cmd" | grep -qE "$rx"; then return 0; fi
  done
  return 1
}

echo "puente de GPU escuchando en $B/requests/  (Ctrl-C para parar)"
while true; do
  for req in "$B"/requests/*.json; do
    [ -e "$req" ] || continue
    id=$(basename "$req" .json)
    res="$B/results/$id.json"
    [ -e "$res" ] && continue
    cmd=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('cmd',''))" "$req" 2>/dev/null)
    log="$B/logs/$id.log"
    if [ -z "$cmd" ]; then
      python3 -c "import json,sys;json.dump({'id':sys.argv[1],'status':'rejected','reason':'peticion sin cmd'},open(sys.argv[2],'w'))" "$id" "$res"
      continue
    fi
    if ! allowed "$cmd"; then
      echo "[$(date +%H:%M:%S)] RECHAZADA $id: $cmd"
      python3 - "$id" "$res" "$cmd" <<'PY'
import json,sys
json.dump({'id':sys.argv[1],'status':'rejected',
           'reason':'no esta en la lista blanca del puente',
           'cmd':sys.argv[3]}, open(sys.argv[2],'w'), indent=2)
PY
      continue
    fi
    echo "[$(date +%H:%M:%S)] EJECUTANDO $id: $cmd"
    start=$(date +%s)
    ( cd "$REPO" && PYTHONPATH=src:. eval "$cmd" ) > "$log" 2>&1
    rc=$?
    end=$(date +%s)
    python3 - "$id" "$res" "$cmd" "$rc" "$((end-start))" "$log" <<'PY'
import json,sys
from pathlib import Path
tail = Path(sys.argv[6]).read_text(errors='replace').splitlines()[-60:]
json.dump({'id':sys.argv[1],'status':'done','cmd':sys.argv[3],
           'exit_code':int(sys.argv[4]),'seconds':int(sys.argv[5]),
           'log':sys.argv[6],'stdout_tail':tail},
          open(sys.argv[2],'w'), indent=2, ensure_ascii=False)
PY
    echo "[$(date +%H:%M:%S)] LISTA $id (exit=$rc, $((end-start))s)"
  done
  sleep 3
done
