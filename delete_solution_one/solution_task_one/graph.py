"""El grafo de la pizarra (LangGraph) para la tarea 1.

    START
      -> intake          (escribe el caso, tal cual llega del structured-prompt)
      -> expert_prior    (clasificador kNN: sugerencia A +/- dA)
      -> expert_protocol (criterio EAU aplicable al cubo clínico del paciente)
      -> l1_agent  <-> l1_tools     (sólo search_guidelines; RAG sobre la guía EAU)
      -> l1_post
      -> l2_agent  <-> l2_tools     (las herramientas clínicas MCP)
      -> l2_post
      -> expert_image    (FeatureStore + run_predictor)
      -> l3_chair        (decide, valida contra Task1Output y cierra la pizarra)
    END

Dos sub-bucles ReAct independientes, cada uno con su propia lista de mensajes
(``l1_messages`` / ``l2_messages``) y su propio presupuesto de rondas. Se
separan a propósito: L1 no debe poder abrir documentos clínicos —su mandato es
dudar, no recuperar— y L2 no debe heredar la conversación de L1, sólo su
conclusión escrita en la pizarra. Lo que viaja entre participantes es la
pizarra, no el historial.

Cuando un sub-bucle agota su presupuesto se pasa por ``*_finalize``, que pide
el informe **sin herramientas atadas**: así el turno siempre termina en texto y
nunca en una llamada a herramienta sin respuesta.
"""

from __future__ import annotations

import logging
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from chimera_agent_baseline.output.schema import (
    build_dynamic_model,
    eligible_variables,
    normalise_to_full_shape,
)

from . import prompts as prompts_v2
from .blackboard import Blackboard
from .decide import (
    called_tools_from_messages,
    extract_json_object,
    fallback_response,
    reveal_sequence_from_messages,
)
from .experts import image_predictor, initial_recommender, protocol

log = logging.getLogger(__name__)

GUIDELINE_TOOL = "search_guidelines"


class BoardState(TypedDict, total=False):
    """Estado del grafo. ``entries`` es la pizarra; lo demás es andamiaje."""

    case_id: str
    task: int
    prompt_payload: dict[str, Any]
    case_prompt: str

    entries: Annotated[list[dict], operator.add]

    l1_messages: Annotated[list, add_messages]
    l2_messages: Annotated[list, add_messages]
    l1_rounds: int
    l2_rounds: int
    l2_nudged: bool

    structured_response: dict[str, Any]
    reveal_sequence: list[str]
    warnings: Annotated[list[str], operator.add]


def _render(state: BoardState) -> str:
    board = Blackboard(state["case_id"], state.get("task", 1))
    board.entries = Blackboard.from_dict(
        {"case_id": state["case_id"], "task": state.get("task", 1), "entries": state.get("entries", [])}
    ).entries
    return board.render()


def _entry(speaker: str, role: str, title: str, body: str, data: dict | None = None) -> dict:
    return {"speaker": speaker, "role": role, "title": title, "body": body.strip(), "data": data or {}}


def _last_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None):
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


#: Matices que se añaden a la descripción de una herramienta antes de atarla al
#: investigador. La descripción es lo que el modelo lee para decidir si llama, y
#: ``tool_score`` del evaluador es precisión: decir cuándo NO usar una herramienta
#: vale tanto como decir cuándo sí. No se toca ``tools/definitions.py`` upstream:
#: se atan copias.
_DESCRIPTION_NOTES = {
    "get_lab_results": (
        " USE SPARINGLY: only when you have a specific question it answers - free-PSA fraction on "
        "a borderline PSA, infection or prostatitis as a confounder for a raised PSA, or fitness "
        "for an invasive procedure. Do not call it to re-confirm a PSA already shown in the panel."
    ),
    "get_family_history": (
        " DO NOT CALL for a biopsy decision: in this reading form the family-history anamnesis is "
        "not part of the biopsy work-up, and a first-degree history does not change whether this "
        "patient is sampled today."
    ),
    "get_mri_report": (
        " Highest-yield document in this decision: it carries the lesion size and zone and any "
        "comparison with a previous MRI, which is what distinguishes new disease from known disease."
    ),
}


def _retuned(tools: list[BaseTool]) -> list[BaseTool]:
    """Copias de las herramientas con la descripción matizada para el investigador."""
    out = []
    for tool in tools:
        note = _DESCRIPTION_NOTES.get(tool.name)
        out.append(tool.model_copy(update={"description": tool.description + note}) if note else tool)
    return out


