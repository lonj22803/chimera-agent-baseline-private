# Notas de entorno para agentes

## Intérpretes de Python — importa cuál uses

| Para | Intérprete | Por qué |
|---|---|---|
| Tests, código general | `.venv/bin/python` | Python 3.12.3, dependencias del proyecto |
| **Cualquier paso que invoque el juez** | **`.venv-eval/bin/python`** | **`deepeval` sólo está instalado ahí** |

Con `.venv` el juez falla con `No module named 'deepeval'` → `El juez no arrancó`, y el
`rationale_score` se queda sin calcular. No es un fallo del código: es el intérprete.

## Servicios del host

- **Ollama**: `http://localhost:11434`, modelo `gemma4:e4b`. Está permanentemente arriba.
- **Evaluador oficial**: `~/PycharmProjects/CHIMERA-agent-eval/evaluation` (fuera de este repo, sólo lectura).

Si desde el sandbox `localhost:11434` da `HTTP 000`, **no es que Ollama esté caído**: es el
aislamiento de red del sandbox. Repórtalo como tal en vez de concluir que el servicio no existe.

## Zonas intocables

- `delete_solution_one/` — tarea 1 cerrada y entregada (0,8390). No modificar.
- `delete_expert_modelate/` — expertos ya entrenados y medidos. No modificar.

## El plan

`delete/PLAN_CODEX.md` contiene el plan completo por fases, con el prompt exacto de cada paso.
Son ~17.800 tokens: un `cat` entero se trunca a 14.000 y pierde el final. Para fases del final
del documento, léelo por tramos con `sed -n 'A,Bp' delete/PLAN_CODEX.md`.

## La GPU NO es visible desde el sandbox

`nvidia-smi` falla dentro del sandbox de Codex con "couldn't communicate with the NVIDIA
driver" (código 9), porque `bwrap --dev /dev` monta un `/dev` mínimo sin los nodos
`/dev/nvidia*`. **Ningún paso que necesite la GPU puede ejecutarse desde aquí**: ni vLLM,
ni `nvidia-smi`, ni comprobar cuánta VRAM hay libre.

Si un paso del plan pide una corrida de GPU (2.2 y 4.3), **no la intentes y no supongas
el estado de la tarjeta**: repórtalo como no ejecutable desde el sandbox y para. Esos
pasos los corre el humano (o Claude) en el host.

Restricción de la tarjeta, para cuando se corran fuera: vLLM (28,2 GiB) y el juez de
Ollama (6,5 GiB) NO caben a la vez en la RTX 5090 (32,6 GiB). Hay que serializarlos:
generar con vLLM, apagarlo, y sólo entonces puntuar con el juez.

## `pytest -q` NO verifica el trabajo nuevo

`pyproject.toml` fija `testpaths = ["tests"]`. Un `pytest -q` a secas colecciona
**92 tests y ninguno** de `delete_final_versions_task/`: pasa en verde aunque el
trabajo nuevo esté roto o no exista. No lo uses como aceptación de un paso.

Para verificar de verdad, corre **todas** las suites:

```
./delete/run_tests.sh
```

Cubre: upstream (92), common (44), task_2 agent (4), task_2 expertos (4),
task_3 (11). Y si un paso produce un artefacto —una corrida, un informe, un
README—, comprueba **ese artefacto**, no que los tests sigan verdes: una corrida
de GPU que genera 0/195 casos deja los tests intactos.
