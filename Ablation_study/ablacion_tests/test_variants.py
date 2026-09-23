from __future__ import annotations

from copy import deepcopy

from Ablation_study.harness.sim import simulate_variant
from Ablation_study.harness.variants import load_variants
from version_final_reto.task_1.agent import protocol as P


def test_every_registered_variant_builds_without_mutating_protocol_params() -> None:
    before = deepcopy(P.PARAMS)
    variants = load_variants()

    assert len(variants) == 50
    assert all(variant.spec.id == variant.id for variant in variants.values())
    assert P.PARAMS == before


def test_psa_ablation_changes_zero_rows() -> None:
    before = deepcopy(P.PARAMS)
    variants = load_variants()
    baseline = simulate_variant(variants["A0"].spec, "honest")
    without_psa = simulate_variant(variants["S-PSA-off"].spec, "honest")

    assert without_psa == baseline
    assert P.PARAMS == before


def test_grounding_ablation_removes_both_guard_layers() -> None:
    variants = load_variants()
    baseline = simulate_variant(variants["A0"].spec, "honest")
    without_grounding = simulate_variant(variants["S-G-off"].spec, "honest")

    assert all(
        left["pred"]["biopsy_decision"] == right["pred"]["biopsy_decision"]
        for left, right in zip(baseline, without_grounding)
    )
    assert any(left["pred"] != right["pred"] for left, right in zip(baseline, without_grounding))
