"""Estadistica pareada pre-registrada para el estudio de ablacion."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import binomtest, wilcoxon

BOOTSTRAP_SEED = 20260921
BOOTSTRAP_RESAMPLES = 10_000
COMPONENTS = (
    "confidence_score",
    "variable_weight_score",
    "important_decisive_factor_score",
    "tool_score",
    "section_grounding_score",
)


@dataclass(frozen=True)
class PairedTest:
    statistic: float
    p_value: float
    n: int
    base_only: int = 0
    variant_only: int = 0


@dataclass(frozen=True)
class BootstrapResult:
    delta: float
    low: float
    high: float
    n: int
    resamples: int


def _f1_yes(rows: Sequence[Mapping[str, Any]]) -> float:
    tp = sum(int(row["gt"] == 1 and row["pred"] == 1) for row in rows)
    fp = sum(int(row["gt"] == 0 and row["pred"] == 1) for row in rows)
    fn = sum(int(row["gt"] == 1 and row["pred"] == 0) for row in rows)
    denominator = 2 * tp + fp + fn
    return 2 * tp / denominator if denominator else 0.0


def ranking_from_rows(rows: Sequence[Mapping[str, Any]]) -> float:
    """Reproduce ``compute_aggregate_metrics`` para filas de Task 1."""
    if not rows:
        raise ValueError("No se puede calcular ranking sin filas.")
    mean_case = fmean(float(row["case_score"]) for row in rows)
    return (mean_case + _f1_yes(rows)) / 2


def _aligned(
    baseline: Sequence[Mapping[str, Any]], variant: Sequence[Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    left = {str(row["case_id"]): row for row in baseline}
    right = {str(row["case_id"]): row for row in variant}
    if set(left) != set(right):
        missing_left = sorted(set(right) - set(left))
        missing_right = sorted(set(left) - set(right))
        raise ValueError(
            f"Los brazos no contienen los mismos casos; baseline={missing_left}, variante={missing_right}."
        )
    return [(left[case_id], right[case_id]) for case_id in sorted(left)]


def _metric(rows: Sequence[Mapping[str, Any]], metric: str) -> float:
    if metric == "ranking":
        return ranking_from_rows(rows)
    if metric == "f1_yes":
        return _f1_yes(rows)
    if metric == "gate":
        return fmean(float(row["decision_score"]) for row in rows)
    values = [float(row[metric]) for row in rows if row.get(metric) is not None]
    if not values:
        raise ValueError(f"La metrica {metric} no tiene observaciones.")
    return fmean(values)


def paired_bootstrap(
    baseline: Sequence[Mapping[str, Any]],
    variant: Sequence[Mapping[str, Any]],
    metric: str,
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> BootstrapResult:
    """IC percentil pareado; F se restringe a aciertos comunes."""
    pairs = _aligned(baseline, variant)
    if metric in COMPONENTS:
        pairs = [
            pair
            for pair in pairs
            if pair[0]["decision_score"] == pair[1]["decision_score"] == 1.0
            and pair[0].get(metric) is not None
            and pair[1].get(metric) is not None
        ]
    if not pairs:
        raise ValueError(f"No hay pares validos para {metric}.")

    base_rows = [pair[0] for pair in pairs]
    variant_rows = [pair[1] for pair in pairs]
    observed = _metric(base_rows, metric) - _metric(variant_rows, metric)
    rng = np.random.default_rng(seed)
    deltas = np.empty(resamples, dtype=float)
    n = len(pairs)
    for index in range(resamples):
        sample = rng.integers(0, n, size=n)
        sampled_base = [base_rows[position] for position in sample]
        sampled_variant = [variant_rows[position] for position in sample]
        deltas[index] = _metric(sampled_base, metric) - _metric(sampled_variant, metric)
    low, high = np.quantile(deltas, (0.025, 0.975))
    return BootstrapResult(observed, float(low), float(high), n, resamples)


def _f1_vector(gt: np.ndarray, pred: np.ndarray) -> np.ndarray:
    tp = np.sum((gt == 1) & (pred == 1), axis=1)
    fp = np.sum((gt == 0) & (pred == 1), axis=1)
    fn = np.sum((gt == 1) & (pred == 0), axis=1)
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros_like(tp, dtype=float), where=denominator != 0)


def paired_bootstrap_metrics(
    baseline: Sequence[Mapping[str, Any]],
    variant: Sequence[Mapping[str, Any]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, BootstrapResult]:
    """Calcula los ocho IC de una comparacion con remuestreo vectorizado."""
    pairs = _aligned(baseline, variant)
    if not pairs:
        raise ValueError("No hay pares para el bootstrap.")
    rng = np.random.default_rng(seed)
    n = len(pairs)
    sample = rng.integers(0, n, size=(resamples, n))

    base_case = np.asarray([float(left["case_score"]) for left, _ in pairs])
    variant_case = np.asarray([float(right["case_score"]) for _, right in pairs])
    base_correct = np.asarray([float(left["decision_score"]) for left, _ in pairs])
    variant_correct = np.asarray([float(right["decision_score"]) for _, right in pairs])
    gt = np.asarray([int(left["gt"]) for left, _ in pairs])
    base_pred = np.asarray([int(left["pred"]) for left, _ in pairs])
    variant_pred = np.asarray([int(right["pred"]) for _, right in pairs])

    base_f1 = _f1_vector(gt[sample], base_pred[sample])
    variant_f1 = _f1_vector(gt[sample], variant_pred[sample])
    f1_deltas = base_f1 - variant_f1
    gate_deltas = np.mean(base_correct[sample] - variant_correct[sample], axis=1)
    ranking_deltas = (
        np.mean(base_case[sample] - variant_case[sample], axis=1) + f1_deltas
    ) / 2

    observed_f1 = _f1_yes([left for left, _ in pairs]) - _f1_yes([right for _, right in pairs])
    observed_gate = float(np.mean(base_correct - variant_correct))
    observed_ranking = ranking_from_rows([left for left, _ in pairs]) - ranking_from_rows(
        [right for _, right in pairs]
    )

    def result(delta: float, values: np.ndarray, count: int) -> BootstrapResult:
        low, high = np.quantile(values, (0.025, 0.975))
        return BootstrapResult(float(delta), float(low), float(high), count, resamples)

    results = {
        "ranking": result(observed_ranking, ranking_deltas, n),
        "gate": result(observed_gate, gate_deltas, n),
        "f1_yes": result(observed_f1, f1_deltas, n),
    }
    for component in COMPONENTS:
        common = [
            pair
            for pair in pairs
            if pair[0]["decision_score"] == pair[1]["decision_score"] == 1.0
            and pair[0].get(component) is not None
            and pair[1].get(component) is not None
        ]
        if not common:
            raise ValueError(f"No hay aciertos comunes para {component}.")
        differences = np.asarray(
            [float(left[component]) - float(right[component]) for left, right in common]
        )
        component_sample = rng.integers(0, len(common), size=(resamples, len(common)))
        sampled = np.mean(differences[component_sample], axis=1)
        results[component] = result(float(np.mean(differences)), sampled, len(common))
    return results


def mcnemar_exact(
    baseline: Sequence[Mapping[str, Any]] | None = None,
    variant: Sequence[Mapping[str, Any]] | None = None,
    *,
    base_only: int | None = None,
    variant_only: int | None = None,
) -> PairedTest:
    """McNemar exacto bilateral sobre los pares discordantes."""
    if baseline is not None or variant is not None:
        if baseline is None or variant is None:
            raise ValueError("McNemar necesita ambos brazos.")
        pairs = _aligned(baseline, variant)
        base_only = sum(
            int(left["decision_score"] == 1.0 and right["decision_score"] != 1.0)
            for left, right in pairs
        )
        variant_only = sum(
            int(right["decision_score"] == 1.0 and left["decision_score"] != 1.0)
            for left, right in pairs
        )
    if base_only is None or variant_only is None or min(base_only, variant_only) < 0:
        raise ValueError("Los discordantes deben ser enteros no negativos.")
    discordant = int(base_only + variant_only)
    p_value = 1.0 if discordant == 0 else float(
        binomtest(min(base_only, variant_only), discordant, 0.5, alternative="two-sided").pvalue
    )
    return PairedTest(
        statistic=float(abs(base_only - variant_only)),
        p_value=p_value,
        n=discordant,
        base_only=int(base_only),
        variant_only=int(variant_only),
    )


def sign_test(differences: Iterable[float]) -> PairedTest:
    values = [float(value) for value in differences if float(value) != 0.0]
    positive = sum(value > 0 for value in values)
    negative = len(values) - positive
    p_value = 1.0 if not values else float(
        binomtest(min(positive, negative), len(values), 0.5, alternative="two-sided").pvalue
    )
    return PairedTest(float(abs(positive - negative)), p_value, len(values), positive, negative)


def wilcoxon_common_correct(
    baseline: Sequence[Mapping[str, Any]],
    variant: Sequence[Mapping[str, Any]],
    component: str,
) -> PairedTest:
    if component not in COMPONENTS:
        raise ValueError(f"Componente desconocido: {component}.")
    pairs = [
        pair
        for pair in _aligned(baseline, variant)
        if pair[0]["decision_score"] == pair[1]["decision_score"] == 1.0
        and pair[0].get(component) is not None
        and pair[1].get(component) is not None
    ]
    differences = np.asarray(
        [float(left[component]) - float(right[component]) for left, right in pairs], dtype=float
    )
    if not len(differences) or np.all(differences == 0):
        return PairedTest(0.0, 1.0, len(differences))
    result = wilcoxon(differences, zero_method="wilcox", alternative="two-sided")
    return PairedTest(float(result.statistic), float(result.pvalue), len(differences))


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    """Ajuste step-down de Holm, preservando las etiquetas de entrada."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    total = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, float(value) * (total - rank)))
        adjusted[name] = running
    return adjusted


