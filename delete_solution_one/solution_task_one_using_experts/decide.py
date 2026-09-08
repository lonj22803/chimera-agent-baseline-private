"""Cierre del caso, y las guardias que no se le piden por favor a un modelo.

Heredado de la junta anterior —``reveal_sequence`` derivada de las
herramientas que de verdad se ejecutaron, guardia de procedencia, guardia de
aterrizaje, respaldo determinista— más **una guardia nueva** que sale de leer
lo que el urólogo lector escribió en los 49 casos con biopsia previa positiva:

:func:`documented_grade`
    Busca en lo que las herramientas devolvieron (no en lo que el LLM resumió)
    el grado de la biopsia previa: ISUP grade group o Gleason. En la serie
    etiquetada, cuando el grado está documentado el urólogo decide con él —
    GG ≥ 2 es un problema de tratamiento y no se re-biopsia (7 de 8); GG 1 en
    vigilancia se confirma con una nueva biopsia (3 de 4). Es un hecho que un
    modelo de lenguaje pequeño lee mal (escribe "ISUP 2" donde el documento
    dice "Gleason 3+4", o al revés), así que se extrae con una expresión
    regular sobre el texto crudo y se deja en el acta con la cita.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import ToolMessage

from .roster import SECTION_BY_TOOL

log = logging.getLogger(__name__)


def reveal_sequence_from_messages(messages: list) -> list[str]:
    """Secciones realmente reveladas, en orden de primera aparición."""
    out: list[str] = []
    for message in messages:
        if not isinstance(message, ToolMessage) or not message.name:
            continue
        section = SECTION_BY_TOOL.get(message.name)
        if section is not None and section not in out:
            out.append(section)
    return out


def called_tools_from_messages(messages: list) -> set[str]:
    return {m.name for m in messages if isinstance(m, ToolMessage) and m.name}


def tool_corpus(messages: list, only: set[str] | None = None) -> str:
    """Todo lo que las herramientas devolvieron, concatenado."""
    parts = []
    for m in messages:
        if isinstance(m, ToolMessage) and m.content and (only is None or m.name in only):
            parts.append(m.content if isinstance(m.content, str) else str(m.content))
    return "\n".join(parts)


def extract_json_object(text: str) -> str:
    if not text:
        return text
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start: i + 1]
    return text[start:]


def parse_json(text: str) -> dict:
    raw = extract_json_object(text or "")
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


# ---------------------------------------------------------------------------
# La guardia de procedencia: ningún número sin fuente
# ---------------------------------------------------------------------------

_VALUE = re.compile(r"\b\d+[.,]\d+\b|\b\d{3,}\b")
_YEAR = re.compile(r"^(19|20)\d{2}$")


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(",", "."))


def unsourced_values(report: str, corpus: str, panel: str, limit: int = 6) -> list[str]:
    """Valores del informe que no aparecen ni en las herramientas ni en el panel."""
    haystack = _normalise(corpus) + " " + _normalise(panel)
    out: list[str] = []
    for raw in _VALUE.findall(report or ""):
        value = raw.replace(",", ".")
        if _YEAR.match(value.split(".")[0]) and "." not in value:
            continue
        if value in haystack or value.rstrip("0").rstrip(".") in haystack:
            continue
        if value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# El grado documentado de la biopsia previa, leído del texto crudo
# ---------------------------------------------------------------------------

_ISUP = re.compile(r"\bISUP\s*(?:grade\s*group\s*|grade\s*|GG\s*)?(\d)\b", re.I)
_GG = re.compile(r"\b(?:grade\s*group|GG)\s*(\d)\b", re.I)
_GLEASON = re.compile(r"\bGleason\s*(?:score\s*)?(?:of\s*)?(\d)\s*\+\s*(\d)\b", re.I)
_GLEASON_SUM = re.compile(r"\bGleason\s*(?:score\s*)?(?:of\s*)?(6|7|8|9|10)\b(?!\s*\+)", re.I)
_SURVEILLANCE = re.compile(r"active surveillance|surveillance (protocol|programme|program|pathway)|"
                           r"under surveillance|on surveillance", re.I)
_SESSION = re.compile(r"biops(y|ies)", re.I)


def _gg_from_gleason(a: int, b: int) -> int:
    s = a + b
    if s <= 6:
        return 1
    if s == 7:
        return 2 if a == 3 else 3
    if s == 8:
        return 4
    return 5


def documented_grade(corpus: str) -> dict[str, Any]:
    """Grado de la biopsia previa tal como lo recogen los documentos abiertos.

    Devuelve ``gg`` (1-5) y la cita literal, o ``gg=None`` si ningún documento
    abierto lo recoge. Si hay varias menciones se toma la más alta: es lo que
    manda en la decisión de tratar.
    """
    text = corpus or ""
    found: list[tuple[int, str]] = []
    for m in _ISUP.finditer(text):
        found.append((int(m.group(1)), m.group(0)))
    for m in _GG.finditer(text):
        found.append((int(m.group(1)), m.group(0)))
    for m in _GLEASON.finditer(text):
        found.append((_gg_from_gleason(int(m.group(1)), int(m.group(2))), m.group(0)))
    for m in _GLEASON_SUM.finditer(text):
        s = int(m.group(1))
        found.append(({6: 1, 7: 2, 8: 4, 9: 5, 10: 5}[s], m.group(0)))
    found = [(g, q) for g, q in found if 1 <= g <= 5]
    gg, quote = (max(found, key=lambda t: t[0]) if found else (None, None))
    return {
        "gg": gg,
        "quote": quote,
        "mentions": [q for _, q in found][:6],
        "on_surveillance": bool(_SURVEILLANCE.search(text)),
        "biopsy_mentions": len(_SESSION.findall(text)),
    }


# ---------------------------------------------------------------------------
# Líneas mecánicas del verificador y del registrador
# ---------------------------------------------------------------------------

_VERDICT_LINE = re.compile(
    r"VERDICT:\s*(ready|not-?ready)\s*\|\s*SUGGEST:\s*(biopsy|defer)\s*\|\s*MISSING:\s*([^\n|]*)",
    re.I)


def verifier_line(body: str) -> dict[str, Any]:
    m = None
    for m in _VERDICT_LINE.finditer(body or ""):
        pass
    if m is None:
        return {"ready": True, "suggest": None, "missing": None, "parsed": False}
    missing = m.group(3).strip().strip(".").lower()
    return {
        "ready": m.group(1).lower().replace("-", "") == "ready",
        "suggest": m.group(2).lower(),
        "missing": None if missing in ("", "none", "nothing", "n/a") else missing,
        "parsed": True,
    }


_LEAN_TOKEN = re.compile(r"^\s*LEAN:\s*(biopsy|defer|unclear)\s*$", re.I | re.M)


def registrar_lean(body: str) -> str | None:
    tokens = _LEAN_TOKEN.findall(body or "")
    if not tokens:
        return None
    return {"biopsy": "yes", "defer": "no", "unclear": None}[tokens[-1].lower()]


# ---------------------------------------------------------------------------
# Aterrizaje y respaldo
# ---------------------------------------------------------------------------

_SECTION_OF = {
    "pirads": "radiology_report", "psad": "radiology_report", "vol": "radiology_report",
    "cspca": "radiology_report", "dre": "laboratory_results", "fh": "family_history",
}

#: ``bx`` se aterriza con ``pathology_report``, que no existe en la tarea 1: es
#: un ungrounded inevitable, y se deja pesar porque lo que gana en
#: ``variable_weight_score`` e ``important_decisive_factor_score`` supera lo
#: que cuesta en grounding (medido en la generación anterior y de nuevo aquí:
#: quitarlo cuesta ~0.05 de case score y devuelve ~0.03).
_UNGROUNDABLE_BY_DESIGN = ("bx",)


def enforce_grounding(structured: dict[str, Any], revealed: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Baja a ``not_used`` toda variable cuya sección no se abrió."""
    weights = dict(structured.get("variable_weights") or {})
    downgraded: list[str] = []
    for var, section in _SECTION_OF.items():
        if weights.get(var, "not_used") != "not_used" and section not in revealed:
            weights[var] = "not_used"
            downgraded.append(var)
    out = dict(structured)
    out["variable_weights"] = weights
    return out, downgraded


def fallback_reasoning(payload: dict[str, Any], protocol: dict[str, Any]) -> str:
    """Prosa determinista para cuando el presidente no entrega un formulario válido."""
    decision = protocol.get("decision") == "yes"
    bx = str(payload.get("bx") or "not recorded")
    return (
        f"Decision to {'proceed with biopsy' if decision else 'defer biopsy'} for a "
        f"{payload.get('age')}-year-old man with PI-RADS {payload.get('pirads')}, PSA "
        f"{payload.get('psa')} ng/mL, PSA density {payload.get('psad')} and a prior biopsy status "
        f"of '{bx}'. The panel protocol settled it by the rule '{protocol.get('rule')}' "
        f"({protocol.get('who')}); {protocol.get('track') or ''} The conference did not return a "
        "readable structured form, so this record was completed from the minute alone; no finding "
        "is asserted beyond the values in it."
    )


def to_gc_outputs(structured: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    decision = "yes" if structured["biopsy_decision"] else "no"
    reasoning = {
        "confidence": structured["confidence"],
        "variable_weights": structured["variable_weights"],
        "reveal_sequence": structured["reveal_sequence"],
        "free_text": structured["reasoning"],
    }
    return decision, reasoning
