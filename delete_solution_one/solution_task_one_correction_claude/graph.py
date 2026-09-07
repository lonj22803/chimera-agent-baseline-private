"""Grafo de la pizarra con moderador y rondas (LangGraph).

    START
      -> intake            el structured-prompt renderizado con la plantilla upstream
      -> expert_prior      clasificador elegido por ablación: p(biopsia) +/- dp
      -> expert_protocol   criterio EAU del cubo clínico del paciente
      -> expert_image      FeatureStore + run_predictor sobre los embeddings
      -> moderator_open    fija la AGENDA: qué documento y qué pregunta
      -> l1_agent  <-> l1_tools   (search_guidelines; RAG sobre la guía EAU)
      -> l1_post
      -> l2_agent  <-> l2_tools   (las herramientas clínicas MCP; guardia anti-fabricación)
      -> l2_post
      -> moderator_close   ¿suficiente? ¿consenso?
           |-- reabrir --> l1_agent  (ronda + 1, mensajes reiniciados, revelaciones acumuladas)
           `-- cerrar  --> l3_chair  -> END

Diferencias de fondo con la primera generación
----------------------------------------------
1. **Rondas.** Los mensajes de L1 y L2 se reinician al reabrir para que cada
   ronda sea un turno limpio contra la pizarra actualizada, pero las
   revelaciones y las herramientas llamadas se **acumulan**: nadie vuelve a
   abrir lo que ya está abierto y ``reveal_sequence`` sigue siendo honesta.
2. **El moderador tiene la última palabra procedimental**, no clínica: decide
   si se puede decidir, no qué se decide.
3. **Los tres expertos deterministas hablan antes que ningún LLM**, para que la
   agenda se fije sobre evidencia y no sobre la primera impresión de un modelo.
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

from . import moderator as MOD
from . import prompts as prompts_default
from .blackboard import Blackboard
from .decide import (
    called_tools_from_messages,
    cites_retrieved_evidence,
    enforce_grounding,
    extract_json_object,
    fallback_response,
    reveal_sequence_from_messages,
)
from .experts import image_predictor, protocol
from .experts.classifier_expert import ClassifierExpert

log = logging.getLogger(__name__)

GUIDELINE_TOOL = "search_guidelines"


def _messages_reducer(old: list, new: Any) -> list:
    """``add_messages`` normal, más un reinicio explícito al abrir una ronda."""
    if isinstance(new, dict) and new.get("__reset__"):
        return list(new.get("messages") or [])
    return add_messages(old, new)


def _dedup(old: list, new: list) -> list:
    out = list(old or [])
    for x in new or []:
        if x not in out:
            out.append(x)
    return out


class BoardState(TypedDict, total=False):
    case_id: str
    task: int
    prompt_payload: dict[str, Any]
    case_files: dict[str, dict]
    case_prompt: str

    entries: Annotated[list[dict], operator.add]

    l1_messages: Annotated[list, _messages_reducer]
    l2_messages: Annotated[list, _messages_reducer]
    l1_rounds: int
    l2_rounds: int
    l2_nudged: bool

    round: int
    agenda: list[str]
    agenda_questions: dict[str, str]
    revealed: Annotated[list[str], _dedup]
    tools_called: Annotated[list[str], _dedup]
    consensus: dict[str, Any]

    structured_response: dict[str, Any]
    warnings: Annotated[list[str], operator.add]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _render(state: BoardState) -> str:
    board = Blackboard.from_dict(
        {"case_id": state["case_id"], "task": state.get("task", 1), "entries": state.get("entries", [])}
    )
    return board.render()


def _entry(speaker: str, role: str, title: str, body: str, data: dict | None = None,
           round_: int = 1) -> dict:
    return {"speaker": speaker, "role": role, "title": title, "body": body.strip(),
            "data": data or {}, "round": round_}


def _last_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None):
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


_DESCRIPTION_NOTES = {
    "get_lab_results": (
        " USE SPARINGLY: only when the moderator's agenda asks for it, or when you have a "
        "specific question it answers - free-PSA fraction on a borderline PSA, infection or "
        "prostatitis as a confounder, or fitness for an invasive procedure."
    ),
    "get_family_history": (
        " DO NOT CALL for a biopsy decision: in this reading form the family-history anamnesis "
        "is not part of the biopsy work-up and does not change whether this patient is sampled."
    ),
    "get_mri_report": (
        " Highest-yield document: lesion size and zone, and any comparison with a previous MRI, "
        "which is what distinguishes new disease from known disease."
    ),
}


def _retuned(tools: list[BaseTool]) -> list[BaseTool]:
    out = []
    for tool in tools:
        note = _DESCRIPTION_NOTES.get(tool.name)
        out.append(tool.model_copy(update={"description": tool.description + note}) if note else tool)
    return out


# ---------------------------------------------------------------------------
# el grafo
# ---------------------------------------------------------------------------


def create_board_graph(
    tools: list[BaseTool],
    model: BaseChatModel,
    feature_store: Any = None,
    classifier: ClassifierExpert | None = None,
    *,
    max_rounds: int = 2,
    l1_max_rounds: int = 2,
    l2_max_rounds: int = 6,
    l3_max_retries: int = 3,
    step_timeout: int = 900,
    prompts: Any = None,
):
    prompts = prompts or prompts_default
    guideline_tools = [t for t in tools if t.name == GUIDELINE_TOOL]
    l1_model = model.bind_tools(guideline_tools) if guideline_tools else model
    l2_model = model.bind_tools(_retuned(tools))

    # -- expertos deterministas ---------------------------------------------

    def intake(state: BoardState) -> dict[str, Any]:
        body = (
            "The structured clinical record below is the read-only panel the urologist sees up "
            "front, exactly as it arrives in this patient's record. The documents it refers to "
            "are masked and must be retrieved.\n\n"
            f"{state['case_prompt']}\n\n"
            "[Note for the conference: for a task-1 biopsy decision only FOUR masked documents "
            "exist on file - the radiology / mpMRI report, the PSA history, the previous notes "
            "and the laboratory panel - plus the family-history anamnesis. There is no pathology "
            "report to retrieve for this task; the prior-biopsy status in the panel above is all "
            "the pathology information on record.]"
        )
        return {"entries": [_entry("INTAKE", "the patient record, verbatim; adds no interpretation",
                                   "CASE FILE", body, {"case_id": state["case_id"]})],
                "round": 1}

    def expert_prior(state: BoardState) -> dict[str, Any]:
        if classifier is None:
            body = "No statistical classifier is deployed for this case."
            return {"entries": [_entry("EXPERT-PRIOR", "statistical expert", "STATISTICAL PRIOR", body)]}
        role, body, data = classifier.render(state["case_files"])
        return {"entries": [_entry("EXPERT-PRIOR", role, "STATISTICAL PRIOR (classifier)", body, data)]}

    def expert_protocol(state: BoardState) -> dict[str, Any]:
        role, body, data = protocol.render(state["prompt_payload"])
        return {"entries": [_entry("EXPERT-PROTOCOL", role, "GUIDELINE CRITERION FOR THIS SITUATION",
                                   body, data)]}

    def expert_image(state: BoardState) -> dict[str, Any]:
        role, body, data = image_predictor.render(state["case_id"], feature_store)
        return {"entries": [_entry("EXPERT-IMAGE", role, "IMAGE-EMBEDDING PREDICTOR", body, data)]}

    # -- moderador: apertura -------------------------------------------------

    def moderator_open(state: BoardState) -> dict[str, Any]:
        proto = next((e for e in reversed(state["entries"]) if e["speaker"] == "EXPERT-PROTOCOL"), None)
        proto_data = (proto or {}).get("data") or {}
        bucket = proto_data.get("bucket", "unknown")
        raw = ""
        try:
            resp = model.invoke([
                SystemMessage(content=prompts.MODERATOR_OPEN_SYSTEM),
                HumanMessage(content=prompts.moderator_open_user(_render(state), bucket)),
            ])
            raw = resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as exc:  # noqa: BLE001 — el moderador nunca bloquea un caso
            log.warning("moderator_open falló en %s: %s", state["case_id"], exc)

        obj = MOD.parse_json(raw)
        agenda = [d for d in (obj.get("agenda") or []) if d in MOD.DOCUMENTS]
        if not agenda:
            agenda = MOD.default_agenda(state["prompt_payload"], proto_data)
        questions = {k: str(v) for k, v in (obj.get("questions") or {}).items() if k in MOD.DOCUMENTS}
        agenda, pruned = MOD.prune_agenda(agenda, questions)
        if not agenda:
            agenda = MOD.default_agenda(state["prompt_payload"], proto_data)
        note = " ".join(x for x in (str(obj.get("note") or ""), pruned) if x)

        body = MOD.render_open(agenda, questions, note, 1)
        return {
            "entries": [_entry("MODERATOR", MOD.ROLE, "AGENDA (round 1)", body,
                               {"agenda": agenda, "questions": questions, "raw": obj})],
            "agenda": agenda,
            "agenda_questions": questions,
        }

    # -- L1 ------------------------------------------------------------------

    def l1_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("l1_messages") or []
        if not messages:
            messages = [SystemMessage(content=prompts.L1_SYSTEM),
                        HumanMessage(content=prompts.l1_user(_render(state)))]
            return {"l1_messages": {"__reset__": True, "messages": [*messages, l1_model.invoke(messages)]}}
        return {"l1_messages": [l1_model.invoke(messages)]}

    def l1_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=(
            "Your guideline-search budget is spent. Write your contribution to the blackboard "
            "now, under your headings, with no further tool calls."))
        return {"l1_messages": [nudge, model.invoke([*state["l1_messages"], nudge])]}

    def l1_post(state: BoardState) -> dict[str, Any]:
        text = _last_text(state.get("l1_messages") or []) or \
            "The gap analyst returned no readable contribution for this case."
        return {"entries": [_entry(
            "LLM-1-GAP-ANALYST",
            "raises doubt only; has no access to clinical documents and issues no recommendation",
            f"GAPS AND DOUBTS (round {state.get('round', 1)})", text, round_=state.get("round", 1))]}

    # -- L2 ------------------------------------------------------------------

    def l2_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("l2_messages") or []
        if not messages:
            messages = [SystemMessage(content=prompts.L2_SYSTEM),
                        HumanMessage(content=prompts.l2_user(_render(state)))]
            return {"l2_messages": {"__reset__": True, "messages": [*messages, l2_model.invoke(messages)]},
                    "l2_rounds": 0}
        return {"l2_messages": [l2_model.invoke(messages)]}

    def l2_nudge(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=(
            "You wrote a report without opening a single document. That is a fabrication: "
            "everything under RETRIEVED must come from a tool result. Call the tools the "
            "moderator's agenda names - at minimum `get_mri_report` - and write nothing until "
            "they answer."))
        return {"l2_messages": [nudge, l2_model.invoke([*state["l2_messages"], nudge])],
                "l2_nudged": True}

    def l2_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=(
            "Your retrieval budget is spent. Write your evidence report now, under your four "
            "headings, using only what you actually retrieved. No further tool calls."))
        return {"l2_messages": [nudge, model.invoke([*state["l2_messages"], nudge])]}

    def l2_post(state: BoardState) -> dict[str, Any]:
        messages = state.get("l2_messages") or []
        text = _last_text(messages) or "The evidence investigator returned no readable report."
        new_revealed = reveal_sequence_from_messages(messages)
        new_called = sorted(called_tools_from_messages(messages))
        all_revealed = _dedup(state.get("revealed") or [], new_revealed)
        if new_called:
            footer = (f"\n\n[Opened in this round: {', '.join(new_revealed) if new_revealed else 'none'}. "
                      f"Open on the board so far: {', '.join(all_revealed) if all_revealed else 'none'}.]")
        else:
            footer = ("\n\n[WARNING FOR THE CHAIR: NO DOCUMENT WAS OPENED IN THIS ROUND. Nothing "
                      "above under RETRIEVED came from the record in this round.]")
        return {
            "entries": [_entry("LLM-2-EVIDENCE",
                               "the only participant who retrieved documents; reports findings, not verdicts",
                               f"EVIDENCE REPORT (round {state.get('round', 1)})", text + footer,
                               {"revealed": new_revealed, "tools_called": new_called},
                               round_=state.get("round", 1))],
            "revealed": new_revealed,
            "tools_called": new_called,
        }

    # -- moderador: cierre ---------------------------------------------------

    def moderator_close(state: BoardState) -> dict[str, Any]:
        round_ = state.get("round", 1)
        status = MOD.agenda_status(state.get("agenda") or [], state.get("revealed") or [])
        votes = MOD.stances(state.get("entries", []))
        cons = MOD.consensus(votes)

        raw = ""
        try:
            resp = model.invoke([
                SystemMessage(content=prompts.MODERATOR_CLOSE_SYSTEM),
                HumanMessage(content=prompts.moderator_close_user(
                    _render(state), status, votes, round_, max_rounds)),
            ])
            raw = resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as exc:  # noqa: BLE001
            log.warning("moderator_close falló en %s: %s", state["case_id"], exc)
        obj = MOD.parse_json(raw)

        # Regla de reapertura: DETERMINISTA. Se reabre si queda ronda y o bien la
        # agenda no se cumplió, o bien las posturas siguen divididas.
        #
        # El LLM no tiene voto aquí, y no es un descuido: medido sobre la primera
        # tanda de casos, este modelo respondió `genuine_disagreement: false` y
        # `reopen: false` en el 100 % de ellos, incluidos aquellos en los que dos
        # participantes decían cosas opuestas. Es el fallo que documentan Huang
        # et al. (ICLR 2024): un LLM no juzga con fiabilidad si su propio
        # expediente necesita más trabajo. Lo que sí aporta —qué falta y por qué—
        # se conserva y se le pasa a la siguiente ronda.
        can_reopen = round_ < max_rounds
        reopen = bool(can_reopen and ((not status["fulfilled"]) or (not cons["reached"])))

        note = str(obj.get("note") or "")
        body = MOD.render_close(status, cons, reopen, note, round_, max_rounds)
        consensus_state = {**cons, "rounds": round_, "status": status,
                           "llm": obj, "reopened": reopen}
        return {
            "entries": [_entry("MODERATOR", MOD.ROLE,
                               f"CLOSING CHECK (round {round_})", body, consensus_state,
                               round_=round_)],
            "consensus": consensus_state,
            "round": round_ + 1 if reopen else round_,
            **({"l1_messages": {"__reset__": True, "messages": []},
                "l2_messages": {"__reset__": True, "messages": []},
                "l1_rounds": 0, "l2_rounds": 0, "l2_nudged": False} if reopen else {}),
        }

    # -- L3 ------------------------------------------------------------------

    def l3_chair(state: BoardState) -> dict[str, Any]:
        case_id = state["case_id"]
        called = set(state.get("tools_called") or [])
        revealed = list(state.get("revealed") or [])

        elig = eligible_variables(1, called)
        Dynamic = build_dynamic_model(1, called)  # noqa: N806
        parser = PydanticOutputParser(pydantic_object=Dynamic)

        prior_entry = next((e for e in reversed(state["entries"]) if e["speaker"] == "EXPERT-PRIOR"), None)
        proto_entry = next((e for e in reversed(state["entries"]) if e["speaker"] == "EXPERT-PROTOCOL"), None)
        prior_data = (prior_entry or {}).get("data") or {}
        proto_data = (proto_entry or {}).get("data") or {}

        base_user = prompts.l3_user(_render(state), case_id, elig, prompts.l3_skeleton(elig),
                                    state["prompt_payload"], prior_data, proto_data,
                                    state.get("consensus"))

        warnings: list[str] = []
        structured: dict[str, Any] | None = None
        retry_hint: str | None = None
        for attempt in range(1, l3_max_retries + 1):
            content = base_user if retry_hint is None else f"{base_user}\n\n{retry_hint}"
            try:
                resp = model.invoke([SystemMessage(content=prompts.L3_SYSTEM),
                                     HumanMessage(content=content)])
                raw = resp.content if isinstance(resp.content, str) else str(resp.content)
                structured = parser.parse(extract_json_object(raw)).model_dump(mode="json")
                break
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"l3 attempt {attempt}: {type(exc).__name__}: {exc}")
                log.warning("L3 parse failed (%d) for %s: %s", attempt, case_id, exc)
                if attempt < l3_max_retries:
                    retry_hint = prompts.l3_retry(str(exc))

        # -- reto: ¿anuló a un experto con historial sin citar nada recuperado? --
        if structured is not None and proto_data.get("verdict") is None \
                and prior_data.get("veredicto_operativo") in ("firm", "supports") \
                and prior_data.get("prediccion") in ("yes", "no"):
            chair_says = "yes" if structured.get("biopsy_decision") else "no"
            bodies = {e["speaker"]: e["body"] for e in state.get("entries", [])}
            grounded = cites_retrieved_evidence(structured.get("reasoning", ""),
                                                bodies.get("INTAKE", ""),
                                                bodies.get("LLM-2-EVIDENCE", ""))
            if chair_says != prior_data["prediccion"] and not grounded:
                warnings.append("l3: challenged (overrode a tracked expert without citing retrieval)")
                try:
                    resp = model.invoke([
                        SystemMessage(content=prompts.L3_SYSTEM),
                        HumanMessage(content=f"{base_user}\n\n{prompts.l3_challenge(prior_data)}"),
                    ])
                    raw = resp.content if isinstance(resp.content, str) else str(resp.content)
                    structured = parser.parse(extract_json_object(raw)).model_dump(mode="json")
                except Exception as exc:  # noqa: BLE001 — si el reto falla, vale la respuesta previa
                    warnings.append(f"l3 challenge failed: {type(exc).__name__}: {exc}")

        used_fallback = structured is None
        if used_fallback:
            structured = fallback_response(case_id, state["prompt_payload"], prior_data, revealed)
            warnings.append("l3: deterministic fallback used")

        structured["reveal_sequence"] = revealed
        full = normalise_to_full_shape(1, structured)
        full, downgraded = enforce_grounding(full, revealed)
        if downgraded:
            warnings.append(f"grounding guard: {', '.join(downgraded)} -> not_used (section not opened)")

        verdict = "BIOPSY" if full["biopsy_decision"] else "NO BIOPSY"
        marks = ", ".join(f"{k}={v}" for k, v in full["variable_weights"].items() if v != "not_used")
        body = (f"FINAL DECISION: {verdict}   (confidence: {full['confidence']})\n\n"
                f"{full['reasoning']}\n\n"
                f"Variables that carried weight: {marks or 'none'}\n"
                f"Sections revealed: {', '.join(revealed) if revealed else 'none'}"
                + ("\n[completed by deterministic fallback]" if used_fallback else ""))
        return {
            "entries": [_entry("LLM-3-CHAIR", "chairs the conference; the only participant who decides",
                               "FINAL DECISION AND FORM", body, full, round_=state.get("round", 1))],
            "structured_response": full,
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
        if not called_tools_from_messages(messages) and not state.get("l2_nudged") \
                and not (state.get("revealed") or []):
            return "l2_nudge"
        return "l2_post"

    def route_l2_after_tools(state: BoardState) -> str:
        return "l2_finalize" if state.get("l2_rounds", 0) >= l2_max_rounds else "l2_agent"

    def route_close(state: BoardState) -> str:
        return "l1_agent" if (state.get("consensus") or {}).get("reopened") else "l3_chair"

    def count_l1(state: BoardState) -> dict[str, Any]:
        return {"l1_rounds": state.get("l1_rounds", 0) + 1}

    def count_l2(state: BoardState) -> dict[str, Any]:
        return {"l2_rounds": state.get("l2_rounds", 0) + 1}

    # -- montaje -------------------------------------------------------------

    b = StateGraph(BoardState)
    for name, fn in (("intake", intake), ("expert_prior", expert_prior),
                     ("expert_protocol", expert_protocol), ("expert_image", expert_image),
                     ("moderator_open", moderator_open),
                     ("l1_agent", l1_agent), ("l1_count", count_l1), ("l1_finalize", l1_finalize),
                     ("l1_post", l1_post),
                     ("l2_agent", l2_agent), ("l2_count", count_l2), ("l2_nudge", l2_nudge),
                     ("l2_finalize", l2_finalize), ("l2_post", l2_post),
                     ("moderator_close", moderator_close), ("l3_chair", l3_chair)):
        b.add_node(name, fn)
    b.add_node("l1_tools", ToolNode(guideline_tools or tools, messages_key="l1_messages"))
    b.add_node("l2_tools", ToolNode(tools, messages_key="l2_messages"))

    b.add_edge(START, "intake")
    b.add_edge("intake", "expert_prior")
    b.add_edge("expert_prior", "expert_protocol")
    b.add_edge("expert_protocol", "expert_image")
    b.add_edge("expert_image", "moderator_open")
    b.add_edge("moderator_open", "l1_agent")

    b.add_conditional_edges("l1_agent", route_l1, {"l1_tools": "l1_tools", "l1_post": "l1_post"})
    b.add_edge("l1_tools", "l1_count")
    b.add_conditional_edges("l1_count", route_l1_after_tools,
                            {"l1_agent": "l1_agent", "l1_finalize": "l1_finalize"})
    b.add_edge("l1_finalize", "l1_post")
    b.add_edge("l1_post", "l2_agent")

    _l2 = {"l2_tools": "l2_tools", "l2_post": "l2_post", "l2_nudge": "l2_nudge"}
    b.add_conditional_edges("l2_agent", route_l2, _l2)
    b.add_conditional_edges("l2_nudge", route_l2, _l2)
    b.add_edge("l2_tools", "l2_count")
    b.add_conditional_edges("l2_count", route_l2_after_tools,
                            {"l2_agent": "l2_agent", "l2_finalize": "l2_finalize"})
    b.add_edge("l2_finalize", "l2_post")
    b.add_edge("l2_post", "moderator_close")

    b.add_conditional_edges("moderator_close", route_close,
                            {"l1_agent": "l1_agent", "l3_chair": "l3_chair"})
    b.add_edge("l3_chair", END)

    graph = b.compile()
    graph.step_timeout = step_timeout
    log.info("Grafo con moderador compilado: %d herramientas, max_rounds=%d", len(tools), max_rounds)
    return graph
