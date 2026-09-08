"""Cierre del caso, y las guardias que no se le piden por favor a un modelo.

Seis piezas, cada una contra un fallo concreto que se midió:

* :func:`reveal_sequence_from_messages` — la ``reveal_sequence`` **no la escribe
  el LLM**: se deriva de las herramientas que de verdad se ejecutaron.

* :func:`unsourced_values` — todo número que el registrador escriba tiene que
  aparecer en un resultado de herramienta, en el panel o en el acta. Es la
  comprobación mecánica que sustituye a «baja la temperatura».

* :func:`documented_grade` — el grado de la biopsia previa, leído con expresión
  regular del **texto crudo** que devolvió la herramienta, no del resumen del
  modelo. Es el hecho que decide el cubo difícil y un modelo pequeño lo copia
  mal («ISUP 2» donde el documento dice «Gleason 3+4»).

* :func:`process_language` — **la guardia nueva de esta versión**. El texto
  libre que puntúa el reto es la traza de razonamiento de un urólogo. En la
  corrida de 195 casos de la generación anterior el presidente escribía cosas
  como «*the decision to defer biopsy is supported by the cohort criterion and
  the EXPERT-LIBRARY precedent … the VERIFIER noted that the GRADE remains
  unanswered*»: describe cómo se produjo el dictamen en vez de describir al
  paciente, y ningún urólogo escribe así. Aquí se detecta con una lista de
  patrones, se le devuelve el turno una vez, y si reincide se redacta la nota
  de forma determinista.

* :func:`clinical_note` — esa redacción determinista. Construida sólo con
  valores del caso y hechos recuperados, en el registro de la serie etiquetada.

* :func:`enforce_grounding` — baja a ``not_used`` toda variable cuya sección no
  se abrió.
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


# ---------------------------------------------------------------------------
# El grado inventado: la guardia de procedencia para hechos, no para números
# ---------------------------------------------------------------------------
#
# La guardia de valores mira números con decimales o de tres cifras, y a
# propósito ignora los enteros de una cifra porque aparecen en cualquier texto.
# Eso deja fuera precisamente el hecho más decisivo de la tarea: «Gleason 3+4»,
# «ISUP grade group 2». Medido sobre los 195 casos de la primera corrida
# completa: el registrador escribió un grado que NO está en el fichero clínico
# en **13 informes (6.7 %)** —con comillas, como si lo citara— y **5 de esas
# invenciones llegaron a la nota que se entrega**.
#
# El protocolo nunca se dejó engañar, porque `documented_grade` lee el texto
# crudo que devolvió la herramienta y no el resumen del registrador. Pero la
# nota clínica sí, porque el parte del presidente incluye ese resumen. Se cierra
# aquí, en las tres capas donde puede colarse: se le reta al registrador, se
# limpia el parte del presidente, y se comprueba la nota entregada.

_GRADE_CLAIM = re.compile(
    r"\bISUP\s*(?:grade\s*group\s*|grade\s*|GG\s*)?\d\b|\b(?:grade\s*group|GG)\s*\d\b|"
    r"\bGleason\s*(?:score\s*)?\d\s*\+\s*\d\b|\bGleason\s*(?:score\s*)?(?:6|7|8|9|10)\b", re.I)


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def unsourced_grades(text: str, corpus: str) -> list[str]:
    """Grados que el texto afirma y que no están en el corpus recuperado."""
    hay = _squash(corpus)
    out: list[str] = []
    for m in _GRADE_CLAIM.finditer(text or ""):
        frag = m.group(0).strip()
        if _squash(frag) not in hay and frag.lower() not in {o.lower() for o in out}:
            out.append(frag)
    return out


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
    abierto lo recoge. Con varias menciones manda la más alta: es la que decide
    tratar.
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
# La guardia de registro: la nota describe al paciente, no al procedimiento
# ---------------------------------------------------------------------------
#
# Lista curada, no una lista de palabras sueltas: en prosa clínica legítima
# aparecen «laboratory panel», «surveillance protocol», «PI-RADS score» y
# «Gleason score», y marcarlas sería enseñar a ignorar la guardia. Cada patrón
# de aquí abajo sólo casa con el uso que describe la maquinaria.

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


def _pirads_phrase(p: dict[str, Any]) -> str:
    v = p.get("pirads")
    return f"PI-RADS {v}" if v not in (None, "", "NA") else "no PI-RADS recorded"


def clinical_note(payload: dict[str, Any], grade: dict[str, Any] | None, opened: list[str],
                  because: str, decision: str, against: str | None = None,
                  alternative: str | None = None) -> str:
    """La nota redactada de forma determinista, en el registro de la serie.

    Es la red de seguridad de :func:`process_language` y también la del
    presidente que no entrega JSON válido. Sólo contiene valores del caso y
    hechos que salieron de los documentos abiertos, de modo que no puede
    inventar nada ni nombrar la maquinaria.
    """
    p = payload or {}
    g = grade or {}
    bx = str(p.get("bx") or "None")
    stance = {"None": "biopsy-naive", "Negative": "prior negative biopsy",
              "Positive": "known prostate cancer"}.get(bx, f"prior biopsy {bx}")
    if g.get("on_surveillance"):
        stance = "on active surveillance"

    bits = [f"{p.get('age')}-year-old man" if p.get("age") else "man", stance]
    head = ", ".join(x for x in bits if x) + "."

    facts = [_pirads_phrase(p)]
    if isinstance(p.get("psa"), (int, float)):
        facts.append(f"PSA {p['psa']:g} ng/mL")
    if isinstance(p.get("psad"), (int, float)):
        facts.append(f"PSAD {p['psad']:g}")
    if str(p.get("dre") or "").strip().lower() not in ("", "normal", "not done", "none"):
        facts.append(f"DRE {p['dre']}")
    values = ", ".join(facts) + "."

    # El hecho documentado sólo se enuncia si la justificación clínica no lo
    # dice ya: repetir «ISUP 3» en dos frases seguidas es lo que delata una
    # plantilla, y el urólogo no escribe así.
    doc = ""
    quote = str(g.get("quote") or "")
    if g.get("gg") is not None and quote and quote.lower() not in (because or "").lower():
        doc = f" Prior biopsy documented as {quote}."
    elif (g.get("gg") is None and bx in ("Positive", "ASAP/HGPIN") and "previous_notes" in (opened or [])
          and "nowhere recorded" not in (because or "")):
        # Sólo tiene sentido en quien ya fue biopsiado: un hombre sin biopsia
        # previa no tiene un ISUP inicial que echar en falta.
        doc = " Initial ISUP not recorded in the notes."

    tail = ""
    if because:
        clause = because.rstrip(". ")
        tail = f" {clause[0].upper()}{clause[1:]}."
    if against:
        tail += f" Against that, {against.rstrip('. ')}."
    verdict = " Biopsy." if decision == "yes" else " No biopsy for now."
    if alternative:
        verdict = verdict.rstrip(".") + f"; {alternative.rstrip('. ')}."
    note = f"{head} {values}{doc}{tail}{verdict}".strip()
    return re.sub(r"\s+", " ", note)


# ---------------------------------------------------------------------------
# Líneas mecánicas del verificador y del registrador
# ---------------------------------------------------------------------------

_VERDICT_LINE = re.compile(
    r"VERDICT:\s*(ready|not-?ready)\s*\|\s*SUGGEST:\s*(biopsy|defer)\s*\|\s*MISSING:\s*([^\n|]*)", re.I)


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


_LEAN_TOKEN = re.compile(r"^\s*LEAN:\s*(biopsy|defer|unclear)\s*$", re.I | re.M)


def registrar_lean(body: str) -> str | None:
    tokens = _LEAN_TOKEN.findall(body or "")
    if not tokens:
        return None
    return {"biopsy": "yes", "defer": "no", "unclear": None}[tokens[-1].lower()]


# ---------------------------------------------------------------------------
# Aterrizaje y salida
# ---------------------------------------------------------------------------

_SECTION_OF = {"pirads": "radiology_report", "psad": "radiology_report", "vol": "radiology_report",
               "cspca": "radiology_report", "dre": "laboratory_results", "fh": "family_history"}

#: ``bx`` se aterriza con ``pathology_report``, que no existe en la tarea 1: es
#: un ungrounded inevitable, y se deja pesar porque lo que gana en
#: ``variable_weight_score`` e ``important_decisive_factor_score`` supera lo
#: que cuesta en grounding (medido: −0.05 quitarlo, +0.03 devolver).
UNGROUNDABLE_BY_DESIGN = ("bx",)


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


def validate_output(structured: dict[str, Any]) -> tuple[bool, str]:
    """Valida el registro final contra ``Task1Output``, el esquema del reto.

    Es la última comprobación antes de escribir: el reto rechaza cualquier
    salida que no valide, así que se comprueba aquí en vez de descubrirlo en el
    servidor. ``output/schema.py`` es intocable por reglas del reto y por eso se
    importa, no se reimplementa.
    """
    from chimera_agent_baseline.output.schema import Task1Output  # noqa: PLC0415
    try:
        Task1Output(**structured)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def to_gc_outputs(structured: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Los dos ficheros de Grand Challenge de la tarea 1, desde el registro validado."""
    decision = "yes" if structured["biopsy_decision"] else "no"
    reasoning = {"confidence": structured["confidence"],
                 "variable_weights": structured["variable_weights"],
                 "reveal_sequence": structured["reveal_sequence"],
                 "free_text": structured["reasoning"]}
    return decision, reasoning
