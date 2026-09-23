"""Valida las 18 evaluaciones y estima efectos narrativos pareados."""

from __future__ import annotations

import json
import math
from statistics import fmean, stdev

import numpy as np

from .evaluator import write_json
from .paths import DATA, RESULTS
from .score_runs import ARMS, BASELINE
from .stats import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED

PASSES = (1, 2, 3)


def path(arm: str, pass_number: int):
    return RESULTS / f"J_{arm}_p{pass_number}.json"


def _valid(arm: str, task: int, pass_number: int) -> dict:
    target = path(arm, pass_number)
    if not target.is_file():
        return {"valid": False, "reason": "missing"}
    try:
        rows = json.loads(target.read_text()).get("rows") or []
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "reason": str(exc)}
    expected = {
        item.name for item in (DATA / f"task{task}" / "ground_truth").iterdir() if item.is_dir()
    }
    ids = {str(row.get("case_id")) for row in rows}
    eligible = rows if task == 3 else [row for row in rows if row.get("decision_score") == 1.0]
    scores = [row.get("rationale_score") for row in eligible]
    finite = scores and all(isinstance(value, (int, float)) and math.isfinite(value) for value in scores)
    return {
        "valid": len(rows) == len(expected) and ids == expected and bool(finite),
        "cases": len(rows),
        "judged": sum(isinstance(value, (int, float)) and math.isfinite(value) for value in scores),
    }


def validate() -> dict:
    files = {
        path(arm, pass_number).name: _valid(arm, task, pass_number)
        for pass_number in PASSES
        for arm, task in ARMS.items()
    }
    report = {
        "expected": len(files),
        "valid": sum(item["valid"] for item in files.values()),
        "files": files,
    }
    report["complete"] = report["valid"] == report["expected"]
    write_json(RESULTS / "J_session_validation.json", report)
    return report


def _arm_scores(arm: str, task: int) -> tuple[dict[str, float], list[float]]:
    passes, means = [], []
    for pass_number in PASSES:
        rows = json.loads(path(arm, pass_number).read_text())["rows"]
        values = {
            str(row["case_id"]): float(row["rationale_score"])
            for row in rows
            if row.get("rationale_score") is not None
            and (task == 3 or row.get("decision_score") == 1.0)
        }
        passes.append(values)
        means.append(fmean(values.values()))
    common = set.intersection(*(set(item) for item in passes))
    return {
        case_id: fmean(item[case_id] for item in passes) for case_id in sorted(common)
    }, means


def _effect(base: dict[str, float], other: dict[str, float]) -> dict:
    common = sorted(set(base) & set(other))
    difference = np.asarray([base[case_id] - other[case_id] for case_id in common])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sample = rng.integers(0, len(common), size=(BOOTSTRAP_RESAMPLES, len(common)))
    bootstrap = np.mean(difference[sample], axis=1)
    low, high = np.quantile(bootstrap, (0.025, 0.975))
    return {
        "baseline": fmean(base[case_id] for case_id in common),
        "variant": fmean(other[case_id] for case_id in common),
        "delta": float(np.mean(difference)),
        "ci95": [float(low), float(high)],
        "n": len(common),
    }


def analyze() -> dict:
    validation = validate()
    if not validation["complete"]:
        raise RuntimeError(f"Sesion incompleta: {validation['valid']}/{validation['expected']}")
    scores, means = {}, {}
    for arm, task in ARMS.items():
        scores[arm], means[arm] = _arm_scores(arm, task)
    margins = {}
    for task, baseline in BASELINE.items():
        spread = stdev(means[baseline]) / math.sqrt(len(PASSES))
        margins[task] = max(0.030, 2 * spread)
    effects = []
    for arm, task in ARMS.items():
        effect = _effect(scores[BASELINE[task]], scores[arm])
        effects.append({
            "arm": arm,
            "task": task,
            **effect,
            "pass_means": means[arm],
            "delta_n": margins[task],
            "within_margin": effect["ci95"][0] >= -margins[task]
            and effect["ci95"][1] <= margins[task],
        })
    payload = {
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "delta_n": {f"task{task}": value for task, value in margins.items()},
        "effects": effects,
    }
    write_json(RESULTS / "J_effects.json", payload)
    print(json.dumps({"complete": True, "delta_n": payload["delta_n"]}, indent=2))
    return payload


if __name__ == "__main__":
    analyze()
