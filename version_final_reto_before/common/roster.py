"""Qué herramientas EXISTEN de verdad en la tarea 1, y cuánto cuesta cada una.

Heredado de la junta anterior con un cambio de fondo: **el plan ya no lo
inventa el moderador**. Lo fija EXPERT-TRACE —el modelo de traza del urólogo
lector, reforzado por los precedentes— y el moderador sólo reparte las
preguntas. La razón está medida: ``tool_score`` es precisión contra lo que el
urólogo abrió, y lo que el urólogo abre depende del caso de forma que un
modelo entrenado sobre sus 91 trazas predice mejor que cualquier lista escrita
a mano.

``tool_score`` del evaluador oficial::

    score = |secciones abiertas ∩ secciones que abrió el urólogo| / |secciones abiertas|

Abrir de menos es gratis; abrir de más se paga. Frecuencia con la que el
urólogo abrió cada sección en los 91 casos etiquetados: imagen 97 %, serie de
PSA 87 %, notas previas 85 %, laboratorio 45 %, antecedentes familiares 0 %.
"""

from __future__ import annotations

import re
from typing import Any

#: Herramienta -> sección del vocabulario de ``Task1Output.reveal_sequence``.
SECTION_BY_TOOL: dict[str, str] = {
    "get_mri_report": "radiology_report",
    "get_psa_trend": "psa_trend",
    "get_previous_notes": "previous_notes",
    "get_lab_results": "laboratory_results",
    "get_family_history": "family_history",
}
TOOL_BY_SECTION: dict[str, str] = {v: k for k, v in SECTION_BY_TOOL.items()}
GUIDELINE_TOOL = "search_guidelines"

#: Cuántas veces de 91 abrió el urólogo cada sección.
UROLOGIST_RATE: dict[str, float] = {
    "radiology_report": 0.97, "psa_trend": 0.87, "previous_notes": 0.85,
    "laboratory_results": 0.45, "family_history": 0.00,
}

#: Qué aporta cada documento, en una línea, para el moderador.
WHAT_IT_ADDS: dict[str, str] = {
    "radiology_report": ("the mpMRI prose behind PI-RADS: lesion size and zone, extraprostatic "
                         "extension, and whether it is compared against an earlier study"),
    "psa_trend": "the serial PSA values behind the single headline number: rising, flat or falling",
    "previous_notes": ("the management context: what the prior biopsy showed (Gleason / ISUP), "
                       "whether there is a surveillance protocol, how many biopsy sessions there "
                       "were and when, what is already planned"),
    "laboratory_results": ("the full panel: free-PSA fraction, renal function, haemoglobin, and "
                           "where the DRE finding is filed"),
    "family_history": "first-degree family history. The reading urologist asked for it in 0 of 91 cases",
}

#: La pregunta que cada documento tiene que contestar, si el moderador no
#: escribe una mejor. Salen del criterio del urólogo lector (§2 del README).
DEFAULT_QUESTION: dict[str, str] = {
    "radiology_report": ("Does the mpMRI prose compare against an earlier study, and is the lesion "
                         "new, larger or unchanged? Size and zone of the index lesion."),
    "psa_trend": ("What shape does the serial PSA have — rising, flat, falling or oscillating — "
                  "over what period, and does the last value confirm the headline?"),
    "previous_notes": ("Is the grade of the prior biopsy recorded (Gleason or ISUP)? How many biopsy "
                       "sessions, and when was the last? Is he on a surveillance protocol, and is a "
                       "confirmatory biopsy due? Is any treatment already agreed or declined?"),
    "laboratory_results": ("Free-PSA fraction, and anything that would explain the PSA (infection, "
                           "prostatitis) or bear on fitness for the procedure (renal function, "
                           "coagulation)."),
}

#: Las tres preguntas que justifican abrir el laboratorio cuando el modelo de
#: traza NO lo pide y el verificador lo nombra.
LAB_JUSTIFIED = re.compile(
    r"free[- ]?psa|prostatit|infect|uti\b|urinary tract|coagul|renal|creatinin|egfr|"
    r"fitness|anticoagul|platelet|inr\b|testoster", re.I)

#: Los valores que el panel ya imprime. Preguntar por ellos manda al registrador
#: a abrir un documento para recuperar un número que ya está sobre la mesa.
PANEL_VALUE = re.compile(
    r"psa[- ]?densit|\bpsad\b|pi-?rads|prostate volume|\bage\b|\bdre\b|digital rectal|"
    r"prior[- ]biopsy status|\bcspca\b|csPCa|psa (value|level|result)|headline psa", re.I)

