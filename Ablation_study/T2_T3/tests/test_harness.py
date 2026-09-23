from __future__ import annotations

import json

import pytest

from Ablation_study.T2_T3.harness.paths import DATA3, RESULTS
from Ablation_study.T2_T3.harness.stats import t2_bootstrap, t3_bootstrap
from version_final_reto.task_3.agent.protocol import Panel
from version_final_reto.task_3.agent.run_task3 import load_inputs
from version_final_reto.common.chimera_experts import dataset_task3 as ds


def test_t2_cpu_anchor_and_factorial_are_complete():
    payload = json.loads((RESULTS / "T2_cpu.json").read_text())
    assert payload["n"] == 72
    assert len(payload["variants"]) == 32
    assert payload["baseline"]["ranking"] == pytest.approx(0.7783863062229879)


def test_t3_selected_anchor_is_stable():
    panel = Panel("oof", spokesperson="selected")
    values = []
    for case in load_inputs(DATA3):
        values.append(panel.horizon(case, ds._surgical(case)["capra_s"])["months_to_recurrence"])
    assert len(values) == 75
    assert len(set(values)) > 60


def test_bootstrap_exact_identity_is_zero():
    t2 = [
        {"case_id": "a", "gt_decision": "x", "pred_decision": "x", "case_score": 1.0,
         "decision_score": 1.0, "confidence_score": 1.0, "variable_weight_score": 1.0,
         "important_decisive_factor_score": 1.0, "tool_score": 1.0,
         "section_grounding_score": 1.0},
        {"case_id": "b", "gt_decision": "y", "pred_decision": "y", "case_score": .5,
         "decision_score": 1.0, "confidence_score": .5, "variable_weight_score": .5,
         "important_decisive_factor_score": .5, "tool_score": .5,
         "section_grounding_score": .5},
    ]
    assert all(value["delta"] == 0 for value in t2_bootstrap(t2, t2, resamples=100).values())
    t3 = [
        {"case_id": "a", "gt_months": 1.0, "gt_event": 1, "pred_months": 1.0,
         "case_score": 1.0, "event_score": 1.0, "time_score": 1.0},
        {"case_id": "b", "gt_months": 2.0, "gt_event": 0, "pred_months": 2.0,
         "case_score": 1.0, "event_score": 1.0, "time_score": 1.0},
    ]
    assert all(value["delta"] == 0 for value in t3_bootstrap(t3, t3, resamples=100).values())
