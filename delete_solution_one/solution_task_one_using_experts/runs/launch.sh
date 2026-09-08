#!/usr/bin/env bash
# Lanza una corrida de la junta con expertos en tmux, para que sobreviva a una desconexión.
#
#   ./launch.sh deployed "--mode deployed"          # los 91 etiquetados, panel tal como se entrenó
#   ./launch.sh honest   "--mode honest"            # los 91 etiquetados, panel out-of-fold + biblioteca LOO
#   ./launch.sh pilot    "--mode deployed --limit 6"
#
# Para correr dos modos a la vez en una GPU (--gpu-util 0.45 en cada uno), el
# segundo necesita su propio socket del servicio de embeddings del RAG:
#   ./launch.sh honest "--mode honest --gpu-util 0.45" "CHIMERA_EMBED_SOCKET=/tmp/chimera_embed_honest.sock"
#
#   tmux attach -t chimera-expertos-<nombre>      (salir sin matarla: Ctrl-b d)
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
NAME="${1:?uso: launch.sh <nombre> \"<args>\"}"
ARGS="${2:-}"
ENV="${3:-}"
SESSION="chimera-expertos-$NAME"
OUT="$REPO/delete_solution_one/solution_task_one_using_experts/runs/$NAME"
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "La sesión $SESSION ya existe. Reenganchar: tmux attach -t $SESSION"
    exit 0
fi
mkdir -p "$OUT"
tmux new-session -d -s "$SESSION" -c "$REPO" \
  "source .venv/bin/activate && ${ENV:+export $ENV;} PYTHONPATH=src:. python -m delete_solution_one.solution_task_one_using_experts.run_task1 \
      --out-root '$OUT' $ARGS 2>&1 | tee '$OUT.log'; echo; echo '=== fin ($NAME) ==='; sleep 86400"
echo "Lanzada en tmux: $SESSION"
echo "  ver:      tmux attach -t $SESSION"
echo "  progreso: wc -l $OUT/summary.jsonl"
