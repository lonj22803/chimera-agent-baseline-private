"""Qué herramientas EXISTEN de verdad en la tarea 1, y cuánto cuesta cada una.

Esta pieza existe por un error concreto que corrige esta generación.

El encargo pedía que el moderador tuviera en su contexto ``get_psa_trend``,
``get_lab_results``, ``get_mri_report``, ``get_pathology_report``,
``get_previous_notes``, ``get_family_history`` y ``search_guidelines``. En la
tarea 1 **``get_pathology_report`` no existe**: el registro de herramientas de
los organizadores
(:mod:`chimera_agent_baseline.tools.definitions`, ``TASK1_TOOLS``) expone cinco
documentos y ese no está entre ellos, y ``pathology_report`` tampoco figura en
el vocabulario de ``Task1Output.reveal_sequence``. Anunciarle a un modelo una
herramienta que no puede llamar es la forma más barata de provocar una
alucinación: el modelo escribe "el informe de anatomía patológica indica…" sobre
un documento que nunca se le sirvió.

Por eso el catálogo **no se escribe a mano aquí**: se construye a partir de la
lista de herramientas MCP que el servidor entrega en tiempo de ejecución. Si un
día la tarea 1 expone la patología, aparece sola; mientras no la exponga, nadie
la ve.

El coste de cada revelación
---------------------------
``tool_score`` del evaluador oficial es **precisión**, no cobertura::

    score = |secciones abiertas ∩ secciones que abrió el urólogo| / |secciones abiertas|

(``evaluation/evaluate.py::cost_aware_tool_score``). Abrir de menos es gratis;
abrir de más se paga. Frecuencia con la que el urólogo abrió cada sección en los
91 casos etiquetados: imagen 97 %, serie de PSA 87 %, notas previas 85 %,
laboratorio 45 %, antecedentes familiares 0 %. De ahí salen las dos reglas
duras de este módulo: el techo de tres documentos y la lista de justificaciones
del laboratorio.
"""

from __future__ import annotations

import re
from typing import Any

#: Herramienta -> sección del vocabulario de ``Task1Output.reveal_sequence``.
#: Sólo estas cinco cuentan como revelación. ``search_guidelines`` es libre.
SECTION_BY_TOOL: dict[str, str] = {
    "get_mri_report": "radiology_report",
    "get_psa_trend": "psa_trend",
    "get_previous_notes": "previous_notes",
    "get_lab_results": "laboratory_results",
    "get_family_history": "family_history",
}

TOOL_BY_SECTION: dict[str, str] = {v: k for k, v in SECTION_BY_TOOL.items()}

GUIDELINE_TOOL = "search_guidelines"

#: Cuántas veces de 91 abrió el urólogo cada sección. Es lo que convierte "abrir
#: todo" en una decisión con precio.
UROLOGIST_RATE: dict[str, float] = {
    "radiology_report": 0.97,
    "psa_trend": 0.87,
    "previous_notes": 0.85,
    "laboratory_results": 0.45,
    "family_history": 0.00,
}

#: Qué aporta cada documento, en una línea, para el plan del moderador.
WHAT_IT_ADDS: dict[str, str] = {
    "radiology_report": (
        "the mpMRI prose behind PI-RADS: lesion size and zone, extraprostatic extension, and "
        "above all whether it is compared against an earlier study"
    ),
    "psa_trend": "the serial PSA values behind the single headline number: rising, flat or falling",
    "previous_notes": (
        "the management context: what the prior biopsy showed, whether there is a surveillance "
        "protocol, what was agreed with the patient, what is already planned"
    ),
    "laboratory_results": (
        "the full panel, and where the DRE finding is filed. The reading urologist skips it more "
        "than half the time"
    ),
    "family_history": (
        "first-degree family history. The reading urologist asked for it in 0 of 91 labelled "
        "biopsy decisions"
    ),
}

#: Las tres preguntas que justifican abrir el laboratorio. Sin una de ellas por
#: escrito, el documento se cae del plan.
LAB_JUSTIFIED = re.compile(
    r"free[- ]?psa|prostatit|infect|uti\b|urinary tract|coagul|renal|creatinin|egfr|"
    r"fitness|anticoagul|platelet|inr\b|testoster",
    re.I,
)

#: Los valores que el panel ya imprime. Preguntar por cualquiera de ellos manda
#: al registrador a abrir un documento para recuperar un número que ya está sobre
#: la mesa.
PANEL_VALUE = re.compile(
    r"psa[- ]?densit|\bpsad\b|pi-?rads|prostate volume|\bage\b|\bdre\b|digital rectal|"
    r"prior[- ]biopsy status|\bcspca\b|csPCa|psa (value|level|result)|headline psa",
    re.I,
)

