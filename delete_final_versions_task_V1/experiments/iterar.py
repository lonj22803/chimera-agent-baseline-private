"""Ciclo corto para probar un cambio de prompt en minutos, no en horas.

El ciclo completo es caro por una razón estructural: cambiar un prompt obliga a
**regenerar la prosa con vLLM**, y vLLM (~21 GiB) y el juez de Ollama (~6,5 GiB) no
caben a la vez en la tarjeta. Cada iteración son dos cargas de GPU en serie. Sobre los
91 casos de T1 eso es más de una hora; sobre una muestra de 20, unos quince minutos.

    generar prosa (vLLM, N casos)  ->  liberar GPU  ->  juzgar (Ollama, N x 2)

Dos aceleraciones, ambas con su precio declarado:

- **Muestra.** `--n 20` sobre DEV basta para ver si un cambio va en la dirección
  correcta. No basta para adoptarlo: con 20 casos el error típico del `rationale_score`
  ronda ±0,05, así que sólo se distinguen cambios grandes.
- **Paralelismo.** El runner de Ollama tiene 4 slots (`-np 4`) y el bucle riguroso usa
  uno. Aquí se lanzan varias peticiones a la vez. **Cambia las condiciones de medida**:
  sirve para explorar, no para decidir.

**Nada medido aquí se adopta.** La adopción exige el pase pareado completo de
`paired_judge.py`: cohorte entera, dos pases, secuencial, en una sola carga. Esta
herramienta dice a qué merece la pena dedicarle esa hora.
"""
from __future__ import annotations
import argparse
import json
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V1 = Path(__file__).resolve().parents[1]
RESULTS = Path(__file__).resolve().parents[0] / 'results'


def muestra(task, n, seed):
    ids = sorted((REPO/f'dev/splits/task{task}_dev.txt').read_text().split())
    random.Random(seed).shuffle(ids)
    return sorted(ids[:n])


def generar(task, ids, out_root, gpu_util=0.8):
    """Regenera la prosa de esos casos con vLLM. Es la mitad cara del ciclo."""
    out_root = Path(out_root)
    if out_root.exists():
        subprocess.run(['rm', '-rf', str(out_root)], check=False)
    cmd = [sys.executable, '-m', f'delete_final_versions_task_V1.task_{task}.agent.run_task{task}',
           '--out-root', str(out_root), '--pids', *ids]
    if task == 3:
        cmd = [c for c in cmd if c != '--pids'] + []
        cmd = [sys.executable, '-m', 'delete_final_versions_task_V1.task_3.agent.run_task3',
               '--out-root', str(out_root), '--backend', 'vllm', '--mode', 'deployed']
    else:
        cmd += [f'--gpu-util={gpu_util}']
    import os
    env = {**os.environ, 'PYTHONPATH': f'{REPO}/src:{REPO}'}
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=REPO, env=env)
    return {'exit_code': p.returncode, 'segundos': round(time.monotonic()-t0, 1), 'cmd': cmd}


def liberar_gpu(modelo='gemma4:e4b'):
    """vLLM muere con su proceso; aquí sólo se comprueba que la tarjeta quedó libre."""
    libre = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader'],
                           text=True, capture_output=True).stdout.strip()
    return libre


def juzgar(task, ids, base_root, cand_root, hilos=4):
    """Juzga base y candidato sobre los mismos casos, en paralelo. Exploratorio."""
    from dev import score_with_judge as loader
    ev = loader.load_evaluator(loader.DEFAULT_EVAL_REPO)
    data = REPO/f'data/task{task}'
    gts = {ev.get_case_id(g): g for g in ev.load_ground_truth_records(data/'ground_truth', f'task{task}')}
    preds = {'base': loader.load_predictions(Path(base_root), data, task),
             'cand': loader.load_predictions(Path(cand_root), data, task)}
    faltan = {k: [i for i in ids if i not in v] for k, v in preds.items()}
    if any(faltan.values()):
        raise ValueError(f'faltan predicciones: {faltan}')
    judge = ev.build_rationale_judge()
    if judge is None:
        raise RuntimeError('El juez oficial no arrancó; ¿se usó .venv-eval?')

    def una(arg):
        etiqueta, cid = arg
        fila = (ev.evaluate_recurrence_case(gts[cid], preds[etiqueta][cid], judge) if task == 3
                else ev.evaluate_case(gts[cid], preds[etiqueta][cid], None, judge))
        return etiqueta, cid, fila.get('rationale_score')

    trabajos = [(e, c) for c in ids for e in ('base', 'cand')]
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=hilos) as pool:
        salidas = list(pool.map(una, trabajos))
    notas = {'base': [], 'cand': []}
    for etiqueta, _, s in salidas:
        if s is not None:
            notas[etiqueta].append(s)
    media = {k: (sum(v)/len(v) if v else None) for k, v in notas.items()}
    return {'n': len(ids), 'hilos': hilos, 'segundos': round(time.monotonic()-t0, 1),
            'juzgados': {k: len(v) for k, v in notas.items()},
            'rationale': {k: (round(v, 4) if v is not None else None) for k, v in media.items()},
            'delta': (round(media['cand']-media['base'], 4)
                      if None not in (media['base'], media['cand']) else None)}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--task', type=int, required=True, choices=[1, 2, 3])
    p.add_argument('--n', type=int, default=20, help='casos de DEV a muestrear')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--hilos', type=int, default=4, help='peticiones simultáneas al juez (el runner tiene 4 slots)')
    p.add_argument('--fase', choices=['generar', 'juzgar', 'ambas'], default='ambas',
                   help='generar necesita .venv; juzgar necesita .venv-eval')
    p.add_argument('--cand-root', type=Path, help='prosa ya generada; si se da, se salta generar')
    p.add_argument('--base-root', type=Path,
                   help='por defecto, la corrida de referencia de resultados/')
    p.add_argument('--json-out', type=Path)
    args = p.parse_args()

    ids = muestra(args.task, args.n, args.seed)
    cand = args.cand_root or (V1/f'experiments/iter/task{args.task}')
    base = args.base_root or (REPO/f'delete_final_versions_task/resultados/task_{args.task}/output')
    salida = {'task': args.task, 'n': args.n, 'seed': args.seed, 'casos': ids,
              'aviso': 'Exploratorio: muestra pequeña y peticiones en paralelo. No adopta nada; '
                       'la decisión exige el pase pareado completo de paired_judge.py.'}

    if args.fase in ('generar', 'ambas') and not args.cand_root:
        print(f'[1/2] generando prosa de {len(ids)} casos con vLLM...', flush=True)
        salida['generar'] = generar(args.task, ids, cand)
        salida['vram_tras_generar'] = liberar_gpu()
        print(f"      {salida['generar']['segundos']} s · VRAM ahora {salida['vram_tras_generar']}", flush=True)

    if args.fase in ('juzgar', 'ambas'):
        print(f'[2/2] juzgando {len(ids)} casos x 2 versiones con {args.hilos} hilos...', flush=True)
        salida['juzgar'] = juzgar(args.task, ids, base, cand/f'output/task{args.task}'
                                  if (cand/f'output/task{args.task}').exists() else cand, args.hilos)

    destino = args.json_out or (RESULTS/f'iterar_task{args.task}.json')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({k: v for k, v in salida.items() if k != 'casos'}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
