"""Puntua ``test/output/`` con el evaluador OFICIAL, sin Docker.

Importa las funciones de scoring de ``DIAGNijmegen/CHIMERA-agent/evaluation``
en vez de reimplementarlas: si los organizadores cambian los pesos, este script
cambia con ellos. Reimplementar la metrica es la forma mas rapida de optimizar
contra un numero que no existe.

    python dev/score_local.py                        # todo lo que haya en test/output/
    python dev/score_local.py --split val            # solo los casos de dev/splits/
    python dev/score_local.py --tasks 1 2

Requiere el repo de evaluacion clonado. Por defecto lo busca como hermano del
proyecto; usa --eval-repo si lo tienes en otro sitio.

El juez de razonamiento (Ollama) queda DESACTIVADO: es el modo determinista y
reproducible para iterar. Ojo — apagarlo *redistribuye* los pesos, no los pone
a cero, asi que un numero de aqui no es comparable con uno obtenido con juez.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean

# Antes de importar el evaluador: su modulo lee esta variable al cargarse.
os.environ.setdefault("USE_RATIONALE_JUDGE", "0")

DEFAULT_EVAL_REPO = Path.home() / "PycharmProjects" / "CHIMERA-agent-eval"

PRED_FILES = {
    1: ("prostate-biopsy-decision.json", "prostate-biopsy-decision-reasoning.json"),
    2: ("prostate-treatment-decision.json", "prostate-treatment-decision-reasoning.json"),
    3: ("prostate-time-to-recurrence-or-last-follow-up.json", None),
}

TASK_RANKING_WEIGHTS = {1: 2.0, 2: 2.0, 3: 1.0}


def load_evaluator(eval_repo: Path):
    """Importa el evaluate.py oficial."""
    evaluation_dir = eval_repo / "evaluation"
    if not (evaluation_dir / "evaluate.py").exists():
        sys.exit(
            f"No encuentro el evaluador en {evaluation_dir}.\n"
            "Clonalo con:  git clone https://github.com/DIAGNijmegen/CHIMERA-agent.git "
            f"{eval_repo}"
        )
    sys.path.insert(0, str(evaluation_dir))
    import evaluate  # noqa: PLC0415 — la ruta se inyecta arriba

    return evaluate


def load_predictions(output_root: Path, task: int) -> dict[str, dict]:
    """Lee ``test/output/task<N>/<case>/`` al mismo shape plano que el ground truth."""
    task_dir = output_root / f"task{task}"
    if not task_dir.is_dir():
        return {}

    decision_name, reasoning_name = PRED_FILES[task]
    preds: dict[str, dict] = {}
    for case in sorted(p for p in task_dir.iterdir() if p.is_dir()):
        decision_file = case / decision_name
        if not decision_file.exists():
            continue
        decision = json.loads(decision_file.read_text())

        if task == 3:
            record = dict(decision) if isinstance(decision, dict) else {}
        else:
            reasoning_file = case / reasoning_name
            if not reasoning_file.exists():
                continue
            record = json.loads(reasoning_file.read_text())
            if not isinstance(record, dict):
                continue
            record = dict(record)
            if task == 1:
                record["biopsy_decision"] = decision
            else:
                record["treatment_recommendation"] = {"primary": decision}

        record["case_id"] = case.name
        preds[case.name] = record
    return preds


def read_split(split_dir: Path, task: int, split: str) -> set[str] | None:
    if split == "all":
        return None
    f = split_dir / f"task{task}_{split}.txt"
    if not f.exists():
        sys.exit(f"No existe {f}. Genera los splits con:  python dev/make_split.py")
    return {line.strip() for line in f.read_text().splitlines() if line.strip()}


def score_task(
    ev,
    data_root: Path,
    output_root: Path,
    task: int,
    wanted: set[str] | None,
    count_missing: bool = False,
) -> dict | None:
    gt_records = ev.load_ground_truth_records(data_root / f"task{task}" / "ground_truth", f"task{task}")
    preds = load_predictions(output_root, task)

    rows = []
    scored = missing = 0
    for gt in gt_records:
        case_id = ev.get_case_id(gt)
        if wanted is not None and case_id not in wanted:
            continue
        pred = preds.get(case_id)
        if pred is None:
            missing += 1
            if not count_missing:
                continue
            # Asi lo cuenta el evaluador oficial cuando un job no entrega
            # salida: puntua el caso con pred=None en vez de ignorarlo. Es lo
            # que pasa en Grand Challenge si el contenedor aborta.
            rows.append(ev.evaluate_case(gt, None, None, None))
            continue
        rows.append(ev.evaluate_case(gt, pred, None, None))
        scored += 1

    if not rows:
        print(f"  task{task}: 0 casos puntuables ({missing} etiquetados sin prediccion todavia)")
        return None

    agg = ev.aggregate_recurrence_metrics(rows) if task == 3 else ev.compute_aggregate_metrics(rows)
    agg["_scored"] = scored
    agg["_missing"] = missing
    agg["_rows"] = rows
    agg["_count_missing"] = count_missing
    return agg


def report(task: int, agg: dict) -> None:
    nota = " (contados como fallo)" if agg["_count_missing"] else " (excluidos)"
    print(
        f"\n  ── task{task} · {agg['_scored']} con prediccion, "
        f"{agg['_missing']} sin ella{nota if agg['_missing'] else ''}"
    )
    print(f"     mean_case_score      {agg.get('mean_case_score', float('nan')):.4f}")
    if task == 3:
        for k in ("c_index", "mean_event_score", "mean_time_score"):
            if agg.get(k) is not None:
                print(f"     {k:20} {agg[k]:.4f}")
    else:
        gate = sum(1 for r in agg["_rows"] if r.get("decision_score") == 1.0)
        print(f"     puerta de decision   {gate}/{agg['_scored']} = {gate / agg['_scored']:.1%}")
        for k in ("decision_f1_yes", "decision_weighted_f1"):
            if agg.get(k) is not None:
                print(f"     {k:20} {agg[k]:.4f}")
        # El agregado oficial no expone los componentes por caso, solo el
        # case_score compuesto. Los promediamos aqui sobre las filas que pasan
        # la puerta, que son las unicas donde se calculan.
        passed = [r for r in agg["_rows"] if r.get("decision_score") == 1.0]
        if passed:
            print("     componentes, solo casos que pasan la puerta (media sobre las filas):")
            for key, weight in (
                ("variable_weight_score", 0.275),
                ("confidence_score", 0.225),
                ("important_decisive_factor_score", 0.175),
                ("section_grounding_score", 0.175),
                ("tool_score", 0.150),
            ):
                vals = [r[key] for r in passed if r.get(key) is not None]
                if vals:
                    m = mean(vals)
                    print(f"        {key:36} {m:.4f}   (peso {weight:.3f} -> aporta {m * weight:.4f})")
    if agg.get("ranking_score") is not None:
        print(f"     RANKING_SCORE        {agg['ranking_score']:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Puntua test/output/ con el evaluador oficial")
    ap.add_argument("--data-root", default="data")
    ap.add_argument("--output-root", default="test/output")
    ap.add_argument("--eval-repo", default=str(DEFAULT_EVAL_REPO))
    ap.add_argument("--split-dir", default="dev/splits")
    ap.add_argument("--split", default="all", choices=["all", "dev", "val"])
    ap.add_argument("--tasks", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--json-out", default=None, help="Vuelca los agregados a un fichero")
    ap.add_argument(
        "--count-missing",
        action="store_true",
        help="Puntua los casos etiquetados sin prediccion como fallo (pred=None), que es lo que\n"
        "hace Grand Challenge cuando un contenedor aborta. Sin esta bandera se excluyen,\n"
        "lo que da un numero optimista si el agente abandona casos.",
    )
    args = ap.parse_args()

    ev = load_evaluator(Path(args.eval_repo))
    print(f"Evaluador: {args.eval_repo}  ·  juez de razonamiento: DESACTIVADO")
    print(f"Split: {args.split}  ·  predicciones: {args.output_root}")

    results: dict[int, dict] = {}
    for task in args.tasks:
        wanted = read_split(Path(args.split_dir), task, args.split)
        agg = score_task(ev, Path(args.data_root), Path(args.output_root), task, wanted, args.count_missing)
        if agg:
            results[task] = agg
            report(task, agg)

    ranked = {t: a for t, a in results.items() if a.get("ranking_score") is not None}
    if ranked:
        total_w = sum(TASK_RANKING_WEIGHTS[t] for t in ranked)
        overall = sum(a["ranking_score"] * TASK_RANKING_WEIGHTS[t] for t, a in ranked.items()) / total_w
        print(f"\n  ══ OVERALL RANKING SCORE  {overall:.4f}")
        print(f"     (media ponderada 2:2:1 sobre las tareas presentes: {sorted(ranked)})")
        if len(ranked) < 3:
            print("     PARCIAL — faltan tareas, no comparable con una corrida completa")

    if args.json_out:
        dump = {f"task{t}": {k: v for k, v in a.items() if not k.startswith("_")} for t, a in results.items()}
        Path(args.json_out).write_text(json.dumps(dump, indent=2, default=str))
        print(f"\n  Agregados escritos en {args.json_out}")


if __name__ == "__main__":
    main()