def shapley_values(
    values: Mapping[frozenset[str], float], players: Sequence[str]
) -> dict[str, float]:
    """Shapley exacto a partir del factorial completo de una metrica."""
    player_set = frozenset(players)
    expected = {frozenset(group) for size in range(len(players) + 1) for group in combinations(players, size)}
    missing = expected - set(values)
    if missing:
        raise ValueError(f"Factorial incompleto; faltan {len(missing)} coaliciones.")
    factorial = math.factorial
    n = len(players)
    result: dict[str, float] = {}
    for player in players:
        others = player_set - {player}
        contribution = 0.0
        for size in range(len(others) + 1):
            weight = factorial(size) * factorial(n - size - 1) / factorial(n)
            for group in combinations(sorted(others), size):
                coalition = frozenset(group)
                contribution += weight * (values[coalition | {player}] - values[coalition])
        result[player] = contribution
    return result


def detectability_table(n: int = 91, alpha: float = 0.05) -> list[dict[str, Any]]:
    """McNemar para k discordantes a favor y ninguno en contra."""
    if n < 1:
        raise ValueError("n debe ser positivo.")
    rows = []
    for discordant in range(n + 1):
        test = mcnemar_exact(base_only=discordant, variant_only=0)
        rows.append(
            {
                "n": n,
                "base_only": discordant,
                "variant_only": 0,
                "net": discordant,
                "p_value": test.p_value,
                "detectable": test.p_value < alpha,
            }
        )
    return rows
