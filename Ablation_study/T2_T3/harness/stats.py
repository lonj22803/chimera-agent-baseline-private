"""Bootstrap pareado pre-registrado para las tareas 2 y 3."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

BOOTSTRAP_SEED = 20260923
BOOTSTRAP_RESAMPLES = 10_000
T2_COMPONENTS = (
    "confidence_score",
    "variable_weight_score",
    "important_decisive_factor_score",
    "tool_score",
    "section_grounding_score",
)


@dataclass(frozen=True)
class Interval:
    delta: float
    low: float
    high: float
    n: int
    resamples: int


def _aligned(
    baseline: Sequence[Mapping[str, Any]], variant: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    left = {str(row["case_id"]): row for row in baseline}
    right = {str(row["case_id"]): row for row in variant}
    if set(left) != set(right):
        raise ValueError("Los brazos no contienen los mismos casos")
    return [(left[case_id], right[case_id]) for case_id in sorted(left)]


def _interval(observed: float, values: np.ndarray, n: int) -> dict[str, Any]:
    low, high = np.quantile(values, (0.025, 0.975))
    return asdict(Interval(float(observed), float(low), float(high), n, len(values)))


def _weighted_f1_samples(gt: np.ndarray, pred: np.ndarray, sample: np.ndarray) -> np.ndarray:
    classes = sorted(set(gt.tolist()))
    n_boot, n = sample.shape
    result = np.zeros(n_boot, dtype=float)
    sampled_gt = gt[sample]
    sampled_pred = pred[sample]
    for label in classes:
        truth = sampled_gt == label
        guess = sampled_pred == label
        support = np.sum(truth, axis=1)
        tp = np.sum(truth & guess, axis=1)
        fp = np.sum(~truth & guess, axis=1)
        fn = support - tp
        denominator = 2 * tp + fp + fn
        f1 = np.divide(2 * tp, denominator, out=np.zeros(n_boot), where=denominator != 0)
        result += support * f1
    return result / n


def t2_bootstrap(
    baseline: Sequence[Mapping[str, Any]],
    variant: Sequence[Mapping[str, Any]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, dict[str, Any]]:
    """Deltas referencia-variante; ranking usa el F1 ponderado oficial."""
    pairs = _aligned(baseline, variant)
    n = len(pairs)
    rng = np.random.default_rng(seed)
    sample = rng.integers(0, n, size=(resamples, n))
    gt_labels = sorted({str(left["gt_decision"]) for left, _ in pairs})
    code = {label: index for index, label in enumerate(gt_labels)}
    missing = len(code)
    gt = np.asarray([code[str(left["gt_decision"])] for left, _ in pairs])
    base_pred = np.asarray([code.get(str(left.get("pred_decision")), missing) for left, _ in pairs])
    var_pred = np.asarray([code.get(str(right.get("pred_decision")), missing) for _, right in pairs])
    base_case = np.asarray([float(left["case_score"]) for left, _ in pairs])
    var_case = np.asarray([float(right["case_score"]) for _, right in pairs])
    base_gate = np.asarray([float(left["decision_score"]) for left, _ in pairs])
    var_gate = np.asarray([float(right["decision_score"]) for _, right in pairs])

    base_f1 = _weighted_f1_samples(gt, base_pred, sample)
    var_f1 = _weighted_f1_samples(gt, var_pred, sample)
    case_delta = np.mean(base_case[sample] - var_case[sample], axis=1)
    gate_delta = np.mean(base_gate[sample] - var_gate[sample], axis=1)
    f1_delta = base_f1 - var_f1
    rank_delta = (case_delta + f1_delta) / 2

    def f1_observed(pred: np.ndarray) -> float:
        return float(_weighted_f1_samples(gt, pred, np.arange(n)[None, :])[0])

    result = {
        "ranking_score": _interval(
            (float(np.mean(base_case)) - float(np.mean(var_case))
             + f1_observed(base_pred) - f1_observed(var_pred)) / 2,
            rank_delta,
            n,
        ),
        "decision_accuracy": _interval(float(np.mean(base_gate - var_gate)), gate_delta, n),
        "decision_weighted_f1": _interval(
            f1_observed(base_pred) - f1_observed(var_pred), f1_delta, n
        ),
        "mean_case_score": _interval(float(np.mean(base_case - var_case)), case_delta, n),
    }
    for component in T2_COMPONENTS:
        common = [
            (left, right)
            for left, right in pairs
            if left["decision_score"] == right["decision_score"] == 1.0
            and left.get(component) is not None
            and right.get(component) is not None
        ]
        differences = np.asarray(
            [float(left[component]) - float(right[component]) for left, right in common]
        )
        component_sample = rng.integers(0, len(common), size=(resamples, len(common)))
        result[component] = _interval(
            float(np.mean(differences)), np.mean(differences[component_sample], axis=1), len(common)
        )
    return result


def _c_index_matrices(rows: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    times = np.asarray([float(row["gt_months"]) for row in rows])
    events = np.asarray([int(row["gt_event"]) for row in rows])
    preds = np.asarray([float(row["pred_months"]) for row in rows])
    comparable = ((events[:, None] == 1) & (times[:, None] < times[None, :])).astype(float)
    concordance = (preds[:, None] < preds[None, :]).astype(float)
    concordance += 0.5 * (preds[:, None] == preds[None, :])
    return comparable, comparable * concordance


def _quadratic(values: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return np.einsum("bi,ij,bj->b", values, matrix, values, optimize=True)


def t3_bootstrap(
    baseline: Sequence[Mapping[str, Any]],
    variant: Sequence[Mapping[str, Any]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, dict[str, Any]]:
    """Bootstrap por caso; el c-index se calcula con multiplicidades del remuestreo."""
    pairs = _aligned(baseline, variant)
    base = [left for left, _ in pairs]
    other = [right for _, right in pairs]
    n = len(pairs)
    rng = np.random.default_rng(seed)
    sample = rng.integers(0, n, size=(resamples, n))
    counts = np.zeros((resamples, n), dtype=float)
    np.add.at(counts, (np.arange(resamples)[:, None], sample), 1.0)

    denominator, base_numerator = _c_index_matrices(base)
    other_denominator, other_numerator = _c_index_matrices(other)
    base_den = _quadratic(counts, denominator)
    other_den = _quadratic(counts, other_denominator)
    base_ci = np.divide(_quadratic(counts, base_numerator), base_den,
                        out=np.full(resamples, np.nan), where=base_den > 0)
    other_ci = np.divide(_quadratic(counts, other_numerator), other_den,
                         out=np.full(resamples, np.nan), where=other_den > 0)

    def c_index(rows: Sequence[Mapping[str, Any]]) -> float:
        den, num = _c_index_matrices(rows)
        total = float(np.sum(den))
        return float(np.sum(num) / total)

    metrics = {
        "mean_case_score": "case_score",
        "mean_event_score": "event_score",
        "mean_time_score": "time_score",
    }
    result = {
        "ranking_score": _interval(
            c_index(base) - c_index(other), (base_ci - other_ci)[np.isfinite(base_ci - other_ci)], n
        )
    }
    for name, key in metrics.items():
        difference = np.asarray([float(left[key]) - float(right[key]) for left, right in pairs])
        values = np.mean(difference[sample], axis=1)
        result[name] = _interval(float(np.mean(difference)), values, n)
    return result
