"""Un solo punto de entrada para las tres juntas.

Los tres `run_taskN.py` aceptan banderas distintas por razones históricas. Este
módulo traduce un vocabulario común al de cada runner y delega: no reimplementa
ningún grafo, así que lo que se lanza desde aquí es exactamente el código medido.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PKG = 'delete_final_versions_task_V1_1'


def build_command(task, out_root, split, backend='vllm', mode=None, limit=None, extra=()):
    """Argumentos del runner de esa tarea. `split='all'` es la cobertura completa."""
    cmd = [sys.executable, '-m', f'{PKG}.task_{task}.agent.run_task{task}',
           '--out-root', str(out_root), '--split', split]
    if task == 3:
        cmd += ['--backend', backend, '--mode', mode or ('deployed' if backend == 'vllm' else 'oof')]
    elif mode:
        cmd += ['--mode', mode]
    if limit:
        cmd += ['--limit', str(limit)]
    return cmd + list(extra)


def run(task, out_root, split='all', backend='vllm', mode=None, limit=None, extra=(), log=None):
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    cmd = build_command(task, out_root, split, backend, mode, limit, extra)
    (out_root/'command.json').write_text(json.dumps(cmd, indent=2)+'\n')
    start = time.monotonic()
    env = {'PYTHONPATH': f'{REPO}/src:{REPO}'}
    handle = open(log, 'w') if log else None
    try:
        proc = subprocess.run(cmd, cwd=REPO, stdout=handle or None, stderr=subprocess.STDOUT,
                              env={**__import__('os').environ, **env})
    finally:
        if handle:
            handle.close()
    return {'task': task, 'exit_code': proc.returncode, 'seconds': round(time.monotonic()-start, 1),
            'out_root': str(out_root), 'split': split, 'backend': backend if task == 3 else 'vllm'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task', type=int, required=True, choices=[1, 2, 3])
    p.add_argument('--out-root', type=Path, required=True)
    p.add_argument('--split', default='all', choices=['all', 'labeled', 'unlabeled', 'dev', 'val'])
    p.add_argument('--backend', default='vllm', choices=['vllm', 'ollama'], help='sólo tarea 3')
    p.add_argument('--mode', default=None)
    p.add_argument('--limit', type=int)
    p.add_argument('--log', type=Path)
    args, extra = p.parse_known_args()
    result = run(args.task, args.out_root, args.split, args.backend, args.mode, args.limit, extra, args.log)
    print(json.dumps(result, indent=2))
    raise SystemExit(result['exit_code'])


if __name__ == '__main__':
    main()
