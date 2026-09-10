#!/usr/bin/env bash
# Corrida completa de las tres juntas sobre los casos etiquetados, y su
# puntuación con el evaluador OFICIAL en los dos modos (sin juez y con juez).
#
#   ./run_all.sh              # todas las fases pendientes, en orden
#   ./run_all.sh 4 5          # sólo las fases indicadas
#
# La GPU es de uso exclusivo: T1/T2 levantan vLLM con los pesos locales y T3 y
# el juez hablan con Ollama. Las dos cosas no caben a la vez en la 5090, así que
# las fases van estrictamente en serie y cada una descarga lo que cargó antes de
# ceder el turno. Cada fase es idempotente: si su marca existe, se salta.
set -uo pipefail

RES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$RES/../.." && pwd)"
PY="$REPO/.venv/bin/python"
PY_EVAL="$REPO/.venv-eval/bin/python"
JUDGE_MODEL="${JUDGE_MODEL:-gemma4:e4b}"
export PYTHONPATH="$REPO/src:$REPO"

mkdir -p "$RES/scores" "$RES/logs" "$RES/output"

log()  { printf '\n\033[1m== %s\033[0m  %s\n' "$1" "$(date +%H:%M:%S)"; }
done_marker() { echo "$RES/logs/.done_$1"; }
is_done() { [[ -f "$(done_marker "$1")" ]]; }
mark()    { date -Is > "$(done_marker "$1")"; }

# Ollama deja el modelo residente tras responder; vLLM necesita la tarjeta entera.
free_gpu() {
    curl -s http://localhost:11434/api/generate \
         -d "{\"model\":\"$JUDGE_MODEL\",\"keep_alive\":0}" >/dev/null 2>&1 || true
    sleep 5
    nvidia-smi --query-gpu=memory.used --format=csv,noheader
}

# --- Fase 1/2: las juntas con vLLM ------------------------------------------
run_conference() {  # $1 = nº de tarea
    local task="$1" out="$RES/task_$1"
    log "Fase $task · junta de la tarea $task (vLLM, $( [[ $task == 1 ]] && echo 91 || echo 72 ) casos etiquetados)"
    free_gpu
    mkdir -p "$out"
    "$PY" -m "delete_final_versions_task.task_${task}.agent.run_task${task}" \
        --out-root "$out" --split labeled 2>&1 | tee "$RES/logs/task${task}.log"
    local n; n=$(find "$out/output/task${task}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    echo "  casos con salida: $n"
    ln -sfn "../task_${task}/output/task${task}" "$RES/output/task${task}"
}

# --- Fase 3: la junta de T3, que no usa vLLM sino Ollama --------------------
run_task3() {
    log "Fase 3 · junta de la tarea 3 (Ollama $JUDGE_MODEL, 75 casos etiquetados)"
    local out="$RES/task_3"
    "$PY" -m delete_final_versions_task.task_3.agent.run_task3 \
        --out-root "$out" --mode oof --model "$JUDGE_MODEL" 2>&1 | tee "$RES/logs/task3.log"
    ln -sfn "../task_3/output/task3" "$RES/output/task3"
}

# --- Fase 4: evaluador oficial, juez APAGADO (determinista) -----------------
score_no_judge() {
    log "Fase 4 · evaluador oficial SIN juez (determinista, los tres a la vez)"
    "$PY" "$REPO/dev/score_local.py" \
        --output-root "$RES/output" --tasks 1 2 3 --count-missing \
        --json-out "$RES/scores/no_judge.json" 2>&1 | tee "$RES/logs/score_no_judge.log"
}

# --- Fase 5: evaluador oficial, juez ENCENDIDO (pesos reales de GC) ---------
score_judge() {
    log "Fase 5 · evaluador oficial CON juez de razonamiento ($JUDGE_MODEL)"
    free_gpu
    for task in 1 2 3; do
        echo "  -- tarea $task --"
        "$PY_EVAL" "$REPO/dev/score_with_judge.py" \
            --output-root "$RES/output" --task "$task" \
            --json-out "$RES/scores/judge_task${task}.json" 2>&1 \
            | tee "$RES/logs/score_judge_task${task}.log"
    done
}

PHASES=("$@")
[[ ${#PHASES[@]} -eq 0 ]] && PHASES=(1 2 3 4 5)

cd "$REPO"
for phase in "${PHASES[@]}"; do
    if is_done "$phase"; then echo "Fase $phase ya hecha; se salta."; continue; fi
    case "$phase" in
        1) run_conference 1 ;;
        2) run_conference 2 ;;
        3) run_task3 ;;
        4) score_no_judge ;;
        5) score_judge ;;
        *) echo "Fase desconocida: $phase" >&2; exit 2 ;;
    esac
    mark "$phase"
done

log "Fin"
echo "Puntuaciones en $RES/scores/  ·  actas en $RES/task_*/boards/ y task_3/output/task3/*/acta.md"
