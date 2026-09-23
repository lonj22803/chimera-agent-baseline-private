from __future__ import annotations

from pathlib import Path

import pytest

from Ablation_study.harness.sim import A0, score_rows, simulate_variant
from version_final_reto.task_1.agent import protocol as P
from version_final_reto.task_1.analysis import simulate as v4_simulate
from version_final_reto.task_1.experts_1.panel import CACHE, Panel


@pytest.mark.parametrize("mode", ["deployed", "honest"])
def test_a0_is_field_identical_to_v4(mode: str) -> None:
    panel = Panel(Path(CACHE))
    expected = v4_simulate.simulate(
        mode,
        True,
        3,
        dict(P.PARAMS),
        "model+mode",
        panel,
    )
    actual = simulate_variant(A0, mode, panel=panel)

    assert actual == expected
    score = score_rows(actual)
    assert len(actual) == len(score["rows"]) == 91
    expected_score = v4_simulate.score(expected)
    assert score["ranking"] == expected_score["ranking"]
    assert score["gate"] == expected_score["gate"]
    assert score["f1_yes"] == expected_score["f1_yes"]
    assert score["components"] == expected_score["components"]


def test_all_cases_simulates_195_without_scoring_unlabelled_cases() -> None:
    rows = simulate_variant(A0, "deployed", all_cases=True)
    assert len(rows) == 195
    assert len(score_rows(rows)["rows"]) == 91
