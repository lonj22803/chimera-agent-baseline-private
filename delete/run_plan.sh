#!/usr/bin/env bash
# Orquestador del PLAN_CODEX: lanza los pasos del plan contra Codex, en orden,
# verificando entre uno y otro y parando al primer fallo.
#
#   ./delete/run_plan.sh --list            estado de todos los pasos
#   ./delete/run_plan.sh 2.1               un paso suelto
#   ./delete/run_plan.sh --track A         una via entera (A|B|C|final)
#   ./delete/run_plan.sh --dry-run 2.1     imprime el prompt sin lanzarlo
#   ./delete/run_plan.sh --resume         retoma 1.3 + lo que quedo pendiente tras un corte
#
# Vias (del camino critico del plan):
#   A  tarea 1:  2.1 -> 2.2* -> 2.3
#   B  tarea 2:  3.2 -> 4.2  -> 4.3*
#   C  tarea 3:  5.2 -> 5.3  -> 6.2
#   final:       7.1 -> 7.2
#   (*) pasos de GPU: 2.2 y 4.3 NO pueden solaparse; el script los serializa con un lock.
set -uo pipefail

REPO=/home/jjlondono/PycharmProjects/chimera-agent-baseline
PLAN=$REPO/delete/PLAN_CODEX.md
PLUGIN=/home/jjlondono/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/codex-companion.mjs
RUNS=$REPO/delete/plan_runs
GPULOCK=$RUNS/.gpu.lock
mkdir -p "$RUNS"

# paso -> "contexto_extra|gpu|verificacion"
#   contexto_extra: pasos [PLAN] que hay que leer antes (criterio de diseno)
meta() { case "$1" in
  1.1) echo "36,117|no|pytest_common" ;;
  1.2) echo "36,117|no|forms_report" ;;
  1.3) echo "|no|pytest_all" ;;
  1.4) echo "|no|pytest_all" ;;
  2.1) echo "|no|pytest_all" ;;
  2.2) echo "|SI|pytest_all" ;;
  2.3) echo "|no|readme_task1" ;;
  3.2) echo "571,579|no|pytest_all" ;;
  4.2) echo "642,666|no|pytest_all" ;;
  4.3) echo "|SI|readme_task2" ;;
  5.2) echo "810,836|no|pytest_all" ;;
  5.3) echo "|no|pytest_all" ;;
  6.2) echo "1004,1025|no|pytest_all" ;;
  7.1) echo "|no|pytest_all" ;;
  7.2) echo "|no|readme_raiz" ;;
  *)   echo "" ;;
esac; }

track() { case "$1" in
  A) echo "2.1 2.2 2.3" ;;  B) echo "3.2 4.2 4.3" ;;
  C) echo "5.2 5.3 6.2" ;;  final) echo "7.1 7.2" ;;
  *) echo "" ;;
esac; }

# rango de lineas del paso, leido del propio plan (sobrevive a ediciones)
step_range() { python3 - "$PLAN" "$1" <<'PY'
import re,sys
plan,step=sys.argv[1],sys.argv[2]
L=open(plan).read().splitlines()
start=None
for i,l in enumerate(L,1):
    if re.match(rf'^### {re.escape(step)} \[', l): start=i; break
if start is None: sys.exit(1)
end=len(L)
for i,l in enumerate(L[start:],start+1):
    if re.match(r'^#{2,3} ', l): end=i-1; break
print(f"{start},{end}")
PY
}

verify() { local kind=$1; cd "$REPO"
  case "$kind" in
    pytest_common) PYTHONPATH=src:. .venv/bin/python -m pytest delete_final_versions_task/common/tests -q 2>&1 | tail -3 ;;
    pytest_all)    .venv/bin/python -m pytest -q 2>&1 | tail -3 ;;
    forms_report)  [ -f delete_final_versions_task/common/analysis/forms_report.json ] \
                     && python3 -m json.tool delete_final_versions_task/common/analysis/forms_report.json >/dev/null \
                     && echo "forms_report.json OK" || echo "FALTA/ILEGIBLE forms_report.json" ;;
    readme_task1)  [ -f delete_final_versions_task/task_1/README.md ] && echo "README task_1 OK" || echo "FALTA README task_1" ;;
    readme_task2)  [ -f delete_final_versions_task/task_2/README.md ] && echo "README task_2 OK" || echo "FALTA README task_2" ;;
    readme_raiz)   [ -f delete_final_versions_task/README.md ] && echo "README raiz OK" || echo "FALTA README raiz" ;;
  esac
}

