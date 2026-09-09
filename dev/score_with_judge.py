"""Puntúa una corrida con el evaluador OFICIAL y el **juez de razonamiento activado**.

Es el hermano de ``dev/score_local.py``, que corre en modo determinista con el
juez apagado. Aquí se enciende, que es como puntúa Grand Challenge:

* el juez es el de los organizadores, no uno propio: ``build_rationale_judge()``
  de su ``evaluate.py``, que monta un ``GEval`` de DeepEval sobre Ollama con el
  modelo ``gemma4:e4b`` y su rúbrica literal;
* el ``clinical_data`` se adjunta al registro de predicción **igual que hace
  ``process_interf0``** en el pipeline real, leyéndolo del socket de entrada del
  caso. Sin él la rúbrica no puede comprobar su criterio (3), «no contradice los
  datos clínicos», y el juez puntuaría a ciegas;
* con el juez encendido los pesos son otros: rationale 0.20, confidence 0.20,
  var_weight 0.25, factor_f1 0.15, tool 0.15, section_grounding 0.05. Un número
  de aquí **no es comparable** con uno de ``score_local.py``, donde el 0.20 del
  juez se reparte entre los otros cinco.

En las tareas 1/2 sólo se juzgan los casos que pasan la puerta de decisión.
La tarea 3 usa las métricas de recurrencia y no tiene esa puerta.

Un aviso esperable con este layout: el evaluador imprime «missing clinical data»
por cada caso, porque busca el ``*-clinical-data.json`` **dentro de**
``ground_truth/<caso>/`` y aquí las entradas y las etiquetas viven separadas a
propósito, para que el agente no pueda ver la respuesta. Es inofensivo: la
rúbrica lee el contexto clínico de ``pred["clinical_data"]``, no del ground
truth, y este script se lo adjunta desde ``agent_input/`` igual que hace
``process_interf0``.

    .venv-eval/bin/python dev/score_with_judge.py \
        --output-root delete_solution_one/solution_task_one_using_experts_final/runs/final/output

Se ejecuta con ``.venv-eval`` y no con ``.venv``: DeepEval arrastra su propio
árbol de dependencias y el entorno de entrega tiene ``mcp`` y vLLM fijados.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from statistics import mean

os.environ["USE_RATIONALE_JUDGE"] = "1"
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("JUDGE_MODEL", "gemma4:e4b")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

REPO = Path(__file__).resolve().parents[1]
DEFAULT_EVAL_REPO = Path.home() / "PycharmProjects" / "CHIMERA-agent-eval"
DECISION = {
    1: "prostate-biopsy-decision.json",
    2: "prostate-treatment-decision.json",
    3: "prostate-time-to-recurrence-or-last-follow-up.json",
}
REASONING = {task: name.removesuffix(".json") + "-reasoning.json" for task, name in DECISION.items()}
CLINICAL = {task: name.removesuffix(".json") + "-clinical-data.json" for task, name in DECISION.items()}


def load_evaluator(eval_repo: Path):
    d = eval_repo / "evaluation"
    if not (d / "evaluate.py").exists():
        sys.exit(f"No encuentro el evaluador en {d}")
    sys.path.insert(0, str(d))
    import evaluate  # noqa: PLC0415
    return evaluate


def load_predictions(output_root: Path, data_root: Path, task: int = 1) -> dict[str, dict]:
    """Los dos ficheros del reto por caso, más el ``clinical_data`` del socket."""
    preds: dict[str, dict] = {}
    task_dir = output_root / f"task{task}"
    if not task_dir.is_dir():
        return preds
    for case in sorted(p for p in task_dir.iterdir() if p.is_dir()):
        d, r = case / DECISION[task], case / REASONING[task]
        if not (d.exists() and r.exists()):
            continue
        rec = json.loads(r.read_text())
        decision = json.loads(d.read_text())
        if task == 3:
            rec = {"free_text": rec}
            rec.update(decision)
        else:
            rec["biopsy_decision" if task == 1 else "action"] = decision
            if task == 2:
                # The official evaluator reads the GC treatment wrapper.
                rec["treatment_recommendation"] = {"primary": decision}
        rec["case_id"] = case.name
        clin = data_root / "agent_input" / case.name / CLINICAL[task]
        rec["clinical_data"] = json.loads(clin.read_text()) if clin.exists() else {}
        preds[case.name] = rec
    return preds


def main() -> None:
    ap = argparse.ArgumentParser(description="Puntúa con el evaluador oficial y el juez encendido")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--task", type=int, choices=(1, 2, 3), default=1)
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--eval-repo", default=str(DEFAULT_EVAL_REPO))
    ap.add_argument("--limit", type=int, default=None, help="sólo los N primeros casos, para probar")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    ev = load_evaluator(Path(args.eval_repo))
    task = args.task
    data_root = Path(args.data_root) if args.data_root else REPO / "data" / f"task{task}"
    preds = load_predictions(Path(args.output_root), data_root, task)
    print(f"Evaluador: {args.eval_repo}  ·  juez: {os.environ['JUDGE_MODEL']} en {os.environ['OLLAMA_BASE_URL']}")
    print(f"Predicciones: {args.output_root}  ({len(preds)} casos con salida)")

    if not preds:
        print(f"\n  ── task{task} · 0 casos con salida; nada que juzgar")
        if args.json_out:
            out = Path(args.json_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"aggregate": {"n_cases": 0}, "rows": []}, indent=2))
        return

    judge = ev.build_rationale_judge()
    if judge is None:
        sys.exit("El juez no arrancó; mira el mensaje de arriba.")

    gts = ev.load_ground_truth_records(data_root / "ground_truth", f"task{task}")
    if args.limit:
        gts = gts[: args.limit]
    rows, t0 = [], time.time()
    for i, gt in enumerate(gts, 1):
        cid = ev.get_case_id(gt)
        if task == 3:
            rows.append(ev.evaluate_recurrence_case(gt, preds.get(cid), judge))
        else:
            rows.append(ev.evaluate_case(gt, preds.get(cid), None, judge))
        if i % 10 == 0 or i == len(gts):
            done = [r for r in rows if r.get("rationale_score") is not None]
            print(f"  {i}/{len(gts)} casos · {len(done)} juzgados · "
                  f"{(time.time() - t0) / i:.1f} s/caso", flush=True)

    if not rows:
        agg = {"n_cases": 0}
    elif task == 3:
        agg = ev.aggregate_recurrence_metrics(rows)
    else:
        agg = ev.compute_aggregate_metrics(rows)
    judged = [r["rationale_score"] for r in rows if r.get("rationale_score") is not None]
    passed = [r for r in rows if r.get("decision_score") == 1.0]

    if not rows:
        print(f"\n  ── task{task} · 0 casos")
    elif task == 3:
        print(f"\n  ── task3 · {len(rows)} casos · {len(judged)} con razonamiento juzgado")
        for key in ("ranking_score", "mean_case_score", "mean_event_score", "mean_time_score",
                    "event1_time_mae_months", "time_dependent_auc", "mean_rationale_score"):
            value = agg[key]
            formatted = f"{value:.4f}" if isinstance(value, (int, float)) else json.dumps(value)
            print(f"     {key:26} {formatted}")
    else:
        print(f"\n  ── task{task} · {len(rows)} casos · {len(judged)} con razonamiento juzgado "
              f"(de {len(passed)} que pasan la puerta)")
        print(f"     mean_case_score      {agg['mean_case_score']:.4f}")
        print(f"     puerta de decision   {len(passed)}/{len(rows)} = {len(passed) / len(rows):.1%}")
        f1_key = "decision_f1_yes" if task == 1 else "decision_weighted_f1"
        print(f"     {f1_key:20} {agg[f1_key]:.4f}")
        print("     componentes, solo casos que pasan la puerta:")
        for key, w in (("rationale_score", 0.20), ("variable_weight_score", 0.25), ("confidence_score", 0.20),
                       ("important_decisive_factor_score", 0.15), ("tool_score", 0.15),
                       ("section_grounding_score", 0.05)):
            vals = [r[key] for r in passed if r.get(key) is not None]
            if vals:
                m = mean(vals)
                print(f"        {key:36} {m:.4f}   (peso {w:.2f} -> aporta {m * w:.4f})")
        print(f"     RANKING_SCORE        {agg['ranking_score']:.4f}")

    if judged:
        lo = sorted((r for r in (rows if task == 3 else passed) if r.get("rationale_score") is not None),
                    key=lambda r: r["rationale_score"])[:3]
        print("\n     las tres notas peor juzgadas:")
        for r in lo:
            print(f"        {r['case_id']}  {r['rationale_score']:.2f}  {str(r.get('reason', ''))[:150]}")

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(
            {"aggregate": {k: v for k, v in agg.items() if not k.startswith("_")},
             "rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]},
            indent=2, default=str))
        print(f"\n  Escrito {args.json_out}")


if __name__ == "__main__":
    main()
