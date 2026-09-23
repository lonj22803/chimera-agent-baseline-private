from __future__ import annotations

from Ablation_study.harness.synthesize import _combine


def test_combine_prefers_stable_necessary_and_requires_all_spare() -> None:
    assert _combine(["SOBRA_D", "NECESARIA_D"], "D") == "NECESARIA_D"
    assert _combine(["SOBRA_F", "SOBRA"], "F") == "SOBRA_F"
    assert _combine(["SOBRA_D", "INDETERMINADA_D"], "D") == "INDETERMINADA_D"
