from __future__ import annotations

import pytest

from Ablation_study.harness.judge_analysis import paired_narrative_effect


def test_paired_narrative_effect_uses_common_cases_and_baseline_minus_variant() -> None:
    result = paired_narrative_effect(
        {"a": 0.9, "b": 0.8, "only_base": 0.1},
        {"a": 0.7, "b": 0.7, "only_variant": 1.0},
        resamples=500,
    )

    assert result["n"] == 2
    assert result["baseline"] == pytest.approx(0.85)
    assert result["variant"] == pytest.approx(0.70)
    assert result["delta"] == pytest.approx(0.15)
    assert result["ci95"][0] > 0
