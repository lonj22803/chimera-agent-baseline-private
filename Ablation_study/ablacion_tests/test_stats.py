from __future__ import annotations

import pytest

from Ablation_study.harness.classify import classify
from Ablation_study.harness.sim import A0, score_rows, simulate_variant
from Ablation_study.harness.stats import (
    detectability_table,
    mcnemar_exact,
    ranking_from_rows,
    shapley_values,
)


def test_ranking_reimplements_the_official_evaluator_to_1e_12() -> None:
    scored = score_rows(simulate_variant(A0, "honest"))
    assert ranking_from_rows(scored["rows"]) == pytest.approx(scored["ranking"], abs=1e-12)


def test_mcnemar_six_to_zero_is_003125() -> None:
    result = mcnemar_exact(base_only=6, variant_only=0)
    assert result.p_value == pytest.approx(0.03125)


def test_exact_zero_is_redundant_by_construction() -> None:
    assert classify(0.0, (0.0, 0.0), level="D", exact_zero=True) == "SOBRA"


def test_large_delta_with_ci_crossing_zero_is_indeterminate() -> None:
    assert classify(0.03, (-0.01, 0.06), level="D", p_value=0.01) == "INDETERMINADA_D"


def test_detectability_is_monotone_and_starts_at_six_cases() -> None:
    table = detectability_table(91)
    p_values = [row["p_value"] for row in table]
    assert all(left >= right for left, right in zip(p_values, p_values[1:]))
    assert next(row["net"] for row in table if row["detectable"]) == 6


def test_shapley_exactly_recovers_an_additive_factorial() -> None:
    players = ("cohort", "grade", "E1", "E3")
    merit = {"cohort": 0.4, "grade": 0.2, "E1": 0.1, "E3": 0.3}
    values = {
        coalition: sum(merit[player] for player in coalition)
        for coalition in (
            frozenset(),
            *(
                frozenset({players[index] for index in range(len(players)) if mask & (1 << index)})
                for mask in range(1, 1 << len(players))
            ),
        )
    }
    assert shapley_values(values, players) == pytest.approx(merit)