build_prompt() { local step=$1 rng=$2 ctx=$3 gpu=$4
  cat <<EOF
Repo: $REPO

Lee primero AGENTS.md (raiz del repo): interpretes de Python, servicios del host y zonas intocables.

Plan completo en delete/PLAN_CODEX.md. NO lo leas entero (se trunca a 14k tokens). Lee solo:
  sed -n '${rng}p' delete/PLAN_CODEX.md      <- el paso $step, que es lo que tienes que ejecutar
$( [ -n "$ctx" ] && echo "  sed -n '${ctx}p' delete/PLAN_CODEX.md      <- criterio de diseno, leelo antes" )

$( [ -f delete_final_versions_task/common/analysis/forms_report.json ] && cat <<'GATE'
VEREDICTO DE LA COMPUERTA 1.2 — obligatorio respetarlo
delete_final_versions_task/common/analysis/forms_report.json ya esta medido. Leelo
(python3 -c "import json;d=json.load(open('delete_final_versions_task/common/analysis/forms_report.json'))")
antes de disenar nada. Solo se adopta lo que tenga "adoptar": true:
  - task1: arbitrate_cells y aprendido_entero en variable_weight_score; arbitrate_cells en important_decisive.
  - task1: expected_f1_set NO se adopta (pierde contra la moda).
  - task2: NINGUNA politica bate al suelo. Para la tarea 2 se publica la moda / la constante.
  - confidence_from_rung no fue medible en ninguna tarea: no lo presentes como validado.
No adoptes una politica con "adoptar": false por mucho que el plan la proponga; el plan
mismo dice que lo que no bate al suelo se reporta como no adoptado.
GATE
)

Ejecuta UNICAMENTE el paso $step. El bloque del plan trae la especificacion exacta
(API publica, tests y criterio de aceptacion): siguela al pie de la letra.

RESTRICCIONES
- No toques delete_solution_one/ ni delete_expert_modelate/.
- Sin dependencias nuevas: numpy y stdlib salvo que el paso diga otra cosa.
- No avances al paso siguiente aunque el plan lo tenga. Al terminar $step, PARA.
$( [ "$gpu" = "SI" ] && echo "- Este paso usa vLLM y pide ~90% de la VRAM. No lances nada mas en GPU en paralelo." )

VERIFICACION (obligatoria antes de reportar)
- Corre la aceptacion que indique el propio paso en el plan.
- Comprueba ademas que la suite existente sigue verde: .venv/bin/python -m pytest -q
- Si algo no pasa, dilo explicitamente en el informe en vez de darlo por bueno.

Reporta: archivos creados/modificados, un resumen por archivo, y la salida real de cada verificacion.
EOF
}

