from __future__ import annotations

from Ablation_study.harness.run_tier_s import LOO_BLOCKS
from Ablation_study.harness.variants import load_variants


def test_loo_selection_has_the_preregistered_33_variants() -> None:
    selected = [variant for variant in load_variants().values() if variant.bloque in LOO_BLOCKS]
    assert len(selected) == 33
    assert selected[0].id == "A0"
