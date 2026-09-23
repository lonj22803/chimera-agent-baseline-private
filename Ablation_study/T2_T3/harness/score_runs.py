"""Valida, puntua y compara los seis brazos T2/T3 sin juez."""

from __future__ import annotations

import json
from statistics import fmean
from typing import Any

from dev.score_local import load_predictions

from .evaluator import load_evaluator, write_json
from .paths import DATA, RESULTS, RUNS, ensure_dirs
from .stats import t2_bootstrap, t3_bootstrap

ARMS = {
    "T2-L0": 2,
    "T2-Lmin": 2,
    "T2-Ldet": 2,
    "T3-L0": 3,
    "T3-Lmin": 3,
    "T3-Ldet": 3,
}
BASELINE = {2: "T2-L0", 3: "T3-L0"}


def _jsonl(path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _cost(arm: str) -> dict[str, Any]:
    root = RUNS / arm
    summaries = _jsonl(root / "summary.jsonl")
    latest = {str(row.get("case_id")): row for row in summaries if row.get("case_id")}
    telemetry = _jsonl(root / "telemetry.jsonl")
    if arm.startswith("T2"):
        calls = [row for row in telemetry if row.get("kind") == "llm"]
        prompt_tokens = sum(int(row.get("prompt_tokens") or 0) for row in calls)
        completion_tokens = sum(int(row.get("completion_tokens") or 0) for row in calls)
    else:
        calls = [call for row in telemetry for call in (row.get("calls") or [])]
        prompt_tokens = sum(int(call.get("input_tokens") or 0) for call in calls)
        completion_tokens = sum(int(call.get("output_tokens") or 0) for call in calls)
    seconds = [float(row["seconds"]) for row in latest.values() if row.get("seconds") is not None]
    if not seconds and arm.startswith("T3"):
        latest_telemetry = {
            str(row.get("case_id")): row for row in telemetry if row.get("case_id")
        }
        seconds = [
            float(row["seconds"])
            for row in latest_telemetry.values()
            if row.get("seconds") is not None
        ]
    return {
        "cases": len(latest),
        "llm_calls": len(calls),
        "llm_calls_per_case": len(calls) / len(latest) if latest else None,
        "seconds_total": sum(seconds),
        "seconds_per_case": fmean(seconds) if seconds else None,
        "prompt_tokens": prompt_tokens or None,
        "completion_tokens": completion_tokens or None,
    }


def _score(arm: str, task: int) -> dict[str, Any]:
    evaluator = load_evaluator()
    data = DATA / f"task{task}"
    ground_truth = {
        evaluator.get_case_id(record): record
        for record in evaluator.load_ground_truth_records(data / "ground_truth", f"task{task}")
    }
    predictions = load_predictions(RUNS / arm / "output", task)
    expected = set(ground_truth)
    rows = [
        evaluator.evaluate_case(ground_truth[case_id], predictions.get(case_id), None, None)
        for case_id in sorted(expected)
    ]
    aggregate = (
        evaluator.aggregate_recurrence_metrics(rows)
        if task == 3
        else evaluator.compute_aggregate_metrics(rows)
    )
    schema_errors = [
        {"case_id": row["case_id"], "gate": row["gate"], "reason": row["reason"]}
        for row in rows
        if row.get("gate") in {"missing_candidate", "schema_failed"}
    ]
    return {
        "arm": arm,
        "task": task,
        "expected": len(expected),
        "predictions": len(predictions),
        "missing": sorted(expected - set(predictions)),
        "extra": sorted(set(predictions) - expected),
        "schema_errors": schema_errors,
        "accepted": len(predictions) == len(expected) and not schema_errors and set(predictions) == expected,
        "aggregate": aggregate,
        "rows": rows,
        "predictions_by_case": predictions,
        "cost": _cost(arm),
    }


def _identity(base: dict[str, Any], other: dict[str, Any], task: int) -> dict[str, Any]:
    differences = []
    for case_id in sorted(base["predictions_by_case"]):
        left = base["predictions_by_case"][case_id]
        right = other["predictions_by_case"][case_id]
        if task == 2:
            fields = ("treatment_recommendation", "confidence", "variable_weights", "reveal_sequence")
        else:
            fields = ("event", "months_to_recurrence")
        changed = [field for field in fields if left.get(field) != right.get(field)]
        if changed:
            differences.append({"case_id": case_id, "fields": changed})
    return {"exact": not differences, "n_different": len(differences), "differences": differences}


def main() -> None:
    ensure_dirs()
    scored = {arm: _score(arm, task) for arm, task in ARMS.items()}
    results = []
    for arm, task in ARMS.items():
        base = scored[BASELINE[task]]
        bootstrap = None
        if arm != BASELINE[task]:
            bootstrap = (
                t2_bootstrap(base["rows"], scored[arm]["rows"])
                if task == 2
                else t3_bootstrap(base["rows"], scored[arm]["rows"])
            )
        results.append(
            {
                key: value
                for key, value in scored[arm].items()
                if key not in {"rows", "predictions_by_case"}
            }
            | {
                "identity_with_l0": _identity(base, scored[arm], task),
                "bootstrap": bootstrap,
            }
        )
    payload = {
        "accepted": all(item["accepted"] for item in results),
        "arms": results,
    }
    write_json(RESULTS / "D_F_effects.json", payload)
    print(json.dumps({
        "accepted": payload["accepted"],
        "arms": {
            item["arm"]: {
                "n": item["predictions"],
                "ranking": item["aggregate"]["ranking_score"],
                "identity": item["identity_with_l0"]["exact"],
                "calls": item["cost"]["llm_calls"],
            }
            for item in results
        },
    }, indent=2))
    if not payload["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