run_step() { local step=$1 rng ctx gpu vfy m
  m=$(meta "$step"); [ -z "$m" ] && { echo "paso desconocido: $step"; return 1; }
  ctx=${m%%|*}; gpu=$(echo "$m" | cut -d'|' -f2); vfy=${m##*|}
  rng=$(step_range "$step") || { echo "no encuentro el paso $step en el plan"; return 1; }

  local pf="$RUNS/prompt_$step.txt" lg="$RUNS/run_$step.log"
  build_prompt "$step" "$rng" "$ctx" "$gpu" > "$pf"
  if [ "${DRY:-0}" = "1" ]; then echo "--- prompt para $step (lineas $rng) ---"; cat "$pf"; return 0; fi

  if [ "$gpu" = "SI" ]; then
    echo "[$step] esperando el lock de GPU..."
    exec 9>"$GPULOCK"; flock 9
  fi

  echo "=== [$step] lanzando (lineas $rng del plan) $(date +%H:%M:%S) ==="
  cd "$REPO"
  node "$PLUGIN" task --prompt-file "$pf" --write --fresh 2>&1 | tee "$lg"
  local rc=${PIPESTATUS[0]}
  [ "$gpu" = "SI" ] && exec 9>&-

  echo "=== [$step] verificando ==="
  # El runtime devuelve el control con "subagent work drained" pendiente: los
  # artefactos pueden tardar en aterrizar. Reintenta hasta 90s antes de fallar.
  local out=""; local t
  for t in $(seq 1 18); do
    out=$(verify "$vfy")
    echo "$out" | grep -qiE "failed|error|FALTA|ILEGIBLE" || break
    [ "$t" -eq 1 ] && echo "    (artefacto aun no visible; reintentando hasta 90s)"
    sleep 5
  done
  echo "$out"
  if echo "$out" | grep -qiE "failed|error|FALTA|ILEGIBLE"; then
    echo "!!! [$step] VERIFICACION FALLIDA — me paro aqui. Log: $lg"; return 1
  fi
  echo "=== [$step] OK $(date +%H:%M:%S) ==="; return $rc
}

case "${1:-}" in
  --list)
    printf "%-5s %-6s %-9s %s\n" PASO GPU RANGO ESTADO
    for s in 1.1 1.2 2.1 2.2 2.3 3.2 4.2 4.3 5.2 5.3 6.2 7.1 7.2; do
      m=$(meta "$s"); g=$(echo "$m" | cut -d'|' -f2); r=$(step_range "$s" 2>/dev/null || echo "?")
      st="pendiente"; [ -f "$RUNS/run_$s.log" ] && st="lanzado"
      printf "%-5s %-6s %-9s %s\n" "$s" "$g" "$r" "$st"
    done ;;
  --all)
    # Grafo del camino critico:
    #   1.2 es compuerta: A y B dependen de ella. C (tarea 3) no.
    #   A, B y C tocan tareas distintas -> corren en paralelo.
    #   2.2 y 4.3 son GPU y se serializan solas con el flock.
    echo "########## FASE 1 restante + vias en paralelo ##########"
    run_step 1.2; rc12=$?
    if [ $rc12 -ne 0 ]; then
      echo "!!! 1.2 fallo. A y B dependen de el: no los lanzo."
      echo "    Lanzo solo la via C (tarea 3), que no depende de la fase 1."
    fi
    pids=""
    if [ $rc12 -eq 0 ]; then
      ( for s in $(track A); do run_step "$s" || exit 1; done ) > "$RUNS/track_A.log" 2>&1 & pids="$pids $!:A"
      ( for s in $(track B); do run_step "$s" || exit 1; done ) > "$RUNS/track_B.log" 2>&1 & pids="$pids $!:B"
    fi
    ( for s in $(track C); do run_step "$s" || exit 1; done ) > "$RUNS/track_C.log" 2>&1 & pids="$pids $!:C"
    fail=0
    for pt in $pids; do
      pid=${pt%%:*}; nm=${pt##*:}
      if wait "$pid"; then echo "=== via $nm OK ==="; else echo "!!! via $nm FALLO (log: $RUNS/track_$nm.log)"; fail=1; fi
    done
    if [ $fail -ne 0 ]; then echo "Alguna via fallo: no lanzo la fase 7."; exit 1; fi
    echo "########## FASE 7 (convergencia) ##########"
    for s in $(track final); do run_step "$s" || exit 1; done
    echo "########## PLAN COMPLETO ##########" ;;
  --track) shift; for s in $(track "${1:-}"); do run_step "$s" || exit 1; done ;;
  --resume)
    # Retoma donde el limite de uso de Codex corto el --all anterior:
    # 2.1/3.2/5.3 ya cayeron y verificaron. Sigue desde ahi.
    echo "########## 1.3 (huecos de confianza) ##########"
    run_step 1.3
    echo "########## resto de las vias, en paralelo ##########"
    pids=""
    ( run_step 2.2 && run_step 2.3 ) > "$RUNS/track_A.log" 2>&1 & pids="$pids $!:A"
    ( run_step 4.2 && run_step 4.3 ) > "$RUNS/track_B.log" 2>&1 & pids="$pids $!:B"
    ( run_step 6.2 )                > "$RUNS/track_C.log" 2>&1 & pids="$pids $!:C"
    fail=0
    for pt in $pids; do
      pid=${pt%%:*}; nm=${pt##*:}
      if wait "$pid"; then echo "=== via $nm OK ==="; else echo "!!! via $nm FALLO (log: $RUNS/track_$nm.log)"; fail=1; fi
    done
    if [ $fail -ne 0 ]; then echo "Alguna via fallo: no lanzo la fase 7."; exit 1; fi
    echo "########## FASE 7 (convergencia) ##########"
    for s in $(track final); do run_step "$s" || exit 1; done
    echo "########## PLAN COMPLETO ##########" ;;
  --dry-run) shift; DRY=1 run_step "${1:-}" ;;
  "" | -h | --help) sed -n '2,16p' "$0" ;;
  *) run_step "$1" ;;
esac
