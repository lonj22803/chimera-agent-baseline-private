"""El grafo de la junta: siete estados de la pizarra, nueve papeles.

    ESTADO 0   pizarra en blanco
      |
      +-- INTAKE .................. intervenciones 1 y 2   -> ESTADO 1
      |     1  el structured-prompt.json, crudo
      |     2  el mismo, renderizado con templates/prompts/agent_prompt.j2
      |
      +-- EXPERT-CLASSIFIER ....... intervencion 3         -> ESTADO 2
      +-- EXPERT-COHORT ........... intervencion 4
      |
      +-- EXPERT-EAU <-> search_guidelines ... 5           -> ESTADO 3
      |
      +-- MODERATOR ............... 6                      -> ESTADO 4
      |     plan de verificacion + preguntas abiertas
      |
      +-- EXPERT-IMAGE (si lo pide) 7                      -> ESTADO 5
      +-- REGISTRAR <-> herramientas MCP ..... 8
      |
      +-- VERIFIER <-> search_guidelines ..... 9           -> ESTADO 6
      |     |-- no listo y queda pase y queda documento --> vuelve al MODERATOR
      |     `-- listo ------------------------------------> CHAIR
      |
      +-- CHAIR ................... 10                     -> ESTADO 7
            el formulario validado contra Task1Output

Tres cosas que decide el codigo y no un modelo, y por que
--------------------------------------------------------
1. **Que herramientas existen.** El catalogo sale de la lista MCP viva
   (:mod:`roster`), no de una tabla escrita a mano. Un modelo al que se le
   anuncia ``get_pathology_report`` en la tarea 1 —donde no existe— acaba
   citando un informe que nadie le sirvio.
2. **Cuando se reabre la sesion.** El verificador dice si esta listo; la regla
   de reapertura la aplica el grafo, y exige las tres condiciones a la vez:
   queda pase, queda presupuesto de revelacion y queda un documento cerrado que
   pueda contestar. Sin la tercera, reabrir es releer, que fue justo el gasto
   inutil que se midio en la generacion anterior.
3. **Que ningun numero se cuele sin fuente.** El informe del registrador se
   compara contra lo que devolvieron las herramientas y contra el panel; si hay
   un valor que no esta en ninguno de los dos, se le devuelve el turno con la
   lista delante.
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
from . import roster as R
from . import sampling
from .board import Board
from .decide import (
    called_tools_from_messages,
    enforce_grounding,
    extract_json_object,
    fallback_response,
    parse_json,
    registrar_lean,
    reveal_sequence_from_messages,
    tool_corpus,
    unsourced_values,
    verifier_line,
)
from .experts import classifier as classifier_expert
from .experts import cohort as cohort_expert
from .experts import image as image_expert

log = logging.getLogger(__name__)


def _messages_reducer(old: list, new: Any) -> list:
    """``add_messages`` normal, mas un reinicio explicito al reabrir un pase."""
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
    plan: list[dict]
    questions: list[str]
    need_image: bool
    image_done: bool
    still_missing: list[str]
    extra_granted: bool

    revealed: Annotated[list[str], _dedup]
    tools_called: Annotated[list[str], _dedup]
    verdict: dict[str, Any]

    structured_response: dict[str, Any]
    warnings: Annotated[list[str], operator.add]


# ---------------------------------------------------------------------------
# ayudas
# ---------------------------------------------------------------------------


def _board(state: BoardState) -> Board:
    return Board.from_dicts(state["case_id"], state.get("task", 1),
                            state.get("interventions", []))


def _render(state: BoardState) -> str:
    return _board(state).render()


def _say(state: BoardState, speaker: str, body: str, data: dict | None = None,
         offset: int = 0) -> dict:
    return {"n": len(state.get("interventions") or []) + 1 + offset,
            "speaker": speaker, "body": body.strip(), "data": data or {},
            "pass_": state.get("pass_", 1)}


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
    parts = [i["body"] for i in state.get("interventions", []) if i["speaker"] == speaker]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# el grafo
# ---------------------------------------------------------------------------


def create_conference_graph(
    tools: list[BaseTool],
    model: BaseChatModel,
    feature_store: Any = None,
    classifier: Any = None,
    *,
    max_passes: int = 3,
    max_reveals: int = R.MAX_REVEALS,
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
    #: El registrador ve los documentos que merece la pena abrir y la busqueda en
    #: la guia. `get_family_history` NO se le enlaza: el urologo la pidio 0 de 91
    #: veces, asi que cada llamada es precision regalada. Impedirlo enlazando
    #: menos herramientas es mas fiable que pedirselo en el prompt.
    registrar_tools = roster.document_tools() + guideline_tools

    eau_model = m_eau.bind_tools(guideline_tools) if guideline_tools else m_eau
    reg_model = m_reg.bind_tools(registrar_tools) if registrar_tools else m_reg
    ver_model = m_ver.bind_tools(guideline_tools) if guideline_tools else m_ver

    moderator_system = prompts.moderator_system(roster.catalogue())

    def _budget(state: BoardState) -> int:
        cap = min(max_reveals + (1 if state.get("extra_granted") else 0), R.HARD_CAP)
        return max(0, cap - len(state.get("revealed") or []))

    # -- ESTADO 1: el expediente --------------------------------------------

    def intake(state: BoardState) -> dict[str, Any]:
        raw = json.dumps(state["prompt_payload"], indent=2, ensure_ascii=False)
        one = (
            "Colleagues, this is the record as it arrived, field by field. I read it out and "
            "interpret nothing; everything after this is yours.\n\n"
            f"{raw}"
        )
        openable = ", ".join(s for s in roster.sections if s not in R.NEVER)
        two = (
            "And this is the same record as the reading form presents it — the panel the "
            "urologist sees up front, with the masked documents named but not shown.\n\n"
            f"{state['case_prompt']}\n\n"
            "One correction to that last paragraph before anybody acts on it: the documents this "
            f"task actually serves are {openable}, plus the family-history anamnesis. "
            "There is NO pathology report to pull up in a task-1 biopsy decision — the "
            "prior-biopsy status on the panel above is all the pathology on record. Nobody should "
            "ask for one, and nobody should quote one."
        )
        return {
            "interventions": [
                _say(state, "INTAKE", one, {"gist": "record read out, field by field", "raw": True}),
                _say(state, "INTAKE", two, {"gist": "record as the reading form presents it"}, offset=1),
            ],
            "pass_": 1,
        }

    # -- ESTADO 2: los dos expertos del panel --------------------------------

    def expert_classifier(state: BoardState) -> dict[str, Any]:
        body, data = classifier_expert.render(classifier, state["case_files"])
        return {"interventions": [_say(state, "EXPERT-CLASSIFIER", body, data)]}

    def expert_cohort(state: BoardState) -> dict[str, Any]:
        body, data = cohort_expert.render(state["prompt_payload"])
        return {"interventions": [_say(state, "EXPERT-COHORT", body, data)]}

    # -- ESTADO 3: el especialista en la guia --------------------------------

    def eau_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("eau_messages") or []
        if not messages:
            messages = [SystemMessage(content=prompts.EAU_SYSTEM),
                        HumanMessage(content=prompts.eau_user(_render(state)))]
            return {"eau_messages": {"__reset__": True,
                                     "messages": [*messages, eau_model.invoke(messages)]},
                    "eau_calls": 0}
        return {"eau_messages": [eau_model.invoke(messages)]}

    def eau_nudge(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=prompts.EAU_NUDGE)
        return {"eau_messages": [nudge, eau_model.invoke([*state["eau_messages"], nudge])],
                "eau_nudged": True}

    def eau_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=prompts.EAU_FINALIZE)
        return {"eau_messages": [nudge, m_eau.invoke([*state["eau_messages"], nudge])]}

    def eau_post(state: BoardState) -> dict[str, Any]:
        messages = state.get("eau_messages") or []
        text = _last_text(messages) or "I have nothing usable from the guideline for this case."
        searched = "search_guidelines" in called_tools_from_messages(messages)
        if not searched:
            text += ("\n\n[EXPERT-EAU retrieved nothing from the guideline in this turn, so nothing "
                     "above is attributable to it.]")
        gist = "guideline reading" + ("" if searched else " (no retrieval — treat as unsupported)")
        return {"interventions": [_say(state, "EXPERT-EAU", text,
                                       {"gist": gist, "searched": searched})]}

    # -- ESTADO 4: el moderador ----------------------------------------------

    def moderator(state: BoardState) -> dict[str, Any]:
        pass_ = state.get("pass_", 1)
        budget = _budget(state)
        already = list(state.get("revealed") or [])
        raw = ""
        try:
            resp = m_mod.invoke([
                SystemMessage(content=moderator_system),
                HumanMessage(content=prompts.moderator_user(
                    _render(state), pass_, budget, already, state.get("still_missing"))),
            ])
            raw = resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as exc:  # noqa: BLE001 — el moderador nunca bloquea un caso
            log.warning("El moderador fallo en %s: %s", state["case_id"], exc)

        obj = parse_json(raw)
        plan, notes = R.clean_plan(obj.get("plan") or [], roster, already, budget)
        if not plan and pass_ == 1 and budget > 0:
            plan = R.default_plan(state["prompt_payload"], roster, already, budget)
            notes.append("No readable plan came back, so the conference falls back to the documents "
                         "the reading urologist opened most often in this situation.")
        if pass_ == 1:
            plan, floor_notes = R.apply_floor(plan, roster, already, budget)
            notes += floor_notes

        # Una pregunta cuyo valor ya está impreso en el panel manda al registrador
        # a buscar lo que ya está sobre la mesa. Se cae aquí, además de estar
        # prohibida en los dos prompts.
        questions, dropped_q = [], []
        for q in (obj.get("questions") or []):
            q = " ".join(str(q).split())
            if not q:
                continue
            (dropped_q if R.drops_panel_question(q) else questions).append(q)
        questions = questions[:4]
        if dropped_q:
            notes.append(f"Dropped {len(dropped_q)} question(s) that asked for a value already "
                         f"printed on the panel: \"{dropped_q[0]}\" — the room can read it off "
                         "intervention 1.")
        need_image = bool(obj.get("need_image")) and not state.get("image_done")
        opening = " ".join(str(obj.get("to_colleagues") or "").split())

        body = _moderator_body(opening, plan, questions, notes, need_image, pass_)
        return {
            "interventions": [_say(state, "MODERATOR", body,
                                   {"plan": plan, "questions": questions, "need_image": need_image,
                                    "gist": ("plan: " + (", ".join(p["section"] for p in plan) or "nothing further")
                                             + f"; {len(questions)} open question(s)")})],
            "plan": plan,
            "questions": questions,
            "need_image": need_image,
        }

    # -- ESTADO 5: imagen y registrador --------------------------------------

    def expert_image(state: BoardState) -> dict[str, Any]:
        body, data = image_expert.render(state["case_id"], feature_store)
        return {"interventions": [_say(state, "EXPERT-IMAGE", body, data)], "image_done": True}

    def registrar_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("reg_messages") or []
        if not messages:
            messages = [SystemMessage(content=prompts.REGISTRAR_SYSTEM),
                        HumanMessage(content=prompts.registrar_user(
                            _render(state), state.get("plan") or [], state.get("pass_", 1)))]
            return {"reg_messages": {"__reset__": True,
                                     "messages": [*messages, reg_model.invoke(messages)]},
                    "reg_calls": 0}
        return {"reg_messages": [reg_model.invoke(messages)]}

    def registrar_nudge(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=prompts.REGISTRAR_NUDGE)
        return {"reg_messages": [nudge, reg_model.invoke([*state["reg_messages"], nudge])],
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

        # -- guardia de procedencia: ningun valor sin fuente ------------------
        corpus = tool_corpus(messages)
        panel = _body_of(state, "INTAKE")
        offenders = unsourced_values(text, corpus, panel)
        if offenders:
            warnings.append(f"registrar: unsourced values challenged ({', '.join(offenders)})")
            try:
                challenge = HumanMessage(content=prompts.registrar_quote_challenge(offenders))
                resp = m_reg.invoke([*messages, challenge])
                retold = resp.content if isinstance(resp.content, str) else str(resp.content)
                if retold.strip():
                    still = unsourced_values(retold, corpus, panel)
                    text = retold
                    if still:
                        warnings.append(f"registrar: still unsourced after challenge ({', '.join(still)})")
            except Exception as exc:  # noqa: BLE001 — si el reto falla vale el informe previo
                warnings.append(f"registrar challenge failed: {type(exc).__name__}: {exc}")

        lean = registrar_lean(text)
        if not new_called and not (state.get("revealed") or []):
            text += ("\n\n[REGISTRAR opened no document in this turn, so nothing above under WHAT I "
                     "FOUND came from the record.]")

        gist = ("opened " + (", ".join(new_revealed) if new_revealed else "nothing")
                + f"; leans {({'yes': 'biopsy', 'no': 'defer'}.get(lean, 'unclear'))}")
        return {
            "interventions": [_say(state, "REGISTRAR", text,
                                   {"revealed": new_revealed, "tools_called": new_called,
                                    "lean": lean, "gist": gist})],
            "revealed": new_revealed,
            "tools_called": new_called,
            "warnings": warnings,
        }

    # -- ESTADO 6: el verificador --------------------------------------------

    def verifier_agent(state: BoardState) -> dict[str, Any]:
        messages = state.get("ver_messages") or []
        if not messages:
            open_docs = list(state.get("revealed") or [])
            closed = [s for s in roster.sections if s not in R.NEVER and s not in open_docs]
            messages = [SystemMessage(content=prompts.VERIFIER_SYSTEM),
                        HumanMessage(content=prompts.verifier_user(
                            _render(state), state.get("questions") or [], open_docs, closed,
                            state.get("pass_", 1), max_passes))]
            return {"ver_messages": {"__reset__": True,
                                     "messages": [*messages, ver_model.invoke(messages)]},
                    "ver_calls": 0}
        return {"ver_messages": [ver_model.invoke(messages)]}

    def verifier_post(state: BoardState) -> dict[str, Any]:
        pass_ = state.get("pass_", 1)
        text = _last_text(state.get("ver_messages") or []) or \
            "I could not produce a readable check for this record."
        line = verifier_line(text)

        revealed = list(state.get("revealed") or [])
        closed = [s for s in roster.sections if s not in R.NEVER and s not in revealed]

        # ¿Nombro un documento cerrado que existe? Eso, y solo eso, autoriza el
        # cuarto documento por encima del techo normal de precision.
        named = None
        for section in closed:
            if line.get("missing") and section.replace("_", " ") in line["missing"].replace("_", " "):
                named = section
                break

        # Y si lo que nombra es el laboratorio, tiene que haber nombrado tambien
        # una de las tres preguntas que lo justifican -- en su propio texto, no
        # en la linea mecanica.
        #
        # Medido en el piloto de 10 casos: el verificador nombro
        # `laboratory_results` como lo que faltaba en 7 de 10, por reflejo (es el
        # unico documento que normalmente queda cerrado, asi que es el que
        # aparece cuando se le pregunta que falta). Consecuencias: se abrio el
        # laboratorio en 4 de 10 -- frente al 45 % del urologo y al 6/91 de la
        # generacion anterior -- y `tool_score` cayo de 0.878 a 0.817. Peor: en
        # un caso la sesion dio las tres vueltas pidiendo el laboratorio que
        # `clean_plan` volvia a tirar cada vez por no venir justificado, y acabo
        # con UN solo documento abierto. La regla de reapertura y el filtro del
        # plan tienen que estar de acuerdo, o el bucle gira en vacio.
        rejected_lab = False
        if named == "laboratory_results" and not R.LAB_JUSTIFIED.search(text):
            named, rejected_lab = None, True

        extra = bool(named) and not state.get("extra_granted")
        cap = min(max_reveals + (1 if (state.get("extra_granted") or extra) else 0), R.HARD_CAP)
        budget_left = max(0, cap - len(revealed))

        # Documentos que reabrir podria de verdad conseguir: los que sobreviven
        # al mismo filtro que aplicara `clean_plan` en la vuelta siguiente.
        openable = [s for s in closed
                    if s != "laboratory_results" or R.LAB_JUSTIFIED.search(text)]

        reopen = bool(
            pass_ < max_passes
            and not line["ready"]
            and openable
            and budget_left > 0
        )

        tail = []
        if reopen:
            tail.append(f"[The conference reopens for pass {pass_ + 1}: "
                        + (f"'{named}' is named as missing and is still closed." if named
                           else f"{', '.join(openable)} still closed.") + "]")
        else:
            if line["ready"]:
                why = "the verifier called the record ready"
            elif rejected_lab and not openable:
                why = ("the only document still closed is the laboratory panel, and the verifier "
                       "did not name one of the three questions that justify opening it (free-PSA "
                       "fraction, infection or prostatitis explaining the PSA, fitness for the "
                       "procedure). Reopening could not obtain it, so it would only cost a round")
            elif not openable:
                why = "no closed document is left that could answer"
            else:
                why = "the reveal budget or the pass budget is spent"
            tail.append(f"[The conference closes after pass {pass_}: {why}. The chair decides on "
                        "the record as it stands.]")
        if not line["parsed"]:
            tail.append("[No machine-readable VERDICT line was written, so the conference closed by "
                        "the default rule: reopening has to be asked for explicitly.]")

        verdict = {**line, "passes": pass_, "reopened": reopen, "named_missing": named,
                   "closed_documents": closed, "openable": openable,
                   "lab_rejected": rejected_lab}
        gist = (f"{'ready' if line['ready'] else 'not ready'}"
                + (f", suggests {line['suggest']}" if line.get("suggest") else "")
                + (f", reopening for {named}" if reopen else ""))

        out: dict[str, Any] = {
            "interventions": [_say(state, "VERIFIER", text + "\n\n" + "\n".join(tail),
                                   {**verdict, "gist": gist})],
            "verdict": verdict,
        }
        if reopen:
            out |= {
                "pass_": pass_ + 1,
                "still_missing": [named] if named else closed,
                "extra_granted": bool(state.get("extra_granted") or extra),
                "reg_messages": {"__reset__": True, "messages": []},
                "ver_messages": {"__reset__": True, "messages": []},
                "reg_calls": 0, "ver_calls": 0, "reg_nudged": False,
            }
        return out

    # -- ESTADO 7: el presidente ---------------------------------------------

    def chair(state: BoardState) -> dict[str, Any]:
        case_id = state["case_id"]
        called = set(state.get("tools_called") or [])
        revealed = list(state.get("revealed") or [])

        elig = eligible_variables(1, called)
        Dynamic = build_dynamic_model(1, called)  # noqa: N806
        parser = PydanticOutputParser(pydantic_object=Dynamic)

        prior = _data_of(state, "EXPERT-CLASSIFIER")
        cohort = _data_of(state, "EXPERT-COHORT")

        base_user = prompts.chair_user(
            _render(state), _board(state).thread(), case_id, elig,
            prompts.chair_skeleton(elig), state["prompt_payload"], prior, cohort,
            state.get("verdict"))

        warnings: list[str] = []
        structured: dict[str, Any] | None = None
        retry_hint: str | None = None
        for attempt in range(1, chair_max_retries + 1):
            content = base_user if retry_hint is None else f"{base_user}\n\n{retry_hint}"
            try:
                resp = m_chair.invoke([SystemMessage(content=prompts.CHAIR_SYSTEM),
                                       HumanMessage(content=content)])
                raw = resp.content if isinstance(resp.content, str) else str(resp.content)
                structured = parser.parse(extract_json_object(raw)).model_dump(mode="json")
                break
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"chair attempt {attempt}: {type(exc).__name__}: {exc}")
                log.warning("El presidente no valido (%d) en %s: %s", attempt, case_id, exc)
                if attempt < chair_max_retries:
                    retry_hint = prompts.chair_retry(str(exc))

        # -- reto al presidente cuando anula a un colega con historial ----------
        #
        # Quien tiene historial en este caso, en este orden: el criterio de
        # cohorte donde se pronuncia (24/24 sin biopsia previa, 16/18 tras una
        # negativa), y donde se abstiene, el clasificador si esta en un tramo
        # medido -- dentro del cubo indeterminado, `firm`+`supports` cubren 13 de
        # 49 casos y aciertan 0.923, frente al 0.472 de `discuss`.
        #
        # El reto salta sobre la DISIDENCIA, no sobre la falta de citas. La
        # version anterior sólo actuaba cuando el razonamiento no citaba nada
        # recuperado, y medida sobre los 91 casos salto 7 veces: desde que el
        # registrador abre tres documentos en todos los casos, el presidente
        # siempre puede citar algo. Mientras tanto anulo a un colega con
        # historial en 15 casos y acerto en 1. Volteando esos 15 la nota pasa de
        # 0.5952 a 0.7056, asi que el reto tiene que dispararse en los 15.
        standing_answer = standing_who = standing_track = None
        if cohort.get("verdict") in ("yes", "no"):
            standing_answer = cohort["verdict"]
            standing_who = "EXPERT-COHORT"
            standing_track = (
                f"It matched the reading urologist in {cohort['hits']} of {cohort['n']} labelled "
                f"cases in exactly this situation ({cohort['bucket']})."
                if cohort.get("hits") is not None else
                "It applies the standard criterion for this clinical situation."
            )
        elif prior.get("veredicto_operativo") in ("firm", "supports") \
                and prior.get("prediccion") in ("yes", "no"):
            standing_answer = prior["prediccion"]
            standing_who = "EXPERT-CLASSIFIER"
            acc, n_tier = (prior.get("acierto_tramo") or (None, 0))
            standing_track = (
                f"EXPERT-COHORT has no answer for this man, so the classifier is the only colleague "
                f"here with a measured track record, and it spoke from its "
                f"'{prior['veredicto_operativo']}' tier"
                + (f", where it was right {acc:.0%} of the time over {n_tier} labelled cases."
                   if acc is not None else ".")
            )

        if structured is not None and standing_answer is not None:
            chair_says = "yes" if structured.get("biopsy_decision") else "no"
            if chair_says != standing_answer:
                warnings.append(f"chair: challenged (overrode {standing_who})")
                directive = prompts.chair_directive(standing_answer, standing_who, standing_track)
                try:
                    resp = m_chair.invoke([
                        SystemMessage(content=prompts.CHAIR_SYSTEM),
                        HumanMessage(content=f"{base_user}\n\n{directive}"),
                    ])
                    raw = resp.content if isinstance(resp.content, str) else str(resp.content)
                    structured = parser.parse(extract_json_object(raw)).model_dump(mode="json")
                except Exception as exc:  # noqa: BLE001 — si el reto falla vale la respuesta previa
                    warnings.append(f"chair directive failed: {type(exc).__name__}: {exc}")

                # Si tras el aviso sigue disintiendo, manda el colega con
                # historial: la mesa se lo ha dicho dos veces y el registro dice
                # que en 14 de 15 el colega tenia razon. Se anota en la traza.
                #
                # Pero no basta con voltear el booleano. Medido en la corrida
                # anterior: el presidente fue advertido 15 veces y no cedio
                # ninguna, asi que la anulacion actuo en 12 casos y dejo un
                # formulario que decia `yes` sobre una prosa que empezaba
                # "Deferral is appropriate". Se le pide el formulario una tercera
                # vez con la decision ya fijada, para que el texto la sostenga.
                still = "yes" if structured.get("biopsy_decision") else "no"
                if still != standing_answer:
                    warnings.append(f"chair: decision settled by {standing_who} after two warnings")
                    settled = prompts.chair_settled(standing_answer, standing_who, standing_track)
                    rewritten = None
                    try:
                        resp = m_chair.invoke([
                            SystemMessage(content=prompts.CHAIR_SYSTEM),
                            HumanMessage(content=f"{base_user}\n\n{settled}"),
                        ])
                        raw = resp.content if isinstance(resp.content, str) else str(resp.content)
                        candidate = parser.parse(extract_json_object(raw)).model_dump(mode="json")
                        if ("yes" if candidate.get("biopsy_decision") else "no") == standing_answer:
                            rewritten = candidate
                        else:
                            warnings.append("chair: rewrite still disagreed; boolean forced")
                    except Exception as exc:  # noqa: BLE001
                        warnings.append(f"chair rewrite failed: {type(exc).__name__}: {exc}")
                    structured = rewritten if rewritten is not None else structured
                    structured["biopsy_decision"] = standing_answer == "yes"

        used_fallback = structured is None
        if used_fallback:
            structured = fallback_response(case_id, state["prompt_payload"], prior, cohort, revealed)
            warnings.append("chair: deterministic fallback used")

        structured["reveal_sequence"] = revealed
        full = normalise_to_full_shape(1, structured)
        full, downgraded = enforce_grounding(full, revealed)
        if downgraded:
            warnings.append(f"grounding guard: {', '.join(downgraded)} -> not_used (section not opened)")

        verdict = "BIOPSY" if full["biopsy_decision"] else "NO BIOPSY"
        marks = ", ".join(f"{k}={v}" for k, v in full["variable_weights"].items() if v != "not_used")
        body = (
            f"MY DECISION: {verdict}   (confidence: {full['confidence']})\n\n"
            f"{full['reasoning']}\n\n"
            f"What carried weight: {marks or 'nothing above not_used'}\n"
            f"Documents this conference opened: {', '.join(revealed) if revealed else 'none'}"
            + ("\n[completed by the deterministic fallback: the form did not validate]"
               if used_fallback else "")
        )
        return {
            "interventions": [_say(state, "CHAIR", body, {**full, "gist": f"decision {verdict}, "
                                                          f"confidence {full['confidence']}"})],
            "structured_response": full,
            "warnings": warnings,
        }

    # -- routers -------------------------------------------------------------

    def _has_tool_calls(messages: list) -> bool:
        return bool(messages) and bool(getattr(messages[-1], "tool_calls", None))

    def route_eau(state: BoardState) -> str:
        messages = state.get("eau_messages") or []
        if _has_tool_calls(messages):
            return "eau_tools"
        if guideline_tools and not called_tools_from_messages(messages) and not state.get("eau_nudged"):
            return "eau_nudge"
        return "eau_post"

    def route_eau_after_tools(state: BoardState) -> str:
        return "eau_finalize" if state.get("eau_calls", 0) >= eau_max_calls else "eau_agent"

    def route_after_moderator(state: BoardState) -> str:
        return "expert_image" if state.get("need_image") and not state.get("image_done") \
            else "registrar_agent"

    def route_registrar(state: BoardState) -> str:
        messages = state.get("reg_messages") or []
        if _has_tool_calls(messages):
            return "reg_tools"
        wants_documents = bool(state.get("plan"))
        if wants_documents and not called_tools_from_messages(messages) \
                and not state.get("reg_nudged") and not (state.get("revealed") or []):
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
        return "moderator" if (state.get("verdict") or {}).get("reopened") else "chair"

    def verifier_finalize(state: BoardState) -> dict[str, Any]:
        nudge = HumanMessage(content=(
            "Your guideline-search budget is spent. Write your check now, under your five headings, "
            "and end with your VERDICT line. No further tool calls."))
        return {"ver_messages": [nudge, m_ver.invoke([*state["ver_messages"], nudge])]}

    def count_eau(state: BoardState) -> dict[str, Any]:
        return {"eau_calls": state.get("eau_calls", 0) + 1}

    def count_reg(state: BoardState) -> dict[str, Any]:
        return {"reg_calls": state.get("reg_calls", 0) + 1}

    def count_ver(state: BoardState) -> dict[str, Any]:
        return {"ver_calls": state.get("ver_calls", 0) + 1}

    # -- montaje -------------------------------------------------------------

    b = StateGraph(BoardState)
    for name, fn in (
        ("intake", intake),
        ("expert_classifier", expert_classifier), ("expert_cohort", expert_cohort),
        ("eau_agent", eau_agent), ("eau_count", count_eau), ("eau_nudge", eau_nudge),
        ("eau_finalize", eau_finalize), ("eau_post", eau_post),
        ("moderator", moderator), ("expert_image", expert_image),
        ("registrar_agent", registrar_agent), ("reg_count", count_reg),
        ("registrar_nudge", registrar_nudge), ("registrar_finalize", registrar_finalize),
        ("registrar_post", registrar_post),
        ("verifier_agent", verifier_agent), ("ver_count", count_ver),
        ("verifier_finalize", verifier_finalize), ("verifier_post", verifier_post),
        ("chair", chair),
    ):
        b.add_node(name, fn)
    b.add_node("eau_tools", ToolNode(guideline_tools or tools, messages_key="eau_messages"))
    b.add_node("reg_tools", ToolNode(registrar_tools or tools, messages_key="reg_messages"))
    b.add_node("ver_tools", ToolNode(guideline_tools or tools, messages_key="ver_messages"))

    b.add_edge(START, "intake")
    b.add_edge("intake", "expert_classifier")
    b.add_edge("expert_classifier", "expert_cohort")
    b.add_edge("expert_cohort", "eau_agent")

    _eau = {"eau_tools": "eau_tools", "eau_nudge": "eau_nudge", "eau_post": "eau_post"}
    b.add_conditional_edges("eau_agent", route_eau, _eau)
    b.add_conditional_edges("eau_nudge", route_eau, _eau)
    b.add_edge("eau_tools", "eau_count")
    b.add_conditional_edges("eau_count", route_eau_after_tools,
                            {"eau_agent": "eau_agent", "eau_finalize": "eau_finalize"})
    b.add_edge("eau_finalize", "eau_post")
    b.add_edge("eau_post", "moderator")

    b.add_conditional_edges("moderator", route_after_moderator,
                            {"expert_image": "expert_image", "registrar_agent": "registrar_agent"})
    b.add_edge("expert_image", "registrar_agent")

    _reg = {"reg_tools": "reg_tools", "registrar_nudge": "registrar_nudge",
            "registrar_post": "registrar_post"}
    b.add_conditional_edges("registrar_agent", route_registrar, _reg)
    b.add_conditional_edges("registrar_nudge", route_registrar, _reg)
    b.add_edge("reg_tools", "reg_count")
    b.add_conditional_edges("reg_count", route_registrar_after_tools,
                            {"registrar_agent": "registrar_agent",
                             "registrar_finalize": "registrar_finalize"})
    b.add_edge("registrar_finalize", "registrar_post")
    b.add_edge("registrar_post", "verifier_agent")

    b.add_conditional_edges("verifier_agent", route_verifier,
                            {"ver_tools": "ver_tools", "verifier_finalize": "verifier_finalize",
                             "verifier_post": "verifier_post"})
    b.add_edge("ver_tools", "ver_count")
    b.add_edge("ver_count", "verifier_agent")
    b.add_edge("verifier_finalize", "verifier_post")

    b.add_conditional_edges("verifier_post", route_close,
                            {"moderator": "moderator", "chair": "chair"})
    b.add_edge("chair", END)

    graph = b.compile()
    graph.step_timeout = step_timeout
    log.info("Junta compilada: %d herramientas MCP, documentos abribles %s, max_passes=%d, "
             "techo de revelaciones %d", len(tools),
             [s for s in roster.sections if s not in R.NEVER], max_passes, max_reveals)
    return graph


def _moderator_body(opening: str, plan: list[dict], questions: list[str],
                    notes: list[str], need_image: bool, pass_: int) -> str:
    """El cuerpo de la intervencion del moderador: lo que dice, y luego el plan."""
    rendered = R.render_plan(plan, questions, notes, need_image, pass_)
    return f"{opening}\n\n{rendered}".strip() if opening else rendered
