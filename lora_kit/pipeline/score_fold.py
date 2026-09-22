"""Puntúa las salidas del agente en los casos de test de un pliegue, con el evaluador oficial.

    python pipeline/score_fold.py --data-root ../data --output-root runs/r16/fold0/eval_out \
        --split runs/r16/fold0/split.json --eval-repo ../CHIMERA-agent --out runs/r16/fold0/score.json

Un caso etiquetado sin salida cuenta como fallo, igual que en Grand Challenge.
Guarda también las filas por caso para las comparaciones pareadas de ``report.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("USE_RATIONALE_JUDGE", "0")  # antes de importar el evaluador

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "agent_baseline" / "dev"))
from score_local import TASK_RANKING_WEIGHTS, load_evaluator, score_task  # noqa: E402


def _clean(v):
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--split", type=Path, default=None, help="split.json de train_lora.py (usa 'test')")
    ap.add_argument("--eval-repo", type=Path, required=True)
    ap.add_argument("--tasks", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    ev = load_evaluator(args.eval_repo)
    wanted = set(json.loads(args.split.read_text())["test"]) if args.split else None
    result = {"tasks": {}, "rows": {}}
    for task in args.tasks:
        agg = score_task(ev, args.data_root, args.output_root, task, wanted, count_missing=True)
        if agg is None:
            continue
        rows = agg.pop("_rows")
        result["rows"][str(task)] = _clean(rows)
        result["tasks"][str(task)] = _clean({k: v for k, v in agg.items() if not k.startswith("_")} | {
            "n_scored": agg["_scored"], "n_missing": agg["_missing"]})
    present = [t for t in args.tasks if result["tasks"].get(str(t), {}).get("ranking_score") is not None]
    if present:
        result["overall"] = sum(result["tasks"][str(t)]["ranking_score"] * TASK_RANKING_WEIGHTS[t] for t in present) \
            / sum(TASK_RANKING_WEIGHTS[t] for t in present)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    for t in present:
        s = result["tasks"][str(t)]
        extra = s.get("decision_accuracy") if t != 3 else s.get("concordance_index")
        print(f"task{t}: ranking={s['ranking_score']:.4f}  {'acc' if t != 3 else 'c-index'}={extra}  "
              f"sin_salida={s['n_missing']}")
    if "overall" in result:
        print(f"OVERALL={result['overall']:.4f}")


if __name__ == "__main__":
    main()
