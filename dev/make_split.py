"""Estratifica los casos etiquetados en dev / val.

Solo una parte de los casos trae ground truth: los demas son, con toda
probabilidad, el conjunto de test. Este script parte SOLO los etiquetados, y lo
hace de forma estratificada porque las clases estan muy desbalanceadas —
``watchful_waiting`` tiene 2 casos de 72 en task 2, asi que un corte ingenuo
deja la validacion sin ningun ejemplo de esa clase.

    python dev/make_split.py                  # escribe dev/splits/
    python dev/make_split.py --val-frac 0.3

La semilla esta fijada: el mismo split en cada ejecucion, o los numeros entre
iteraciones no son comparables.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

GT_DECISION = {
    1: "prostate-biopsy-decision.json",
    2: "prostate-treatment-decision.json",
    3: "prostate-time-to-recurrence-or-last-follow-up.json",
}


def _stratum(task: int, payload) -> str:
    """La etiqueta por la que estratificar."""
    if task == 3:
        # En supervivencia lo escaso es el evento, no el tiempo.
        return f"event={payload.get('event')}"
    return str(payload)


def collect(data_root: Path, task: int) -> dict[str, str]:
    """``case_id -> estrato`` para los casos con etiqueta."""
    gt_dir = data_root / f"task{task}" / "ground_truth"
    if not gt_dir.is_dir():
        return {}
    out: dict[str, str] = {}
    for case in sorted(p for p in gt_dir.iterdir() if p.is_dir()):
        f = case / GT_DECISION[task]
        if not f.exists():
            continue
        out[case.name] = _stratum(task, json.loads(f.read_text()))
    return out


def split(labelled: dict[str, str], val_frac: float, seed: int) -> tuple[list[str], list[str]]:
    """Corta cada estrato por separado, con al menos 1 caso en val si hay 2+."""
    by_stratum: dict[str, list[str]] = defaultdict(list)
    for case_id, stratum in labelled.items():
        by_stratum[stratum].append(case_id)

    rng = random.Random(seed)
    dev: list[str] = []
    val: list[str] = []
    for stratum in sorted(by_stratum):
        cases = sorted(by_stratum[stratum])
        rng.shuffle(cases)
        n_val = round(len(cases) * val_frac)
        if len(cases) >= 2:
            n_val = max(1, min(n_val, len(cases) - 1))
        val.extend(cases[:n_val])
        dev.extend(cases[n_val:])
    return sorted(dev), sorted(val)


def main() -> None:
    ap = argparse.ArgumentParser(description="Split estratificado de los casos etiquetados")
    ap.add_argument("--data-root", default="data")
    ap.add_argument("--out-dir", default="dev/splits")
    ap.add_argument("--val-frac", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=20260903)
    args = ap.parse_args()

    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for task in (1, 2, 3):
        labelled = collect(data_root, task)
        if not labelled:
            print(f"task{task}: sin ground truth, saltando")
            continue

        dev, val = split(labelled, args.val_frac, args.seed)
        for name, cases in (("dev", dev), ("val", val)):
            (out_dir / f"task{task}_{name}.txt").write_text("\n".join(cases) + "\n")

        counts = Counter(labelled.values())
        dev_counts = Counter(labelled[c] for c in dev)
        val_counts = Counter(labelled[c] for c in val)
        print(f"task{task}: {len(labelled)} etiquetados -> {len(dev)} dev / {len(val)} val")
        for stratum in sorted(counts):
            print(
                f"    {stratum:26} total {counts[stratum]:3d}"
                f" | dev {dev_counts[stratum]:3d} | val {val_counts[stratum]:3d}"
            )

    print(f"\nEscrito en {out_dir}/. Para correr solo un split:")
    print('    make run RUN_ARGS="agent.tasks=[1] agent.pids=[$(paste -sd, dev/splits/task1_val.txt)]"')


if __name__ == "__main__":
    main()
