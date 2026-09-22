"""What lands on disk for Grand Challenge.

The platform matches output files by exact name and expects bare JSON values for
the decision files. Getting either wrong means a rejected submission, not a low
score, so these names are pinned here rather than trusted to review.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chimera_agent_baseline.run import _write_task_outputs

REASONING = "PI-RADS 4 with a rising PSA density above 0.20 supports proceeding to biopsy."


def _read(path: Path):
    return json.loads(path.read_text())


@pytest.mark.parametrize(
    ("task", "structured", "expected_files"),
    [
        (
            1,
            {
                "biopsy_decision": True,
                "confidence": "clear",
                "variable_weights": {"pirads": "decisive"},
                "reveal_sequence": ["radiology_report"],
                "reasoning": REASONING,
            },
            {"prostate-biopsy-decision.json", "prostate-biopsy-decision-reasoning.json"},
        ),
        (
            2,
            {
                "action": "active_surveillance",
                "confidence": "clear",
                "variable_weights": {"bx_isup": "decisive"},
                "reveal_sequence": [],
                "reasoning": REASONING,
            },
            {"prostate-treatment-decision.json", "prostate-treatment-decision-reasoning.json"},
        ),
        (
            3,
            {"months_to_recurrence": 42.5, "reasoning": REASONING},
            {
                "prostate-time-to-recurrence-or-last-follow-up.json",
                "prostate-time-to-recurrence-or-last-follow-up-reasoning.json",
            },
        ),
    ],
)
def test_writes_exactly_the_two_expected_files(tmp_path: Path, task, structured, expected_files) -> None:
    _write_task_outputs(tmp_path, task, structured)

    assert {p.name for p in tmp_path.iterdir()} == expected_files


@pytest.mark.parametrize(("decision", "expected"), [(True, "yes"), (False, "no")])
def test_task1_decision_is_a_bare_yes_no_string(tmp_path: Path, decision: bool, expected: str) -> None:
    """The schema field is a bool; the submitted file is ``"yes"`` / ``"no"``."""
    _write_task_outputs(
        tmp_path,
        1,
        {
            "biopsy_decision": decision,
            "confidence": "clear",
            "variable_weights": {},
            "reveal_sequence": [],
            "reasoning": REASONING,
        },
    )

    assert _read(tmp_path / "prostate-biopsy-decision.json") == expected


def test_task2_decision_is_a_bare_action_string(tmp_path: Path) -> None:
    _write_task_outputs(
        tmp_path,
        2,
        {
            "action": "watchful_waiting",
            "confidence": "borderline",
            "variable_weights": {},
            "reveal_sequence": [],
            "reasoning": REASONING,
        },
    )

    assert _read(tmp_path / "prostate-treatment-decision.json") == "watchful_waiting"


def test_reasoning_file_renames_reasoning_to_free_text(tmp_path: Path) -> None:
    """The schema calls it ``reasoning``; the submitted JSON calls it ``free_text``."""
    _write_task_outputs(
        tmp_path,
        1,
        {
            "biopsy_decision": True,
            "confidence": "clear",
            "variable_weights": {"pirads": "decisive"},
            "reveal_sequence": ["radiology_report"],
            "reasoning": REASONING,
        },
    )

    payload = _read(tmp_path / "prostate-biopsy-decision-reasoning.json")

    assert set(payload) == {"confidence", "variable_weights", "reveal_sequence", "free_text"}
    assert payload["free_text"] == REASONING


def test_task3_decision_carries_months_and_event(tmp_path: Path) -> None:
    _write_task_outputs(tmp_path, 3, {"months_to_recurrence": 42.5, "reasoning": REASONING})

    payload = _read(tmp_path / "prostate-time-to-recurrence-or-last-follow-up.json")

    assert payload == {"event": 0, "months_to_recurrence": 42.5}


def test_task3_event_defaults_to_zero_because_the_schema_has_no_such_field(tmp_path: Path) -> None:
    """Documented gap, not an accident.

    ``Task3Output`` exposes no ``event`` field, so ``run.py`` always writes 0.
    Harrell's C-index only ranks by ``months_to_recurrence``, so this does not
    cost points today — but a solution that starts predicting the event has to
    change both ends. This test fails loudly if only one end changes.
    """
    _write_task_outputs(tmp_path, 3, {"months_to_recurrence": 1.0, "event": 1, "reasoning": REASONING})

    assert _read(tmp_path / "prostate-time-to-recurrence-or-last-follow-up.json")["event"] == 1


def test_task3_reasoning_file_is_a_bare_string(tmp_path: Path) -> None:
    _write_task_outputs(tmp_path, 3, {"months_to_recurrence": 42.5, "reasoning": REASONING})

    assert _read(tmp_path / "prostate-time-to-recurrence-or-last-follow-up-reasoning.json") == REASONING


def test_unknown_task_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _write_task_outputs(tmp_path, 4, {})


def test_case_directory_is_created_on_demand(tmp_path: Path) -> None:
    nested = tmp_path / "task1" / "PT-test-0001"

    _write_task_outputs(
        nested,
        1,
        {
            "biopsy_decision": False,
            "confidence": "uncertain",
            "variable_weights": {},
            "reveal_sequence": [],
            "reasoning": REASONING,
        },
    )

    assert (nested / "prostate-biopsy-decision.json").exists()
