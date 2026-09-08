"""Cierre del caso, y las guardias que no se le piden por favor a un modelo.

Cinco piezas, cada una contra un fallo concreto que se midió:

* :func:`reveal_sequence_from_messages` — la ``reveal_sequence`` **no la escribe
  el LLM**: se deriva de las herramientas que de verdad se ejecutaron. Honesta
  por construcción, y hace que ``tool_score`` mida el comportamiento del agente
  y no lo que el agente dice de sí mismo.

* :func:`unsourced_values` — la guardia nueva de esta generación. Todo número
  que el registrador escriba tiene que aparecer en un resultado de herramienta o
  en el panel. Es la comprobación mecánica que sustituye a "baja la
  temperatura": a temperatura 0 el modelo ya no muestrea, y aun así puede
  arrastrar un número de un caso anterior o de su propio texto. Un número sin
  fuente se detecta contando, no rezando.

* :func:`enforce_grounding` — baja a ``not_used`` toda variable cuya sección no
  se abrió. El prompt del presidente ya lo enuncia; un modelo pequeño no lo
  cumple solo. Medido en la generación anterior: seguía pesando ``dre`` sin
  abrir el laboratorio, y eso hundía ``section_grounding_score`` de 0.92 a 0.79.

* :func:`cites_retrieved_evidence` — comprueba si el razonamiento del presidente
  cita algo que sólo puede venir de un documento. Es lo que dispara el reto
  cuando anula a un experto con historial sin haber recuperado nada.

* :func:`fallback_response` — la red de seguridad. El ``form_fill`` del baseline
  lanza una excepción al agotar reintentos, y en Grand Challenge un caso perdido
  cuesta doble: ``case_score`` 0 y recall en el F1 de su clase verdadera. Aquí
  siempre sale una respuesta válida, construida de forma determinista a partir
  de lo que hay en el acta — nunca inventada.
"""

from __future__ import annotations

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


def tool_corpus(messages: list) -> str:
    """Todo lo que las herramientas devolvieron en este turno, concatenado."""
    parts = []
    for m in messages:
        if isinstance(m, ToolMessage) and m.content:
            parts.append(m.content if isinstance(m.content, str) else str(m.content))
    return "\n".join(parts)


def extract_json_object(text: str) -> str:
    """Recorta el primer objeto JSON balanceado de una respuesta cruda."""
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
                return text[start : i + 1]
    return text[start:]


def parse_json(text: str) -> dict:
    """Primer objeto JSON legible del texto; ``{}`` si no hay ninguno."""
    import json
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

#: Un valor clínico tiene coma o punto decimal, o al menos tres cifras, o va
#: pegado a una unidad. Los enteros sueltos de una o dos cifras (una numeración,
#: un PI-RADS, un recuento de líneas) se ignoran a propósito: aparecen en
#: cualquier texto y sólo producirían falsos positivos.
_VALUE = re.compile(r"\b\d+[.,]\d+\b|\b\d{3,}\b")

#: Los años se ignoran: el modelo los reformatea legítimamente ("Jan 2025" ->
#: "2025") y no son afirmaciones clínicas.
_YEAR = re.compile(r"^(19|20)\d{2}$")


def _normalise(text: str) -> str:
    """Quita separadores para que 4.7 y 4,7 comparen igual, y colapsa espacios."""
    return re.sub(r"\s+", " ", (text or "").replace(",", "."))