def create_board_graph(
    tools: list[BaseTool],
    model: BaseChatModel,
    feature_store: Any = None,
    *,
    l1_max_rounds: int = 2,
    l2_max_rounds: int = 6,
    l3_max_retries: int = 3,
    step_timeout: int = 900,
    prompts: Any = None,
):
    """Compila el grafo de la pizarra.

    *tools* son las herramientas MCP de la tarea 1 (las cinco clínicas más
    ``search_guidelines``). *feature_store* puede ser ``None``: el experto de
    imagen lo declara y sigue.

    *prompts* permite fijar qué versión de los textos se usa (``prompts`` por
    defecto, ``prompts_v1`` para reproducir la corrida 1).
    """
    prompts = prompts or prompts_v2
    guideline_tools = [t for t in tools if t.name == GUIDELINE_TOOL]
    l1_model = model.bind_tools(guideline_tools) if guideline_tools else model
    l2_model = model.bind_tools(_retuned(tools))

    # -- 1. el caso ----------------------------------------------------------

    def intake(state: BoardState) -> dict[str, Any]:
        body = (
            "The structured clinical record below is the read-only panel the urologist sees up "
            "front, exactly as it arrives in this patient's record. The documents it refers to "
            "are masked and must be retrieved.\n\n"
            f"{state['case_prompt']}\n\n"
            "[Note for the conference: for a task-1 biopsy decision only FOUR masked documents "
            "actually exist on file - the radiology / mpMRI report, the PSA history, the previous "
            "notes and the laboratory panel - plus the family-history anamnesis. There is no "
            "pathology report to retrieve for this task; the prior-biopsy status shown in the "
            "panel above is all the pathology information on record.]"
        )
        return {
            "entries": [
                _entry(
                    "INTAKE",
                    "the patient record, verbatim; adds no interpretation",
                    "CASE FILE",
                    body,
                    {"case_id": state["case_id"]},
                )
            ]
        }

    # -- 2. el clasificador --------------------------------------------------

    def expert_prior(state: BoardState) -> dict[str, Any]:
        role, body, data = initial_recommender.render(state["prompt_payload"])
        return {"entries": [_entry("EXPERT-PRIOR", role, "INITIAL RECOMMENDATION (statistical prior)", body, data)]}

    # -- 2b. el criterio de protocolo ---------------------------------------

    def expert_protocol(state: BoardState) -> dict[str, Any]:
        role, body, data = protocol.render(state["prompt_payload"])
        return {
            "entries": [
                _entry("EXPERT-PROTOCOL", role, "GUIDELINE CRITERION FOR THIS SITUATION", body, data)
            ]
        }

    # -- 3. L1: el que duda --------------------------------------------------

    def l1_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("l1_messages") or []
        if not messages:
            messages = [
                SystemMessage(content=prompts.L1_SYSTEM),
                HumanMessage(content=prompts.l1_user(_render(state))),
            ]
            response = l1_model.invoke(messages)
            return {"l1_messages": [*messages, response]}
        return {"l1_messages": [l1_model.invoke(messages)]}

    def l1_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(
            content=(
                "Your guideline-search budget is spent. Write your contribution to the "
                "blackboard now, under your headings, with no further tool calls."
            )
        )
        messages = [*state["l1_messages"], nudge]
        return {"l1_messages": [nudge, model.invoke(messages)]}

    def l1_post(state: BoardState) -> dict[str, Any]:
        text = _last_text(state.get("l1_messages") or [])
        if not text.strip():
            text = "The gap analyst returned no readable contribution for this case."
        return {
            "entries": [
                _entry(
                    "LLM-1-GAP-ANALYST",
                    "raises doubt only; has no access to clinical documents and issues no recommendation",
                    "GAPS AND DOUBTS",
                    text,
                )
            ]
        }

    # -- 4. L2: el que recupera ---------------------------------------------

    def l2_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("l2_messages") or []
        if not messages:
            messages = [
                SystemMessage(content=prompts.L2_SYSTEM),
                HumanMessage(content=prompts.l2_user(_render(state))),
            ]
            response = l2_model.invoke(messages)
            return {"l2_messages": [*messages, response], "l2_rounds": 0}
        return {"l2_messages": [l2_model.invoke(messages)]}

    def l2_nudge(state: BoardState) -> dict[str, Any]:
        """L2 escribió el informe sin abrir nada. Se le exige recuperar antes de opinar.

        Es la única forma estructural de impedir el fallo más caro que se vio al
        probar la v2: el modelo redacta un ``RETRIEVED`` con documentos que nunca
        pidió. Se dispara como mucho una vez por caso.
        """
        nudge = HumanMessage(
            content=(
                "You wrote a report without opening a single document. That is a fabrication: "
                "everything under RETRIEVED must come from a tool result. Call the tools you "
                "need now - at minimum `get_mri_report` - and write nothing until they answer."
            )
        )
        messages = [*state["l2_messages"], nudge]
        return {"l2_messages": [nudge, l2_model.invoke(messages)], "l2_nudged": True}

    def l2_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(
            content=(
                "Your retrieval budget is spent. Write your evidence report now, under your four "
                "headings, using only what you actually retrieved. No further tool calls."
            )
        )
        messages = [*state["l2_messages"], nudge]
        return {"l2_messages": [nudge, model.invoke(messages)]}

    def l2_post(state: BoardState) -> dict[str, Any]:
        messages = state.get("l2_messages") or []
        text = _last_text(messages)
        revealed = reveal_sequence_from_messages(messages)
        called = sorted(called_tools_from_messages(messages))
        if not text.strip():
            text = "The evidence investigator returned no readable report for this case."
        if called:
            footer = (
                "\n\n[Sections actually revealed in this consultation: "
                f"{', '.join(revealed) if revealed else 'none'}. "
                f"Tools executed: {', '.join(called)}.]"
            )
        else:
            footer = (
                "\n\n[WARNING FOR THE CHAIR: NO DOCUMENT WAS OPENED FOR THIS CASE. No tool was "
                "executed, so nothing above under RETRIEVED came from the record. Treat this "
                "report as empty, decide on the visible panel and the guideline criterion alone, "
                "and set your confidence accordingly.]"
            )
        return {
            "entries": [
                _entry(
                    "LLM-2-EVIDENCE",
                    "the only participant who retrieved documents; reports findings, not verdicts",
                    "EVIDENCE REPORT",
                    text + footer,
                    {"revealed": revealed, "tools_called": called},
                )
            ],
            "reveal_sequence": revealed,
        }

    # -- 5. el predictor de imagen ------------------------------------------

    def expert_image(state: BoardState) -> dict[str, Any]:
        role, body, data = image_predictor.render(state["case_id"], feature_store)
        return {"entries": [_entry("EXPERT-IMAGE", role, "IMAGE-EMBEDDING PREDICTOR", body, data)]}

    # -- 6. L3: el que decide ------------------------------------------------

    def l3_chair(state: BoardState) -> dict[str, Any]:
        case_id = state["case_id"]
        messages = state.get("l2_messages") or []
        called = called_tools_from_messages(messages)
        revealed = state.get("reveal_sequence") or reveal_sequence_from_messages(messages)

        elig = eligible_variables(1, called)
        Dynamic = build_dynamic_model(1, called)  # noqa: N806 — clase dinámica
        parser = PydanticOutputParser(pydantic_object=Dynamic)

        prior_entry = next(
            (e for e in reversed(state.get("entries", [])) if e["speaker"] == "EXPERT-PRIOR"), None
        )
        prior_data = (prior_entry or {}).get("data") or {}
        proto_entry = next(
            (e for e in reversed(state.get("entries", [])) if e["speaker"] == "EXPERT-PROTOCOL"), None
        )
        proto_data = (proto_entry or {}).get("data") or {}
        base_user = prompts.l3_user(
            _render(state),
            case_id,
            elig,
            prompts.l3_skeleton(elig),
            state["prompt_payload"],
            prior_data,
            proto_data,
        )

        warnings: list[str] = []
        structured: dict[str, Any] | None = None
        retry_hint: str | None = None

        for attempt in range(1, l3_max_retries + 1):
            content = base_user if retry_hint is None else f"{base_user}\n\n{retry_hint}"
            try:
                response = model.invoke(
                    [SystemMessage(content=prompts.L3_SYSTEM), HumanMessage(content=content)]
                )
                raw = response.content if isinstance(response.content, str) else str(response.content)
                structured = parser.parse(extract_json_object(raw)).model_dump(mode="json")
                break
            except Exception as exc:  # noqa: BLE001 — cualquier fallo de parseo reintenta
                warnings.append(f"l3 attempt {attempt}: {type(exc).__name__}: {exc}")
                log.warning("L3 parse failed (attempt %d) for %s: %s", attempt, case_id, exc)
                if attempt < l3_max_retries:
                    retry_hint = prompts.l3_retry(str(exc))

        used_fallback = structured is None
        if used_fallback:
            structured = fallback_response(case_id, state["prompt_payload"], prior_data, revealed)
            warnings.append("l3: deterministic fallback used")

        structured["reveal_sequence"] = revealed
        full = normalise_to_full_shape(1, structured)

        verdict = "BIOPSY" if full["biopsy_decision"] else "NO BIOPSY"
        marks = ", ".join(f"{k}={v}" for k, v in full["variable_weights"].items() if v != "not_used")
        body = (
            f"FINAL DECISION: {verdict}   (confidence: {full['confidence']})\n\n"
            f"{full['reasoning']}\n\n"
            f"Variables that carried weight: {marks or 'none'}\n"
            f"Sections revealed: {', '.join(revealed) if revealed else 'none'}"
            + ("\n[completed by deterministic fallback]" if used_fallback else "")
        )
        return {
            "entries": [
                _entry(
                    "LLM-3-CHAIR",
                    "chairs the conference; the only participant who decides",
                    "FINAL DECISION AND FORM",
                    body,
                    full,
                )
            ],
            "structured_response": full,
            "reveal_sequence": revealed,
            "warnings": warnings,
        }

    # -- routers -------------------------------------------------------------

    def _has_tool_calls(messages: list) -> bool:
        return bool(messages) and bool(getattr(messages[-1], "tool_calls", None))

    def route_l1(state: BoardState) -> str:
        return "l1_tools" if _has_tool_calls(state.get("l1_messages") or []) else "l1_post"

    def route_l1_after_tools(state: BoardState) -> str:
        return "l1_finalize" if state.get("l1_rounds", 0) >= l1_max_rounds else "l1_agent"

    def route_l2(state: BoardState) -> str:
        messages = state.get("l2_messages") or []
        if _has_tool_calls(messages):
            return "l2_tools"
        if not called_tools_from_messages(messages) and not state.get("l2_nudged"):
            return "l2_nudge"
        return "l2_post"

    def route_l2_after_tools(state: BoardState) -> str:
        return "l2_finalize" if state.get("l2_rounds", 0) >= l2_max_rounds else "l2_agent"

    def count_l1(state: BoardState) -> dict[str, Any]:
        return {"l1_rounds": state.get("l1_rounds", 0) + 1}

    def count_l2(state: BoardState) -> dict[str, Any]:
        return {"l2_rounds": state.get("l2_rounds", 0) + 1}

    # -- montaje -------------------------------------------------------------

    builder = StateGraph(BoardState)
    builder.add_node("intake", intake)
    builder.add_node("expert_prior", expert_prior)
    builder.add_node("expert_protocol", expert_protocol)

    builder.add_node("l1_agent", l1_agent)
    builder.add_node("l1_tools", ToolNode(guideline_tools or tools, messages_key="l1_messages"))
    builder.add_node("l1_count", count_l1)
    builder.add_node("l1_finalize", l1_finalize)
    builder.add_node("l1_post", l1_post)

    builder.add_node("l2_agent", l2_agent)
    builder.add_node("l2_tools", ToolNode(tools, messages_key="l2_messages"))
    builder.add_node("l2_count", count_l2)
    builder.add_node("l2_nudge", l2_nudge)
    builder.add_node("l2_finalize", l2_finalize)
    builder.add_node("l2_post", l2_post)

    builder.add_node("expert_image", expert_image)
    builder.add_node("l3_chair", l3_chair)

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "expert_prior")
    builder.add_edge("expert_prior", "expert_protocol")
    builder.add_edge("expert_protocol", "l1_agent")

    builder.add_conditional_edges("l1_agent", route_l1, {"l1_tools": "l1_tools", "l1_post": "l1_post"})
    builder.add_edge("l1_tools", "l1_count")
    builder.add_conditional_edges(
        "l1_count", route_l1_after_tools, {"l1_agent": "l1_agent", "l1_finalize": "l1_finalize"}
    )
    builder.add_edge("l1_finalize", "l1_post")
    builder.add_edge("l1_post", "l2_agent")

    _l2_targets = {"l2_tools": "l2_tools", "l2_post": "l2_post", "l2_nudge": "l2_nudge"}
    builder.add_conditional_edges("l2_agent", route_l2, _l2_targets)
    builder.add_conditional_edges("l2_nudge", route_l2, _l2_targets)
    builder.add_edge("l2_tools", "l2_count")
    builder.add_conditional_edges(
        "l2_count", route_l2_after_tools, {"l2_agent": "l2_agent", "l2_finalize": "l2_finalize"}
    )
    builder.add_edge("l2_finalize", "l2_post")
    builder.add_edge("l2_post", "expert_image")

    builder.add_edge("expert_image", "l3_chair")
    builder.add_edge("l3_chair", END)

    graph = builder.compile()
    graph.step_timeout = step_timeout
    log.info(
        "Grafo de pizarra compilado: %d herramientas (%s), L1<=%d rondas, L2<=%d rondas",
        len(tools),
        ", ".join(t.name for t in tools),
        l1_max_rounds,
        l2_max_rounds,
    )
    return graph
