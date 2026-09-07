#!/usr/bin/env bash
# Lanza la corrida 2 en una sesion tmux llamada `chimera-run2`, para que
# sobreviva a una desconexion.
#
#   ./launch_run2.sh                 # arranca (o reengancha si ya existe)
#   tmux attach -t chimera-run2      # ver la consola
#   tmux kill-session -t chimera-run2  # abortar
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SESSION=chimera-run2
OUT="$REPO/delete_solution_one/solution_task_one/runs/run2"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "La sesion $SESSION ya existe. Reenganchar con: tmux attach -t $SESSION"
    exit 0
fi

mkdir -p "$OUT"
tmux new-session -d -s "$SESSION" -c "$REPO" \
    "source .venv/bin/activate && PYTHONPATH=src:. python -m delete_solution_one.solution_task_one.run_task1 \
        --out-root '$OUT' --prompts v2 2>&1 | tee '$OUT.log'; \
     echo; echo '=== corrida 2 terminada (codigo '\$?') ==='; sleep 86400"
echo "Lanzada en tmux: $SESSION"
echo "  ver:       tmux attach -t $SESSION   (salir con Ctrl-b d)"
echo "  progreso:  wc -l $OUT/summary.jsonl"
echo "  log:       tail -f $OUT.log"
