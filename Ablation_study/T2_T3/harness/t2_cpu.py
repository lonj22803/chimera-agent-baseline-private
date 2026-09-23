"""Ablacion exhaustiva de los cinco expertos cacheados de T2, sin LLM."""

from __future__ import annotations

import copy
import csv
import itertools
import json
from collections import Counter

from version_final_reto.task_2.agent import protocol as P
from version_final_reto.task_2.analysis.simulate import CLINICAL_FILE, PROMPT_FILE, score
from version_final_reto.task_2.experts_2.panel import Panel

from .evaluator import write_json
from .paths import DATA2, RESULTS, SPLITS, ensure_dirs
from .stats import t2_bootstrap

EXPERTS = tuple(f"expert_{name}" for name in ("one", "two", "three", "four", "five"))


def simulate_removed(panel: Panel, removed: frozenset[str]) -> list[dict]:
    rows = []
    for directory in sorted(path for path in (DATA2 / "ground_truth").iterdir() if path.is_dir()):
        case_id = directory.name
        payload = json.loads((DATA2 / "agent_input" / case_id / PROMPT_FILE).read_text())
        experts = copy.deepcopy(panel.verdicts(case_id)["experts"])
        for name in removed:
            experts[name] = {"available": False, "ablation": True}
        result = P.consolidate(payload, experts, list(P.INTERNAL_PLAN))
        pred = {
            "action": result["decision"],
            "treatment_recommendation": {"primary": result["decision"]},
            "confidence": result["confidence"],
            "variable_weights": dict(result["variable_weights"]),
            "reveal_sequence": [],
            "free_text": "simulated",
            "case_id": case_id,
        }
        rows.append(
            {"case_id": case_id, "pred": pred, "who": result["who"], "rule": result["rule"]}
        )
    return rows


def _aggregate(rows: list[dict]) -> tuple[dict, list[dict]]:
    result = score(rows)
    evaluated = result.pop("rows")
    return result, evaluated


def _split_metrics(rows: list[dict], wanted: set[str]) -> dict:
    selected = [row for row in rows if row["case_id"] in wanted]
    aggregate, _ = _aggregate(selected)
    return aggregate


def main() -> None:
    ensure_dirs()
    panel = Panel()
    dev = set((SPLITS / "task2_dev.txt").read_text().split())
    val = set((SPLITS / "task2_val.txt").read_text().split())
    variants = []
    for size in range(len(EXPERTS) + 1):
        for group in itertools.combinations(EXPERTS, size):
            variants.append(frozenset(group))

    raw: dict[frozenset[str], tuple[list[dict], dict, list[dict]]] = {}
    for removed in variants:
        rows = simulate_removed(panel, removed)
        aggregate, evaluated = _aggregate(rows)
        raw[removed] = rows, aggregate, evaluated
    base_rows, base_aggregate, base_evaluated = raw[frozenset()]
    base_decisions = {row["case_id"]: row["pred"]["action"] for row in base_rows}

    results = []
    for removed in variants:
        rows, aggregate, evaluated = raw[removed]
        decisions = {row["case_id"]: row["pred"]["action"] for row in rows}
        changed = sorted(case_id for case_id in decisions if decisions[case_id] != base_decisions[case_id])
        spokespeople = Counter(row["who"] for row in rows)
        results.append(
            {
                "id": "full" if not removed else "drop_" + "+".join(sorted(removed)),
                "removed": sorted(removed),
                "n_removed": len(removed),
                "aggregate": aggregate,
                "dev": _split_metrics(rows, dev),
                "val": _split_metrics(rows, val),
                "spokesperson": dict(sorted(spokespeople.items())),
                "changed_cases": changed,
                "n_changed": len(changed),
                "bootstrap": None if not removed else t2_bootstrap(base_evaluated, evaluated),
            }
        )

    payload = {
        "warning": "Within-sample frozen panel comparison; not external validation.",
        "n": len(base_rows),
        "experts": list(EXPERTS),
        "baseline": base_aggregate,
        "variants": results,
    }
    write_json(RESULTS / "T2_cpu.json", payload)
    with (RESULTS / "T2_cpu.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "id", "removed", "n_removed", "n_changed", "ranking_score", "decision_accuracy",
                "decision_weighted_f1", "mean_case_score", "delta_rank", "delta_rank_low",
                "delta_rank_high", "dev_accuracy", "val_accuracy", "spokesperson",
            ),
        )
        writer.writeheader()
        for item in results:
            interval = (item["bootstrap"] or {}).get("ranking_score", {})
            writer.writerow(
                {
                    "id": item["id"],
                    "removed": ",".join(item["removed"]),
                    "n_removed": item["n_removed"],
                    "n_changed": item["n_changed"],
                    "ranking_score": item["aggregate"]["ranking"],
                    "decision_accuracy": item["aggregate"]["gate"],
                    "decision_weighted_f1": item["aggregate"].get("decision_weighted_f1"),
                    "mean_case_score": item["aggregate"]["mean_case"],
                    "delta_rank": interval.get("delta"),
                    "delta_rank_low": interval.get("low"),
                    "delta_rank_high": interval.get("high"),
                    "dev_accuracy": item["dev"]["gate"],
                    "val_accuracy": item["val"]["gate"],
                    "spokesperson": json.dumps(item["spokesperson"], sort_keys=True),
                }
            )
    print(f"T2 CPU: {len(results)} variantes x {len(base_rows)} casos")


if __name__ == "__main__":
    main()
