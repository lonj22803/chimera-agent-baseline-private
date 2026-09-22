"""Tabla final: brazos × tareas, fuera de pliegue, con intervalos y comparación pareada.

    python pipeline/report.py --eval-repo ../CHIMERA-agent --ref B0 \
        --arm B0="runs/B0/fold*/score.json" \
        --arm L1="runs/r16/fold*/eval/score.json" \
        --arm L1-T="runs/r16/fold*/eval_t02/score.json" \
        --out runs/REPORT.md

Para cada brazo:
  * media ± desviación entre pliegues del ``ranking_score`` por tarea y del OVERALL;
  * agregado sobre TODAS las filas fuera de pliegue juntas (una predicción por caso);
  * IC bootstrap al 95 % de la diferencia con el brazo de referencia, remuestreando
    casos de forma pareada y recalculando las métricas con el evaluador oficial;
  * T1/T2: prueba de McNemar sobre la puerta de decisión.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import statistics as st
import sys
from pathlib import Path

os.environ.setdefault("USE_RATIONALE_JUDGE", "0")
KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "agent_baseline" / "dev"))
from score_local import TASK_RANKING_WEIGHTS, load_evaluator  # noqa: E402


def load_arm(pattern: str) -> tuple[list[dict], dict[int, dict[str, dict]]]:
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"sin ficheros para {pattern}")
    folds, rows = [], {}
    for f in files:
        d = json.loads(Path(f).read_text())
        folds.append(d)
        for t, rs in d["rows"].items():
            for r in rs:
                rows.setdefault(int(t), {})[r["case_id"]] = r
    return folds, rows


def ranking(ev, task: int, rows: list[dict]) -> float | None:
    if not rows:
        return None
    agg = ev.aggregate_recurrence_metrics(rows) if task == 3 else ev.compute_aggregate_metrics(rows)
    return agg.get("ranking_score")


def overall(scores: dict[int, float | None]) -> float | None:
    ok = {t: s for t, s in scores.items() if s is not None}
    if not ok:
        return None
    return sum(s * TASK_RANKING_WEIGHTS[t] for t, s in ok.items()) / sum(TASK_RANKING_WEIGHTS[t] for t in ok)


def mcnemar(a: list[int], b: list[int]) -> float:
    n01 = sum(1 for x, y in zip(a, b) if x == 0 and y == 1)
    n10 = sum(1 for x, y in zip(a, b) if x == 1 and y == 0)
    n = n01 + n10
    if n == 0:
        return 1.0
    k = min(n01, n10)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * p)


def fmt(x, nd=4):
    return "—" if x is None else f"{x:.{nd}f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-repo", type=Path, required=True)
    ap.add_argument("--arm", action="append", required=True, help='NOMBRE="glob de score.json"')
    ap.add_argument("--ref", default=None, help="brazo de referencia para las diferencias")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    ev = load_evaluator(args.eval_repo)
    arms = {}
    for spec in args.arm:
        name, pattern = spec.split("=", 1)
        arms[name] = load_arm(pattern.strip('"'))
    tasks = sorted({t for _, rows in arms.values() for t in rows})
    lines = ["# Resultados fuera de pliegue", "",
             "| brazo | " + " | ".join(f"T{t} (media±sd pliegues)" for t in tasks) + " | OVERALL (media±sd) | OVERALL agrupado |",
             "|---|" + "---:|" * (len(tasks) + 2)]
    pooled = {}
    for name, (folds, rows) in arms.items():
        cells = []
        for t in tasks:
            vals = [f["tasks"].get(str(t), {}).get("ranking_score") for f in folds]
            vals = [v for v in vals if v is not None]
            cells.append(f"{st.mean(vals):.4f} ± {st.pstdev(vals):.4f}" if vals else "—")
        ov = [f.get("overall") for f in folds if f.get("overall") is not None]
        pooled[name] = {t: ranking(ev, t, list(rows.get(t, {}).values())) for t in tasks}
        lines.append(f"| {name} | " + " | ".join(cells)
                     + f" | {st.mean(ov):.4f} ± {st.pstdev(ov):.4f} | {fmt(overall(pooled[name]))} |"
                     if ov else f"| {name} | " + " | ".join(cells) + " | — | — |")

    if args.ref and args.ref in arms:
        rng = random.Random(args.seed)
        _, ref_rows = arms[args.ref]
        lines += ["", f"## Diferencia con {args.ref} (bootstrap pareado por caso, IC 95 %)", "",
                  "| brazo | " + " | ".join(f"ΔT{t}" for t in tasks) + " | ΔOVERALL | McNemar puerta T1 / T2 |",
                  "|---|" + "---:|" * (len(tasks) + 2)]
        for name, (_, rows) in arms.items():
            if name == args.ref:
                continue
            common = {t: sorted(set(rows.get(t, {})) & set(ref_rows.get(t, {}))) for t in tasks}
            deltas = {t: [] for t in tasks}
            dov = []
            for _ in range(args.boot):
                s_arm, s_ref = {}, {}
                for t in tasks:
                    ids = [rng.choice(common[t]) for _ in common[t]] if common[t] else []
                    s_arm[t] = ranking(ev, t, [rows[t][i] for i in ids]) if ids else None
                    s_ref[t] = ranking(ev, t, [ref_rows[t][i] for i in ids]) if ids else None
                    if s_arm[t] is not None and s_ref[t] is not None:
                        deltas[t].append(s_arm[t] - s_ref[t])
                a, b = overall(s_arm), overall(s_ref)
                if a is not None and b is not None:
                    dov.append(a - b)

            def ci(v):
                if not v:
                    return "—"
                v = sorted(v)
                return f"{st.mean(v):+.4f} [{v[int(0.025 * len(v))]:+.4f}, {v[int(0.975 * len(v)) - 1]:+.4f}]"

            mc = []
            for t in (1, 2):
                if t in tasks and common[t]:
                    a = [int(rows[t][i].get("decision_score") == 1.0) for i in common[t]]
                    b = [int(ref_rows[t][i].get("decision_score") == 1.0) for i in common[t]]
                    mc.append(f"p={mcnemar(b, a):.3f} ({sum(a)}/{len(a)} vs {sum(b)}/{len(b)})")
                else:
                    mc.append("—")
            lines.append(f"| {name} | " + " | ".join(ci(deltas[t]) for t in tasks) + f" | {ci(dov)} | {' / '.join(mc)} |")

    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)


if __name__ == "__main__":
    main()
