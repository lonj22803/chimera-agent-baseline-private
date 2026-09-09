#!/usr/bin/env bash
# Avance REAL de Codex. No se fia del status del job (puede decir "running"
# con el turno abortado hace 10 minutos); mira el rollout, que es la verdad.
set -uo pipefail
S=/home/jjlondono/.codex/sessions
F=$(ls -t $S/*/*/*/rollout-*.jsonl 2>/dev/null | head -1)
[ -z "$F" ] && { echo "no hay sesiones de Codex"; exit 1; }
AGE=$(( $(date +%s) - $(stat -c %Y "$F") ))

echo "sesion : $(basename "$F" | cut -c9-27)"
echo "tamano : $(stat -c%s "$F") bytes"
echo -n "estado : "
if grep -q "task_complete" "$F"; then echo "TERMINADO"
elif grep -q "turn_aborted" "$F"; then echo "ABORTADO / INTERRUMPIDO"
elif [ "$AGE" -gt 600 ]; then echo "ESTANCADO (${AGE}s sin actividad)"
else echo "TRABAJANDO (ultimo evento hace ${AGE}s)"; fi

python3 - "$F" <<'PY'
import json,sys
msgs=[];cmds=[]
for line in open(sys.argv[1]):
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except: continue
    p=o.get('payload',{}); ts=(o.get('timestamp') or '')[11:19]
    if p.get('type')=='message' and p.get('role')=='assistant':
        t=''.join(c.get('text','') for c in p.get('content',[]) if isinstance(c,dict))
        if t.strip(): msgs.append((ts,t))
    if p.get('type')=='custom_tool_call': cmds.append(ts)
print(f"\nturnos : {len(msgs)} mensajes · {len(cmds)} llamadas a herramientas")
if msgs:
    ts,t=msgs[-1]
    print(f"\nultimo mensaje [{ts}]:\n  {t[:600]}")
PY
