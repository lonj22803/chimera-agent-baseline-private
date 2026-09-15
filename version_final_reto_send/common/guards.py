"""Guardias compartidas de procedencia, lenguaje y salida."""

from __future__ import annotations

import re
import json
from typing import Any

from langchain_core.messages import ToolMessage
from .roster import SECTION_BY_TOOL

_VALUE = re.compile(r"\b\d+[.,]\d+\b|\b\d{3,}\b")


_YEAR = re.compile(r"^(19|20)\d{2}$")


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(",", "."))


def unsourced_values(report: str, corpus: str, panel: str, limit: int = 6) -> list[str]:
    """Valores del informe que no aparecen en ninguna de las fuentes dadas.

    ``panel`` se pasa concatenado con todo lo que ya está en el acta: en la
    generación anterior la guardia marcaba el umbral 0.15 ng/mL² dieciséis
    veces, y ese número no es una alucinación — está en la intervención del
    especialista en la guía. Un falso positivo repetido enseña a ignorar la
    guardia, así que se corrige la guardia.
    """
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


_GRADE_CLAIM = re.compile(
    r"\bISUP\s*(?:grade\s*group\s*|grade\s*|GG\s*)?\d\b|\b(?:grade\s*group|GG)\s*\d\b|"
    r"\bGleason\s*(?:score\s*)?\d\s*\+\s*\d\b|\bGleason\s*(?:score\s*)?(?:6|7|8|9|10)\b", re.I)


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def unsourced_grades(text: str, corpus: str) -> list[str]:
    """Grados que el texto afirma y que no están en el corpus recuperado."""
    hay = _squash(corpus)
    def canonical(fragment):
        if not fragment.lower().startswith('gleason'):
            return 'isup' + re.search(r'\d', fragment).group()
        return re.sub(r'gleasonscore', 'gleason', _squash(fragment))
    recorded = {canonical(m.group()) for m in _GRADE_CLAIM.finditer(corpus or '')}
    out: list[str] = []
    for m in _GRADE_CLAIM.finditer(text or ""):
        frag = m.group(0).strip()
        if (_squash(frag) not in hay and canonical(frag) not in recorded
                and frag.lower() not in {o.lower() for o in out}):
            out.append(frag)
    return out


_PROCESS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("expert", re.compile(r"\bexpert[-\s]?(?:one|two|three|four|1|2|3|4|classifier|cohort|library|trace|"
                          r"psa|fusion|image|eau)\b|\bexperts?\b", re.I)),
    ("panel protocol", re.compile(r"\bpanel[-\s]?protocol\b|\bthe protocol\b|\bprotocol (?:answered|was|"
                                  r"settled|carried|triggered|says|states|indicates)\b", re.I)),
    ("the panel", re.compile(r"\bthe panel\b(?!\s+(?:of\s+)?(?:blood|labs?|laboratory|bloods))|"
                             r"\bpanel(?:'s)? (?:answer|decision|position|configuration)\b", re.I)),
    ("criterion / rule", re.compile(r"\bcohort criterion\b|\bthe criterion\b|\bcriteria (?:used|applied)\b|"
                                    r"\bthe rule\b|\brule (?:fired|applied|carried)\b", re.I)),
    ("classifier / model", re.compile(r"\bclassifier\b|\bthe model\b|\bmodels?\s+(?:predict|suggest|scored)\b|"
                                      r"\bmachine learning\b|\balgorithm\b", re.I)),
    # "high probability of undetected cancer" es prosa clinica legitima y aparece
    # en el ground truth; lo que no lo es son las probabilidades del modelo.
    ("probability / tier", re.compile(r"\bp\(biops\w*\)|\bprobabilit\w+\s*(?:of\s*)?[=:]?\s*0?\.\d|"
                                      r"\b(?:predicted|estimated|calculated|computed|model)\s+probabilit\w+|"
                                      r"\bcspca probabilit\w+|\breliability tier\b|"
                                      r"\b(?:firm|supports|discuss) tier\b|\bout[-\s]of[-\s]fold\b|"
                                      r"\bconfidence interval\b|\berror bar\b", re.I)),
    ("precedent / series", re.compile(r"\bprecedent\w*\b|\bcase librar\w+\b|\blabelled (?:series|case)\w*\b|"
                                      r"\blabeled (?:series|case)\w*\b|\bcohort of \d+\b|\bsimilar cases in\b",
                                      re.I)),
    ("conference / minute", re.compile(r"\bconferenc\w+\b|\bthe minute\b|\bintervention \d+\b|"
                                       r"\bmultidisciplinar\w+\b|\bmdt\b|\bthe meeting\b|\bthe board\b|"
                                       r"\bcase discussion\b", re.I)),
    ("roles", re.compile(r"\bregistrar\b|\bverifier\b|\bmoderator\b|\bthe chair\b|\bcolleagues?\b|"
                         r"\bthe room\b|\breviewer\b|\bguideline specialist\b", re.I)),
    # El presidente no debe comentar la ausencia de una alternativa: «No
    # alternative plan.» al final de una nota clinica es lenguaje del formulario,
    # no del paciente. Medido: 1 de 8 en la corrida de prueba.
    ("meta-comment", re.compile(r"\bno alternative plan\b|\balternative plan (?:exists|is indicated|"
                                r"is available)\b|\bno further (?:plan|alternative) (?:exists|is indicated)\b",
                                re.I)),
    ("process verbs", re.compile(r"\bthe evidence converged\b|\bcarried the decision\b|"
                                 r"\bwas triggered by\b|\bconverged on\b|\bconsensus\b|"
                                 r"\bthis decision is supported by the\b|\bper the assessment\b|"
                                 r"\bthe assessment (?:was|is)\b", re.I)),
)


