"""Intervención III — el clasificador, dicho en cinco líneas.

Se **reutiliza tal cual** el mejor clasificador de la generación anterior: el
Random Forest sobre el núcleo de 8 variables del panel que eligió el estudio de
ablación (15 familias × 6 conjuntos, 5×5 CV, y después 10 semillas de
estabilidad: gana al kNN de la v1 en 10 de 10, Wilcoxon p = 0.002). No se
reentrena nada aquí ni se cambia el modelo: se importa
:class:`ClassifierExpert` del paquete anterior y se carga su artefacto.

Lo único que cambia es **cómo habla**. La versión anterior escribía dieciocho
líneas: dos incertidumbres con su párrafo explicativo, el protocolo de
validación, la escalera de tramos y dos avisos. Un participante de una junta no
habla así. Aquí dice lo que un colega diría:

    esto es lo que sugiere · con cuánta incertidumbre · con cuánta confianza ·
    con qué variables lo ha mirado · y que la decisión no es suya

Los números no se pierden — siguen íntegros en ``data``, que es lo que se
persiste y lo que consulta el presidente al final. Lo que se acorta es el texto
que entra en el contexto de los demás modelos, que es exactamente donde una
explicación de más se convierte en una alucinación de más.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

#: Cómo se dice en voz alta cada tramo de la escalera de incertidumbre, con el
#: acierto medido out-of-fold sobre los 91 casos etiquetados.
_CONFIDENCE = {
    "firm": ("HIGH", "in this tier it was right in every one of the {n} labelled cases it covered"),
    "supports": ("MODERATE", "in this tier it was right {acc:.0%} of the time over {n} labelled cases"),
    "discuss": ("LOW", "in this tier it was right {acc:.0%} of the time over {n} labelled cases — "
                       "barely better than a coin, so treat it as an opening bid and nothing more"),
}

#: Nombres legibles de las 8 variables del conjunto ``A-core``. Es lo que el
#: resto de la junta necesita para saber qué NO ha mirado.
_READABLE = {
    "pirads": "PI-RADS", "bx_ord": "prior biopsy status", "psa": "PSA", "age": "age",
    "psad": "PSA density", "dre_ord": "DRE", "vol": "prostate volume",
    "n_pmhx": "number of problems on the list",
}


def render(expert: Any, case_files: dict[str, dict]) -> tuple[str, dict[str, Any]]:
    """(cuerpo, datos) de la intervención del clasificador."""
    if expert is None:
        return ("No statistical classifier is deployed for this case, so there is no opening "
                "suggestion to react to.", {"available": False})

    try:
        o = expert.predict(case_files)
    except Exception as exc:  # noqa: BLE001 — la junta sigue sin él
        log.warning("El clasificador no pudo puntuar el caso: %s", exc)
        return (f"I could not score this patient ({exc}), so I contribute no suggestion. "
                "Do not read the absence of a number as reassurance.",
                {"available": False, "error": str(exc)})

    tier = o["veredicto_operativo"]
    acc, n_tier = (o.get("acierto_tramo") or (None, 0))
    word, tail = _CONFIDENCE.get(tier, ("LOW", "its track record in this tier is not established"))
    track = tail.format(acc=acc, n=n_tier) if acc is not None else "its track record here is not established"

    cols = expert.s.get("columns") or []
    read = ", ".join(_READABLE.get(c, c) for c in cols)
    m = o["rendimiento_validacion"]
    missing = ", ".join(o["variables_faltantes"]) or "none"
    verdict = "BIOPSY" if o["prediccion"] == "yes" else "NO BIOPSY"

    body = f"""A classifier trained only to open the discussion, not to close it. Here is its bid.

SUGGESTION: {verdict}   p(biopsy) = {o["A"]:.2f}
  uncertainty  +/- {o["delta_A"]:.2f} (95% CI {o["intervalo_95"][0]:.2f}-{o["intervalo_95"][1]:.2f}); \
among patients it cannot tell apart the outcome was {o["entropia_aleatoria"]:.2f} of 1.00 mixed
  confidence   {word} — {track}

It read ONLY these variables: {read}. Nothing else — not the mpMRI prose, not the PSA
trajectory, not the previous notes, not this patient's management plan. Values it could not
read for this patient: {missing}.
Out-of-fold over {m["n"]} labelled cases ({m["protocol"]}): accuracy {m["acc"]} against a
majority-class baseline of {m["majority"]}, AUC {m["auc"]}, F1(yes) {m["f1_yes"]}.

The final call is the senior urologist's."""

    o["gist"] = (f"classifier suggests {verdict}, p={o['A']:.2f} +/- {o['delta_A']:.2f}, "
                 f"{word} confidence ({tier} tier)")
    o["available"] = True
    return body, o
