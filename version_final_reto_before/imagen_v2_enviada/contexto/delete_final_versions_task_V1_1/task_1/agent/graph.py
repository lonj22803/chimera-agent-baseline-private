"""El grafo de la junta: quince intervenciones, cuatro expertos entrenados.

    ESTADO 0   pizarra en blanco
      |
      +-- INTAKE ................... 1, 2      el expediente, crudo y renderizado
      +-- EXPERT-STRUCTURED ........ 3         Experto 1 (panel)               -> ESTADO 1
      +-- EXPERT-COHORT ............ 4         criterio por cubo
      +-- EXPERT-EXPERIENCE ........... 5         precedentes etiquetados
      +-- EXPERT-TRACE ............. 6         que abre y que pesa el urologo  -> fija el plan
      |
      +-- EXPERT-EAU <-> search_guidelines 7                                   -> ESTADO 2
      +-- MODERATOR ................ 8         preguntas; una por documento    -> ESTADO 3
      +-- EXPERT-IMAGE (si lo pide)  9
      +-- REGISTRAR <-> herramientas 10        abre exactamente el plan        -> ESTADO 4
      |
      +-- EXPERT-PSA ............... 11        Experto 2, sobre la serie abierta
      +-- EXPERT-FUSION ............ 12        Experto 3, sobre los documentos abiertos
      +-- PANEL-PROTOCOL ........... 13        la cascada, con la regla escrita -> ESTADO 5
      |
      +-- VERIFIER <-> search_guidelines 14                                    -> ESTADO 6
      |     |-- no listo y queda un documento DEL PLAN sin abrir --> MODERATOR (pase 2)
      |     `-- listo -------------------------------------------> CHAIR
      |
      +-- CHAIR .................... 15        la nota clinica y el formulario -> ESTADO 7

Lo que decide el codigo y no un modelo, y por que
-------------------------------------------------
1. **Que documentos se abren**: EXPERT-TRACE. El ``tool_score`` es precision
   contra lo que abrio el urologo, y un modelo entrenado sobre sus 91 trazas lo
   predice mejor que un moderador. Nada fuera del plan se abre nunca.
2. **La decision**: PANEL-PROTOCOL, una cascada por acierto medido. Los votos
   del LLM estan en el azar en el cubo dificil (registrador 0.47, verificador
   0.49), asi que no votan: aportan lo que RECUPERAN, que si decide.
3. **La confianza y los pesos**: EXPERT-TRACE, con la guardia de aterrizaje.
4. **El grado documentado**: leido con expresion regular del texto crudo de la
   herramienta, no del resumen del registrador.
5. **Que la nota clinica no describa el procedimiento**: el presidente no ve el
   acta —ve un parte clinico sin locutores— y ademas se le comprueba.
"""

from __future__ import annotations

import json
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

from . import prompts as prompts_default
from . import protocol as protocol_mod
from delete_final_versions_task_V1_1.common import deadline
from delete_final_versions_task_V1_1.common import roster as R
from delete_final_versions_task_V1_1.common import sampling
from delete_final_versions_task_V1_1.common.board import Board
from .decide import (
    called_tools_from_messages,
    clinical_note,
    documented_grade,
    drop_unsourced_grade_lines,
    enforce_grounding,
    extract_json_object,
    parse_json,
    process_language,
    registrar_lean,
    reveal_sequence_from_messages,
    tool_corpus,
    unsourced_grades,
    unsourced_values,
    validate_output,
    verifier_line,
)
from delete_final_versions_task_V1_1.task_1.experts_1 import cohort as cohort_expert
from delete_final_versions_task_V1_1.task_1.experts_1 import fusion as fusion_expert
from delete_final_versions_task_V1_1.task_1.experts_1 import image as image_expert
from delete_final_versions_task_V1_1.task_1.experts_1 import experience as library_expert
from delete_final_versions_task_V1_1.task_1.experts_1 import psa as psa_expert
from delete_final_versions_task_V1_1.task_1.experts_1 import structured as structured_expert
from delete_final_versions_task_V1_1.task_1.experts_1 import trace as trace_expert

log = logging.getLogger(__name__)


def _messages_reducer(old: list, new: Any) -> list:
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

    interventions: Annotated[list[dict], operator.add]

    eau_messages: Annotated[list, _messages_reducer]
    reg_messages: Annotated[list, _messages_reducer]
    ver_messages: Annotated[list, _messages_reducer]
    eau_calls: int
    reg_calls: int
    ver_calls: int
    eau_nudged: bool
    reg_nudged: bool

    pass_: int
    planned: list[str]
    plan: list[dict]
    questions: list[str]
    need_image: bool
    image_done: bool
    still_missing: list[str]

    revealed: Annotated[list[str], _dedup]
    tools_called: Annotated[list[str], _dedup]
    corpus: Annotated[list[str], operator.add]
    verdict: dict[str, Any]

    library: dict[str, Any]
    trace: dict[str, Any]
    protocol: dict[str, Any]
    grade: dict[str, Any]

    structured_response: dict[str, Any]
    chair_audit: dict[str, Any]
    warnings: Annotated[list[str], operator.add]