DOCUMENT_CONCEPT = re.compile(
    r"earlier|previous|prior (mri|study|scan|imaging|report|note|biops)|unchanged|interval|"
    r"trend|trajector|serial|over time|rising|velocit|"
    r"note|record(ed|s)?\b|document(ed)?|"
    r"gleason|isup|grade group|\bgrade\b|surveillance|protocol|treatment|management|plan|"
    r"session|confirmator|"
    r"laborator|free[- ]?psa|infect|prostatit|creatinin|coagul|testoster|haemoglobin|hemoglobin|"
    r"lesion (size|zone|location)|extraprostatic|zone|prose|report say", re.I)


def drops_panel_question(question: str) -> bool:
    """¿La pregunta pide un valor que el panel ya imprime, y sólo eso?"""
    q = question or ""
    return bool(PANEL_VALUE.search(q)) and not DOCUMENT_CONCEPT.search(q)


NEVER = ("family_history",)
HARD_CAP = 4


class Roster:
    """El catálogo real de esta corrida, derivado de las herramientas MCP vivas."""

    def __init__(self, tools: list[Any]) -> None:
        self.names = [t.name for t in tools]
        self.tools = list(tools)
        self.sections = sorted(
            (SECTION_BY_TOOL[n] for n in self.names if n in SECTION_BY_TOOL),
            key=lambda s: -UROLOGIST_RATE.get(s, 0.0),
        )
        self.has_guidelines = GUIDELINE_TOOL in self.names

    def guideline_tools(self) -> list[Any]:
        return [t for t in self.tools if t.name == GUIDELINE_TOOL]

    def document_tools(self) -> list[Any]:
        return [t for t in self.tools
                if t.name in SECTION_BY_TOOL and SECTION_BY_TOOL[t.name] not in NEVER]

    def tool_for(self, section: str) -> str | None:
        name = TOOL_BY_SECTION.get(section)
        return name if name in self.names else None

    def catalogue(self) -> str:
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
                    + " — the reading urologist never asked for it in this decision.")
        free = ("\n  search_guidelines is free: it is not a patient document and costs no precision."
                if self.has_guidelines else "")
        return "\n".join(rows) + tail + free


# ---------------------------------------------------------------------------
# El plan: fijado por EXPERT-TRACE, preguntas del moderador
# ---------------------------------------------------------------------------


def plan_from_sections(sections: list[str], roster: Roster, already_open: list[str],
                       questions_by_section: dict[str, str] | None = None) -> list[dict]:
    """El plan del pase: exactamente las secciones predichas que existen y no están abiertas."""
    out: list[dict] = []
    qs = questions_by_section or {}
    for section in sections:
        tool = roster.tool_for(section)
        if tool is None or section in NEVER or section in already_open:
            continue
        if any(p["section"] == section for p in out):
            continue
        q = " ".join(str(qs.get(section) or "").split()) or DEFAULT_QUESTION.get(
            section, "what does it add beyond the visible panel?")
        out.append({"section": section, "tool": tool, "question": q})
    return out


def moderator_questions_by_section(raw_plan: list[dict]) -> dict[str, str]:
    """Las preguntas que el moderador adjuntó a cada documento, si escribió alguna."""
    out: dict[str, str] = {}
    for item in raw_plan or []:
        if not isinstance(item, dict):
            continue
        section = str(item.get("section") or item.get("document") or "").strip()
        question = " ".join(str(item.get("question") or "").split())
        if section and question:
            out[section] = question
    return out


def render_plan(plan: list[dict], questions: list[str], notes: list[str],
                need_image: bool, pass_: int, fixed_by: str) -> str:
    lines: list[str] = []
    if pass_ == 1:
        lines.append(f"The documents for this session were fixed by {fixed_by}; what I add is the "
                     "question each one has to answer, and the open questions for the room.")
    else:
        lines.append(f"We are reopening (pass {pass_}). This is what is still missing, and how I "
                     "want it closed.")
    lines.append("")
    if plan:
        lines.append("REGISTRAR — pull these up, and answer exactly the question attached to each:")
        for p in plan:
            lines.append(f"  {p['section']} ({p['tool']}) -> {p['question']}")
    else:
        lines.append("REGISTRAR — nothing to pull up in this pass: the reading urologist decides "
                     "this kind of case on the panel, or everything worth opening is already open. "
                     "Do not open anything else.")
    lines.append("")
    if need_image:
        lines.append("EXPERT-IMAGE — give us what the frozen MRI vectors contribute, and say plainly "
                     "how much it is worth.")
        lines.append("")
    if questions:
        lines.append("OPEN QUESTIONS for this conference — these are what the decision hangs on:")
        for i, q in enumerate(questions, 1):
            lines.append(f"  Q{i}. {q}")
        lines.append("")
    if notes:
        lines.append("On the plan itself: " + " ".join(notes))
    return "\n".join(lines).strip()
