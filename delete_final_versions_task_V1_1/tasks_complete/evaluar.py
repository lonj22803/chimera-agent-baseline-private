"""Las fases de puntuación, en serie y con la GPU compartida a la fuerza.

vLLM ocupa ~28 GiB y el juez de Ollama ~6,5 GiB: en una tarjeta de 32 no caben a
la vez, así que las fases van estrictamente en serie y cada una libera lo que
cargó. Las juntas de T1/T2 y la de T3 con `--backend vllm` levantan vLLM; el juez
habla con Ollama.

Dos reglas que vienen de mediciones y no de gusto:

1. El juez **no es determinista ni dentro de una carga**: dos pases seguidos de
   T2 dieron 0,8031 y 0,8150 sin tocar nada. Por eso `--pases 2` es el mínimo
   defendible para adoptar un cambio de prosa.
2. Comparar dos corridas con el juez recargado entre medias no es comparar. La
   comparación pareada (`experiments/paired_judge.py`) puntúa base y candidato
   dentro de la misma carga, y es la única cifra con juez que admite conclusión.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

V1 = Path(__file__).resolve().parents[1]
REPO = V1.parent
JUDGE_MODEL = os.environ.get('JUDGE_MODEL', 'gemma4:e4b')
OLLAMA = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')


def free_gpu(wait=5):
    """Ollama deja el modelo residente tras responder; vLLM necesita la tarjeta entera."""
    try:
        urllib.request.urlopen(urllib.request.Request(
            OLLAMA.rstrip('/')+'/api/generate',
            data=json.dumps({'model': JUDGE_MODEL, 'keep_alive': 0}).encode(),
            headers={'Content-Type': 'application/json'}), timeout=30).read()
    except OSError:
        pass
    time.sleep(wait)
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader'],
                             text=True, capture_output=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = 'nvidia-smi no disponible'
    return out


def _python(venv):
    path = REPO/venv/'bin/python'
    return str(path) if path.exists() else sys.executable


def score_no_judge(output_root, json_out, tasks=(1, 2, 3)):
    """Evaluador oficial, juez apagado. Determinista y comparable entre corridas."""
    cmd = [_python('.venv'), str(REPO/'dev/score_local.py'), '--output-root', str(output_root),
           '--tasks', *[str(t) for t in tasks], '--count-missing', '--json-out', str(json_out)]
    return {'cmd': cmd, 'exit_code': subprocess.run(cmd, cwd=REPO).returncode}


def score_judge(output_root, out_dir, tasks=(1, 2, 3), passes=2):
    """Juez encendido, varios pases DENTRO de una sola carga; nunca se descarga en medio."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    free_gpu()
    results = []
    for task in tasks:
        for p in range(1, passes+1):
            target = out_dir/f'judge_task{task}_pase{p}.json'
            cmd = [_python('.venv-eval'), str(REPO/'dev/score_with_judge.py'),
                   '--output-root', str(output_root), '--task', str(task), '--json-out', str(target)]
            code = subprocess.run(cmd, cwd=REPO).returncode
            results.append({'task': task, 'pase': p, 'exit_code': code, 'json': str(target)})
    return {'passes': passes, 'runs': results,
            'note': 'Los pases comparten carga de Ollama. Un solo pase no distingue mejora de ruido.'}


def paired(baseline, candidate, task, split, out):
    """Base y candidato puntuados dentro de la misma carga. La única cifra con juez comparable."""
    cmd = [_python('.venv-eval'), '-m', 'delete_final_versions_task_V1_1.experiments.paired_judge',
           '--baseline', str(baseline), '--candidate', str(candidate),
           '--task', str(task), '--split', split, '--out', str(out)]
    env = {**os.environ, 'PYTHONPATH': f'{REPO}/src:{REPO}'}
    return {'cmd': cmd, 'exit_code': subprocess.run(cmd, cwd=REPO, env=env).returncode}


def contra_baseline(scores, baseline_dir=V1/'baseline_scores'):
    """Δ frente a la línea base congelada. Sin juez: comparable. Con juez: sólo pareado."""
    base = json.loads((Path(baseline_dir)/'no_judge.json').read_text())
    new = json.loads(Path(scores).read_text())
    rows = []
    for key in ('task1', 'task2', 'task3'):
        b, n = base.get(key, {}), new.get(key, {})
        if not b or not n:
            continue
        rows.append({'task': key,
                     'ranking_baseline': b.get('ranking_score'), 'ranking_nuevo': n.get('ranking_score'),
                     'delta': None if None in (b.get('ranking_score'), n.get('ranking_score'))
                     else round(n['ranking_score']-b['ranking_score'], 6),
                     'mean_case_baseline': b.get('mean_case_score'), 'mean_case_nuevo': n.get('mean_case_score')})
    weights = {'task1': 2, 'task2': 2, 'task3': 1}
    def overall(src):
        vals = [(weights[k], src[k]['ranking_score']) for k in weights
                if src.get(k, {}).get('ranking_score') is not None]
        return round(sum(w*v for w, v in vals)/sum(w for w, _ in vals), 10) if vals else None
    return {'por_tarea': rows, 'overall_baseline': overall(base), 'overall_nuevo': overall(new),
            'aviso': 'Sin juez. El OVERALL con juez sólo es comparable en pases pareados.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-root', type=Path, help='raíz con task1/ task2/ task3/')
    p.add_argument('--out-dir', type=Path, default=V1/'verification/scores')
    p.add_argument('--tasks', nargs='+', type=int, default=[1, 2, 3])
    p.add_argument('--pases', type=int, default=2, help='pases del juez dentro de una carga')
    p.add_argument('--con-juez', action='store_true')
    p.add_argument('--contra', type=Path, help='comparar unos scores ya escritos contra la línea base')
    args = p.parse_args()
    if args.contra:
        print(json.dumps(contra_baseline(args.contra), indent=2, ensure_ascii=False))
        return
    if not args.output_root:
        p.error('--output-root es obligatorio salvo con --contra')
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = {'vram_antes': free_gpu()}
    report['sin_juez'] = score_no_judge(args.output_root, args.out_dir/'no_judge.json', args.tasks)
    if (args.out_dir/'no_judge.json').exists():
        report['contra_baseline'] = contra_baseline(args.out_dir/'no_judge.json')
    if args.con_juez:
        report['con_juez'] = score_judge(args.output_root, args.out_dir, args.tasks, args.pases)
    (args.out_dir/'evaluacion.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