def process_language(text: str, limit: int = 6) -> list[str]:
    """Trozos de la nota que describen el procedimiento en vez de al paciente.

    Devuelve las coincidencias literales, para poder enseñárselas al modelo.
    """
    out: list[str] = []
    for _, pattern in _PROCESS_PATTERNS:
        for m in pattern.finditer(text or ""):
            frag = m.group(0).strip()
            if frag and frag.lower() not in {o.lower() for o in out}:
                out.append(frag)
            if len(out) >= limit:
                return out
    return out


def enforce_grounding(weights: dict, opened: list[str], section_of: dict) -> tuple[dict, list[str]]:
    """Baja a ``not_used`` toda variable cuya sección no se abrió."""
    weights = dict(weights)
    downgraded: list[str] = []
    for var, section in section_of.items():
        if weights.get(var, "not_used") != "not_used" and section not in opened:
            weights[var] = "not_used"
            downgraded.append(var)
    return weights, downgraded


def validate_output(task: int, payload: dict) -> tuple[bool, str]:
    """Valida el registro contra el esquema oficial de su tarea."""
    from chimera_agent_baseline.output.schema import Task1Output, Task2Output, Task3Output

    try:
        {1: Task1Output, 2: Task2Output, 3: Task3Output}[task](**payload)
        if task in (1, 2):
            from .vocab import VARIABLES_BY_TASK
            actual = set(payload.get('variable_weights') or {})
            expected = set(VARIABLES_BY_TASK[task])
            if actual != expected:
                raise ValueError(f"variable_weights: missing={sorted(expected - actual)}, "
                                 f"extra={sorted(actual - expected)}")
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


_LEAN_TOKEN = re.compile(r"^\s*LEAN:\s*(biopsy|defer|unclear)\s*$", re.I | re.M)


_VERDICT_LINE = re.compile(
    r"VERDICT:\s*(ready|not-?ready)\s*\|\s*SUGGEST:\s*(biopsy|defer)\s*\|\s*MISSING:\s*([^\n|]*)", re.I)


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


def drop_unsourced_grade_lines(text: str, corpus: str) -> tuple[str, list[str]]:
    """Quita las líneas que afirman un grado ausente del corpus.

    Se tira la línea entera y no sólo el fragmento: sustituirlo dentro de la
    frase deja una frase rota, y perder una línea del informe es barato
    comparado con enseñarle al presidente un grado que nadie documentó.
    """
    dropped: list[str] = []
    keep: list[str] = []
    for line in (text or "").splitlines():
        bad = unsourced_grades(line, corpus)
        if bad:
            dropped.extend(bad)
            continue
        keep.append(line)
    return "\n".join(keep).strip(), dropped


def verifier_line(body: str) -> dict[str, Any]:
    m = None
    for m in _VERDICT_LINE.finditer(body or ""):
        pass
    if m is None:
        return {"ready": True, "suggest": None, "missing": None, "parsed": False}
    missing = m.group(3).strip().strip(".").lower()
    return {"ready": m.group(1).lower().replace("-", "") == "ready",
            "suggest": m.group(2).lower(),
            "missing": None if missing in ("", "none", "nothing", "n/a") else missing,
            "parsed": True}


def registrar_lean(body: str) -> str | None:
    tokens = _LEAN_TOKEN.findall(body or "")
    if not tokens:
        return None
    return {"biopsy": "yes", "defer": "no", "unclear": None}[tokens[-1].lower()]