#: …salvo que la pregunta apunte a algo que sólo vive DENTRO de un documento. Una
#: pregunta puede nombrar el PI-RADS y seguir siendo legítima si lo que pide es
#: la prosa que hay detrás: la comparación con un estudio anterior, el grado
#: previo, la trayectoria. Eso es lo que distingue "¿cuál es el PSA density?" de
#: "¿registran las notas el grado de la biopsia previa?".
DOCUMENT_CONCEPT = re.compile(
    # una comparación cuenta sólo si es contra un estudio anterior, no contra un
    # umbral: "compare against an earlier MRI" sí, "compare against 0.15" no
    r"earlier|previous|prior (mri|study|scan|imaging|report|note)|unchanged|interval|"
    r"trend|trajector|serial|over time|rising|velocit|"
    r"note|record(ed|s)?\b|document(ed)?|"
    r"gleason|isup|grade group|\bgrade\b|surveillance|protocol|treatment|management|plan|"
    r"laborator|free[- ]?psa|infect|prostatit|creatinin|coagul|testoster|haemoglobin|hemoglobin|"
    r"lesion (size|zone|location)|extraprostatic|zone|prose|report say",
    re.I,
)


def drops_panel_question(question: str) -> bool:
    """¿La pregunta pide un valor que el panel ya imprime, y sólo eso?

    Medido en el piloto: el especialista en la guía pedía «the PSA density» bajo
    *lo que aún nos falta*, el moderador lo convertía en pregunta abierta, el
    registrador salía a buscarlo y el verificador acababa autorizando un cuarto
    documento — todo para recuperar un número que estaba en la intervención 1.
    Se corta aquí, además de en los dos prompts, porque es la clase de regla que
    se puede comprobar en vez de pedir por favor.
    """
    q = question or ""
    return bool(PANEL_VALUE.search(q)) and not DOCUMENT_CONCEPT.search(q)


#: Suelo del plan, medido: el urólogo abrió el informe de imagen en el 97 % de
#: los 91 casos y la serie de PSA en el 87 %. Pedir los dos cuesta ~0.013 de
#: precisión frente a pedir sólo el primero, y a cambio pone sobre la mesa la
#: trayectoria del PSA, que es una de las cuatro cosas de las que depende esta
#: decisión. El moderador conserva el tercer hueco para lo que el caso pida.
FLOOR = (
    ("radiology_report",
     "Does the mpMRI prose compare against an earlier study, and is the lesion new, larger or "
     "unchanged?"),
    ("psa_trend",
     "What shape does the serial PSA have — rising, flat, falling or oscillating — and over what "
     "period?"),
)

#: Nunca se pide: 0 de 91. Cada llamada es precisión regalada.
NEVER = ("family_history",)

#: Techo normal de revelaciones por caso, y el máximo absoluto que el verificador
#: puede autorizar una sola vez cuando nombra un dato decisivo que falta.
MAX_REVEALS = 3
HARD_CAP = 4


class Roster:
    """El catálogo real de esta corrida, derivado de las herramientas MCP vivas."""

    def __init__(self, tools: list[Any]) -> None:
        self.names = [t.name for t in tools]
        self.tools = list(tools)
        #: secciones que de verdad se pueden abrir en esta tarea, ordenadas por
        #: la frecuencia con que el urólogo las abrió
        self.sections = sorted(
            (SECTION_BY_TOOL[n] for n in self.names if n in SECTION_BY_TOOL),
            key=lambda s: -UROLOGIST_RATE.get(s, 0.0),
        )
        self.has_guidelines = GUIDELINE_TOOL in self.names

    # -- consultas -----------------------------------------------------------

    def guideline_tools(self) -> list[Any]:
        return [t for t in self.tools if t.name == GUIDELINE_TOOL]

    def document_tools(self) -> list[Any]:
        """Herramientas de documento que sí conviene ofrecer (sin las de 0/91)."""
        return [t for t in self.tools
                if t.name in SECTION_BY_TOOL and SECTION_BY_TOOL[t.name] not in NEVER]

    def tool_for(self, section: str) -> str | None:
        name = TOOL_BY_SECTION.get(section)
        return name if name in self.names else None

    def catalogue(self) -> str:
        """La tabla que se le enseña al moderador. Sólo lo que existe."""
        rows = []
        for section in self.sections:
            if section in NEVER:
                continue
            rate = UROLOGIST_RATE.get(section, 0.0)
            rows.append(f"  {section:<20} ({self.tool_for(section)})\n"
                        f"      gives: {WHAT_IT_ADDS[section]}\n"
                        f"      the reading urologist opened it in {rate:.0%} of the 91 labelled cases")
        never = [s for s in self.sections if s in NEVER]
        tail = ""
        if never:
            tail = ("\n  Deliberately NOT on the menu: " + ", ".join(never)
                    + " — the reading urologist never asked for it in this decision, so opening it "
                      "only costs precision.")
        free = ("\n  search_guidelines is free: it is not a patient document, it costs no precision, "
                "and it may be used whenever a threshold is genuinely in doubt." if self.has_guidelines else "")
        return "\n".join(rows) + tail + free


# ---------------------------------------------------------------------------
# El plan: una pregunta por documento
# ---------------------------------------------------------------------------


