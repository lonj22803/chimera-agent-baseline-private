"""Experto #3 — el criterio de protocolo (EAU) aplicable a ESTE paciente.

Por qué existe
--------------
El diagnóstico de la corrida 1 (``runs/CORRECCIONES.md``) dejó una cosa clara:
la tarea 1 no es un problema homogéneo, son **tres problemas distintos** según
el estado de biopsia previa, y sólo dos de ellos están determinados por el
panel visible. Medido sobre los 91 casos etiquetados:

===================  ====  ==========================================  ==========
cubo                 n     criterio                                    acierto
===================  ====  ==========================================  ==========
``bx = None``        24    biopsiar si PI-RADS >= 3                     24 / 24
``bx = Negative``    18    biopsiar si PI-RADS >= 4                     16 / 18
``bx = Positive``    49    **el panel no lo determina**                 --
===================  ====  ==========================================  ==========

Los dos primeros no son un ajuste a los datos: son la recomendación estándar
—mpMRI antes de biopsiar, biopsia dirigida sobre lesión PI-RADS >= 3 en el
paciente sin biopsiar, re-biopsia dirigida sobre PI-RADS >= 4 tras una biopsia
negativa— y por eso se sostienen igual en los dos splits (dev 0.703, val 0.741
sobre el conjunto completo cuando se combinan con el agente).

El tercero sí es irreducible con lo que hay en el panel: en los 49 casos con
biopsia previa positiva ninguna variable estructurada separa ``yes`` de ``no``
(el PSA sube en los 49), los propios urólogos discrepan entre casos casi
idénticos, y ninguna regla que se pruebe en ``dev`` sobrevive en ``val``. Lo
honesto —y lo que este experto escribe— es decir que el panel **no** decide y
que la decisión tiene que salir de los documentos recuperados.

Qué NO hace
-----------
No decide. Escribe su criterio en la pizarra como un participante más, con su
acierto medido y con la frase explícita de que sólo ha leído el panel visible.
El presidente puede apartarse de él nombrando un hallazgo recuperado; es la
misma carga de la prueba que se le exige para apartarse del prior estadístico.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_ROLE = "protocol expert; applies the guideline criterion for this patient's clinical situation"


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v


def criterion(payload: dict[str, Any]) -> dict[str, Any]:
    """El criterio aplicable y el veredicto que implica (``None`` si no aplica)."""
    bx = str(payload.get("bx") or "None").strip()
    pirads = _num(payload.get("pirads"))

    if bx == "None":
        verdict = "yes" if (pirads is not None and pirads >= 3) else "no"
        return {
            "bucket": "biopsy-naive",
            "rule": "Biopsy when the mpMRI shows a PI-RADS 3 or higher lesion; defer when PI-RADS is 1-2.",
            "verdict": verdict,
            "hits": 24,
            "n": 24,
            "note": (
                "In the labelled cohort this criterion matched the reading urologist in every one "
                "of the 24 biopsy-naive cases (20 of them PI-RADS 4-5 and biopsied, 4 of them "
                "PI-RADS 2 or unreadable and deferred)."
            ),
        }

    if bx == "Negative":
        verdict = "yes" if (pirads is not None and pirads >= 4) else "no"
        return {
            "bucket": "prior negative biopsy",
            "rule": (
                "Re-biopsy (targeted) when the mpMRI shows a PI-RADS 4-5 lesion; do not repeat a "
                "negative biopsy for a PI-RADS 3 or lower picture that has not changed."
            ),
            "verdict": verdict,
            "hits": 16,
            "n": 18,
            "note": (
                "In the labelled cohort this criterion matched the reading urologist in 16 of the "
                "18 cases with a prior negative biopsy."
            ),
        }

    if bx == "Positive":
        return {
            "bucket": "prior positive biopsy",
            "rule": (
                "The visible panel does NOT determine this decision. The patient already has a "
                "tissue diagnosis, so neither a high PI-RADS nor a rising PSA is new information. "
                "The decision must come from the retrieved documents: whether the prior grade is "
                "documented, whether the lesion changed against a previous MRI, whether a "
                "surveillance re-biopsy is due, and whether treatment is already agreed."
            ),
            "verdict": None,
            "hits": None,
            "n": 49,
            "note": (
                "Measured on the 49 labelled cases with a prior positive biopsy: no structured "
                "variable separates the two answers (PSA is rising in all 49), the split is "
                "26 defer / 23 biopsy, and every rule fitted on one half of the data failed on "
                "the other. This is genuinely undetermined by the panel."
            ),
        }

    return {
        "bucket": f"prior biopsy '{bx}'",
        "rule": (
            "An atypical prior finding (ASAP / high-grade PIN) is not a diagnosis: re-biopsy when "
            "a concordant PI-RADS 4-5 lesion or a rising PSA density is present, follow otherwise."
        ),
        "verdict": "yes" if (pirads is not None and pirads >= 4) else "no",
        "hits": None,
        "n": 0,
        "note": "This situation does not appear in the labelled cohort, so the criterion is unvalidated here.",
    }


def render(payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """(role, body, data) para la pizarra."""
    c = criterion(payload)

    if c["verdict"] is None:
        head = (
            f"CLINICAL SITUATION: {c['bucket']}.\n\n"
            "THIS CRITERION RETURNS NO ANSWER FOR THIS PATIENT."
        )
        implication = (
            "Do not read this as 'defer' and do not read it as 'biopsy'. It means the panel "
            "cannot settle the case and the retrieved documents must."
        )
    else:
        verdict = "BIOPSY" if c["verdict"] == "yes" else "DEFER BIOPSY"
        head = f"CLINICAL SITUATION: {c['bucket']}.\n\nCRITERION VERDICT: {verdict}."
        implication = (
            f"Track record of this criterion on the labelled cohort: {c['hits']} of {c['n']} cases "
            "matched the reading urologist. Departing from it needs a specific finding from a "
            "retrieved document, named explicitly - not a restatement of the panel numbers it "
            "already used."
        )

    body = f"""{head}

The criterion: {c["rule"]}

{c["note"]}

{implication}

Like the statistical prior, this expert has read ONLY the visible panel. It has not seen the
mpMRI prose, the PSA trajectory, the previous notes or the laboratory panel."""

    return _ROLE, body, c
