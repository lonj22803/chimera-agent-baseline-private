"""Parches reversibles de las variantes Tier L, sin editar la V4."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Iterator
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph

from version_final_reto.common import roster as R
from version_final_reto.task_1.agent import graph as graph_module


@dataclass(frozen=True)
class GraphVariantSpec:
    id: str
    remove_eau: bool = False
    remove_moderator: bool = False
    remove_verifier: bool = False
    disable_image: bool = False
    deterministic_chair: bool = False
    disable_provenance_guards: bool = False
    disable_process_guard: bool = False

    @property
    def removed_speakers(self) -> frozenset[str]:
        speakers = set()
        if self.remove_eau:
            speakers.add("EXPERT-EAU")
        if self.remove_moderator:
            speakers.add("MODERATOR")
        if self.remove_verifier:
            speakers.add("VERIFIER")
        if self.disable_image:
            speakers.add("EXPERT-IMAGE")
        return frozenset(speakers)


GRAPH_VARIANTS = {
    "A0": GraphVariantSpec("A0"),
    "N07-off": GraphVariantSpec("N07-off", remove_eau=True),
    "N08-off": GraphVariantSpec("N08-off", remove_moderator=True),
    "N09-off": GraphVariantSpec("N09-off", disable_image=True),
    "N14-off": GraphVariantSpec("N14-off", remove_verifier=True),
    "N15-deterministic": GraphVariantSpec("N15-deterministic", deterministic_chair=True),
    "G1G2-off": GraphVariantSpec("G1G2-off", disable_provenance_guards=True),
    "G3-off": GraphVariantSpec("G3-off", disable_process_guard=True),
    "LLM-minimal": GraphVariantSpec(
        "LLM-minimal",
        remove_eau=True,
        remove_moderator=True,
        remove_verifier=True,
    ),
}


def get_graph_variant(variant_id: str) -> GraphVariantSpec:
    try:
        return GRAPH_VARIANTS[variant_id]
    except KeyError as exc:
        raise ValueError(f"Variante de grafo desconocida: {variant_id}.") from exc


def _eau_agent_stub(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "eau_messages": {
            "__reset__": True,
            "messages": [AIMessage(content="{}")],
        },
        "eau_calls": 0,
        "eau_nudged": True,
    }


def _moderator_stub(state: dict[str, Any]) -> dict[str, Any]:
    already = set(state.get("revealed") or [])
    plan = []
    for section in state.get("planned") or []:
        tool = R.TOOL_BY_SECTION.get(section)
        if tool and section not in R.NEVER and section not in already:
            plan.append(
                {
                    "section": section,
                    "tool": tool,
                    "question": R.DEFAULT_QUESTION.get(
                        section, "what does it add beyond the visible panel?"
                    ),
                }
            )
    return {"plan": plan, "questions": [], "need_image": False}


def _verifier_agent_stub(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "ver_messages": {
            "__reset__": True,
            "messages": [AIMessage(content="{}")],
        },
        "ver_calls": 0,
    }


def _verifier_post_stub(state: dict[str, Any]) -> dict[str, Any]:
    revealed = list(state.get("revealed") or [])
    unopened = [section for section in state.get("planned") or [] if section not in revealed]
    return {
        "verdict": {
            "ready": True,
            "parsed": True,
            "suggest": None,
            "passes": state.get("pass_", 1),
            "reopened": False,
            "planned_unopened": unopened,
        }
    }


def _without_image(action):
    @wraps(action)
    def wrapped(state):
        result = dict(action(state) or {})
        result["need_image"] = False
        interventions = []
        for item in result.get("interventions") or []:
            updated = dict(item)
            data = dict(updated.get("data") or {})
            data["need_image"] = False
            updated["data"] = data
            interventions.append(updated)
        if interventions:
            result["interventions"] = interventions
        return result

    return wrapped


def _replacement(spec: GraphVariantSpec, name: str, action):
    if spec.remove_eau:
        if name == "eau_agent":
            return _eau_agent_stub
        if name == "eau_post":
            return lambda state: {}
    if spec.remove_moderator and name == "moderator":
        return _moderator_stub
    if spec.remove_verifier:
        if name == "verifier_agent":
            return _verifier_agent_stub
        if name == "verifier_post":
            return _verifier_post_stub
    if spec.disable_image:
        if name == "moderator":
            return _without_image(action)
        if name == "expert_image":
            return lambda state: {"need_image": False, "image_done": True}
    return action


@contextmanager
def apply_graph_variant(spec: GraphVariantSpec) -> Iterator[None]:
    """Aplica una variante durante compilacion y ejecucion, y restaura al salir."""
    original_add_node = StateGraph.add_node
    original_create = graph_module.create_conference_graph

    def add_node(builder, name, action=None, *args, **kwargs):
        return original_add_node(
            builder,
            name,
            _replacement(spec, str(name), action),
            *args,
            **kwargs,
        )

    def create_graph(*args, **kwargs):
        if spec.remove_verifier:
            kwargs["max_passes"] = 1
        if spec.deterministic_chair:
            kwargs["chair_max_retries"] = 0
        return original_create(*args, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(StateGraph, "add_node", add_node))
        stack.enter_context(patch.object(graph_module, "create_conference_graph", create_graph))

        # run_task1 importo el simbolo directamente; hay que parchear tambien
        # ese alias para que --arm use exactamente el mismo contexto.
        from version_final_reto.task_1.agent import run_task1

        stack.enter_context(patch.object(run_task1, "create_conference_graph", create_graph))
        if spec.disable_provenance_guards:
            stack.enter_context(patch.object(graph_module, "unsourced_values", lambda *a, **k: []))
            stack.enter_context(patch.object(graph_module, "unsourced_grades", lambda *a, **k: []))
            stack.enter_context(
                patch.object(graph_module, "drop_unsourced_grade_lines", lambda text, corpus: (text, []))
            )
        if spec.disable_process_guard:
            stack.enter_context(patch.object(graph_module, "process_language", lambda *a, **k: []))
        yield
