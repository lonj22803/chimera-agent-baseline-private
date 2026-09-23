from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool

from Ablation_study.harness.graph_variants import (
    GRAPH_VARIANTS,
    apply_graph_variant,
)
from Ablation_study.harness.paths import DATA
from version_final_reto.common.roster import GUIDELINE_TOOL, SECTION_BY_TOOL
from version_final_reto.task_1.agent import graph as graph_module
from version_final_reto.task_1.experts_1.experience import ProfessionalExperience
from version_final_reto.task_1.experts_1.panel import CACHE, Panel


class _Mute(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "mute"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="{}"))])


def _fake_tools() -> list[StructuredTool]:
    def noop(query: str = "") -> str:
        """Herramienta muda para pruebas de recorrido."""
        return "{}"

    return [
        StructuredTool.from_function(
            noop,
            name=name,
            description=f"Fake {name} used by graph variant tests.",
        )
        for name in (*SECTION_BY_TOOL, GUIDELINE_TOOL)
    ]


def _compile():
    return graph_module.create_conference_graph(
        _fake_tools(),
        _Mute(),
        None,
        Panel(Path(CACHE)),
        ProfessionalExperience(DATA, exclude_self=True, k=3),
        mode="honest",
    )


def _topology(graph) -> tuple[tuple[str, ...], tuple[tuple[str, str, str], ...]]:
    drawable = graph.get_graph()
    nodes = tuple(sorted(drawable.nodes))
    edges = tuple(sorted((edge.source, edge.target, str(edge.data)) for edge in drawable.edges))
    return nodes, edges


def _case_state() -> dict:
    case_id = sorted(path.name for path in (DATA / "ground_truth").iterdir() if path.is_dir())[0]
    root = DATA / "agent_input" / case_id
    payload = json.loads((root / "structured-prompt.json").read_text())
    clinical = json.loads((root / "prostate-biopsy-decision-clinical-data.json").read_text())
    features_path = root / "prostate-modality-level-neural-representations.json"
    features = json.loads(features_path.read_text()) if features_path.exists() else {}
    return {
        "case_id": case_id,
        "task": 1,
        "prompt_payload": payload,
        "case_files": {"prompt": payload, "clinical": clinical, "features": features},
        "case_prompt": "Muted graph traversal test.",
    }


def test_a0_topology_is_identical_and_context_restores_the_v4() -> None:
    original_create = graph_module.create_conference_graph
    original_guard = graph_module.process_language
    expected = _topology(_compile())

    with apply_graph_variant(GRAPH_VARIANTS["A0"]):
        assert _topology(_compile()) == expected

    assert graph_module.create_conference_graph is original_create
    assert graph_module.process_language is original_guard
    assert _topology(_compile()) == expected


@pytest.mark.parametrize(
    "variant_id",
    ["A0", "N07-off", "N08-off", "N09-off", "N14-off", "N15-deterministic", "G1G2-off", "G3-off", "LLM-minimal"],
)
def test_each_variant_compiles_and_reaches_end_without_retired_speakers(variant_id: str) -> None:
    spec = GRAPH_VARIANTS[variant_id]
    with apply_graph_variant(spec):
        state = _compile().invoke(_case_state(), {"recursion_limit": 100})

    assert state["structured_response"]
    speakers = {item["speaker"] for item in state.get("interventions") or []}
    assert not (speakers & spec.removed_speakers)
    expected = {
        "INTAKE",
        "EXPERT-STRUCTURED",
        "EXPERT-COHORT",
        "EXPERT-EXPERIENCE",
        "EXPERT-TRACE",
        "EXPERT-EAU",
        "MODERATOR",
        "REGISTRAR",
        "EXPERT-PSA",
        "EXPERT-FUSION",
        "PANEL-PROTOCOL",
        "VERIFIER",
        "CHAIR",
    }
    assert expected - spec.removed_speakers <= speakers
    if spec.deterministic_chair:
        assert state["chair_audit"]["attempts"] == 0
        assert state["chair_audit"]["fallback_form"] is True
    if spec.disable_image:
        assert state.get("need_image") is False


def test_guard_globals_are_patched_only_inside_the_context() -> None:
    provenance = GRAPH_VARIANTS["G1G2-off"]
    process = GRAPH_VARIANTS["G3-off"]
    original_values = graph_module.unsourced_values
    original_process = graph_module.process_language

    with apply_graph_variant(provenance):
        assert graph_module.unsourced_values("x", "", "") == []
    with apply_graph_variant(process):
        assert graph_module.process_language("the expert said") == []

    assert graph_module.unsourced_values is original_values
    assert graph_module.process_language is original_process
