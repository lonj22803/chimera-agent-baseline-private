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

Sólo se juzgan los casos que pasan la puerta de decisión: el evaluador corta ahí
y ni siquiera calcula los componentes de los que fallan.

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
CLINICAL = "prostate-biopsy-decision-clinical-data.json"


def load_evaluator(eval_repo: Path):
    d = eval_repo / "evaluation"
    if not (d / "evaluate.py").exists():
        sys.exit(f"No encuentro el evaluador en {d}")
    sys.path.insert(0, str(d))
    import evaluate  # noqa: PLC0415
    return evaluate


def load_predictions(output_root: Path, data_root: Path) -> dict[str, dict]:
    """Los dos ficheros del reto por caso, más el ``clinical_data`` del socket."""
    preds: dict[str, dict] = {}
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
        clin = data_root / "agent_input" / case.name / CLINICAL
        rec["clinical_data"] = json.loads(clin.read_text()) if clin.exists() else {}
        preds[case.name] = rec
    return preds


def main() -> None:
    ap = argparse.ArgumentParser(description="Puntúa con el evaluador oficial y el juez encendido")
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--data-root", default=str(REPO / "data" / "task1"))
    ap.add_argument("--eval-repo", default=str(DEFAULT_EVAL_REPO))
    ap.add_argument("--limit", type=int, default=None, help="sólo los N primeros casos, para probar")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    ev = load_evaluator(Path(args.eval_repo))
    data_root = Path(args.data_root)
    preds = load_predictions(Path(args.output_root), data_root)
    print(f"Evaluador: {args.eval_repo}  ·  juez: {os.environ['JUDGE_MODEL']} en {os.environ['OLLAMA_BASE_URL']}")
    print(f"Predicciones: {args.output_root}  ({len(preds)} casos con salida)")

    judge = ev.build_rationale_judge()
    if judge is None:
        sys.exit("El juez no arrancó; mira el mensaje de arriba.")

    gts = ev.load_ground_truth_records(data_root / "ground_truth", "task1")
    if args.limit:
        gts = gts[: args.limit]
    rows, t0 = [], time.time()
    for i, gt in enumerate(gts, 1):
        cid = ev.get_case_id(gt)
        rows.append(ev.evaluate_case(gt, preds.get(cid), None, judge))
        if i % 10 == 0 or i == len(gts):
            done = [r for r in rows if r.get("rationale_score") is not None]
            print(f"  {i}/{len(gts)} casos · {len(done)} juzgados · "
                  f"{(time.time() - t0) / i:.1f} s/caso", flush=True)

    agg = ev.compute_aggregate_metrics(rows)
    judged = [r["rationale_score"] for r in rows if r.get("rationale_score") is not None]
    passed = [r for r in rows if r.get("decision_score") == 1.0]

    print(f"\n  ── task1 · {len(rows)} casos · {len(judged)} con razonamiento juzgado "
          f"(de {len(passed)} que pasan la puerta)")
    print(f"     mean_case_score      {agg['mean_case_score']:.4f}")
    print(f"     puerta de decision   {len(passed)}/{len(rows)} = {len(passed) / len(rows):.1%}")
    print(f"     decision_f1_yes      {agg['decision_f1_yes']:.4f}")
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
        lo = sorted((r for r in passed if r.get("rationale_score") is not None),
                    key=lambda r: r["rationale_score"])[:3]
        print("\n     las tres notas peor juzgadas:")
        for r in lo:
            print(f"        {r['case_id']}  {r['rationale_score']:.2f}  {str(r.get('reason', ''))[:150]}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"aggregate": {k: v for k, v in agg.items() if not k.startswith("_")},
             "rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]},
            indent=2, default=str))
        print(f"\n  Escrito {args.json_out}")


if __name__ == "__main__":
    main()