def clean_plan(
    raw: list[dict], roster: Roster, already_open: list[str], budget: int,
) -> tuple[list[dict], list[str]]:
    """Deja el plan del moderador en lo que de verdad se puede y se debe abrir.

    Devuelve ``(plan, motivos del recorte)``. Cada elemento del plan es
    ``{"section", "tool", "question"}``. Cuatro filtros, en este orden:

    1. la sección tiene que existir en esta tarea (contra la patología inventada);
    2. no puede estar ya abierta (nadie abre dos veces);
    3. el laboratorio necesita una de sus tres preguntas por escrito;
    4. el presupuesto de revelaciones manda.
    """
    out: list[dict] = []
    notes: list[str] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        section = str(item.get("section") or item.get("document") or "").strip()
        question = " ".join(str(item.get("question") or "").split())
        tool = roster.tool_for(section)

        if tool is None:
            if section:
                notes.append(f"'{section}' is not a document that exists in this task; dropped.")
            continue
        if section in NEVER:
            notes.append(f"{section} dropped: the reading urologist never opened it in this decision.")
            continue
        if section in already_open or any(p["section"] == section for p in out):
            continue
        if section == "laboratory_results" and not LAB_JUSTIFIED.search(question):
            notes.append(
                "laboratory_results dropped: requested without naming one of the three questions "
                "that justify it (free-PSA fraction, infection or prostatitis explaining the PSA, "
                "fitness for the procedure). The DRE and the headline PSA are already on the panel."
            )
            continue
        out.append({"section": section, "tool": tool,
                    "question": question or "what does it add beyond the visible panel?"})

    if len(out) > budget:
        dropped = [p["section"] for p in out[budget:]]
        out = out[:budget]
        if dropped:
            notes.append(
                f"Reveal budget is {budget} more document(s) in this session; deferred "
                f"{', '.join(dropped)}. Every extra reveal is scored on precision."
            )
    return out, notes


def apply_floor(plan: list[dict], roster: Roster, already_open: list[str],
                budget: int) -> tuple[list[dict], list[str]]:
    """Añade al plan los documentos del suelo (:data:`FLOOR`) que falten y quepan.

    Sólo se aplica en el primer pase: en una reapertura esos documentos ya están
    abiertos, así que la función es inerte por construcción.
    """
    notes: list[str] = []
    have = {p["section"] for p in plan} | set(already_open)
    for section, question in FLOOR:
        if len(plan) >= budget:
            break
        tool = roster.tool_for(section)
        if tool is None or section in have:
            continue
        plan.append({"section": section, "tool": tool, "question": question})
        have.add(section)
        notes.append(f"{section} was added to the plan: the reading urologist opened it in "
                     f"{UROLOGIST_RATE[section]:.0%} of the labelled cases, and it carries a fact "
                     "this decision turns on.")
    return plan, notes


def default_plan(payload: dict, roster: Roster, already_open: list[str], budget: int) -> list[dict]:
    """Plan mínimo cuando el moderador no devuelve un JSON legible.

    Sale de lo medido: imagen y serie de PSA casi siempre, y las notas previas
    cuando hay una biopsia previa — que es el único cubo donde vive el grado
    anterior y el plan de manejo, o sea donde las notas deciden de verdad.
    """
    bx = str(payload.get("bx") or "None")
    wanted = [
        ("radiology_report", "Does the mpMRI compare against an earlier study, and is the lesion "
                             "new, larger or unchanged?"),
        ("psa_trend", "What is the shape of the serial PSA: rising, flat, or oscillating?"),
    ]
    if bx in ("Positive", "Negative", "ASAP/HGPIN"):
        wanted.append(("previous_notes",
                       "Is the prior biopsy grade documented, is there a surveillance protocol, "
                       "and is any treatment already agreed?"))
    raw = [{"section": s, "question": q} for s, q in wanted]
    plan, _ = clean_plan(raw, roster, already_open, budget)
    return plan


def render_plan(plan: list[dict], questions: list[str], notes: list[str],
                need_image: bool, pass_: int) -> str:
    """El plan del moderador, dicho como se diría en una sala."""
    lines: list[str] = []
    if pass_ == 1:
        lines.append("Before anyone argues, this is what I want established, and by whom.")
    else:
        lines.append(f"We are reopening (pass {pass_}). This is what the verifier says is still "
                     "missing, and how I want it closed.")
    lines.append("")

    if plan:
        lines.append("REGISTRAR — pull these up, and answer exactly the question attached to each:")
        for p in plan:
            lines.append(f"  {p['section']} ({p['tool']}) -> {p['question']}")
    else:
        lines.append("REGISTRAR — nothing further to pull up: either the panel settles this or the "
                     "documents worth opening are already open. Do not open anything else.")
    lines.append("")

    if need_image:
        lines.append("EXPERT-IMAGE — give us what the frozen MRI vectors contribute, and say plainly "
                     "how much it is worth.")
        lines.append("")

    if questions:
        lines.append("OPEN QUESTIONS for this conference — these are what the decision hangs on, and "
                     "I expect them answered by name, not in general terms:")
        for i, q in enumerate(questions, 1):
            lines.append(f"  Q{i}. {q}")
        lines.append("")

    if notes:
        lines.append("On the plan itself: " + " ".join(notes))
    return "\n".join(lines).strip()
