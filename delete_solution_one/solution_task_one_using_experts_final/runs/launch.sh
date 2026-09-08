#!/usr/bin/env bash
# Lanza una corrida de la junta final en tmux, para que sobreviva a una desconexión.
#
#   ./launch.sh final  "--all-cases"                    # los 195 casos, configuración de entrega
#   ./launch.sh ceiling "--self-match"                  # el techo del mecanismo, sólo para medirlo
#   ./launch.sh pilot  "--limit 6"
#
# Dos corridas a la vez en una GPU: --gpu-util 0.45 en cada una, y la segunda
# necesita su propio socket del servicio de embeddings del RAG:
#   ./launch.sh ceiling "--self-match --gpu-util 0.45" "CHIMERA_EMBED_SOCKET=/tmp/chimera_embed_b.sock"
#
#   tmux attach -t chimera-final-<nombre>      (salir sin matarla: Ctrl-b d)
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
NAME="${1:?uso: launch.sh <nombre> \"<args>\"}"
ARGS="${2:-}"
ENV="${3:-}"
SESSION="chimera-final-$NAME"
OUT="$REPO/delete_solution_one/solution_task_one_using_experts_final/runs/$NAME"
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "La sesión $SESSION ya existe. Reenganchar: tmux attach -t $SESSION"; exit 0
fi
mkdir -p "$OUT"
tmux new-session -d -s "$SESSION" -c "$REPO" \
  "source .venv/bin/activate && ${ENV:+export $ENV;} PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_using_experts_final.run_task1 \
      --out-root '$OUT' $ARGS 2>&1 | tee '$OUT.log'; echo; echo '=== fin ($NAME) ==='; sleep 86400"
echo "Lanzada en tmux: $SESSION"
echo "  ver:      tmux attach -t $SESSION"
echo "  progreso: wc -l $OUT/summary.jsonl"
