"""The MCP tool registries and the store that backs them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chimera_agent_baseline.tools.base import (
    CASE_DATA_FILENAMES_BY_TASK,
    CaseDataStore,
    infer_task_from_data_dir,
)
from chimera_agent_baseline.tools.definitions import TASK1_TOOLS, TASK2_TOOLS, TASK3_TOOLS

from .conftest import CASE_IDS

REGISTRIES = {1: TASK1_TOOLS, 2: TASK2_TOOLS, 3: TASK3_TOOLS}


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        (1, {"get_psa_trend", "get_lab_results", "get_mri_report", "get_previous_notes", "get_family_history"}),
        (
            2,
            {
                "get_psa_trend",
                "get_lab_results",
                "get_mri_report",
                "get_pathology_report",
                "get_previous_notes",
                "get_family_history",
            },
        ),
        (
            3,
            {
                "get_mri_report",
                "get_pathology_report",
                "get_surgical_pathology_report",
                "get_previous_notes",
                "get_family_history",
            },
        ),
    ],
)
def test_registry_exposes_the_documented_tools(task: int, expected: set[str]) -> None:
    assert {spec.name for spec in REGISTRIES[task]} == expected


@pytest.mark.parametrize("task", [1, 2, 3])
def test_tool_names_are_unique(task: int) -> None:
    names = [spec.name for spec in REGISTRIES[task]]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("task", [1, 2, 3])
def test_every_tool_declares_fields_and_a_description(task: int) -> None:
    """The LLM decides what to reveal by reading these descriptions."""
    for spec in REGISTRIES[task]:
        assert spec.fields, f"{spec.name} returns nothing"
        assert len(spec.description) > 20, f"{spec.name} has no usable description"


def test_task1_has_no_pathology_tool() -> None:
    """A biopsy-naive case has no prior pathology to reveal."""
    assert "get_pathology_report" not in {spec.name for spec in TASK1_TOOLS}


@pytest.mark.parametrize("task", [1, 2, 3])
def test_store_indexes_cases_by_id(agent_input, task: int) -> None:
    store = CaseDataStore(agent_input[task])

    assert store.list_case_ids() == [CASE_IDS[task]]
    assert store.get_case(CASE_IDS[task]) is not None


@pytest.mark.parametrize("task", [1, 2, 3])
def test_every_registered_field_is_servable(agent_input, task: int) -> None:
    """Each tool's fields must exist in that task's clinical-data file."""
    store = CaseDataStore(agent_input[task])

    for spec in REGISTRIES[task]:
        payload = store.extract(CASE_IDS[task], spec.fields)
        served = set(payload) - {"case_id"}
        assert served == set(spec.fields), f"{spec.name} could not serve {set(spec.fields) - served}"


def test_extract_omits_absent_fields_instead_of_failing(agent_input) -> None:
    store = CaseDataStore(agent_input[1])

    payload = store.extract(CASE_IDS[1], ("pathology_report",))

    assert payload == {"case_id": CASE_IDS[1]}


def test_extract_rejects_an_unknown_case(agent_input) -> None:
    store = CaseDataStore(agent_input[1])

    with pytest.raises(KeyError):
        store.extract("PT-does-not-exist", ("radiology_report",))


@pytest.mark.parametrize("task", [1, 2, 3])
def test_task_is_inferred_from_the_path(data_root: Path, task: int) -> None:
    assert infer_task_from_data_dir(data_root / f"task{task}" / "agent_input") == task


def test_unknown_path_shape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        infer_task_from_data_dir(tmp_path / "somewhere" / "else")


@pytest.mark.parametrize("task", [1, 2, 3])
def test_clinical_filename_matches_the_grand_challenge_socket(task: int) -> None:
    """These names are the platform's contract, not ours."""
    expected = {
        1: "prostate-biopsy-decision-clinical-data.json",
        2: "prostate-treatment-decision-clinical-data.json",
        3: "prostate-time-to-recurrence-or-last-follow-up-clinical-data.json",
    }
    assert CASE_DATA_FILENAMES_BY_TASK[task] == expected[task]


def test_store_skips_directories_without_the_task_file(data_root: Path) -> None:
    empty = data_root / "task1" / "agent_input" / "PT-empty"
    empty.mkdir()
    (empty / "structured-prompt.json").write_text(json.dumps({"case_id": "PT-empty"}))

    store = CaseDataStore(data_root / "task1" / "agent_input")

    assert "PT-empty" not in store.list_case_ids()