def _board(state: BoardState) -> Board:
    return Board.from_dicts(state["case_id"], state.get("task", 1), state.get("interventions", []))


def _render(state: BoardState) -> str:
    return _board(state).render()


def _say(state: BoardState, speaker: str, body: str, data: dict | None = None, offset: int = 0) -> dict:
    return {"n": len(state.get("interventions") or []) + 1 + offset, "speaker": speaker,
            "body": body.strip(), "data": data or {}, "pass_": state.get("pass_", 1)}


def _last_text(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None):
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


def _data_of(state: BoardState, speaker: str) -> dict:
    for item in reversed(state.get("interventions", [])):
        if item["speaker"] == speaker:
            return item.get("data") or {}
    return {}


def _body_of(state: BoardState, speaker: str) -> str:
    return "\n\n".join(i["body"] for i in state.get("interventions", []) if i["speaker"] == speaker)


def _section_of(text: str, heading: str, stop: tuple[str, ...]) -> str:
    """Recorta un apartado del turno de un participante, por su cabecera."""
    lines, out, on = (text or "").splitlines(), [], False
    for line in lines:
        head = line.strip().upper()
        if head.startswith(heading):
            on = True
            continue
        if on and any(head.startswith(s) for s in stop):
            break
        if on:
            out.append(line)
    return "\n".join(out).strip()