def unsourced_values(report: str, corpus: str, panel: str, limit: int = 6) -> list[str]:
    """Valores del informe que no aparecen ni en las herramientas ni en el panel.

    Comparación por subcadena sobre el texto normalizado, que es deliberadamente
    permisiva: se trata de cazar el número inventado, no de auditar el formato.
    Un valor que el modelo derive correctamente (una diferencia, un porcentaje)
    saldrá marcado; por eso la guardia devuelve el turno una sola vez y con la
    lista delante, en lugar de invalidar el informe.
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
# La línea final del verificador
# ---------------------------------------------------------------------------

_VERDICT_LINE = re.compile(
    r"VERDICT:\s*(ready|not-?ready)\s*\|\s*SUGGEST:\s*(biopsy|defer)\s*\|\s*MISSING:\s*([^\n|]*)",
    re.I,
)


def verifier_line(body: str) -> dict[str, Any]:
    """Lee la línea mecánica del verificador. Si no la escribió, cierra en `ready`.

    Cerrar por defecto no es indulgencia: la alternativa —reabrir cuando el
    modelo no se explica— es exactamente la patología que se midió en la
    generación anterior, donde el bucle se disparaba sin que hubiera nada nuevo
    que abrir. Reabrir tiene que costar una afirmación explícita.
    """
    m = None
    for m in _VERDICT_LINE.finditer(body or ""):
        pass  # nos quedamos con la última, que es la que cierra el turno
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
    """Postura declarada del registrador: ``'yes'``, ``'no'`` o ``None``.

    Se lee del token que él mismo escribe, nunca de la prosa: en la generación
    anterior un detector heurístico leía la cabecera «AGAINST sampling this
    patient now» como si fuera la conclusión y marcaba `defer` en 88 de 90 casos.
    """
    tokens = _LEAN_TOKEN.findall(body or "")
    if not tokens:
        return None
    return {"biopsy": "yes", "defer": "no", "unclear": None}[tokens[-1].lower()]


# ---------------------------------------------------------------------------
# Aterrizaje y respaldo
# ---------------------------------------------------------------------------

#: Variable -> sección que la aterriza, según ``section_variable_mapping.json``
#: del evaluador. ``psa`` y ``age`` están en la ficha y no necesitan revelación;
#: ``comorbidity`` no es declarable y el evaluador la excluye.
_SECTION_OF = {
    "pirads": "radiology_report",
    "psad": "radiology_report",
    "vol": "radiology_report",
    "cspca": "radiology_report",
    "dre": "laboratory_results",
}

#: ``bx`` se aterriza con ``pathology_report``, que **no existe** en el
#: vocabulario de ``Task1Output.reveal_sequence``: en la tarea 1 es un
#: ungrounded inevitable. Se deja pesar de todos modos porque lo que gana en
#: ``variable_weight_score`` (+0.157 medido) y en
#: ``important_decisive_factor_score`` (+0.166) supera lo que cuesta en
#: grounding — y con el juez del reto activo el grounding pesa 0.05 frente a
#: 0.25 y 0.15.
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


def cites_retrieved_evidence(free_text: str, panel_text: str, evidence_text: str) -> bool:
    """¿El razonamiento cita algún valor que SÓLO está en lo recuperado?"""
    nums = {n for n in re.findall(r"\d+\.?\d*", free_text or "") if len(n) > 1}
    if any(n in evidence_text and n not in panel_text for n in nums):
        return True
    return bool(re.search(
        r"compared with (the )?(previous|prior|earlier)|no (previous|prior) (mri|study|comparison)|"
        r"unchanged (since|from)|previous note|the notes record|psa (history|trajectory) (shows|rose|fell)|"
        r"isup grade group|gleason|active surveillance|already (agreed|planned)|"
        r"free[- ]psa|prostatitis",
        free_text or "", re.I))


_TIER_TO_CONFIDENCE = {"firm": "clear", "supports": "borderline", "discuss": "uncertain"}


def fallback_response(
    case_id: str,
    prompt_payload: dict[str, Any],
    prior: dict[str, Any] | None,
    cohort: dict[str, Any] | None,
    reveal_sequence: list[str],
) -> dict[str, Any]:
    """Respuesta válida construida sin el LLM, para que ningún caso se pierda.

    El criterio de cohorte manda donde se pronuncia (24/24 y 16/18 medidos);
    sólo si se abstiene se cae en el clasificador (0.714 out-of-fold frente al
    0.615 de la clase mayoritaria) y, a falta de los dos, en la clase
    mayoritaria. Pesa **sólo** variables cuya sección se reveló, para no regalar
    ``section_grounding_score`` en un caso que ya va mal.
    """
    prior = prior or {}
    has_prior = prior.get("available") and "prediccion" in prior

    verdict = (cohort or {}).get("verdict")
    if verdict in ("yes", "no"):
        decision = verdict == "yes"
    elif has_prior:
        decision = prior["prediccion"] == "yes"
    else:
        decision = True
    confidence = _TIER_TO_CONFIDENCE.get(prior.get("veredicto_operativo", ""), "uncertain")

    mri = "radiology_report" in reveal_sequence
    labs = "laboratory_results" in reveal_sequence
    bx = str(prompt_payload.get("bx") or "")

    weights = {
        "psa": "important",
        "age": "noted",
        "pirads": "important" if mri else "not_used",
        "psad": "noted" if mri else "not_used",
        "vol": "noted" if mri else "not_used",
        "cspca": "noted" if mri else "not_used",
        "dre": "noted" if labs else "not_used",
        "bx": "important" if bx in ("Positive", "ASAP/HGPIN") else "noted",
        "comorbidity": "noted",
    }

    prior_line = (
        f" The classifier on the board gave p(biopsy) = {prior.get('A')} +/- "
        f"{prior.get('delta_A')} ('{prior.get('veredicto_operativo')}' tier)."
        if has_prior else ""
    )
    reasoning = (
        f"Decision to {'proceed with biopsy' if decision else 'defer biopsy'} for a "
        f"{prompt_payload.get('age')}-year-old man with PI-RADS {prompt_payload.get('pirads')}, "
        f"PSA {prompt_payload.get('psa')} ng/mL, PSA density {prompt_payload.get('psad')} ng/mL^2 "
        f"and a prior biopsy status of '{bx or 'not recorded'}'.{prior_line} The conference did not "
        "return a readable structured form, so this record was completed from the values in the "
        "minute alone; no finding is asserted beyond those values."
    )

    return {
        "case_id": case_id, "task": 1, "biopsy_decision": decision, "confidence": confidence,
        "variable_weights": weights, "reveal_sequence": list(reveal_sequence),
        "reasoning": reasoning,
    }


def to_gc_outputs(structured: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Los dos ficheros de Grand Challenge de la tarea 1, desde el registro validado."""
    decision = "yes" if structured["biopsy_decision"] else "no"
    reasoning = {
        "confidence": structured["confidence"],
        "variable_weights": structured["variable_weights"],
        "reveal_sequence": structured["reveal_sequence"],
        "free_text": structured["reasoning"],
    }
    return decision, reasoning
