"""El moderador de la pizarra: suficiencia al abrir, consenso al cerrar.

Es la pieza nueva de esta generación. En la versión anterior la pizarra era una
cadena de montaje: cada participante hablaba una vez, en orden fijo, y el
presidente decidía con lo que hubiera. Aquí hay alguien que **controla si la
sesión está en condiciones de decidir**, y que puede devolverla al principio.

Dos intervenciones:

``open``   antes de que hable ningún LLM. Mira lo que los expertos
           deterministas han puesto sobre la mesa y fija la **agenda**: qué
           documentos hay que abrir y qué pregunta debe contestar cada uno.
           Sirve para que L2 no recupere a bulto.

``close``  antes del veredicto. Comprueba dos cosas distintas que se confunden
           con facilidad:
             1. **suficiencia** — ¿se abrió lo que la agenda pedía, y contestó?
             2. **consenso** — ¿coinciden las posturas de los participantes?
           Si falla cualquiera de las dos y quedan rondas, **reabre la pizarra**.

Diseño híbrido, a propósito
---------------------------
El estado de la mesa (quién dijo qué, qué documentos se abrieron, si la agenda
se cumplió) es **determinista y se calcula aquí**, no se le pregunta al LLM: un
modelo pequeño no es fiable contando. Lo que sí aporta el LLM es la lectura
clínica de si lo recuperado *responde* a la pregunta, y la redacción de la
agenda. Si el LLM no devuelve un JSON legible, la regla determinista decide
igual y la sesión continúa: el moderador nunca puede bloquear un caso.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

#: Documentos que existen en la tarea 1, con la herramienta que los sirve.
DOCUMENTS = {
    "radiology_report": "get_mri_report",
    "psa_trend": "get_psa_trend",
    "previous_notes": "get_previous_notes",
    "laboratory_results": "get_lab_results",
}

ROLE = "moderator; owns the agenda and decides whether the conference may close"

#: Las tres preguntas que justifican abrir el panel de laboratorio. El urólogo
#: lo reveló en el 45 % de los casos etiquetados, así que es la excepción: si el
#: moderador lo pide sin nombrar una de ellas, se cae de la agenda.
_LAB_JUSTIFIED = re.compile(
    r"free[- ]?psa|prostatit|infect|uti\b|urinary tract|coagul|renal|creatinin|egfr|"
    r"fitness|anticoagul|platelet|inr\b",
    re.I,
)

#: Techo de documentos por agenda. Tres es lo normal; el cuarto necesita una de
#: las preguntas de arriba.
MAX_AGENDA = 3


def prune_agenda(agenda: list[str], questions: dict[str, str]) -> tuple[list[str], str | None]:
    """Aplica el techo de la agenda. Devuelve (agenda, motivo del recorte)."""
    out = [d for d in agenda if d in DOCUMENTS]
    reason = None
    if "laboratory_results" in out and not _LAB_JUSTIFIED.search(questions.get("laboratory_results", "")):
        out.remove("laboratory_results")
        reason = ("The laboratory panel was dropped from the agenda: it was requested without "
                  "naming one of the three questions that justify it (free-PSA fraction, "
                  "infection or prostatitis explaining the PSA, or fitness for the procedure). "
                  "The DRE and the headline PSA are already in the visible panel.")
    if len(out) > MAX_AGENDA:
        dropped = out[MAX_AGENDA:]
        out = out[:MAX_AGENDA]
        reason = ((reason + " ") if reason else "") + \
            f"Agenda capped at {MAX_AGENDA} documents; dropped {', '.join(dropped)}."
    return out, reason


# ---------------------------------------------------------------------------
# Parte determinista: el estado de la mesa
# ---------------------------------------------------------------------------


def stances(entries: list[dict]) -> dict[str, str | None]:
    """Postura de cada participante: ``'yes'``, ``'no'`` o ``None`` (se abstiene)."""
    out: dict[str, str | None] = {"prior": None, "protocol": None, "evidence": None}

    prior = next((e for e in reversed(entries) if e["speaker"] == "EXPERT-PRIOR"), None)
    if prior and prior.get("data", {}).get("prediccion") in ("yes", "no"):
        out["prior"] = prior["data"]["prediccion"]

    proto = next((e for e in reversed(entries) if e["speaker"] == "EXPERT-PROTOCOL"), None)
    if proto:
        out["protocol"] = proto.get("data", {}).get("verdict")

    ev = next((e for e in reversed(entries) if e["speaker"] == "LLM-2-EVIDENCE"), None)
    if ev:
        out["evidence"] = evidence_lean(ev["body"])
    return out


#: Token explícito con el que L2 cierra su informe. Se prefiere a cualquier
#: heurística sobre la prosa: la primera versión de este detector leía la
#: cabecera "AGAINST sampling this patient now" como si fuera la conclusión, y
#: clasificó la postura como 'defer' en 88 de 90 casos medidos. Un token que el
#: propio participante escribe no tiene ese problema.
_LEAN_TOKEN = re.compile(r"^\s*LEAN:\s*(biopsy|defer|unclear)\s*$", re.I | re.M)

#: Respaldo por prosa, aplicado SÓLO al texto que sigue a la cabecera de
#: conclusión, nunca al informe entero.
_LEAN_HEAD = re.compile(r"WHERE\s+THIS\s+LEANS", re.I)
_PRO = re.compile(r"re-?biops|biopsy is|sampling (is )?(warrant|indicat|support)|"
                  r"support\w* (a )?(re-?)?biops|warrant\w* (a )?(re-?)?biops|"
                  r"further investigation|toward\w* (recommending )?(a )?(re-?)?biops", re.I)
_CON = re.compile(r"defer|surveillance rather than|no biopsy|against (a )?(re-?)?biops|"
                  r"not (warrant|indicat|support)\w*", re.I)


def evidence_lean(body: str) -> str | None:
    """Postura de LLM-2: ``'yes'``, ``'no'`` o ``None`` si no se pronuncia."""
    tokens = _LEAN_TOKEN.findall(body or "")
    if tokens:
        last = tokens[-1].lower()
        return {"biopsy": "yes", "defer": "no", "unclear": None}[last]

    head = _LEAN_HEAD.search(body or "")
    if not head:
        return None
    tail = body[head.end():]
    tail = tail.split("[Opened in this round")[0].split("[WARNING FOR THE CHAIR")[0]
    pro, con = len(_PRO.findall(tail)), len(_CON.findall(tail))
    return "yes" if pro > con else ("no" if con > pro else None)


def agenda_status(agenda: list[str], revealed: list[str]) -> dict[str, Any]:
    """Qué pedía la agenda y qué se abrió de verdad."""
    wanted = [d for d in agenda if d in DOCUMENTS]
    missing = [d for d in wanted if d not in revealed]
    return {
        "requested": wanted,
        "revealed": list(revealed),
        "missing": missing,
        "fulfilled": not missing,
        "extra": [d for d in revealed if d not in wanted],
    }


def consensus(st: dict[str, str | None]) -> dict[str, Any]:
    """Consenso = las posturas que se pronuncian no se contradicen."""
    voiced = [v for v in st.values() if v in ("yes", "no")]
    if not voiced:
        return {"reached": False, "reason": "no participant took a position", "votes": st}
    agree = len(set(voiced)) == 1
    counts = {v: voiced.count(v) for v in set(voiced)}
    return {
        "reached": agree,
        "reason": "unanimous among those who took a position" if agree
        else f"split {counts}",
        "votes": st,
        "n_voiced": len(voiced),
    }


def default_agenda(prompt: dict, proto: dict | None) -> list[str]:
    """Agenda mínima cuando el LLM no devuelve una legible.

    Sale de lo medido en los 91 casos etiquetados: el urólogo abrió el informe
    de imagen en el 97 % de los casos, la serie de PSA en el 87 % y las notas
    previas en el 85 %; el laboratorio sólo en el 45 %. Y el cubo con biopsia
    previa positiva es el único donde las notas deciden de verdad, porque es
    donde vive el grado previo y el plan de manejo.
    """
    bx = str(prompt.get("bx") or "None")
    agenda = ["radiology_report", "psa_trend"]
    if bx in ("Positive", "Negative", "ASAP/HGPIN") or (proto or {}).get("verdict") is None:
        agenda.append("previous_notes")
    return agenda


# ---------------------------------------------------------------------------
# Parte LLM: la lectura clínica
# ---------------------------------------------------------------------------


def parse_json(text: str) -> dict:
    """Primer objeto JSON balanceado del texto; ``{}`` si no hay ninguno."""
    if not text:
        return {}
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = fence.group(1) if fence else None
    if raw is None:
        start = text.find("{")
        if start < 0:
            return {}
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    raw = text[start : i + 1]
                    break
        if raw is None:
            return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def render_open(agenda: list[str], question_map: dict[str, str], note: str, round_: int) -> str:
    lines = [
        f"AGENDA FOR ROUND {round_}. These are the documents this case needs opened, and the "
        "question each one must answer. Open these and nothing else unless a named question "
        "requires it.",
        "",
    ]
    for doc in agenda:
        q = question_map.get(doc) or "what does it add beyond the visible panel?"
        lines.append(f"  - {doc} ({DOCUMENTS[doc]}) -> {q}")
    if not agenda:
        lines.append("  (no document is required: the panel already settles this case)")
    if note:
        lines += ["", note]
    return "\n".join(lines)


def render_close(status: dict, cons: dict, reopen: bool, reason: str, round_: int,
                 max_rounds: int) -> str:
    head = "THE CONFERENCE MAY CLOSE." if not reopen else f"REOPENING THE BLACKBOARD (round {round_ + 1} of {max_rounds})."
    votes = ", ".join(f"{k}={v or 'abstains'}" for k, v in cons["votes"].items())
    lines = [
        head,
        "",
        f"Positions on the table: {votes}.",
        f"Consensus: {'yes' if cons['reached'] else 'no'} — {cons['reason']}.",
        f"Agenda: requested {status['requested'] or 'nothing'}; "
        f"opened {status['revealed'] or 'nothing'}; "
        f"still missing {status['missing'] or 'nothing'}.",
    ]
    if reason:
        lines += ["", reason]
    if reopen and status["missing"]:
        lines += [
            "",
            "WHY: the agenda is not fulfilled. LLM-2 must open what is still missing "
            f"({', '.join(status['missing'])}) and answer the question attached to it. "
            "Everyone else: address what that document changes, and do not repeat what "
            "round 1 already established.",
        ]
    elif reopen:
        lines += [
            "",
            "WHY: the agenda WAS fulfilled and the participants still disagree, so this is a "
            "disagreement about INTERPRETATION, not about missing data. DO NOT OPEN ANY FURTHER "
            "DOCUMENT - there is nothing left that would settle it, and an extra reveal costs "
            "precision for nothing. Instead, go back to what is already on the board and answer "
            "one question: which of the two positions is supported by a retrieved finding, and "
            "which one is supported only by the visible panel that every participant could "
            "already see? Name that finding.",
        ]
    else:
        lines += ["", "The chair decides on the record as it stands."]
    return "\n".join(lines)
