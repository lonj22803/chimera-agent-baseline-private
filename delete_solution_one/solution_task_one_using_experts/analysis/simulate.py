"""Simula el protocolo SIN LLM y lo puntúa con el evaluador oficial.

Con el juez de razonamiento apagado, el ``case_score`` depende sólo de la
decisión, la confianza, los pesos, las revelaciones y el aterrizaje — y en
esta junta esas cinco cosas las fija el código (protocolo + traza + guardia),
no el presidente. Así que se puede calcular la nota de una configuración sin
cargar el modelo, en segundos, asumiendo que el registrador abre exactamente
lo que el plan nombra (que es lo que la corrida real verifica).

Sirve para dos cosas:

* elegir los parámetros del protocolo (política de confianza, política de
  pesos, umbral, k) mirando la cifra **honesta**, no la memorizada;
* saber, antes de correr, qué nota debería salir en cada modo, y comparar
  después con lo que el LLM entregó de verdad (la diferencia mide cuánto
  estorba o ayuda la sala).

    python -m delete_solution_one.solution_task_one_using_experts.analysis.simulate --grid
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "src"), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("USE_RATIONALE_JUDGE", "0")

from delete_solution_one.solution_task_one_using_experts import protocol as P  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.decide import documented_grade, enforce_grounding  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.experts import cohort as cohort_expert  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.experts import trace as trace_expert  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.experts.library import Library  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.experts.panel import CACHE, Panel  # noqa: E402

DATA = REPO / "data" / "task1"
EVAL = Path.home() / "PycharmProjects" / "CHIMERA-agent-eval" / "evaluation"
SECTION_TEXT = {"previous_notes": "previous_notes", "radiology_report": "radiology_report",
                "laboratory_results": "laboratory_results", "psa_trend": "psa_trend"}


def _evaluator():
    sys.path.insert(0, str(EVAL))
    import evaluate  # noqa: PLC0415
    return evaluate


def _corpus(clinical: dict, opened: list[str]) -> str:
    parts = []
    for s in opened:
        v = clinical.get(s)
        if v is not None:
            parts.append(json.dumps(v, ensure_ascii=False))
    return "\n".join(parts)


def simulate(mode: str, exclude_self: bool, k: int, params: dict, weights_policy: str,
             panel: Panel, only: set[str] | None = None) -> list[dict]:
    library = Library(DATA, exclude_self=exclude_self, k=k)
    rows = []
    for d in sorted(p for p in (DATA / "ground_truth").iterdir() if p.is_dir()):
        cid = d.name
        if only and cid not in only:
            continue
        payload = json.loads((DATA / "agent_input" / cid / "structured-prompt.json").read_text())
        clinical = json.loads((DATA / "agent_input" / cid / "prostate-biopsy-decision-clinical-data.json").read_text())
        _, cohort = cohort_expert.render(payload)
        lib = library.precedents(cid, payload)
        bucket_mode = library.bucket_mode(str(payload.get("bx") or "None"), exclude=cid if exclude_self else None)
        trace = trace_expert.predict(panel, cid, mode, lib, bucket_mode, weights_policy=weights_policy)
        opened = [s for s in trace["reveal_sequence"] if s != "family_history"]
        v = panel.verdicts(cid, mode)
        structured = {**v["structured"], "available": True}
        fusion = ({**v["fusion_full" if "laboratory_results" in opened else "fusion_nolab"], "available": True,
                   "variant": "fusion_full" if "laboratory_results" in opened else "fusion_nolab"}
                  if "radiology_report" in opened else {"available": False})
        grade = documented_grade(_corpus(clinical, opened))
        res = P.consolidate(payload, cohort, structured, fusion, lib, trace, grade, opened, params=params)
        pred = {"biopsy_decision": res["decision"], "confidence": res["confidence"],
                "variable_weights": dict(res["variable_weights"]), "reveal_sequence": opened,
                "free_text": "simulated", "case_id": cid}
        pred, _ = enforce_grounding(pred, opened)
        rows.append({"case_id": cid, "pred": pred, "rule": res["rule"], "who": res["who"], "bx": payload.get("bx")})
    return rows


def score(rows: list[dict]) -> dict:
    ev = _evaluator()
    gts = {ev.get_case_id(g): g for g in ev.load_ground_truth_records(DATA / "ground_truth", "task1")}
    out_rows = [ev.evaluate_case(gts[r["case_id"]], r["pred"], None, None) for r in rows if r["case_id"] in gts]
    agg = ev.compute_aggregate_metrics(out_rows)
    comps = {}
    for key in ("confidence_score", "variable_weight_score", "important_decisive_factor_score", "tool_score",
                "section_grounding_score"):
        vals = [r[key] for r in out_rows if r.get(key) is not None]
        comps[key] = sum(vals) / len(vals) if vals else None
    by_bucket = {}
    for r, o in zip(rows, out_rows):
        b = str(r["bx"])
        by_bucket.setdefault(b, [0, 0])
        by_bucket[b][0] += int(o["decision_score"] == 1.0)
        by_bucket[b][1] += 1
    return {"ranking": agg["ranking_score"], "mean_case": agg["mean_case_score"], "f1_yes": agg["decision_f1_yes"],
            "gate": agg["decision_accuracy"], "components": comps,
            "by_bucket": {b: f"{h}/{n}" for b, (h, n) in by_bucket.items()}, "rows": out_rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--mode", default=None, choices=["deployed", "honest"])
    args = ap.parse_args()
    panel = Panel(Path(args.cache))

    def run(mode, exclude_self, k, conf, wpol, thr, libw, grade):
        params = {**P.PARAMS, "confidence_policy": conf, "threshold": thr, "library_weight": libw, "grade_rule": grade}
        s = score(simulate(mode, exclude_self, k, params, wpol, panel))
        c = s["components"]
        print(f"{mode:9} self={'no ' if exclude_self else 'yes'} k={k} conf={conf:9} w={wpol:10} thr={thr:.2f} "
              f"libw={libw:.1f} grade={int(grade)} | ranking {s['ranking']:.4f} case {s['mean_case']:.4f} "
              f"f1 {s['f1_yes']:.4f} gate {s['gate']:.3f} {s['by_bucket']} | conf {c['confidence_score']:.3f} "
              f"w {c['variable_weight_score']:.3f} f1f {c['important_decisive_factor_score']:.3f} "
              f"tool {c['tool_score']:.3f} gnd {c['section_grounding_score']:.3f}")
        return s

    if args.grid:
        print("=== honest (out-of-fold panel, library leave-one-out) ===")
        for conf, wpol, thr, libw, grade in itertools.product(
                ("trace", "agreement"), ("model+mode", "mode", "model"), (0.5, 0.45, 0.4), (0.5, 0.0), (True, False)):
            run("honest", True, 3, conf, wpol, thr, libw, grade)
        print("\n=== honest, k ===")
        for k in (1, 3, 5, 7):
            run("honest", True, k, "trace", "model+mode", 0.5, 0.5, True)
        print("\n=== deployed (panel as trained, library includes the case) ===")
        run("deployed", False, 3, "trace", "model+mode", 0.5, 0.5, True)
        run("deployed", False, 3, "agreement", "model+mode", 0.5, 0.5, True)
        print("\n=== deployed panel but library leave-one-out (what memorisation the experts alone give) ===")
        run("deployed", True, 3, "trace", "model+mode", 0.5, 0.5, True)
    else:
        modes = [args.mode] if args.mode else ["deployed", "honest"]
        for mode in modes:
            run(mode, mode == "honest", 3, P.PARAMS["confidence_policy"], "model+mode", P.PARAMS["threshold"],
                P.PARAMS["library_weight"], P.PARAMS["grade_rule"])


if __name__ == "__main__":
    main()
