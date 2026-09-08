"""Puntúa una corrida con el evaluador oficial y la compara, caso a caso, con
las generaciones anteriores sobre exactamente los mismos casos.

    python -m ...analysis.compare --run runs/deployed [--others baseline junta v2]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[3]
os.environ.setdefault("USE_RATIONALE_JUDGE", "0")
sys.path.insert(0, str(Path.home() / "PycharmProjects" / "CHIMERA-agent-eval" / "evaluation"))
import evaluate as ev  # noqa: E402

DATA = REPO / "data" / "task1"
OTHERS = {
    "baseline": REPO / "delete_solution_one" / "solution_task_one_correction_claude" / "runs" / "baseline_t0" / "output",
    "pizarra_v1": REPO / "delete_solution_one" / "solution_task_one" / "runs" / "run2" / "output",
    "pizarra_v2": REPO / "delete_solution_one" / "solution_task_one_correction_claude" / "runs" / "full" / "output",
    "junta": REPO / "delete_solution_one" / "solution_task_one_correction_II" / "runs" / "full3" / "output",
}
COMPONENTS = ("confidence_score", "variable_weight_score", "important_decisive_factor_score", "tool_score",
              "section_grounding_score")


def load_preds(output_root: Path) -> dict[str, dict]:
    preds = {}
    task_dir = output_root / "task1"
    if not task_dir.is_dir():
        return preds
    for case in sorted(p for p in task_dir.iterdir() if p.is_dir()):
        d, r = case / "prostate-biopsy-decision.json", case / "prostate-biopsy-decision-reasoning.json"
        if not (d.exists() and r.exists()):
            continue
        rec = json.loads(r.read_text())
        rec["biopsy_decision"] = json.loads(d.read_text())
        rec["case_id"] = case.name
        preds[case.name] = rec
    return preds


def score(preds: dict[str, dict], wanted: set[str]) -> dict:
    gts = ev.load_ground_truth_records(DATA / "ground_truth", "task1")
    rows = []
    for gt in gts:
        cid = ev.get_case_id(gt)
        if cid not in wanted:
            continue
        rows.append(ev.evaluate_case(gt, preds.get(cid), None, None))
    agg = ev.compute_aggregate_metrics(rows)
    out = {"n": len(rows), "ranking": agg["ranking_score"], "mean_case": agg["mean_case_score"],
           "f1_yes": agg["decision_f1_yes"], "gate": agg["decision_accuracy"],
           "missing": sum(1 for r in rows if r["gate"] == "missing_candidate")}
    for k in COMPONENTS:
        vals = [r[k] for r in rows if r.get(k) is not None]
        out[k] = mean(vals) if vals else None
    out["_rows"] = {r["case_id"]: r for r in rows}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="carpeta de la corrida (con output/task1)")
    ap.add_argument("--others", nargs="*", default=list(OTHERS))
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    run_root = Path(args.run)
    mine = load_preds(run_root / "output")
    wanted = set(mine)
    results = {"this": score(mine, wanted)}
    for name in args.others:
        p = OTHERS.get(name)
        if p and p.exists():
            results[name] = score(load_preds(p), wanted)
    print(f"casos comparados: {len(wanted)}\n")
    head = f"{'':14}{'ranking':>9}{'case':>8}{'f1_yes':>8}{'gate':>7}{'conf':>7}{'weight':>8}{'factor':>8}{'tool':>7}{'ground':>8}{'miss':>6}"
    print(head)
    for name, s in results.items():
        print(f"{name:14}{s['ranking']:9.4f}{s['mean_case']:8.4f}{s['f1_yes']:8.4f}{s['gate']:7.3f}"
              f"{(s['confidence_score'] or 0):7.3f}{(s['variable_weight_score'] or 0):8.3f}"
              f"{(s['important_decisive_factor_score'] or 0):8.3f}{(s['tool_score'] or 0):7.3f}"
              f"{(s['section_grounding_score'] or 0):8.3f}{s['missing']:6d}")
    # pareado
    this = results["this"]["_rows"]
    for name, s in results.items():
        if name == "this":
            continue
        up = down = tie = 0
        for cid, r in this.items():
            o = s["_rows"].get(cid)
            if o is None:
                continue
            d = r["case_score"] - o["case_score"]
            up += d > 1e-9; down += d < -1e-9; tie += abs(d) <= 1e-9
        print(f"\nfrente a {name}: {up} casos suben, {down} bajan, {tie} empatan")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "_rows"}
                                                   for k, v in results.items()}, indent=2))


if __name__ == "__main__":
    main()
