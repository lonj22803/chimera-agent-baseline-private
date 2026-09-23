"""Ejecucion reproducible de los experimentos CPU Tier S."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
from datetime import date
from itertools import product
import json
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping

from .paths import RESULTS, SPLITS
from .sim import VariantSpec, score_rows, simulate_variant
from .stats import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    COMPONENTS,
    detectability_table,
    holm_adjust,
    mcnemar_exact,
    paired_bootstrap_metrics,
    ranking_from_rows,
    shapley_values,
    sign_test,
)
from .variants import Variant, load_variants

LOO_BLOCKS = frozenset({"referencia", "decision", "documentos", "plan", "formulario"})
MODES = ("honest", "deployed")
BUCKETS = ("None", "Negative", "Positive")


def _f1(rows: list[Mapping[str, Any]]) -> float:
    tp = sum(row["gt"] == row["pred"] == 1 for row in rows)
    fp = sum(row["gt"] == 0 and row["pred"] == 1 for row in rows)
    fn = sum(row["gt"] == 1 and row["pred"] == 0 for row in rows)
    denominator = 2 * tp + fp + fn
    return 2 * tp / denominator if denominator else 0.0


def _metric(rows: list[Mapping[str, Any]], metric: str) -> float:
    if metric == "ranking":
        return ranking_from_rows(rows)
    if metric == "gate":
        return fmean(float(row["decision_score"]) for row in rows)
    if metric == "f1_yes":
        return _f1(rows)
    values = [float(row[metric]) for row in rows if row.get(metric) is not None]
    return fmean(values)


def _compare(
    baseline: list[dict[str, Any]],
    variant: list[dict[str, Any]],
    *,
    resamples: int,
) -> dict[str, Any]:
    boot = paired_bootstrap_metrics(
        baseline,
        variant,
        resamples=resamples,
        seed=BOOTSTRAP_SEED,
    )
    metrics: dict[str, Any] = {}
    for name, result in boot.items():
        if name in COMPONENTS:
            baseline_value = _metric(
                [
                    left
                    for left, right in zip(baseline, variant)
                    if left["decision_score"] == right["decision_score"] == 1.0
                    and left.get(name) is not None
                    and right.get(name) is not None
                ],
                name,
            )
        else:
            baseline_value = _metric(baseline, name)
        metrics[name] = {
            "baseline": baseline_value,
            "variant": baseline_value - result.delta,
            "delta": result.delta,
            "ci95": [result.low, result.high],
            "n": result.n,
        }
    mcnemar = mcnemar_exact(baseline, variant)
    signed = sign_test(
        float(left["case_score"]) - float(right["case_score"])
        for left, right in zip(baseline, variant)
    )
    return {
        "n": len(baseline),
        "metrics": metrics,
        "mcnemar": asdict(mcnemar),
        "sign_test": asdict(signed),
    }


def _changed_cases(
    baseline_raw: list[dict[str, Any]], variant_raw: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    baseline = {row["case_id"]: row for row in baseline_raw}
    variant = {row["case_id"]: row for row in variant_raw}
    changed = []
    for case_id in sorted(baseline):
        left = baseline[case_id]
        right = variant[case_id]
        if left["pred"]["biopsy_decision"] == right["pred"]["biopsy_decision"]:
            continue
        changed.append(
            {
                "case_id": case_id,
                "a0_pred": left["pred"]["biopsy_decision"],
                "variant_pred": right["pred"]["biopsy_decision"],
                "a0_rule": left["rule"],
                "a0_who": left["who"],
                "variant_rule": right["rule"],
                "variant_who": right["who"],
            }
        )
    return changed


def _flatten_loo_row(row: dict[str, Any]) -> dict[str, Any]:
    flat = {
        "id": row["id"],
        "mode": row["mode"],
        "bloque": row["bloque"],
        "tipo": row["tipo"],
        "n": row["overall"]["n"],
        "seed": row["seed"],
        "resamples": row["resamples"],
        "changed_cases": len(row["changed_cases"]),
        "mcnemar_p": row["overall"]["mcnemar"]["p_value"],
        "mcnemar_holm_p": row["mcnemar_holm_p"],
        "sign_p": row["overall"]["sign_test"]["p_value"],
        "spec": json.dumps(row["spec"], sort_keys=True),
        "by_bucket": json.dumps(row["by_bucket"], sort_keys=True),
        "changes": json.dumps(row["changed_cases"], sort_keys=True),
    }
    for metric, values in row["overall"]["metrics"].items():
        flat[f"value_{metric}"] = values["variant"]
        flat[f"delta_{metric}"] = values["delta"]
        flat[f"ci_low_{metric}"] = values["ci95"][0]
        flat[f"ci_high_{metric}"] = values["ci95"][1]
    return flat


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No hay filas para {path}.")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_loo(*, resamples: int = BOOTSTRAP_RESAMPLES) -> list[dict[str, Any]]:
    variants = load_variants()
    selected = [variant for variant in variants.values() if variant.bloque in LOO_BLOCKS]
    rows: list[dict[str, Any]] = []
    for mode in MODES:
        baseline_raw = simulate_variant(variants["A0"].spec, mode)
        baseline_scored = score_rows(baseline_raw)["rows"]
        for variant in selected:
            variant_raw = baseline_raw if variant.id == "A0" else simulate_variant(variant.spec, mode)
            variant_scored = baseline_scored if variant.id == "A0" else score_rows(variant_raw)["rows"]
            by_bucket = {}
            for bucket in BUCKETS:
                left = [row for row in baseline_scored if str(row["bx"]) == bucket]
                right = [row for row in variant_scored if str(row["bx"]) == bucket]
                by_bucket[bucket] = _compare(left, right, resamples=resamples)
            rows.append(
                {
                    "id": variant.id,
                    "descripcion": variant.descripcion,
                    "bloque": variant.bloque,
                    "tipo": variant.tipo,
                    "hipotesis": list(variant.hipotesis),
                    "mode": mode,
                    "seed": BOOTSTRAP_SEED,
                    "resamples": resamples,
                    "spec": asdict(variant.spec),
                    "overall": _compare(baseline_scored, variant_scored, resamples=resamples),
                    "by_bucket": by_bucket,
                    "changed_cases": _changed_cases(baseline_raw, variant_raw),
                }
            )

        family = {
            row["id"]: row["overall"]["mcnemar"]["p_value"]
            for row in rows
            if row["mode"] == mode and row["tipo"] == "ablacion"
        }
        adjusted = holm_adjust(family)
        for row in rows:
            if row["mode"] == mode:
                row["mcnemar_holm_p"] = adjusted.get(
                    row["id"], row["overall"]["mcnemar"]["p_value"]
                )

    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date.today().isoformat(),
        "seed": BOOTSTRAP_SEED,
        "resamples": resamples,
        "n_variants": len(selected),
        "rows": rows,
    }
    (RESULTS / "S_loo.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(RESULTS / "S_loo.csv", [_flatten_loo_row(row) for row in rows])
    return rows


def _step_rows(
    raw: list[dict[str, Any]], scored: list[dict[str, Any]], mode: str
) -> list[dict[str, Any]]:
    scored_by_case = {row["case_id"]: row for row in scored}
    groups = (
        ("cohort", "EXPERT-COHORT"),
        ("grade", "documented grade"),
        ("vote", "weighted panel"),
    )
    rows = []
    for bucket in ("ALL", *BUCKETS):
        for step, who in groups:
            selected = [
                row
                for row in raw
                if row["who"] == who and (bucket == "ALL" or str(row["bx"]) == bucket)
            ]
            hits = sum(scored_by_case[row["case_id"]]["decision_score"] == 1.0 for row in selected)
            rows.append(
                {
                    "mode": mode,
                    "bucket": bucket,
                    "step": step,
                    "n": len(selected),
                    "hits": hits,
                    "accuracy": hits / len(selected) if selected else 0.0,
                }
            )
    return rows


def run_cascade(*, resamples: int = BOOTSTRAP_RESAMPLES) -> list[dict[str, Any]]:
    variants = load_variants()
    table: list[dict[str, Any]] = []
    vote_comparisons: dict[str, Any] = {}
    for mode in MODES:
        baseline_raw = simulate_variant(variants["A0"].spec, mode)
        yes_raw = simulate_variant(variants["S-VOTO-YES"].spec, mode)
        baseline_scored = score_rows(baseline_raw)["rows"]
        yes_scored = score_rows(yes_raw)["rows"]
        table.extend(_step_rows(baseline_raw, baseline_scored, mode))

        vote_ids = {row["case_id"] for row in baseline_raw if row["who"] == "weighted panel"}
        base_vote = [row for row in baseline_scored if row["case_id"] in vote_ids]
        yes_vote = [row for row in yes_scored if row["case_id"] in vote_ids]
        comparison = _compare(base_vote, yes_vote, resamples=resamples)
        vote_comparisons[mode] = comparison
        hits = sum(row["decision_score"] == 1.0 for row in yes_vote)
        table.append(
            {
                "mode": mode,
                "bucket": "ALL",
                "step": "vote_yes_constant",
                "n": len(yes_vote),
                "hits": hits,
                "accuracy": hits / len(yes_vote) if yes_vote else 0.0,
                "delta_ranking_a0_minus_yes": comparison["metrics"]["ranking"]["delta"],
                "ci_low_ranking": comparison["metrics"]["ranking"]["ci95"][0],
                "ci_high_ranking": comparison["metrics"]["ranking"]["ci95"][1],
            }
        )

    payload = {
        "date": date.today().isoformat(),
        "seed": BOOTSTRAP_SEED,
        "resamples": resamples,
        "table": table,
        "vote_a0_vs_yes": vote_comparisons,
    }
    (RESULTS / "S_cascade.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    fieldnames = [
        "mode",
        "bucket",
        "step",
        "n",
        "hits",
        "accuracy",
        "delta_ranking_a0_minus_yes",
        "ci_low_ranking",
        "ci_high_ranking",
    ]
    csv_rows = [{name: row.get(name, "") for name in fieldnames} for row in table]
    _write_csv(RESULTS / "S_cascade.csv", csv_rows)
    return table


FACTOR_FIELDS = {
    "M1": ("cohort_none",),
    "M2": ("cohort_negative",),
    "M3": ("cohort_positive_psa", "cohort_positive_age", "cohort_positive_pirads"),
    "M4": ("grade_ge2", "grade_gg1"),
    "E1": ("structured",),
    "E3": ("fusion",),
}


def _factorial_spec(coalition: frozenset[str]) -> VariantSpec:
    changes: dict[str, Any] = {}
    for factor, fields in FACTOR_FIELDS.items():
        for field in fields:
            changes[field] = factor in coalition
    label = "+".join(sorted(coalition)) or "none"
    return replace(load_variants()["A0"].spec, id=f"FACT-{label}", **changes)


def _score_summary(spec: VariantSpec, mode: str) -> dict[str, Any]:
    score = score_rows(simulate_variant(spec, mode))
    return {
        "ranking": score["ranking"],
        "gate": score["gate"],
        "f1_yes": score["f1_yes"],
        **score["components"],
    }


def _full_context_interactions(
    values: Mapping[frozenset[str], float], players: tuple[str, ...]
) -> dict[str, float]:
    full = frozenset(players)
    interactions = {}
    for index, left in enumerate(players):
        for right in players[index + 1 :]:
            interactions[f"{left}x{right}"] = (
                values[full]
                - values[full - {left}]
                - values[full - {right}]
                + values[full - {left, right}]
            )
    return interactions


def _document_interaction(mode: str, factor: str, document: str) -> dict[str, Any]:
    base = load_variants()["A0"].spec
    cells: dict[str, dict[str, Any]] = {}
    for factor_on, document_on in product((False, True), repeat=2):
        changes = {field: factor_on for field in FACTOR_FIELDS[factor]}
        changes["closed_documents"] = () if document_on else (document,)
        spec = replace(
            base,
            id=f"INT-{factor}-{document}-{int(factor_on)}{int(document_on)}",
            **changes,
        )
        cells[f"{int(factor_on)}{int(document_on)}"] = _score_summary(spec, mode)
    interactions = {
        metric: cells["11"][metric] - cells["10"][metric] - cells["01"][metric] + cells["00"][metric]
        for metric in ("ranking", "gate")
    }
    return {"factor": factor, "document": document, "cells": cells, "interaction": interactions}


def run_factorial() -> list[dict[str, Any]]:
    players = tuple(FACTOR_FIELDS)
    variants = load_variants()
    csv_rows: list[dict[str, Any]] = []
    output: dict[str, Any] = {}
    for mode in MODES:
        values: dict[str, dict[frozenset[str], float]] = {"ranking": {}, "gate": {}}
        mode_rows = []
        for mask in range(1 << len(players)):
            coalition = frozenset(
                player for index, player in enumerate(players) if mask & (1 << index)
            )
            summary = _score_summary(_factorial_spec(coalition), mode)
            row = {
                "mode": mode,
                "mask": mask,
                "coalition": "+".join(player for player in players if player in coalition) or "none",
                **{f"on_{player}": int(player in coalition) for player in players},
                **summary,
            }
            csv_rows.append(row)
            mode_rows.append(row)
            values["ranking"][coalition] = summary["ranking"]
            values["gate"][coalition] = summary["gate"]

        shapley = {metric: shapley_values(metric_values, players) for metric, metric_values in values.items()}
        full = frozenset(players)
        empty = frozenset()
        checks = {
            metric: {
                "sum_shapley": sum(shapley[metric].values()),
                "full_minus_empty": metric_values[full] - metric_values[empty],
                "absolute_error": abs(sum(shapley[metric].values()) - (metric_values[full] - metric_values[empty])),
            }
            for metric, metric_values in values.items()
        }
        ladder = []
        previous = None
        for variant_id in ("F0", "F1", "F2", "F3", "A0"):
            summary = _score_summary(variants[variant_id].spec, mode)
            ladder.append(
                {
                    "id": variant_id,
                    **summary,
                    "increment_ranking": 0.0 if previous is None else summary["ranking"] - previous["ranking"],
                    "increment_gate": 0.0 if previous is None else summary["gate"] - previous["gate"],
                }
            )
            previous = summary
        output[mode] = {
            "n_configurations": len(mode_rows),
            "shapley": shapley,
            "checks": checks,
            "second_order_full_context": {
                metric: _full_context_interactions(metric_values, players)
                for metric, metric_values in values.items()
            },
            "document_interactions": [
                _document_interaction(mode, "M4", "previous_notes"),
                _document_interaction(mode, "E3", "radiology_report"),
            ],
            "ladder": ladder,
        }

    payload = {
        "date": date.today().isoformat(),
        "players": list(players),
        "modes": output,
    }
    (RESULTS / "S_factorial.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(RESULTS / "S_factorial.csv", csv_rows)
    return csv_rows


def _freeze_decision(
    rows: list[dict[str, Any]], baseline: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    reference = {row["case_id"]: row for row in baseline}
    frozen = []
    for row in rows:
        source = reference[row["case_id"]]
        frozen.append(
            {
                **row,
                "pred": {
                    **row["pred"],
                    "biopsy_decision": source["pred"]["biopsy_decision"],
                },
                "rule": source["rule"],
                "who": source["who"],
            }
        )
    return frozen


def _form_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score = score_rows(rows)
    return {
        "n": len(score["rows"]),
        "ranking": score["ranking"],
        "gate": score["gate"],
        "f1_yes": score["f1_yes"],
        "components": score["components"],
    }


def run_form() -> list[dict[str, Any]]:
    variants = load_variants()
    rows: list[dict[str, Any]] = []
    for mode in MODES:
        baseline_raw = simulate_variant(variants["A0"].spec, mode)
        baseline_summary = _form_summary(baseline_raw)
        configurations = []
        for weights, confidence, grounding, library in product(
            ("model+mode", "mode", "model"),
            ("agreement", "trace"),
            ("default", "off"),
            (True, False),
        ):
            is_a0 = (
                weights == "model+mode"
                and confidence == "agreement"
                and grounding == "default"
                and library
            )
            variant_id = "A0" if is_a0 else f"FORM-{weights}-{confidence}-{grounding}-lib{int(library)}"
            configurations.append(
                (
                    variant_id,
                    variants["A0"].spec
                    if is_a0
                    else replace(
                            variants["A0"].spec,
                            id=variant_id,
                            weights_policy=weights,
                            confidence_policy=confidence,
                            grounding=grounding,
                            library=library,
                        ),
                    False,
                )
            )
        configurations.append(("S-A-board", variants["S-A-board"].spec, True))

        for variant_id, spec, is_add_back in configurations:
            raw = baseline_raw if spec == variants["A0"].spec else simulate_variant(spec, mode)
            frozen = _freeze_decision(raw, baseline_raw)
            summary = _form_summary(frozen)
            by_bucket = {
                bucket: _form_summary(
                    [row for row in frozen if str(row["bx"]) == bucket]
                )
                for bucket in BUCKETS
            }
            rows.append(
                {
                    "id": variant_id,
                    "mode": mode,
                    "is_add_back": is_add_back,
                    "spec": asdict(spec),
                    **summary,
                    "delta_components": {
                        component: baseline_summary["components"][component] - summary["components"][component]
                        for component in COMPONENTS
                    },
                    "by_bucket": by_bucket,
                }
            )

    payload = {
        "date": date.today().isoformat(),
        "decision": "frozen_to_A0",
        "rows": rows,
    }
    (RESULTS / "S_formulario.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    flat_rows = []
    for row in rows:
        flat = {
            "id": row["id"],
            "mode": row["mode"],
            "is_add_back": row["is_add_back"],
            "n": row["n"],
            "ranking": row["ranking"],
            "gate": row["gate"],
            "f1_yes": row["f1_yes"],
            "spec": json.dumps(row["spec"], sort_keys=True),
            "by_bucket": json.dumps(row["by_bucket"], sort_keys=True),
        }
        for component in COMPONENTS:
            flat[component] = row["components"][component]
            flat[f"delta_{component}"] = row["delta_components"][component]
        flat_rows.append(flat)
    _write_csv(RESULTS / "S_formulario.csv", flat_rows)
    return rows


def _sensitivity_family(variant_id: str) -> str:
    if variant_id.startswith("S-T-"):
        return "threshold"
    if variant_id.startswith("S-FM-"):
        return "fusion_mult"
    if variant_id.startswith("S-TW-"):
        return "tier_weights"
    raise ValueError(f"No es una variante de sensibilidad: {variant_id}.")


def run_sensitivity() -> list[dict[str, Any]]:
    variants = load_variants()
    selected = [variant for variant in variants.values() if variant.tipo == "sensitivity"]
    rows: list[dict[str, Any]] = []
    for mode in MODES:
        baseline_raw = simulate_variant(variants["A0"].spec, mode)
        baseline = _form_summary(baseline_raw)
        for variant in selected:
            raw = simulate_variant(variant.spec, mode)
            summary = _form_summary(raw)
            family = _sensitivity_family(variant.id)
            is_a0_value = (
                (family == "threshold" and variant.spec.threshold == variants["A0"].spec.threshold)
                or (family == "fusion_mult" and variant.spec.fusion_mult == variants["A0"].spec.fusion_mult)
                or (family == "tier_weights" and variant.spec.tiers == variants["A0"].spec.tiers)
            )
            rows.append(
                {
                    "id": variant.id,
                    "mode": mode,
                    "family": family,
                    "label": "sensibilidad, no ablacion",
                    "is_a0_value": is_a0_value,
                    "spec": asdict(variant.spec),
                    **summary,
                    "delta_ranking": baseline["ranking"] - summary["ranking"],
                    "delta_gate": baseline["gate"] - summary["gate"],
                    "delta_f1_yes": baseline["f1_yes"] - summary["f1_yes"],
                }
            )

    payload = {"date": date.today().isoformat(), "rows": rows}
    (RESULTS / "S_sensibilidad.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    flat_rows = []
    for row in rows:
        flat = {key: value for key, value in row.items() if key not in {"components", "spec"}}
        flat["spec"] = json.dumps(row["spec"], sort_keys=True)
        flat.update(row["components"])
        flat_rows.append(flat)
    _write_csv(RESULTS / "S_sensibilidad.csv", flat_rows)
    return rows


def _read_split(name: str) -> set[str]:
    return {
        line.strip()
        for line in (SPLITS / f"task1_{name}.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _sign(value: float, tolerance: float = 1e-15) -> str:
    if value > tolerance:
        return "positivo"
    if value < -tolerance:
        return "negativo"
    return "cero"


def _partition_comparison(
    baseline: list[dict[str, Any]], variant: list[dict[str, Any]], case_ids: set[str]
) -> dict[str, Any]:
    left = [row for row in baseline if row["case_id"] in case_ids]
    right = [row for row in variant if row["case_id"] in case_ids]
    delta_ranking = ranking_from_rows(left) - ranking_from_rows(right)
    delta_gate = _metric(left, "gate") - _metric(right, "gate")
    delta_f1 = _metric(left, "f1_yes") - _metric(right, "f1_yes")
    mcnemar = mcnemar_exact(left, right)
    net = mcnemar.base_only - mcnemar.variant_only
    return {
        "n": len(left),
        "delta_ranking": delta_ranking,
        "delta_gate": delta_gate,
        "delta_f1_yes": delta_f1,
        "signo": _sign(delta_ranking),
        "mcnemar": asdict(mcnemar),
        "net_decisions": net,
    }


def run_robustness() -> list[dict[str, Any]]:
    variants = load_variants()
    selected = [variant for variant in variants.values() if variant.bloque in LOO_BLOCKS]
    splits = {name: _read_split(name) for name in ("dev", "val")}
    minimum_detectable = next(
        row["net"] for row in detectability_table(91) if row["detectable"]
    )
    by_variant: dict[str, dict[str, Any]] = {
        variant.id: {
            "id": variant.id,
            "bloque": variant.bloque,
            "tipo": variant.tipo,
            "minimum_detectable_net": minimum_detectable,
            "modes": {},
        }
        for variant in selected
    }
    for mode in MODES:
        baseline_raw = simulate_variant(variants["A0"].spec, mode)
        baseline = score_rows(baseline_raw)["rows"]
        for variant in selected:
            raw = baseline_raw if variant.id == "A0" else simulate_variant(variant.spec, mode)
            scored = baseline if variant.id == "A0" else score_rows(raw)["rows"]
            comparisons = {
                split: _partition_comparison(baseline, scored, ids)
                for split, ids in splits.items()
            }
            full = mcnemar_exact(baseline, scored)
            net = full.base_only - full.variant_only
            by_variant[variant.id]["modes"][mode] = {
                **comparisons,
                "same_sign": comparisons["dev"]["signo"] == comparisons["val"]["signo"],
                "full_net_decisions": net,
                "additional_net_for_zero_opposition_threshold": max(0, minimum_detectable - abs(net)),
            }

    rows = list(by_variant.values())
    payload = {
        "date": date.today().isoformat(),
        "splits": {name: len(ids) for name, ids in splits.items()},
        "detectability": detectability_table(91),
        "rows": rows,
    }
    (RESULTS / "S_robustez.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    flat_rows = []
    for row in rows:
        honest = row["modes"]["honest"]
        deployed = row["modes"]["deployed"]
        flat_rows.append(
            {
                "id": row["id"],
                "bloque": row["bloque"],
                "tipo": row["tipo"],
                "signo_dev": honest["dev"]["signo"],
                "signo_val": honest["val"]["signo"],
                "same_sign": honest["same_sign"],
                "delta_ranking_dev": honest["dev"]["delta_ranking"],
                "delta_ranking_val": honest["val"]["delta_ranking"],
                "signo_dev_deployed": deployed["dev"]["signo"],
                "signo_val_deployed": deployed["val"]["signo"],
                "same_sign_deployed": deployed["same_sign"],
                "minimum_detectable_net": minimum_detectable,
                "full_net_decisions": honest["full_net_decisions"],
                "additional_net_needed": honest["additional_net_for_zero_opposition_threshold"],
            }
        )
    _write_csv(RESULTS / "S_robustez.csv", flat_rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "experiment",
        choices=("loo", "cascade", "factorial", "form", "sensitivity", "robustness"),
    )
    parser.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    args = parser.parse_args()
    if args.experiment == "loo":
        rows = run_loo(resamples=args.resamples)
        print(f"S_loo: {len(rows)} filas")
    elif args.experiment == "cascade":
        rows = run_cascade(resamples=args.resamples)
        print(f"S_cascade: {len(rows)} filas")
    elif args.experiment == "factorial":
        rows = run_factorial()
        print(f"S_factorial: {len(rows)} filas")
    elif args.experiment == "form":
        rows = run_form()
        print(f"S_formulario: {len(rows)} filas")
    elif args.experiment == "sensitivity":
        rows = run_sensitivity()
        print(f"S_sensibilidad: {len(rows)} filas")
    elif args.experiment == "robustness":
        rows = run_robustness()
        print(f"S_robustez: {len(rows)} filas")


if __name__ == "__main__":
    main()
