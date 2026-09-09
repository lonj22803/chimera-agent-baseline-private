#!/usr/bin/env bash
# Pide una operacion de GPU al host. USALO DESDE DENTRO DEL SANDBOX.
#
#   ./delete/gpu_bridge/request.sh "nvidia-smi --query-gpu=memory.free --format=csv"
#   ./delete/gpu_bridge/request.sh ".venv/bin/python -m delete_final_versions_task.task_2.agent.run_task2 --all-cases --split all" 7200
#
# Bloquea hasta que el host responde (o hasta el timeout) e imprime el resultado.
# Solo se aceptan comandos de la lista blanca de watcher.sh: si el tuyo se
# rechaza, NO intentes rodearlo — reportalo y para.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
B=delete/gpu_bridge
CMD="${1:?uso: request.sh \"<comando>\" [timeout_s]}"
TIMEOUT="${2:-7200}"
ID="req-$(date +%Y%m%d-%H%M%S)-$$"

mkdir -p "$B/requests" "$B/results"
python3 - "$B/requests/$ID.json" "$CMD" <<'PY'
import json,sys
json.dump({'cmd':sys.argv[2]}, open(sys.argv[1],'w'), indent=2, ensure_ascii=False)
PY
echo "peticion $ID enviada al host; esperando (timeout ${TIMEOUT}s)..."

waited=0
while [ ! -e "$B/results/$ID.json" ]; do
  sleep 3; waited=$((waited+3))
  if [ "$waited" -ge "$TIMEOUT" ]; then
    echo "TIMEOUT tras ${TIMEOUT}s. La peticion sigue en $B/requests/$ID.json"
    echo "Si el vigilante del host no esta corriendo, avisa al usuario:"
    echo "  ./delete/gpu_bridge/watcher.sh"
    exit 124
  fi
done
python3 - "$B/results/$ID.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
print(f"\n=== {d['status'].upper()} ===")
if d['status']=='rejected':
    print('motivo:', d.get('reason')); print('cmd   :', d.get('cmd')); raise SystemExit(3)
print(f"exit={d['exit_code']}  {d['seconds']}s  log={d['log']}")
print('\n'.join(d.get('stdout_tail') or []))
raise SystemExit(0 if d['exit_code']==0 else 1)
PY