def create_conference_graph(
    tools: list[BaseTool],
    model: BaseChatModel,
    feature_store: Any = None,
    panel: Any = None,
    library: Any = None,
    *,
    mode: str = "deployed",
    protocol_params: dict | None = None,
    weights_policy: str = "model+mode",
    max_passes: int = 2,
    eau_max_calls: int = 2,
    reg_max_calls: int = 6,
    ver_max_calls: int = 1,
    chair_max_retries: int = 3,
    step_timeout: int = 900,
    temperature: float | None = None,
    token_scale: float = 1.0,
    prompts: Any = None,
):
    prompts = prompts or prompts_default
    roster = R.Roster(tools)

    voice = sampling.voices(temperature, token_scale)
    m_eau = sampling.speak_as(model, voice["eau"])
    m_mod = sampling.speak_as(model, voice["moderator"])
    m_reg = sampling.speak_as(model, voice["registrar"])
    m_ver = sampling.speak_as(model, voice["verifier"])
    m_chair = sampling.speak_as(model, voice["chair"])

    guideline_tools = roster.guideline_tools()
    registrar_tools = roster.document_tools() + guideline_tools
    eau_model = m_eau.bind_tools(guideline_tools) if guideline_tools else m_eau
    reg_model = m_reg.bind_tools(registrar_tools) if registrar_tools else m_reg
    ver_model = m_ver.bind_tools(guideline_tools) if guideline_tools else m_ver
    moderator_system = prompts.moderator_system(roster.catalogue())

    # -- ESTADO 1: expediente y expertos del panel ---------------------------

    def intake(state: BoardState) -> dict[str, Any]:
        raw = json.dumps(state["prompt_payload"], indent=2, ensure_ascii=False)
        one = ("Colleagues, this is the record as it arrived, field by field. I read it out and interpret "
               f"nothing; everything after this is yours.\n\n{raw}")
        openable = ", ".join(s for s in roster.sections if s not in R.NEVER)
        two = ("And this is the same record as the reading form presents it — the panel the urologist sees "
               f"up front, with the masked documents named but not shown.\n\n{state['case_prompt']}\n\n"
               "One correction to that last paragraph before anybody acts on it: the documents this task "
               f"actually serves are {openable}, plus the family-history anamnesis. There is NO pathology "
               "report to pull up in a task-1 biopsy decision — the prior-biopsy status on the panel above "
               "is all the pathology on record, and whatever the previous notes say about it. Nobody should "
               "ask for one, and nobody should quote one.")
        return {"interventions": [
            _say(state, "INTAKE", one, {"gist": "record read out, field by field", "raw": True}),
            _say(state, "INTAKE", two, {"gist": "record as the reading form presents it"}, offset=1)],
            "pass_": 1}

    def expert_structured(state: BoardState) -> dict[str, Any]:
        # Un caso que no esta en el cache (todo caso del test real) se puntua
        # aqui en vivo, una sola vez, antes de que hable el primer experto.
        if panel is not None and not panel.has(state["case_id"]):
            try:
                panel.ensure(state["case_id"], state.get("case_files") or {})
            except Exception as exc:  # noqa: BLE001 — la junta corre igual sin los expertos
                log.exception("No se pudo puntuar en vivo %s: %s", state["case_id"], exc)
        body, data = structured_expert.render(panel, state["case_id"], mode, state["prompt_payload"])
        return {"interventions": [_say(state, "EXPERT-STRUCTURED", body, data)]}

    def expert_cohort(state: BoardState) -> dict[str, Any]:
        body, data = cohort_expert.render(state["prompt_payload"])
        return {"interventions": [_say(state, "EXPERT-COHORT", body, data)]}

    def expert_library(state: BoardState) -> dict[str, Any]:
        if library is None:
            return {"interventions": [_say(state, "EXPERT-EXPERIENCE",
                                           "No case library is loaded for this session; no precedent to offer.",
                                           {"available": False, "gist": "no library"})], "library": {}}
        result = library.recall(state["case_id"], state["prompt_payload"])
        body, data = library_expert.render(result, state["prompt_payload"])
        return {"interventions": [_say(state, "EXPERT-EXPERIENCE", body, data)], "library": result}

    def expert_trace(state: BoardState) -> dict[str, Any]:
        payload = state["prompt_payload"]
        bx = str(payload.get("bx") or "None")
        bucket_mode = library.bucket_mode(bx, exclude=state["case_id"] if library.exclude_self else None) \
            if library is not None else None
        trace = trace_expert.predict(panel, state["case_id"], mode, state.get("library"), bucket_mode,
                                     weights_policy=weights_policy)
        body, data = trace_expert.render(trace, bx, (bucket_mode or {}).get("n", 0), payload)
        planned = [s for s in trace["reveal_sequence"] if roster.tool_for(s) and s not in R.NEVER]
        return {"interventions": [_say(state, "EXPERT-TRACE", body, data)], "trace": trace, "planned": planned}

    # -- ESTADO 2: la guia ---------------------------------------------------

    def eau_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("eau_messages") or []
        if not messages:
            messages = [SystemMessage(content=prompts.EAU_SYSTEM),
                        HumanMessage(content=prompts.eau_user(_render(state)))]
            return {"eau_messages": {"__reset__": True, "messages": [*messages, eau_model.invoke(messages)]},
                    "eau_calls": 0}
        return {"eau_messages": [eau_model.invoke(messages)]}

    def eau_nudge(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=prompts.EAU_NUDGE)
        return {"eau_messages": [nudge, eau_model.invoke([*state["eau_messages"], nudge])], "eau_nudged": True}

    def eau_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=prompts.EAU_FINALIZE)
        return {"eau_messages": [nudge, m_eau.invoke([*state["eau_messages"], nudge])]}

    def eau_post(state: BoardState) -> dict[str, Any]:
        messages = state.get("eau_messages") or []
        text = _last_text(messages) or "I have nothing usable from the guideline for this case."
        searched = "search_guidelines" in called_tools_from_messages(messages)
        if not searched:
            text += ("\n\n[EXPERT-EAU retrieved nothing from the guideline in this turn, so nothing above is "
                     "attributable to it.]")
        gist = "guideline reading" + ("" if searched else " (no retrieval — treat as unsupported)")
        return {"interventions": [_say(state, "EXPERT-EAU", text, {"gist": gist, "searched": searched})]}

    # -- ESTADO 3: moderador ------------------------------------------------

    def moderator(state: BoardState) -> dict[str, Any]:
        pass_ = state.get("pass_", 1)
        already = list(state.get("revealed") or [])
        planned = list(state.get("planned") or [])
        raw = ""
        try:
            resp = m_mod.invoke([SystemMessage(content=moderator_system),
                                 HumanMessage(content=prompts.moderator_user(
                                     _render(state), pass_, planned, already, state.get("still_missing")))])
            raw = resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as exc:  # noqa: BLE001
            log.warning("El moderador fallo en %s: %s", state["case_id"], exc)
        obj = parse_json(raw)
        qs_by_section = R.moderator_questions_by_section(obj.get("plan") or [])
        for section, question in (obj.get("document_questions") or {}).items():
            if isinstance(section, str) and isinstance(question, str):
                qs_by_section.setdefault(section.strip(), " ".join(question.split()))
        plan = R.plan_from_sections(planned, roster, already, qs_by_section)
        notes: list[str] = []
        asked = {str(s) for s in ((obj.get("document_questions") or {}).keys())}
        extra = sorted(s for s in asked if s and s not in planned and s in R.SECTION_BY_TOOL.values())
        if extra:
            notes.append(f"The moderator asked for {', '.join(extra)}, which the reading urologist does not "
                         "open in this situation; dropped — every reveal beyond his is scored against us.")
        questions, dropped_q = [], []
        for q in (obj.get("questions") or []):
            q = " ".join(str(q).split())
            if q:
                (dropped_q if R.drops_panel_question(q) else questions).append(q)
        questions = questions[:4]
        if dropped_q:
            notes.append(f"Dropped {len(dropped_q)} question(s) that asked for a value already printed on the "
                         f"panel: \"{dropped_q[0]}\".")
        need_image = bool(obj.get("need_image")) and not state.get("image_done")
        opening = " ".join(str(obj.get("to_colleagues") or "").split())
        rendered = R.render_plan(plan, questions, notes, need_image, pass_, "EXPERT-TRACE")
        body = f"{opening}\n\n{rendered}".strip() if opening else rendered
        return {"interventions": [_say(state, "MODERATOR", body,
                                       {"plan": plan, "questions": questions, "need_image": need_image,
                                        "gist": "plan: " + (", ".join(p["section"] for p in plan) or "nothing")
                                                + f"; {len(questions)} open question(s)"})],
                "plan": plan, "questions": questions, "need_image": need_image}

    # -- ESTADO 4: imagen y registrador -------------------------------------

    def expert_image(state: BoardState) -> dict[str, Any]:
        body, data = image_expert.render(state["case_id"], feature_store)
        return {"interventions": [_say(state, "EXPERT-IMAGE", body, data)], "image_done": True}

    def _registrar_model(state: BoardState):
        """Con el plan vacio el registrador no tiene herramientas de documento.

        Medido en la corrida completa anterior: en los 2 casos en que el urologo
        lector no abrio nada, el plan quedo vacio, el prompt decia "make no tool
        calls" y el modelo abrio tres o cuatro documentos igualmente — los unicos
        dos casos con `tool_score` < 1. Impedirlo desenlazando las herramientas
        es mas fiable que pedirlo por favor.
        """
        if state.get("plan"):
            return reg_model
        return m_reg.bind_tools(guideline_tools) if guideline_tools else m_reg

    def registrar_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("reg_messages") or []
        model_ = _registrar_model(state)
        if not messages:
            messages = [SystemMessage(content=prompts.REGISTRAR_SYSTEM),
                        HumanMessage(content=prompts.registrar_user(_render(state), state.get("plan") or [],
                                                                    state.get("pass_", 1)))]
            return {"reg_messages": {"__reset__": True, "messages": [*messages, model_.invoke(messages)]},
                    "reg_calls": 0}
        return {"reg_messages": [model_.invoke(messages)]}

    def registrar_nudge(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=prompts.REGISTRAR_NUDGE)
        return {"reg_messages": [nudge, _registrar_model(state).invoke([*state["reg_messages"], nudge])],
                "reg_nudged": True}

    def registrar_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=prompts.REGISTRAR_FINALIZE)
        return {"reg_messages": [nudge, m_reg.invoke([*state["reg_messages"], nudge])]}

    def registrar_post(state: BoardState) -> dict[str, Any]:
        messages = state.get("reg_messages") or []
        text = _last_text(messages) or "I could not produce a readable report from what I opened."
        new_revealed = reveal_sequence_from_messages(messages)
        new_called = sorted(called_tools_from_messages(messages))
        warnings: list[str] = []
        doc_tools = set(R.SECTION_BY_TOOL)
        corpus = tool_corpus(messages, only=doc_tools)
        # El acta entera entra en el pajar: el umbral 0.15 ng/mL^2 que el
        # especialista en la guia cita NO es una alucinacion del registrador.
        haystack = _render(state) + "\n" + tool_corpus(messages)
        # Dos guardias sobre el mismo informe: los valores numéricos, y los
        # grados de la biopsia previa. El segundo hace falta porque el primero
        # ignora a propósito los enteros de una cifra, que es justo la forma que
        # tiene el hecho más decisivo de esta tarea.
        offenders = unsourced_values(text, tool_corpus(messages), haystack)
        offenders += [g for g in unsourced_grades(text, corpus) if g not in offenders]
        if offenders:
            warnings.append(f"registrar: unsourced values challenged ({', '.join(offenders)})")
            try:
                challenge = HumanMessage(content=prompts.registrar_quote_challenge(offenders))
                resp = m_reg.invoke([*messages, challenge])
                retold = resp.content if isinstance(resp.content, str) else str(resp.content)
                if retold.strip():
                    still = unsourced_values(retold, tool_corpus(messages), haystack)
                    still += [g for g in unsourced_grades(retold, corpus) if g not in still]
                    text = retold
                    if still:
                        warnings.append(f"registrar: still unsourced after challenge ({', '.join(still)})")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"registrar challenge failed: {type(exc).__name__}: {exc}")
        lean = registrar_lean(text)
        if not new_called and not (state.get("revealed") or []):
            text += ("\n\n[REGISTRAR opened no document in this turn, so nothing above under WHAT I FOUND "
                     "came from the record.]")
        gist = ("opened " + (", ".join(new_revealed) if new_revealed else "nothing")
                + f"; leans {({'yes': 'biopsy', 'no': 'defer'}.get(lean, 'unclear'))}")
        return {"interventions": [_say(state, "REGISTRAR", text,
                                       {"revealed": new_revealed, "tools_called": new_called, "lean": lean,
                                        "gist": gist})],
                "revealed": new_revealed, "tools_called": new_called, "corpus": [corpus], "warnings": warnings}

    # -- ESTADO 5: los expertos que leen documentos, y el protocolo ----------

    def expert_psa(state: BoardState) -> dict[str, Any]:
        body, data = psa_expert.render(panel, state["case_id"], list(state.get("revealed") or []),
                                       state["prompt_payload"])
        return {"interventions": [_say(state, "EXPERT-PSA", body, data)]}

    def expert_fusion(state: BoardState) -> dict[str, Any]:
        body, data = fusion_expert.render(panel, state["case_id"], mode, list(state.get("revealed") or []),
                                          state["prompt_payload"])
        return {"interventions": [_say(state, "EXPERT-FUSION", body, data)]}

    def panel_protocol(state: BoardState) -> dict[str, Any]:
        opened = list(state.get("revealed") or [])
        grade = documented_grade("\n".join(state.get("corpus") or []))
        result = protocol_mod.consolidate(
            state["prompt_payload"], _data_of(state, "EXPERT-COHORT"), _data_of(state, "EXPERT-STRUCTURED"),
            _data_of(state, "EXPERT-FUSION"), _data_of(state, "EXPERT-EXPERIENCE") or None, state.get("trace") or {},
            grade, opened, params=protocol_params, psa=_data_of(state, "EXPERT-PSA"))
        body, data = protocol_mod.render(result)
        return {"interventions": [_say(state, "PANEL-PROTOCOL", body, data)], "protocol": result, "grade": grade}

    # -- ESTADO 6: verificador ----------------------------------------------

    def verifier_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("ver_messages") or []
        if not messages:
            open_docs = list(state.get("revealed") or [])
            unopened = [s for s in (state.get("planned") or []) if s not in open_docs]
            messages = [SystemMessage(content=prompts.VERIFIER_SYSTEM),
                        HumanMessage(content=prompts.verifier_user(_render(state), state.get("questions") or [],
                                                                   open_docs, unopened, state.get("pass_", 1),
                                                                   max_passes))]
            return {"ver_messages": {"__reset__": True, "messages": [*messages, ver_model.invoke(messages)]},
                    "ver_calls": 0}
        return {"ver_messages": [ver_model.invoke(messages)]}

    def verifier_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=("Your guideline-search budget is spent. Write your check now, under your "
                                      "five headings, and end with your VERDICT line. No further tool calls."))
        return {"ver_messages": [nudge, m_ver.invoke([*state["ver_messages"], nudge])]}

    def verifier_post(state: BoardState) -> dict[str, Any]:
        pass_ = state.get("pass_", 1)
        text = _last_text(state.get("ver_messages") or []) or "I could not produce a readable check."
        line = verifier_line(text)
        revealed = list(state.get("revealed") or [])
        unopened = [s for s in (state.get("planned") or []) if s not in revealed]
        reopen = bool(pass_ < max_passes and not line["ready"] and unopened)
        tail = []
        if reopen:
            tail.append(f"[The conference reopens for pass {pass_ + 1}: {', '.join(unopened)} were on the plan "
                        "and were not opened.]")
        else:
            why = ("the verifier called the record ready" if line["ready"] else
                   "every document on the plan is open; nothing outside the plan is ever opened" if not unopened
                   else "the pass budget is spent")
            tail.append(f"[The conference closes after pass {pass_}: {why}. The chair decides on the record as "
                        "it stands.]")
        if not line["parsed"]:
            tail.append("[No machine-readable VERDICT line was written, so the conference closed by the default "
                        "rule: reopening has to be asked for explicitly.]")
        verdict = {**line, "passes": pass_, "reopened": reopen, "planned_unopened": unopened}
        gist = (f"{'ready' if line['ready'] else 'not ready'}"
                + (f", suggests {line['suggest']}" if line.get("suggest") else "")
                + (", reopening" if reopen else ""))
        out: dict[str, Any] = {"interventions": [_say(state, "VERIFIER", text + "\n\n" + "\n".join(tail),
                                                      {**verdict, "gist": gist})], "verdict": verdict}
        if reopen:
            out |= {"pass_": pass_ + 1, "still_missing": unopened,
                    "reg_messages": {"__reset__": True, "messages": []},
                    "ver_messages": {"__reset__": True, "messages": []},
                    "reg_calls": 0, "ver_calls": 0, "reg_nudged": False}
        return out

    # -- ESTADO 7: el presidente --------------------------------------------
    #
    # Aqui esta el cambio de fondo de esta version. El presidente:
    #   * NO ve el acta. Ve un parte clinico construido en codigo, sin locutores.
    #   * NO decide. La decision, la confianza y los pesos vienen del protocolo;
    #     el vota nada porque sus votos se midieron en el azar en el cubo dificil.
    #   * SI escribe la nota, que es lo que puntua el juez de razonamiento, y se
    #     le comprueba que describa al paciente y no al procedimiento.

    def chair(state: BoardState) -> dict[str, Any]:
        case_id = state["case_id"]
        called = set(state.get("tools_called") or [])
        revealed = list(state.get("revealed") or [])
        proto = state.get("protocol") or {}
        grade = state.get("grade") or {}
        payload = state["prompt_payload"]
        decision = proto.get("decision") or "yes"

        warnings: list[str] = []
        because, against, alternative = protocol_mod.clinical_reason(payload, grade, revealed, decision)
        confidence = proto.get("confidence") or "clear"
        # Los pesos se aterrizan ANTES de enseñárselos al presidente: pedirle que
        # pese una variable que la guardia va a bajar después es pedirle que
        # justifique en la nota algo que no se entrega.
        grounded, downgraded = enforce_grounding({"variable_weights": dict(proto.get("variable_weights") or {})},
                                                 revealed)
        weights = grounded["variable_weights"]

        corpus_text = "\n".join(state.get("corpus") or [])
        reg_report = _body_of(state, "REGISTRAR")
        found = _section_of(reg_report, "WHAT I FOUND",
                            ("WHAT I DID NOT OPEN", "WHAT THIS SUPPORTS", "WHERE THIS LEANS")) or reg_report
        # Si el registrador afirmó un grado que ningún documento recoge, esa línea
        # no llega al presidente. `documented_grade` ya lee el texto crudo, así
        # que el protocolo nunca se dejó engañar; lo que se cierra aquí es la vía
        # por la que la invención llegaba a la nota clínica.
        found, dropped_grades = drop_unsourced_grade_lines(found, corpus_text)
        if dropped_grades:
            warnings.append(f"digest: dropped unsourced grade claim(s) {', '.join(dropped_grades)}")
        guideline = _section_of(_body_of(state, "EXPERT-EAU"), "GUIDELINE",
                                ("WHAT THE EXPERTS", "WHAT WE STILL NEED"))
        digest = prompts.clinical_digest(payload, revealed, found, grade, guideline, because, against,
                                         decision, confidence, weights, alternative,
                                         proto.get("variable_view"))

        elig = eligible_variables(1, called)
        Dynamic = build_dynamic_model(1, called)  # noqa: N806
        parser = PydanticOutputParser(pydantic_object=Dynamic)
        base_user = prompts.chair_user(case_id, digest, payload, elig, prompts.chair_skeleton(elig))

        audit: dict[str, Any] = {"digest_chars": len(digest), "attempts": 0, "prose_challenged": False,
                                 "prose_offenders": [], "fallback_note": False, "fallback_form": False}
        structured: dict[str, Any] | None = None
        retry_hint: str | None = None
        for attempt in range(1, chair_max_retries + 1):
            audit["attempts"] = attempt
            content = base_user if retry_hint is None else f"{base_user}\n\n{retry_hint}"
            try:
                resp = m_chair.invoke([SystemMessage(content=prompts.CHAIR_SYSTEM), HumanMessage(content=content)])
                raw = resp.content if isinstance(resp.content, str) else str(resp.content)
                structured = parser.parse(extract_json_object(raw)).model_dump(mode="json")
                break
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"chair attempt {attempt}: {type(exc).__name__}: {str(exc)[:160]}")
                if attempt < chair_max_retries:
                    retry_hint = prompts.chair_retry(str(exc))

        # -- la guardia de registro: la nota describe al paciente -------------
        def _note_faults(t: str) -> list[str]:
            return process_language(t) + [f"{g} (no document records it)"
                                          for g in unsourced_grades(t, corpus_text)]

        note = (structured or {}).get("reasoning") or ""
        offenders = _note_faults(note)
        if structured is not None and offenders:
            audit["prose_challenged"] = True
            audit["prose_offenders"] = offenders
            warnings.append(f"chair: process language in the note ({', '.join(offenders[:4])})")
            try:
                resp = m_chair.invoke([
                    SystemMessage(content=prompts.CHAIR_SYSTEM),
                    HumanMessage(content=f"{base_user}\n\n{prompts.chair_prose_challenge(offenders)}")])
                raw = resp.content if isinstance(resp.content, str) else str(resp.content)
                candidate = parser.parse(extract_json_object(raw)).model_dump(mode="json")
                if not _note_faults(candidate.get("reasoning") or ""):
                    structured = candidate
                    note = candidate["reasoning"]
                    offenders = []
                else:
                    offenders = _note_faults(candidate.get("reasoning") or "")
                    structured["reasoning"] = candidate["reasoning"]
                    note = candidate["reasoning"]
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"chair prose challenge failed: {type(exc).__name__}: {exc}")

        if structured is None:
            audit["fallback_form"] = True
            warnings.append("chair: deterministic fallback used for the whole form")
            structured = {"case_id": case_id, "task": 1, "biopsy_decision": decision == "yes",
                          "confidence": confidence, "variable_weights": {}, "reasoning": ""}
            note, offenders = "", ["<no form>"]
        if offenders or len(note.strip()) < 40:
            audit["fallback_note"] = True
            warnings.append("chair: note rewritten deterministically "
                            + ("(process language persisted)" if offenders else "(too short)"))
            note = clinical_note(payload, grade, revealed, because, decision, against, alternative)

        # -- el registro que se entrega --------------------------------------
        final = dict(structured)
        final["case_id"] = case_id
        final["task"] = 1
        final["biopsy_decision"] = decision == "yes"
        final["confidence"] = confidence
        final["variable_weights"] = dict(weights)
        final["reasoning"] = note
        full = normalise_to_full_shape(1, final)
        full["reveal_sequence"] = revealed
        full, again = enforce_grounding(full, revealed)
        if downgraded or again:
            warnings.append(f"grounding guard: {', '.join(sorted(set(downgraded) | set(again)))} "
                            "-> not_used (section not opened)")
        ok, why = validate_output(full)
        audit["schema_ok"] = ok
        if not ok:  # nunca deberia pasar: el registro se compone en codigo
            warnings.append(f"schema validation failed: {why}")
            full["reasoning"] = clinical_note(payload, grade, revealed, because, decision, against, alternative)
            ok, why = validate_output(full)
            audit["schema_ok"] = ok
        audit["note_words"] = len(full["reasoning"].split())
        audit["note_violations"] = _note_faults(full["reasoning"])

        verdict = "BIOPSY" if full["biopsy_decision"] else "NO BIOPSY"
        marks = ", ".join(f"{k}={v}" for k, v in full["variable_weights"].items() if v != "not_used")
        body = (f"MY DECISION: {verdict}   (confidence: {full['confidence']})\n\n{full['reasoning']}\n\n"
                f"What carried weight: {marks or 'nothing above not_used'}\n"
                f"Sections retrieved: {', '.join(revealed) if revealed else 'none'}")
        return {"interventions": [_say(state, "CHAIR", body, {**full, "audit": audit,
                                                              "gist": f"decision {verdict}, confidence {full['confidence']}"})],
                "structured_response": full, "chair_audit": audit, "warnings": warnings}

    # -- routers -------------------------------------------------------------

    def _has_tool_calls(messages: list) -> bool:
        return bool(messages) and bool(getattr(messages[-1], "tool_calls", None))

    def route_eau(state: BoardState) -> str:
        messages = state.get("eau_messages") or []
        if _has_tool_calls(messages):
            return "eau_tools"
        if (guideline_tools and not called_tools_from_messages(messages)
                and not state.get("eau_nudged") and deadline.allows("nudge")):
            return "eau_nudge"
        return "eau_post"

    def route_eau_after_tools(state: BoardState) -> str:
        return "eau_finalize" if state.get("eau_calls", 0) >= eau_max_calls else "eau_agent"

    def route_after_moderator(state: BoardState) -> str:
        return "expert_image" if state.get("need_image") and not state.get("image_done") else "registrar_agent"

    def route_registrar(state: BoardState) -> str:
        messages = state.get("reg_messages") or []
        if _has_tool_calls(messages):
            return "reg_tools"
        if (state.get("plan") and not called_tools_from_messages(messages)
                and not state.get("reg_nudged") and deadline.allows("nudge")):
            return "registrar_nudge"
        return "registrar_post"

    def route_registrar_after_tools(state: BoardState) -> str:
        return "registrar_finalize" if state.get("reg_calls", 0) >= reg_max_calls else "registrar_agent"

    def route_verifier(state: BoardState) -> str:
        messages = state.get("ver_messages") or []
        if _has_tool_calls(messages) and state.get("ver_calls", 0) < ver_max_calls:
            return "ver_tools"
        if _has_tool_calls(messages):
            return "verifier_finalize"
        return "verifier_post"

    def route_close(state: BoardState) -> str:
        # La segunda vuelta son cuatro llamadas más. Si no cabe, se cierra con
        # lo que hay: el presidente redacta y el protocolo ya decidió.
        reopen = (state.get("verdict") or {}).get("reopened") and deadline.allows("pass")
        return "moderator" if reopen else "chair"

    def count_eau(state: BoardState) -> dict[str, Any]:
        return {"eau_calls": state.get("eau_calls", 0) + 1}

    def count_reg(state: BoardState) -> dict[str, Any]:
        return {"reg_calls": state.get("reg_calls", 0) + 1}

    def count_ver(state: BoardState) -> dict[str, Any]:
        return {"ver_calls": state.get("ver_calls", 0) + 1}

    # -- montaje -------------------------------------------------------------

    b = StateGraph(BoardState)
    for name, fn in (
        ("intake", intake), ("expert_structured", expert_structured), ("expert_cohort", expert_cohort),
        ("expert_library", expert_library), ("expert_trace", expert_trace),
        ("eau_agent", eau_agent), ("eau_count", count_eau), ("eau_nudge", eau_nudge),
        ("eau_finalize", eau_finalize), ("eau_post", eau_post),
        ("moderator", moderator), ("expert_image", expert_image),
        ("registrar_agent", registrar_agent), ("reg_count", count_reg), ("registrar_nudge", registrar_nudge),
        ("registrar_finalize", registrar_finalize), ("registrar_post", registrar_post),
        ("expert_psa", expert_psa), ("expert_fusion", expert_fusion), ("panel_protocol", panel_protocol),
        ("verifier_agent", verifier_agent), ("ver_count", count_ver), ("verifier_finalize", verifier_finalize),
        ("verifier_post", verifier_post), ("chair", chair),
    ):
        b.add_node(name, fn)
    b.add_node("eau_tools", ToolNode(guideline_tools or tools, messages_key="eau_messages"))
    b.add_node("reg_tools", ToolNode(registrar_tools or tools, messages_key="reg_messages"))
    b.add_node("ver_tools", ToolNode(guideline_tools or tools, messages_key="ver_messages"))

    b.add_edge(START, "intake")
    b.add_edge("intake", "expert_structured")
    b.add_edge("expert_structured", "expert_cohort")
    b.add_edge("expert_cohort", "expert_library")
    b.add_edge("expert_library", "expert_trace")
    b.add_edge("expert_trace", "eau_agent")

    _eau = {"eau_tools": "eau_tools", "eau_nudge": "eau_nudge", "eau_post": "eau_post"}
    b.add_conditional_edges("eau_agent", route_eau, _eau)
    b.add_conditional_edges("eau_nudge", route_eau, _eau)
    b.add_edge("eau_tools", "eau_count")
    b.add_conditional_edges("eau_count", route_eau_after_tools, {"eau_agent": "eau_agent", "eau_finalize": "eau_finalize"})
    b.add_edge("eau_finalize", "eau_post")
    b.add_edge("eau_post", "moderator")

    b.add_conditional_edges("moderator", route_after_moderator,
                            {"expert_image": "expert_image", "registrar_agent": "registrar_agent"})
    b.add_edge("expert_image", "registrar_agent")
    _reg = {"reg_tools": "reg_tools", "registrar_nudge": "registrar_nudge", "registrar_post": "registrar_post"}
    b.add_conditional_edges("registrar_agent", route_registrar, _reg)
    b.add_conditional_edges("registrar_nudge", route_registrar, _reg)
    b.add_edge("reg_tools", "reg_count")
    b.add_conditional_edges("reg_count", route_registrar_after_tools,
                            {"registrar_agent": "registrar_agent", "registrar_finalize": "registrar_finalize"})
    b.add_edge("registrar_finalize", "registrar_post")
    b.add_edge("registrar_post", "expert_psa")
    b.add_edge("expert_psa", "expert_fusion")
    b.add_edge("expert_fusion", "panel_protocol")
    b.add_edge("panel_protocol", "verifier_agent")

    b.add_conditional_edges("verifier_agent", route_verifier,
                            {"ver_tools": "ver_tools", "verifier_finalize": "verifier_finalize",
                             "verifier_post": "verifier_post"})
    b.add_edge("ver_tools", "ver_count")
    b.add_edge("ver_count", "verifier_agent")
    b.add_edge("verifier_finalize", "verifier_post")
    b.add_conditional_edges("verifier_post", route_close, {"moderator": "moderator", "chair": "chair"})
    b.add_edge("chair", END)

    graph = b.compile()
    graph.step_timeout = step_timeout
    log.info("Junta final compilada: %d herramientas MCP, modo %s, biblioteca %s, max_passes=%d",
             len(tools), mode, "leave-one-out" if (library is not None and library.exclude_self) else "completa",
             max_passes)
    return graph
