"""The submission contract.

``output/schema.py`` is the one file the challenge rules lock. Everything here
pins its behaviour so a change to the agent can never silently produce a record
the evaluator would reject.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from chimera_agent_baseline.output.schema import (
    TASK1_VARIABLES,
    TASK2_VARIABLES,
    Task1Output,
    Task2Output,
    Task3Output,
    build_dynamic_model,
    eligible_variables,
    normalise_to_full_shape,
)

REASONING = "PI-RADS 4 with a rising PSA density above 0.20 supports proceeding to biopsy."


def _task1_payload(**over) -> dict:
    return {
        "case_id": "PT-test-0001",
        "biopsy_decision": True,
        "confidence": "clear",
        "variable_weights": {"pirads": "decisive", "psa": "important"},
        "reveal_sequence": ["radiology_report"],
        "reasoning": REASONING,
    } | over


def _task2_payload(**over) -> dict:
    return {
        "case_id": "T2-001",
        "action": "active_surveillance",
        "confidence": "clear",
        "variable_weights": {"bx_isup": "decisive"},
        "reveal_sequence": ["pathology_report"],
        "reasoning": REASONING,
    } | over


def _task3_payload(**over) -> dict:
    return {"case_id": "T3-001", "months_to_recurrence": 42.5, "reasoning": REASONING} | over


# --- happy paths -----------------------------------------------------------


def test_task1_accepts_a_well_formed_record() -> None:
    assert Task1Output.model_validate(_task1_payload()).task == 1


def test_task2_accepts_a_well_formed_record() -> None:
    assert Task2Output.model_validate(_task2_payload()).task == 2


def test_task3_accepts_a_well_formed_record() -> None:
    assert Task3Output.model_validate(_task3_payload()).task == 3


# --- the constraints that actually bite ------------------------------------


def test_reasoning_shorter_than_40_chars_is_rejected() -> None:
    """The real ground truth breaks this: 25 of 91 task-1 rationales are shorter.

    Urologists write ~73 characters. The agent must stay terse *and* clear 40.
    """
    with pytest.raises(ValidationError, match="at least 40"):
        Task1Output.model_validate(_task1_payload(reasoning="PI-RADS 2, normal PSA"))


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Task1Output.model_validate(_task1_payload(extra_thoughts="..."))


def test_negative_recurrence_time_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Task3Output.model_validate(_task3_payload(months_to_recurrence=-1.0))


@pytest.mark.parametrize("bad", ["maybe", "CLEAR", ""])
def test_confidence_is_a_closed_enum(bad: str) -> None:
    with pytest.raises(ValidationError):
        Task1Output.model_validate(_task1_payload(confidence=bad))


@pytest.mark.parametrize("bad", ["surgery", "ACTIVE_SURVEILLANCE", "watch"])
def test_treatment_action_is_a_closed_enum(bad: str) -> None:
    with pytest.raises(ValidationError):
        Task2Output.model_validate(_task2_payload(action=bad))


def test_weights_are_a_closed_enum() -> None:
    with pytest.raises(ValidationError):
        Task1Output.model_validate(_task1_payload(variable_weights={"pirads": "very_important"}))


def test_reveal_sequence_rejects_an_unknown_section() -> None:
    with pytest.raises(ValidationError):
        Task1Output.model_validate(_task1_payload(reveal_sequence=["genome_report"]))


def test_task1_cannot_reveal_a_pathology_report() -> None:
    """Task 1 has no prior pathology, so the section is not in its enum."""
    with pytest.raises(ValidationError):
        Task1Output.model_validate(_task1_payload(reveal_sequence=["pathology_report"]))


def test_task2_can_reveal_a_pathology_report() -> None:
    assert Task2Output.model_validate(_task2_payload(reveal_sequence=["pathology_report"]))


def test_reveal_sequence_may_be_empty() -> None:
    """All 72 labelled task-2 cases have an empty sequence in the ground truth."""
    assert Task2Output.model_validate(_task2_payload(reveal_sequence=[])).reveal_sequence == []


# --- dynamic schema: no weight for evidence the agent never saw ------------


def test_only_prompt_variables_are_eligible_without_tool_calls() -> None:
    eligible = eligible_variables(1, called_tools=set())

    assert "fh" not in eligible, "family history needs get_family_history"
    assert "pirads" in eligible


def test_calling_the_tool_unlocks_its_variable() -> None:
    assert "fh" in eligible_variables(1, called_tools={"get_family_history"})


@pytest.mark.parametrize(("task", "variables"), [(1, TASK1_VARIABLES), (2, TASK2_VARIABLES)])
def test_all_variables_eligible_once_every_tool_is_called(task: int, variables: dict) -> None:
    every_tool = {tool for tool in variables.values() if tool}

    assert set(eligible_variables(task, every_tool)) == set(variables)


def test_dynamic_model_forbids_weighting_unseen_evidence() -> None:
    Model = build_dynamic_model(1, called_tools=set())  # noqa: N806

    with pytest.raises(ValidationError):
        Model.model_validate(_task1_payload(variable_weights={"fh": "decisive"}))


def test_dynamic_model_requires_every_eligible_variable() -> None:
    Model = build_dynamic_model(1, called_tools=set())  # noqa: N806

    with pytest.raises(ValidationError):
        Model.model_validate(_task1_payload(variable_weights={"pirads": "decisive"}))


def test_task3_has_no_dynamic_weights() -> None:
    assert build_dynamic_model(3, called_tools=set()) is Task3Output


# --- normalisation back to a uniform on-disk shape -------------------------


@pytest.mark.parametrize(("task", "variables"), [(1, TASK1_VARIABLES), (2, TASK2_VARIABLES)])
def test_normalise_pads_missing_variables_with_not_used(task: int, variables: dict) -> None:
    payload = {"variable_weights": {"pirads": "decisive"}}

    weights = normalise_to_full_shape(task, payload)["variable_weights"]

    assert set(weights) == set(variables)
    assert weights["pirads"] == "decisive"
    assert all(weights[v] == "not_used" for v in variables if v != "pirads")


def test_normalise_is_a_no_op_for_task3() -> None:
    payload = _task3_payload()

    assert normalise_to_full_shape(3, payload) == payload


def test_normalised_record_still_validates() -> None:
    raw = _task1_payload(variable_weights={"pirads": "decisive"})

    assert Task1Output.model_validate(normalise_to_full_shape(1, raw))
