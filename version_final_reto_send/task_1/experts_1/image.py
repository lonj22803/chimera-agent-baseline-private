"""Intervención VI — el predictor sobre los embeddings congelados.

Usa exactamente el punto de extensión que documenta el baseline:
:class:`chimera_agent_baseline.features.FeatureStore` para cargar los vectores
del caso desde ``prostate-modality-level-neural-representations.json``, y
:func:`chimera_agent_baseline.tools.predictor.run_predictor` para reducirlos a
un escalar. Los vectores **no entran nunca** al contexto de un LLM: a la junta
llega qué modalidades hay en el fichero y qué devuelve la cabeza.

Cambio respecto a la generación anterior: aquí **sólo habla cuando el moderador
lo convoca**. Antes intervenía en los 91 casos para decir, en los 91, que no
aporta nada — nueve líneas de contexto por caso a cambio de cero información.
Ahora el moderador decide si lo llama, y si lo llama es porque el caso gira
sobre imagen; el resto del tiempo el acta no lo menciona.

Que la respuesta siga siendo "no aporta" no es un defecto de este módulo: el
sondeo out-of-fold del cuaderno exploratorio midió **AUC ~0.43** para la tarea 1
sobre el embedding de MRI — por debajo del azar —, frente a ~0.80 en la tarea 2.
Decirlo en voz alta es la información: distingue "no se consultó" de "se
consultó y no informa", que es lo que impide que el presidente se invente un
apoyo de imagen. Cuando alguien entrene una cabeza para esta tarea, basta con
sustituir ``run_predictor`` y subir :data:`TASK1_HEAD_AUC`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

#: Discriminación out-of-fold medida para la tarea 1 sobre el embedding de MRI.
TASK1_HEAD_AUC = 0.43

#: A partir de aquí la cabeza se considera evidencia utilizable.
USABLE_AUC = 0.60


def render(
    case_id: str,
    feature_store: Any,
    predictor_fn: Callable[[dict], dict] | None = None,
) -> tuple[str, dict[str, Any]]:
    """(cuerpo, datos) de la intervención. Nunca lanza."""
    from chimera_agent_baseline.tools.predictor import run_predictor  # noqa: PLC0415

    predictor_fn = predictor_fn or run_predictor

    try:
        features = feature_store.get(case_id) if feature_store is not None else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("FeatureStore falló para %s: %s", case_id, exc)
        features = {}

    origins = {origin: len(vectors) for origin, vectors in features.items() if vectors}

    if not origins:
        body = ("There are no frozen image embeddings on file for this patient, so I could not run "
                "the head at all. That contributes nothing in either direction — please do not read "
                "the absence of a score as reassurance.")
        return body, {"case_id": case_id, "origins": {}, "prediction": None,
                      "gist": "no embeddings on file; contributes nothing"}

    try:
        result = predictor_fn(features)
    except Exception as exc:  # noqa: BLE001
        log.warning("run_predictor falló para %s: %s", case_id, exc)
        result = {"prediction": None, "detail": f"{type(exc).__name__}: {exc}"}

    available = ", ".join(f"{k} ({v} vector{'s' if v != 1 else ''})" for k, v in origins.items())
    prediction = result.get("prediction")
    usable = prediction is not None and TASK1_HEAD_AUC >= USABLE_AUC

    if usable:
        verdict = (f"The head returns {prediction}. Its cross-validated discrimination on labelled "
                   f"task-1 cases is AUC {TASK1_HEAD_AUC:.2f}, so weigh it as evidence of that "
                   "strength — reconcile it with the clinical variables, do not substitute it.")
        gist = f"image head returns {prediction} (AUC {TASK1_HEAD_AUC:.2f})"
    elif prediction is not None:
        verdict = (f"The head returns {prediction}, but I have to qualify it: on labelled task-1 "
                   f"cases its cross-validated discrimination is AUC {TASK1_HEAD_AUC:.2f} — at or "
                   "below chance. A score from a head that cannot separate the two answers carries "
                   "no information and must not move this decision.")
        gist = f"image head at chance (AUC {TASK1_HEAD_AUC:.2f}); contributes nothing"
    else:
        verdict = ("No calibrated head is deployed for the biopsy decision, so there is no score. "
                   f"The probe that measured this modality for task 1 reported AUC "
                   f"{TASK1_HEAD_AUC:.2f}, at or below chance, which is why I am asserting nothing.")
        gist = "no head deployed for task 1; contributes nothing"

    body = f"""Frozen foundation-model embeddings on file for this patient: {available}. \
I never show the raw vectors — only a score, if there is one.

{verdict}

So, plainly: the imaging-embedding route adds nothing usable to this biopsy decision. Decide it
on the panel, the retrieved documents and the guideline. Nobody should cite embedding support in
the reasoning, and nobody should count the missing score as a negative finding."""

    return body, {"case_id": case_id, "origins": origins, "head_auc_task1": TASK1_HEAD_AUC,
                  "gist": gist, **result}
