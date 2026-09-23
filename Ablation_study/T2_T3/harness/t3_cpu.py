"""Anclajes y ablaciones numericas de T3 sobre los 75 casos OOF."""

from __future__ import annotations

import csv

from version_final_reto.common.chimera_experts import dataset_task3 as ds
from version_final_reto.task_3.agent.protocol import Panel
from version_final_reto.task_3.agent.run_task3 import load_inputs

from .evaluator import load_evaluator, write_json
from .paths import DATA3, RESULTS, ensure_dirs
from .stats import t3_bootstrap


def predictions(spokesperson: str) -> list[dict]:
    panel = Panel("oof", spokesperson=spokesperson)
    result = []
    for case in load_inputs(DATA3):
        findings = ds._surgical(case)
        horizon = panel.horizon(case, findings["capra_s"])
        result.append(
            {
                "case_id": case.case_id,
                "event": int(horizon["event"]),
                "months_to_recurrence": float(horizon["months_to_recurrence"]),
                "reasoning": "simulated",
            }
        )
    return result


def evaluate(predictions_: list[dict]) -> tuple[dict, list[dict]]:
    evaluator = load_evaluator()
    ground_truth = {
        evaluator.get_case_id(record): record
        for record in evaluator.load_ground_truth_records(DATA3 / "ground_truth", "task3")
    }
    rows = [
        evaluator.evaluate_case(ground_truth[pred["case_id"]], pred, None, None)
        for pred in predictions_
    ]
    return evaluator.aggregate_recurrence_metrics(rows), rows


def main() -> None:
    ensure_dirs()
    selected = predictions("selected")
    capra = predictions("capra")
    variants = {
        "selected": selected,
        "capra": capra,
        "constant60_capra_event": [
            {**row, "months_to_recurrence": 60.0} for row in capra
        ],
        "selected_event0": [{**row, "event": 0} for row in selected],
        "constant60_event0": [
            {**row, "months_to_recurrence": 60.0, "event": 0} for row in selected
        ],
    }
    base_aggregate, base_rows = evaluate(selected)
    output = []
    for name, values in variants.items():
        aggregate, rows = evaluate(values)
        output.append(
            {
                "id": name,
                "aggregate": aggregate,
                "numeric_identity_with_selected": all(
                    left["event"] == right["event"]
                    and left["months_to_recurrence"] == right["months_to_recurrence"]
                    for left, right in zip(selected, values)
                ),
                "bootstrap": None if name == "selected" else t3_bootstrap(base_rows, rows),
            }
        )
    dependencies = [
        {"node": "INTAKE", "numeric_role": "input projection", "minimum": "retain in digest"},
        {"node": "EXPERT-CAPRA", "numeric_role": "event policy and horizon input", "minimum": "retain computation"},
        {"node": "EXPERT-SURGICAL", "numeric_role": "advisory only", "minimum": "collapse into ASGDE engine"},
        {"node": "EXPERT-DIGITAL", "numeric_role": "advisory only", "minimum": "collapse into ASGDE engine"},
        {"node": "MODERATOR", "numeric_role": "none", "minimum": "deterministic digest"},
        {"node": "REGISTRAR", "numeric_role": "fixed document projection", "minimum": "deterministic digest"},
        {"node": "EXPERT-FUSION", "numeric_role": "advisory only", "minimum": "collapse into selected ASGDE"},
        {"node": "PANEL-PROTOCOL", "numeric_role": "selects frozen spokesperson", "minimum": "constant configuration"},
        {"node": "EXPERT-HORIZON", "numeric_role": "months and event", "minimum": "retain"},
        {"node": "VERIFIER", "numeric_role": "none", "minimum": "deterministic checks"},
        {"node": "CHAIR", "numeric_role": "none", "minimum": "retain only for narrative arm"},
    ]
    write_json(
        RESULTS / "T3_cpu.json",
        {
            "warning": "OOF measured cohort; not independent external validation.",
            "n": len(selected),
            "baseline": base_aggregate,
            "variants": output,
            "dependencies": dependencies,
        },
    )
    with (RESULTS / "T3_cpu.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "id", "ranking_score", "mean_case_score", "event_accuracy", "mean_event_score",
                "mean_time_score", "event1_mae", "numeric_identity", "delta_rank",
                "delta_rank_low", "delta_rank_high",
            ),
        )
        writer.writeheader()
        for item in output:
            aggregate = item["aggregate"]
            interval = (item["bootstrap"] or {}).get("ranking_score", {})
            writer.writerow(
                {
                    "id": item["id"],
                    "ranking_score": aggregate["ranking_score"],
                    "mean_case_score": aggregate["mean_case_score"],
                    "event_accuracy": aggregate["recurrence_event_accuracy"],
                    "mean_event_score": aggregate["mean_event_score"],
                    "mean_time_score": aggregate["mean_time_score"],
                    "event1_mae": aggregate["event1_time_mae_months"],
                    "numeric_identity": item["numeric_identity_with_selected"],
                    "delta_rank": interval.get("delta"),
                    "delta_rank_low": interval.get("low"),
                    "delta_rank_high": interval.get("high"),
                }
            )
    print(f"T3 CPU: {len(output)} variantes x {len(selected)} casos")


if __name__ == "__main__":
    main()
