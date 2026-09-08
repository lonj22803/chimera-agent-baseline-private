#!/usr/bin/env bash
# Lanza una corrida de la junta en tmux, para que sobreviva a una desconexión.
#
#   ./launch.sh mc   "--sample 30 --seeds 0 1 2"   # Monte Carlo: 3 muestras de 30 casos
#   ./launch.sh full ""                            # los 91 casos etiquetados
#
#   tmux attach -t chimera-<nombre>      (salir sin matarla: Ctrl-b d)
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
NAME="${1:?uso: launch.sh <nombre> \"<args>\"}"
ARGS="${2:-}"
SESSION="chimera-junta-$NAME"
OUT="$REPO/delete_solution_one/solution_task_one_correction_II/runs/$NAME"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "La sesión $SESSION ya existe. Reenganchar: tmux attach -t $SESSION"
    exit 0
fi
mkdir -p "$OUT"
tmux new-session -d -s "$SESSION" -c "$REPO" \
  "source .venv/bin/activate && PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_correction_II.run_task1 \
      --out-root '$OUT' $ARGS 2>&1 | tee '$OUT.log'; echo; echo '=== fin ($NAME) ==='; sleep 86400"
echo "Lanzada en tmux: $SESSION"
echo "  ver:      tmux attach -t $SESSION"
echo "  progreso: find $OUT -name summary.jsonl | xargs wc -l"
