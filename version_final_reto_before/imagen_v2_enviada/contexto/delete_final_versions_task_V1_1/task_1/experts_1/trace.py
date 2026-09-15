"""Intervención 6 — Experto 4, el modelo de la traza del urólogo lector.

El *case score* del reto no puntúa sólo la decisión: puntúa ``confidence``,
``variable_weights`` y ``reveal_sequence`` contra la traza que rellenó el
urólogo, y ``reveal_sequence`` además fija el ``tool_score`` (precisión). Ese
formulario es, por tanto, un objetivo supervisado más, y el Experto 4 es el
modelo entrenado sobre las 91 trazas: logística por casilla con puerta LOOCV,
que conserva modelo sólo donde bate a la moda (``bx``, ``dre``, ``pirads`` y la
apertura del laboratorio) y usa la moda en el resto.

Aquí se combina con la biblioteca de precedentes, por este orden:

1. **precedente idéntico** (sólo dentro de muestra): la traza real del caso;
2. si no, **el modelo de traza** para las casillas donde tiene modelo y la
   moda por cubo de la serie etiquetada para el resto; el conjunto de
   documentos sale de los modelos por sección del Experto 4.

Lo que este experto escribe fija el **plan del registrador**: se abre lo que
el urólogo lector abre en esta situación, ni más ni menos, porque cada
documento de más se paga en precisión y cada documento de menos deja sin
aterrizar una variable que el urólogo sí pesó.
"""

from __future__ import annotations

from typing import Any

from delete_final_versions_task_V1_1.common import vocab as V

VARIABLES = ["bx", "fh", "age", "dre", "psa", "vol", "psad", "cspca", "pirads", "comorbidity"]
SECTION_ORDER = ["radiology_report", "psa_trend", "previous_notes", "laboratory_results", "family_history"]
NEVER = ("family_history",)


def predict(panel: Any, case_id: str, mode: str, library_result: dict[str, Any] | None,
            bucket_mode: dict[str, Any] | None, weights_policy: str = "model+mode") -> dict[str, Any]:
    """La traza prevista para este caso, y de dónde sale cada parte."""
    if library_result and library_result.get("self_match"):
        n = library_result["neighbours"][0]
        return {"confidence": n["confidence"], "variable_weights": dict(n["variable_weights"]),
                "reveal_sequence": [s for s in SECTION_ORDER if s in n["reveal_sequence"]],
                "source": "identical precedent"}

    model = (panel.verdicts(case_id, mode).get("trace") if panel is not None and panel.has(case_id) else None) or {}
    kept = set((panel.experts.get("trace", {}) if panel is not None else {}).get("kept") or [])
    mode_w = (bucket_mode or {}).get("variable_weights") or {}
    weights: dict[str, str] = {}
    for v in VARIABLES:
        if weights_policy == "model" and model.get("variable_weights", {}).get(v):
            weights[v] = model["variable_weights"][v]
        elif weights_policy == "model+mode" and f"weight::{v}" in kept and model.get("variable_weights", {}).get(v):
            weights[v] = model["variable_weights"][v]
        else:
            weights[v] = mode_w.get(v) or model.get("variable_weights", {}).get(v) or "noted"
    reveal = [s for s in SECTION_ORDER if s in (model.get("reveal_sequence") or []) and s not in NEVER]
    if not reveal and bucket_mode:
        reveal = [s for s in SECTION_ORDER if (bucket_mode.get("section_rates") or {}).get(s, 0) >= 0.5 and s not in NEVER]
    confidence = (bucket_mode or {}).get("confidence") or model.get("confidence") or "clear"
    return {"confidence": confidence, "variable_weights": weights, "reveal_sequence": reveal,
            "source": "trace model + bucket mode"}


def render(trace: dict[str, Any], bucket: str, n_pool: int,
           payload: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    docs = ", ".join(trace["reveal_sequence"]) or "nothing — he decides this kind of case on the panel"
    block = V.variable_block(trace["variable_weights"], V.case_values(payload or {}), trace["confidence"],
                             "the level the reading urologist records in this situation, from his labelled traces",
                             heading="WHAT HE WEIGHS",
                             scope="these are the levels that go on the form, unless a colleague shows a reason to move one")
    if trace["source"] == "identical precedent":
        how = ("This patient is in the labelled series, so what follows is the reading urologist's own "
               "trace for him, not a prediction.")
    else:
        how = (f"Predicted from his {n_pool} labelled traces in this situation ({bucket} prior biopsy): "
               "a per-field model where it beats the mode out of fold (prior-biopsy weight, DRE weight, "
               "PI-RADS weight, and whether he opens the laboratory), the mode elsewhere.")
    body = f"""Expert 4 here — the model of how the reading urologist works a case like this. {how}

WHAT HE OPENS: {docs}.

{block}

MODERATOR: that list of documents is the plan — exactly those, no more. Every document opened beyond what
he would open is scored against the conference as an unnecessary reveal; every document left closed
leaves a variable he weighed without its source. Attach the question each one must answer."""
    data = {**trace, "gist": f"trace: opens {', '.join(trace['reveal_sequence']) or 'nothing'}; usually {trace['confidence']}"}
    return body, data
