"""Analisis pareado de decision y formulario para los brazos Tier L."""

from __future__ import annotations

from datetime import date
import csv
import json
from typing import Any

from .paths import RESULTS, RUNS
from .run_arm import load_arms
from .run_tier_s import _compare
from .sim import A0, score_rows, simulate_variant
from .stats import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, COMPONENTS, holm_adjust
from .validate_arm import _outputs, _prediction_row

ARMS = ("L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L0p")
DF_FIELDS = ("biopsy_decision", "confidence", "variable_weights", "reveal_sequence")


def _normalise(field: str, value: Any) -> Any:
    if field == "biopsy_decision":
        return value is True or str(value).strip().lower() in {"yes", "true"}
    return value


def field_changes(
    baseline: list[dict[str, Any]], variant: list[dict[str, Any]]
) -> dict[str, Any]:
    """Cuenta cambios D/F por caso entre dos listas de predicciones crudas."""
    left = {row["case_id"]: row for row in baseline}
    right = {row["case_id"]: row for row in variant}
    if set(left) != set(right):
        raise ValueError("Las predicciones no contienen los mismos casos.")
    by_field = {field: 0 for field in DF_FIELDS}
    changed_cases: set[str] = set()
    for case_id in sorted(left):
        for field in DF_FIELDS:
            before = _normalise(field, left[case_id]["pred"][field])
            after = _normalise(field, right[case_id]["pred"][field])
            if before != after:
                by_field[field] += 1
                changed_cases.add(case_id)
    return {"by_field": by_field, "cases": sorted(changed_cases), "n_cases": len(changed_cases)}


def _load_arm(arm: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    folders = _outputs(RUNS / arm)
    if len(folders) != 91:
        raise ValueError(f"{arm} no tiene 91 salidas: {len(folders)}.")
    raw = [_prediction_row(case_id, folder) for case_id, folder in sorted(folders.items())]
    return raw, score_rows(raw)


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    comparison = row["versus_l0"]
    flat: dict[str, Any] = {
        "arm": row["arm"],
        "graph_variant": row["graph_variant"],
        "n": comparison["n"],
        "changed_cases_vs_l0": row["changes_vs_l0"]["n_cases"],
        "changed_decisions_vs_l0": row["changes_vs_l0"]["by_field"]["biopsy_decision"],
        "changed_cases_vs_s": row["l_minus_s"]["changes"]["n_cases"],
        "changed_fields_vs_s": json.dumps(row["l_minus_s"]["changes"]["by_field"], sort_keys=True),
        "l_minus_s_ranking": row["l_minus_s"]["ranking"],
        "mcnemar_p": comparison["mcnemar"]["p_value"],
        "mcnemar_holm_p": row["mcnemar_holm_p"],
        "sign_p": comparison["sign_test"]["p_value"],
    }
    for metric, values in comparison["metrics"].items():
        flat[f"value_{metric}"] = values["variant"]
        flat[f"delta_{metric}"] = values["delta"]
        flat[f"ci_low_{metric}"] = values["ci95"][0]
        flat[f"ci_high_{metric}"] = values["ci95"][1]
        flat[f"n_{metric}"] = values["n"]
    return flat


def run(*, resamples: int = BOOTSTRAP_RESAMPLES) -> list[dict[str, Any]]:
    registry = load_arms()
    loaded = {arm: _load_arm(arm) for arm in ARMS}
    baseline_raw, baseline_score = loaded["L0"]
    simulated_raw = simulate_variant(A0, "honest")
    simulated_score = score_rows(simulated_raw)
    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        raw, scored = loaded[arm]
        comparison = _compare(baseline_score["rows"], scored["rows"], resamples=resamples)
        changes_s = field_changes(simulated_raw, raw)
        rows.append(
            {
                "arm": arm,
                "graph_variant": registry[arm]["variante_grafo"],
                "description": registry[arm]["descripcion"],
                "hypotheses": registry[arm].get("hipotesis") or [],
                "score": {key: value for key, value in scored.items() if key != "rows"},
                "versus_l0": comparison,
                "changes_vs_l0": field_changes(baseline_raw, raw),
                "l_minus_s": {
                    "ranking": scored["ranking"] - simulated_score["ranking"],
                    "changes": changes_s,
                },
            }
        )

    primary = {
        row["arm"]: row["versus_l0"]["mcnemar"]["p_value"]
        for row in rows
        if row["arm"] in {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}
    }
    adjusted = holm_adjust(primary)
    for row in rows:
        row["mcnemar_holm_p"] = adjusted.get(
            row["arm"], row["versus_l0"]["mcnemar"]["p_value"]
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date.today().isoformat(),
        "seed": BOOTSTRAP_SEED,
        "resamples": resamples,
        "metrics": ["ranking", "gate", "f1_yes", *COMPONENTS],
        "rows": rows,
    }
    (RESULTS / "L_efectos.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    flat = [_flatten(row) for row in rows]
    with (RESULTS / "L_efectos.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    return rows


def main() -> int:
    rows = run()
    print(json.dumps({row["arm"]: row["changes_vs_l0"]["by_field"] for row in rows}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
