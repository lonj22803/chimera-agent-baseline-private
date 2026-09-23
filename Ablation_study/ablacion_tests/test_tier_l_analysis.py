from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from Ablation_study.harness.run_tier_l import field_changes


REPO_ROOT = Path(__file__).resolve().parents[2]


def _row(case_id: str, decision: object, confidence: str = "clear") -> dict:
    return {
        "case_id": case_id,
        "pred": {
            "biopsy_decision": decision,
            "confidence": confidence,
            "variable_weights": {"age": "noted"},
            "reveal_sequence": ["radiology_report"],
        },
    }


def test_field_changes_normalises_decision_and_counts_form_changes() -> None:
    result = field_changes(
        [_row("a", True), _row("b", "no")],
        [_row("a", "yes"), _row("b", False, confidence="unclear")],
    )

    assert result["by_field"]["biopsy_decision"] == 0
    assert result["by_field"]["confidence"] == 1
    assert result["cases"] == ["b"]


def test_field_changes_requires_the_same_cases() -> None:
    with pytest.raises(ValueError, match="mismos casos"):
        field_changes([_row("a", True)], [_row("b", True)])


def test_judge_plan_has_three_passes_for_all_nine_arms() -> None:
    result = subprocess.run(
        ["bash", "Ablation_study/harness/judge_session.sh", "--plan"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()
    assert len(lines) == 27
    for pass_number in (1, 2, 3):
        selected = [line.split()[1] for line in lines if line.startswith(f"p{pass_number} ")]
        assert set(selected) == {"L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L0p"}
