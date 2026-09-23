"""Valida la sesion del juez y estima efectos narrativos pareados."""

from __future__ import annotations

import argparse
import csv
from datetime import date
import json
import math
from pathlib import Path
from statistics import fmean, stdev
import time
from typing import Any

import numpy as np

from .classify import classify
from .paths import DATA, RESULTS
from .run_tier_l import ARMS
from .stats import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED

PASSES = (1, 2, 3)


def judge_path(arm: str, pass_number: int) -> Path:
    return RESULTS / f"J_{arm}_p{pass_number}.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_file(path: Path, expected_cases: set[str]) -> dict[str, Any]:
    if not path.is_file():
        return {"valid": False, "reason": "missing"}
    try:
        payload = _load(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "reason": f"invalid json: {exc}"}
    rows = payload.get("rows") or []
    ids = {str(row.get("case_id")) for row in rows}
    if len(rows) != len(expected_cases) or ids != expected_cases:
        return {"valid": False, "reason": f"cases={len(rows)}/{len(expected_cases)}"}
    passed = [row for row in rows if row.get("decision_score") == 1.0]
    judged = [row.get("rationale_score") for row in passed]
    if not judged or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in judged):
        return {"valid": False, "reason": f"judged={sum(isinstance(v, (int, float)) for v in judged)}/{len(passed)}"}
    return {"valid": True, "cases": len(rows), "judged": len(judged)}


def validate_session() -> dict[str, Any]:
    expected_cases = {path.name for path in (DATA / "ground_truth").iterdir() if path.is_dir()}
    files = {}
    for pass_number in PASSES:
        for arm in ARMS:
            path = judge_path(arm, pass_number)
            files[path.name] = validate_file(path, expected_cases)
    valid = sum(item["valid"] for item in files.values())
    report = {
        "date": date.today().isoformat(),
        "expected": len(ARMS) * len(PASSES),
        "valid": valid,
        "complete": valid == len(files),
        "files": files,
        "residency_before": (RESULTS / "J_session_before.json").is_file(),
        "residency_after": (RESULTS / "J_session_after.json").is_file(),
    }
    if report["complete"] and not report["residency_after"]:
        report["complete"] = False
    (RESULTS / "J_session_validation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def wait_for_session(interval: int = 30, timeout: int = 0) -> dict[str, Any]:
    started = time.monotonic()
    while True:
        report = validate_session()
        if report["complete"]:
            return report
        if timeout and time.monotonic() - started >= timeout:
            raise TimeoutError(f"Sesion incompleta: {report['valid']}/{report['expected']}.")
        print(f"Juez: {report['valid']}/{report['expected']} artefactos validos; esperando...", flush=True)
        time.sleep(interval)


def _scores_by_arm(arm: str) -> tuple[dict[str, float], list[float]]:
    passes: list[dict[str, float]] = []
    pass_means = []
    for pass_number in PASSES:
        rows = _load(judge_path(arm, pass_number))["rows"]
        values = {
            str(row["case_id"]): float(row["rationale_score"])
            for row in rows
            if row.get("decision_score") == 1.0 and row.get("rationale_score") is not None
        }
        passes.append(values)
        pass_means.append(fmean(values.values()))
    common = set.intersection(*(set(values) for values in passes))
    return {
        case_id: fmean(values[case_id] for values in passes)
        for case_id in sorted(common)
    }, pass_means


def paired_narrative_effect(
    baseline: dict[str, float],
    variant: dict[str, float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    common = sorted(set(baseline) & set(variant))
    if not common:
        raise ValueError("No hay casos juzgados en ambos brazos.")
    differences = np.asarray([baseline[case_id] - variant[case_id] for case_id in common])
    rng = np.random.default_rng(seed)
    sample = rng.integers(0, len(common), size=(resamples, len(common)))
    boot = np.mean(differences[sample], axis=1)
    low, high = np.quantile(boot, (0.025, 0.975))
    return {
        "baseline": fmean(baseline[case_id] for case_id in common),
        "variant": fmean(variant[case_id] for case_id in common),
        "delta": float(np.mean(differences)),
        "ci95": [float(low), float(high)],
        "n": len(common),
        "resamples": resamples,
    }


def analyze(*, resamples: int = BOOTSTRAP_RESAMPLES) -> dict[str, Any]:
    validation = validate_session()
    if not validation["complete"]:
        raise RuntimeError(f"Sesion del juez incompleta: {validation['valid']}/{validation['expected']}.")
    scores = {}
    pass_means = {}
    for arm in ARMS:
        scores[arm], pass_means[arm] = _scores_by_arm(arm)

    replicate_common = sorted(set(scores["L0"]) & set(scores["L0p"]))
    replicate_differences = [scores["L0"][case_id] - scores["L0p"][case_id] for case_id in replicate_common]
    replicate_se = stdev(replicate_differences) / math.sqrt(len(replicate_differences))
    delta_n = max(0.030, 2 * replicate_se)

    rows = []
    for arm in ARMS:
        effect = paired_narrative_effect(scores["L0"], scores[arm], resamples=resamples)
        verdict = classify(
            effect["delta"],
            tuple(effect["ci95"]),
            level="N",
            margin=delta_n,
            exact_zero=arm == "L0",
        )
        rows.append(
            {
                "arm": arm,
                **effect,
                "pass_means": pass_means[arm],
                "verdict_n": verdict,
            }
        )

    payload = {
        "date": date.today().isoformat(),
        "seed": BOOTSTRAP_SEED,
        "resamples": resamples,
        "replicate": {
            "arm": "L0p",
            "n": len(replicate_common),
            "paired_mean_difference": fmean(replicate_differences),
            "standard_error": replicate_se,
            "two_standard_errors": 2 * replicate_se,
        },
        "delta_n": delta_n,
        "rows": rows,
    }
    (RESULTS / "J_efectos.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    flat = [
        {
            **{key: value for key, value in row.items() if key not in {"ci95", "pass_means"}},
            "ci_low": row["ci95"][0],
            "ci_high": row["ci95"][1],
            "pass_1": row["pass_means"][0],
            "pass_2": row["pass_means"][1],
            "pass_3": row["pass_means"][2],
            "delta_n": delta_n,
        }
        for row in rows
    ]
    with (RESULTS / "J_efectos.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    report = wait_for_session(args.interval, args.timeout) if args.wait else validate_session()
    if not report["complete"]:
        print(json.dumps({"complete": False, "valid": report["valid"], "expected": report["expected"]}))
        return 1
    if args.validate_only:
        print(json.dumps({"complete": True, "valid": report["valid"]}))
        return 0
    payload = analyze()
    print(json.dumps({"complete": True, "delta_n": payload["delta_n"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
