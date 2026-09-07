"""Experto #2 — el predictor sobre embeddings de imagen (interviene tras L2).

Reutiliza exactamente el punto de extensión que el baseline documenta:
``chimera_agent_baseline.features.FeatureStore`` para cargar los vectores
congelados del caso y ``chimera_agent_baseline.tools.predictor.run_predictor``
para reducirlos a un escalar. Los vectores **nunca** entran al contexto del
LLM: a la pizarra sólo llega qué orígenes existen y el número que devuelve la
cabeza.

Por qué interviene aunque hoy no prediga
----------------------------------------
El sondeo out-of-fold del cuaderno exploratorio midió la señal de los
embeddings congelados por tarea: AUC ~0.80 en la tarea 2, ~0.65 en la 3 y
**~0.43 en la tarea 1** — es decir, en biopsia la cabeza sobre el embedding de
MRI no distingue mejor que el azar. Con ``run_predictor`` en su forma de
plantilla (sin cabeza entrenada) la entrada correcta en la pizarra no es
silencio, sino una declaración explícita de que esta vía no aporta evidencia
para este caso. Es la diferencia entre "no se consultó" y "se consultó y no
informa": lo segundo impide que el presidente de la mesa se invente un apoyo
de imagen que no existe.

Cuando alguien entrene una cabeza para la tarea 1, basta con sustituir
``run_predictor`` upstream (o pasar ``predictor_fn``) y subir
``TASK1_HEAD_AUC``: el resto del texto se adapta solo.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

#: Discriminación out-of-fold medida para la tarea 1 sobre el embedding de MRI
#: (cuaderno exploratorio, seccion 4.8). <= 0.55 significa "no informa".
TASK1_HEAD_AUC = 0.43

#: A partir de aqui la cabeza se considera evidencia utilizable.
USABLE_AUC = 0.60

_ROLE = "image-embedding expert; frozen foundation-model MRI vectors behind a trained head"


def render(
    case_id: str,
    feature_store: Any,
    predictor_fn: Callable[[dict], dict] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """(role, body, data) para la pizarra. Nunca lanza."""
    from chimera_agent_baseline.tools.predictor import run_predictor  # noqa: PLC0415

    predictor_fn = predictor_fn or run_predictor

    try:
        features = feature_store.get(case_id) if feature_store is not None else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("FeatureStore falló para %s: %s", case_id, exc)
        features = {}

    origins = {origin: len(vectors) for origin, vectors in features.items() if vectors}

    if not origins:
        body = (
            "No frozen image embeddings are on file for this patient, so the image-embedding "
            "head could not be run. This contributes NO evidence in either direction — do not "
            "read the absence of a score as reassurance."
        )
        return _ROLE, body, {"case_id": case_id, "origins": {}, "prediction": None}

    try:
        result = predictor_fn(features)
    except Exception as exc:  # noqa: BLE001
        log.warning("run_predictor falló para %s: %s", case_id, exc)
        result = {"prediction": None, "detail": f"{type(exc).__name__}: {exc}"}

    available = ", ".join(f"{k} ({v} vector{'s' if v != 1 else ''})" for k, v in origins.items())
    prediction = result.get("prediction")
    usable = prediction is not None and TASK1_HEAD_AUC >= USABLE_AUC

    if usable:
        verdict = (
            f"Head output: {prediction}. Cross-validated discrimination on labelled task-1 cases: "
            f"AUC {TASK1_HEAD_AUC:.2f}. Weigh it as evidence of that strength — reconcile it with "
            "the clinical variables, never substitute it for them."
        )
    elif prediction is not None:
        verdict = (
            f"Head output: {prediction}. BUT its cross-validated discrimination on labelled task-1 "
            f"cases is AUC {TASK1_HEAD_AUC:.2f} — at or below chance. A score from a head that "
            "cannot separate the classes carries no information and MUST NOT move the decision."
        )
    else:
        verdict = (
            "No calibrated head is deployed for the biopsy decision, so no score was produced. "
            f"The probe that measured this modality for task 1 reported AUC {TASK1_HEAD_AUC:.2f} "
            "(at or below chance), which is why nothing is being asserted here."
        )

    body = f"""Frozen foundation-model embeddings on file for this patient: {available}.
The raw vectors are never shown; only a compact score would be.

{verdict}

Bottom line for the chair: the image-embedding route contributes NO usable evidence for this
biopsy decision. Decide on the structured panel, the retrieved documents and the guidelines.
Do not cite imaging-embedding support in the reasoning, and do not let the absence of a score
count as a negative finding."""

    return _ROLE, body, {"case_id": case_id, "origins": origins, "head_auc_task1": TASK1_HEAD_AUC, **result}
