"""The agent's view of a case: what it always sees, and what it must not."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chimera_agent_baseline.case_loader import load_cases, render_baseline_prompt

from .conftest import CASE_IDS


@pytest.mark.parametrize("task", [1, 2, 3])
def test_loads_one_query_per_case(agent_input, templates_dir: Path, task: int) -> None:
    cases = load_cases(agent_input[task], task=task, templates_dir=templates_dir)

    assert len(cases) == 1
    case = cases[0]
    assert case["case_id"] == CASE_IDS[task]
    assert case["task"] == task
    assert case["context"].strip()


@pytest.mark.parametrize("task", [1, 2, 3])
def test_prompt_never_leaks_the_masked_ehr(agent_input, templates_dir: Path, task: int) -> None:
    """Reports and notes reach the agent only through MCP tool calls.

    If a future template change inlines them, the reveal_sequence stops
    reflecting what the agent actually read — and that field is scored.
    """
    cases = load_cases(agent_input[task], task=task, templates_dir=templates_dir)
    context = cases[0]["context"]

    assert "PI-RADS 4 lesion, left peripheral zone" not in context
    assert "Father diagnosed with prostate cancer" not in context
    assert "surveillance discussed" not in context


def test_prompt_carries_the_visible_clinical_panel(agent_input, templates_dir: Path) -> None:
    cases = load_cases(agent_input[1], task=1, templates_dir=templates_dir)
    context = cases[0]["context"]

    assert "12.4" in context, "headline PSA should reach the agent without a tool call"


def test_task_is_read_from_the_payload_not_the_argument(agent_input, templates_dir: Path) -> None:
    """``structured-prompt.json`` wins over the caller's default."""
    cases = load_cases(agent_input[2], task=1, templates_dir=templates_dir)

    assert cases[0]["task"] == 2


def test_missing_directory_fails_loudly(tmp_path: Path, templates_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_cases(tmp_path / "nope", task=1, templates_dir=templates_dir)


def test_directory_without_cases_fails_loudly(tmp_path: Path, templates_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_cases(tmp_path, task=1, templates_dir=templates_dir)


def test_malformed_json_fails_loudly(tmp_path: Path, templates_dir: Path) -> None:
    case = tmp_path / "PT-broken"
    case.mkdir()
    (case / "structured-prompt.json").write_text("{not json")

    with pytest.raises(ValueError):
        load_cases(tmp_path, task=1, templates_dir=templates_dir)


def test_render_accepts_a_custom_template(tmp_path: Path) -> None:
    """Participants swap the template rather than editing the baseline's."""
    (tmp_path / "mine.j2").write_text("case {{ case_id }} psa {{ psa }}")

    out = render_baseline_prompt({"case_id": "PT-1", "psa": 12.4}, tmp_path, "mine.j2")

    assert out == "case PT-1 psa 12.4"


def test_case_id_falls_back_to_nothing_when_absent(tmp_path: Path, templates_dir: Path) -> None:
    """The loader requires ``case_id``; a stub prompt must not pass silently.

    ``test/input/interf*/structured-prompt.json`` in this repo are placeholders
    (``{"key": "value"}``), so this is a real shape the loader can meet.
    """
    case = tmp_path / "interf0"
    case.mkdir()
    (case / "structured-prompt.json").write_text(json.dumps({"key": "value"}))

    with pytest.raises(KeyError):
        load_cases(tmp_path, task=1, templates_dir=templates_dir)
