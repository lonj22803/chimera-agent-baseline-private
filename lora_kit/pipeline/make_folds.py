"""Pliegues de validación cruzada estratificados, para las tres tareas.

    python pipeline/make_folds.py --data-root ../data --out runs/folds.json --k 5

* Estrato: T1 la decisión, T2 la acción, T3 el evento.
* Grupo: el ``pid`` del paciente; todas sus muestras caen en el mismo pliegue.
* Semilla fija: los pliegues no cambian entre ejecuciones. No los regeneres a mitad
  de un experimento o los números dejan de ser comparables.

Salida: ``{"1": {case_id: fold}, "2": {...}, "3": {...}}``.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_sft import load_labelled_cases  # noqa: E402


def stratum(task: int, decision) -> str:
    return f"event={decision.get('event')}" if task == 3 else str(decision)


def assign(cases: list[dict], task: int, k: int, rng: random.Random) -> dict[str, int]:
    # Un grupo (paciente) = una unidad; su estrato es el de su primer caso.
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        groups[c["group"]].append(c)
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for g, members in groups.items():
        by_stratum[stratum(task, members[0]["gt_decision"])].append(g)

    fold_of: dict[str, int] = {}
    offset = 0
    for s in sorted(by_stratum):
        gs = sorted(by_stratum[s])
        rng.shuffle(gs)
        # Reparto circular continuando donde acabó el estrato anterior, para que
        # las clases pequeñas no se concentren siempre en el pliegue 0.
        for i, g in enumerate(gs):
            f = (offset + i) % k
            for c in groups[g]:
                fold_of[c["case_id"]] = f
        offset += len(gs)
    return fold_of


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tasks", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260922)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out: dict[str, dict[str, int]] = {}
    for task in args.tasks:
        cases = load_labelled_cases(args.data_root, task)
        out[str(task)] = assign(cases, task, args.k, rng)
        table = Counter((f, stratum(task, c["gt_decision"])) for c in cases for f in [out[str(task)][c["case_id"]]])
        print(f"task{task}: {len(cases)} casos")
        for f in range(args.k):
            row = {s: n for (ff, s), n in sorted(table.items()) if ff == f}
            print(f"  pliegue {f}: {row}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
