"""Parche reversible del grafo T2 para el brazo Lmin."""

from __future__ import annotations

import json
import inspect
from contextlib import contextmanager
from functools import wraps
from typing import Any, Iterator
from unittest.mock import patch

from langgraph.graph import StateGraph

from version_final_reto.task_2.agent import graph as graph_module
from version_final_reto.task_2.agent import protocol as P


def _say(state: dict[str, Any], speaker: str, body: str, data: dict | None = None) -> dict:
    return {
        "n": len(state.get("interventions", [])) + 1,
        "speaker": speaker,
        "body": body,
        "data": data or {},
        "pass_": state.get("pass_", 1),
    }


def _eau_stub(state: dict[str, Any]) -> dict[str, Any]:
    return {}


def _moderator_stub(state: dict[str, Any]) -> dict[str, Any]:
    questions = {
        section: f"What documented findings in {section} affect management?"
        for section in state.get("planned", [])
    }
    return {
        "document_questions": questions,
        "questions": [],
        "interventions": [
            _say(
                state,
                "MODERATOR",
                json.dumps(questions, sort_keys=True),
                {"deterministic": True, "questions": []},
            )
        ],
    }


def _registrar_stub(state: dict[str, Any]) -> dict[str, Any]:
    clinical = state.get("case_files", {}).get("clinical", {})
    documents = dict(state.get("documents") or {})
    for section in state.get("planned", []):
        if section in clinical and clinical[section] is not None:
            documents[section] = clinical[section]
    tools_called = [
        name for name, section in P.SECTION_BY_TOOL.items() if section in documents
    ]
    data = {
        "deterministic": True,
        "opened": list(documents),
        "source": "fixed internal plan over the case input socket",
    }
    return {
        "documents": documents,
        "revealed": list(documents),
        "tools_called": tools_called,
        "warnings": [],
        "interventions": [
            _say(state, "REGISTRAR", "Opened the fixed internal document plan.", data)
        ],
    }


def _verifier_stub(state: dict[str, Any]) -> dict[str, Any]:
    missing = [
        section
        for section in state.get("planned", [])
        if section not in state.get("documents", {})
    ]
    verdict = {
        "ready": not missing,
        "missing": missing,
        "reopened": False,
        "deterministic": True,
    }
    return {
        "verdict": verdict,
        "warnings": [],
        "interventions": [
            _say(state, "VERIFIER", "Actual missing: " + json.dumps(missing), verdict)
        ],
    }


def _replacement(name: str, action):
    return {
        "eau": _eau_stub,
        "moderator": _moderator_stub,
        "registrar": _registrar_stub,
        "verifier": _verifier_stub,
    }.get(name, action)


def _as_async(action):
    if inspect.iscoroutinefunction(action):
        return action

    @wraps(action)
    async def invoke(state):
        return action(state)

    return invoke


async def _direct_call(function, /, *args, **kwargs):
    """Equivalente secuencial de asyncio.to_thread para este grafo por caso."""
    return function(*args, **kwargs)


@contextmanager
def stable_t2_graph(*, reduced: bool) -> Iterator[None]:
    """Evita el executor bloqueado y, opcionalmente, reduce cuatro papeles LLM."""
    original_add_node = StateGraph.add_node

    def add_node(builder, name, action=None, *args, **kwargs):
        selected = _replacement(str(name), action) if reduced else action
        return original_add_node(
            builder, name, _as_async(selected), *args, **kwargs
        )

    with patch.object(StateGraph, "add_node", add_node), patch.object(
        graph_module.asyncio, "to_thread", _direct_call
    ):
        yield


@contextmanager
def reduced_t2_graph() -> Iterator[None]:
    with stable_t2_graph(reduced=True):
        yield
