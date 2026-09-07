"""Cierre del caso: parseo de la salida del presidente, revelaciones y respaldo.

Tres piezas, las tres pensadas contra una regla concreta del evaluador:

* :func:`reveal_sequence_from_messages` — la ``reveal_sequence`` **no la
  escribe el LLM**, se deriva de las herramientas que realmente se ejecutaron.
  Es honesta por construcción y hace que ``tool_score`` mida el comportamiento
  del agente, no lo que el agente dice de sí mismo. (Mismo criterio que
  ``chimera_agent_baseline.agent.form_fill``.)

* :func:`extract_json_object` — recorte tolerante del objeto JSON dentro de la
  respuesta del modelo.

* :func:`fallback_response` — la red de seguridad. El ``form_fill`` del
  baseline lanza una excepción cuando agota los reintentos, y en Grand
  Challenge eso es un caso perdido que cuesta **doble**: ``case_score`` 0 y,
  además, recall en el F1 de su clase verdadera. Aquí un caso siempre sale
  con una respuesta válida, construida de forma determinista a partir de lo
  que hay en la pizarra — nunca inventada.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import ToolMessage

log = logging.getLogger(__name__)

#: Herramienta -> nombre de sección del vocabulario de ``Task1Output``.
#: ``search_guidelines`` y ``get_image_predictor`` no aparecen: no son
#: secciones del formulario y por tanto no cuestan precisión de revelación.
REVEAL_FIELD_BY_TOOL: dict[str, str] = {
    "get_family_history": "family_history",
    "get_previous_notes": "previous_notes",
    "get_lab_results": "laboratory_results",
    "get_psa_trend": "psa_trend",
    "get_mri_report": "radiology_report",
}


def reveal_sequence_from_messages(messages: list) -> list[str]:
    """Secciones realmente reveladas, en orden de primera aparición."""
    out: list[str] = []
    for message in messages:
        if not isinstance(message, ToolMessage) or not message.name:
            continue
        field = REVEAL_FIELD_BY_TOOL.get(message.name)
        if field is not None and field not in out:
            out.append(field)
    return out


def called_tools_from_messages(messages: list) -> set[str]:
    return {m.name for m in messages if isinstance(m, ToolMessage) and m.name}


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


# ---------------------------------------------------------------------------
# Respaldo determinista
# ---------------------------------------------------------------------------

_TIER_TO_CONFIDENCE = {"firme": "clear", "apoya": "borderline", "discutir": "uncertain"}


def fallback_response(
    case_id: str,
    prompt_payload: dict[str, Any],
    prior: dict[str, Any] | None,
    reveal_sequence: list[str],
) -> dict[str, Any]:
    """Respuesta válida construida sin el LLM, para que ningún caso se pierda.

    Usa el veredicto del recomendador inicial cuando existe (acierto medido
    0.69 out-of-fold, frente al 0.62 de la clase mayoritaria) y, si no,
    la clase mayoritaria. Pesa **sólo** variables cuya sección se reveló, para
    no regalar ``section_grounding_score`` en un caso que ya va mal.
    """
    prior = prior or {}
    has_prior = "error" not in prior and "prediccion" in prior

    decision = bool(has_prior and prior["prediccion"] == "yes") or not has_prior
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

    pirads = prompt_payload.get("pirads")
    psa = prompt_payload.get("psa")
    psad = prompt_payload.get("psad")
    verdict = "proceed with biopsy" if decision else "defer biopsy"
    prior_line = (
        f" The statistical prior on the blackboard gave p(biopsy) = {prior.get('A')} "
        f"+/- {prior.get('delta_A')} ({prior.get('veredicto_operativo')} tier)."
        if has_prior
        else ""
    )
    reasoning = (
        f"Decision to {verdict} for a {prompt_payload.get('age')}-year-old man with "
        f"PI-RADS {pirads}, PSA {psa} ng/mL, PSA density {psad} ng/mL^2 and a prior biopsy "
        f"status of '{bx or 'not recorded'}'.{prior_line} The case conference did not return a "
        "readable structured form, so this record was completed from the values on the "
        "blackboard alone; no finding is asserted beyond those values."
    )

    return {
        "case_id": case_id,
        "task": 1,
        "biopsy_decision": decision,
        "confidence": confidence,
        "variable_weights": weights,
        "reveal_sequence": list(reveal_sequence),
        "reasoning": reasoning,
    }


def to_gc_outputs(structured: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Los dos ficheros de Grand Challenge de la tarea 1, a partir del registro validado."""
    decision = "yes" if structured["biopsy_decision"] else "no"
    reasoning = {
        "confidence": structured["confidence"],
        "variable_weights": structured["variable_weights"],
        "reveal_sequence": structured["reveal_sequence"],
        "free_text": structured["reasoning"],
    }
    return decision, reasoning
