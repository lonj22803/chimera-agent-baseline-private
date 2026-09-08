"""Intervención III-b — el criterio de cohorte, en cuatro líneas.

**Esta intervención no estaba en el encargo.** Se conserva, y conviene decir por
qué, porque quitarla habría sido una regresión medible y no una simplificación.

La tarea 1 no es un problema homogéneo: son tres, según el estado de biopsia
previa, y sobre los 91 casos etiquetados los dos primeros están *resueltos* por
una regla de una línea:

===================  ====  =========================================  ========
situación            n     criterio                                   acierto
===================  ====  =========================================  ========
sin biopsia previa   24    biopsiar si PI-RADS >= 3                    24 / 24
biopsia negativa     18    biopsiar si PI-RADS >= 4                    16 / 18
biopsia positiva     49    el panel no lo determina                    --
===================  ====  =========================================  ========

No es un ajuste a los datos: es la recomendación estándar (mpMRI antes de
biopsiar, biopsia dirigida sobre lesión PI-RADS >= 3 en el paciente sin
biopsiar, re-biopsia dirigida sobre PI-RADS >= 4 tras una biopsia negativa), y
por eso aguanta igual en los dos splits. Es de donde sale que la generación
anterior acertara 1.000 y 0.889 en esos dos cubos.

El tercero es el interesante y el honesto: en los 49 casos con biopsia previa
positiva ninguna variable estructurada separa las dos respuestas (el PSA sube en
los 49), el reparto es 26 diferir / 23 biopsiar, y toda regla ajustada en una
mitad falla en la otra. Lo que dice este experto ahí es que **no lo sabe**, y
que la decisión tiene que salir de los documentos. Decirlo explícitamente vale
más que callarse: impide que el presidente lea el silencio como un "diferir".

Cabe entera en una intervención corta y no le quita el turno a nadie, así que
está aquí en lugar de escondida en el prompt del presidente: si pesa en el
dictamen, tiene que verse en el acta.
"""

from __future__ import annotations

from typing import Any


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def criterion(payload: dict[str, Any]) -> dict[str, Any]:
    """El criterio aplicable a este paciente y lo que implica.

    ``verdict`` es ``'yes'``, ``'no'`` o ``None`` cuando el panel no determina.
    """
    bx = str(payload.get("bx") or "None").strip()
    pirads = _num(payload.get("pirads"))

    if bx == "None":
        return {
            "bucket": "never biopsied",
            "rule": "sample when the mpMRI shows a PI-RADS 3 or higher lesion; defer at PI-RADS 1-2",
            "verdict": "yes" if (pirads is not None and pirads >= 3) else "no",
            "hits": 24, "n": 24,
        }
    if bx == "Negative":
        return {
            "bucket": "prior negative biopsy",
            "rule": ("repeat, targeted, when the mpMRI shows a PI-RADS 4-5 lesion; do not repeat a "
                     "negative biopsy for an unchanged PI-RADS 3 or lower picture"),
            "verdict": "yes" if (pirads is not None and pirads >= 4) else "no",
            "hits": 16, "n": 18,
        }
    if bx == "Positive":
        return {
            "bucket": "prior positive biopsy",
            "rule": ("the visible panel does not determine this decision: the man already has a "
                     "tissue diagnosis, so neither a high PI-RADS nor a rising PSA is new "
                     "information"),
            "verdict": None, "hits": None, "n": 49,
        }
    return {
        "bucket": f"prior biopsy '{bx}' (atypical / HGPIN)",
        "rule": ("an atypical focus is not a diagnosis: re-sample on a concordant PI-RADS 4-5 lesion "
                 "or a rising PSA density, follow otherwise"),
        "verdict": "yes" if (pirads is not None and pirads >= 4) else "no",
        "hits": None, "n": 0,
    }


def render(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """(cuerpo, datos) de la intervención."""
    c = criterion(payload)

    if c["verdict"] is None:
        body = f"""This patient's situation: {c["bucket"]}. I have no answer for him, and that is the finding.

The criterion here is that {c["rule"]}. Measured on the {c["n"]} labelled cases in this
situation: no structured variable separates the two answers — PSA is rising in all {c["n"]} — the
split is 26 defer / 23 biopsy, and every rule fitted on one half failed on the other.

Do not read this as 'defer' and do not read it as 'biopsy'. It means the panel cannot settle
this man and the retrieved documents have to."""
        c["gist"] = f"cohort criterion abstains ({c['bucket']}): the panel does not determine this case"
    else:
        verdict = "BIOPSY" if c["verdict"] == "yes" else "DEFER"
        track = (f"In the labelled series this criterion matched the reading urologist in "
                 f"{c['hits']} of {c['n']} cases in exactly this situation."
                 if c["hits"] is not None else
                 "This situation does not appear in the labelled series, so the criterion is "
                 "unvalidated here — weigh it accordingly.")
        body = f"""This patient's situation: {c["bucket"]}. My criterion answers {verdict}.

The criterion: {c["rule"]}. {track}

Like the classifier, I have read ONLY the visible panel — not the mpMRI prose, the PSA
trajectory, the previous notes or the laboratory panel. Departing from me needs a specific
finding from a document somebody actually opened, named out loud. Not a restatement of the
panel numbers I already used."""
        c["gist"] = (f"cohort criterion answers {verdict} ({c['bucket']}"
                     + (f", {c['hits']}/{c['n']} in the labelled series)" if c["hits"] is not None else ")"))
    return body, c
