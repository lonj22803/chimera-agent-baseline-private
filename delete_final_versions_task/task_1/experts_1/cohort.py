"""Intervención 4 — el criterio de cohorte, ampliado al cubo difícil.

La tarea 1 son tres problemas según el estado de biopsia previa. Los dos
primeros se resuelven con una regla de una línea, medida sobre los 91 casos
etiquetados y estándar en la guía:

===================  ====  =========================================  ========
situación            n     criterio                                   acierto
===================  ====  =========================================  ========
sin biopsia previa   24    biopsiar si PI-RADS >= 3                    24 / 24
biopsia negativa     18    biopsiar si PI-RADS >= 4                    16 / 18
===================  ====  =========================================  ========

El tercero —49 casos con biopsia previa positiva— es el que ninguna generación
anterior resolvió, y donde la generación anterior decía «el panel no lo
determina». Esta versión lee el criterio **en el texto del propio urólogo
lector** (los 49 ``free_text`` de la serie etiquetada) y encuentra tres reglas
de panel que él aplica de forma explícita y que son criterio de guía:

===============================  ====  =======================================  ========
regla                            n     lo que escribió el urólogo               acierto
===============================  ====  =======================================  ========
PSA >= 20 ng/mL -> no biopsiar    6    "start treatment and do a PSMA-PET"       5 / 6
edad >= 78 -> no biopsiar         2    "stop checking PSA, no need for           2 / 2
                                       diagnostics"
PI-RADS <= 2 -> no biopsiar       2    "now normal MRI"                          2 / 2
===============================  ====  =======================================  ========

Un hombre con cáncer confirmado y PSA de 70 no necesita otra biopsia, necesita
estadificación; un hombre de 82 años con enfermedad de bajo riesgo no necesita
más diagnóstico; una RM sin lesión no da nada que muestrear. Son 10 casos con
9 aciertos. Para los otros 39 el panel sigue sin determinar la decisión, y este
experto lo dice — la respuesta está en el grado documentado de la biopsia
previa (:func:`decide.documented_grade`) y, a falta de él, en los expertos
entrenados.
"""

from __future__ import annotations

from typing import Any

from delete_final_versions_task.common import vocab as V


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


#: Qué variables sostienen cada regla, en el vocabulario del formulario. El resto
#: queda en ``noted``: el criterio las lee pero no decide con ellas.
RULE_VARIABLES: dict[str, dict[str, str]] = {
    "pirads_ge_3": {"pirads": "decisive", "bx": "important", "psad": "noted", "psa": "noted"},
    "pirads_le_2": {"pirads": "decisive", "bx": "important", "psa": "noted", "psad": "noted"},
    "pirads_ge_4": {"pirads": "decisive", "bx": "important", "psad": "noted", "psa": "noted"},
    "pirads_le_3": {"pirads": "decisive", "bx": "important", "psad": "noted", "psa": "noted"},
    "psa_ge_20": {"psa": "decisive", "bx": "important", "pirads": "noted"},
    "age_ge_78": {"age": "decisive", "bx": "important", "pirads": "noted", "psa": "noted"},
}

#: Reglas de panel del cubo con biopsia previa positiva, con su acierto medido.
POSITIVE_PANEL_RULES = (
    ("psa_ge_20", lambda p: (_num(p.get("psa")) or 0) >= 20.0,
     "PSA >= 20 ng/mL in a man with a tissue diagnosis: the next step is staging and treatment, "
     "not more tissue", 5, 6),
    ("age_ge_78", lambda p: (_num(p.get("age")) or 0) >= 78,
     "age >= 78 with a known diagnosis: no further diagnostics unless high-risk features", 2, 2),
    ("pirads_le_2", lambda p: (_num(p.get("pirads")) is not None and _num(p.get("pirads")) <= 2),
     "PI-RADS 1-2 on the current mpMRI: there is no lesion to sample", 2, 2),
)


def criterion(payload: dict[str, Any]) -> dict[str, Any]:
    """El criterio aplicable a este paciente. ``verdict`` es 'yes', 'no' o None."""
    bx = str(payload.get("bx") or "None").strip()
    pirads = _num(payload.get("pirads"))

    if bx == "None":
        return {"bucket": "never biopsied",
                "rule": "sample when the mpMRI shows a PI-RADS 3 or higher lesion; defer at PI-RADS 1-2",
                "verdict": "yes" if (pirads is not None and pirads >= 3) else "no",
                "hits": 24, "n": 24, "fired": "pirads_ge_3" if (pirads is not None and pirads >= 3) else "pirads_le_2"}
    if bx == "Negative":
        return {"bucket": "prior negative biopsy",
                "rule": ("repeat, targeted, when the mpMRI shows a PI-RADS 4-5 lesion; do not repeat a "
                         "negative biopsy for an unchanged PI-RADS 3 or lower picture"),
                "verdict": "yes" if (pirads is not None and pirads >= 4) else "no",
                "hits": 16, "n": 18, "fired": "pirads_ge_4" if (pirads is not None and pirads >= 4) else "pirads_le_3"}
    if bx == "Positive":
        for name, test, text, hits, n in POSITIVE_PANEL_RULES:
            if test(payload):
                return {"bucket": "prior positive biopsy", "rule": text, "verdict": "no",
                        "hits": hits, "n": n, "fired": name}
        return {"bucket": "prior positive biopsy",
                "rule": ("the visible panel does not determine this decision: he already has a tissue "
                         "diagnosis, so neither a high PI-RADS nor a rising PSA is new information. "
                         "What decides it is the documented grade of the prior biopsy and the "
                         "surveillance history, which live in the previous notes"),
                "verdict": None, "hits": None, "n": 39, "fired": None}
    return {"bucket": f"prior biopsy '{bx}' (atypical / HGPIN)",
            "rule": ("an atypical focus is not a diagnosis: re-sample on a concordant PI-RADS 4-5 lesion "
                     "or a rising PSA density, follow otherwise"),
            "verdict": "yes" if (pirads is not None and pirads >= 4) else "no",
            "hits": None, "n": 0, "fired": None}


def variables_for(c: dict[str, Any]) -> tuple[dict[str, str], str, str]:
    """(pesos, confianza, por qué) del criterio en el vocabulario del formulario."""
    weights = {v: "noted" for v in V.VARIABLES_BY_TASK[1]}
    weights["fh"] = "not_used"
    weights["cspca"] = "not_used"
    if c.get("fired") and c["fired"] in RULE_VARIABLES:
        weights.update(RULE_VARIABLES[c["fired"]])
        conf, why = V.confidence_from_rate(c.get("hits"), c.get("n"))
        return weights, conf, why
    # el cubo positivo sin regla: sabe qué variables NO deciden, y cuál decidiría
    weights.update({"bx": "important", "pirads": "noted", "psa": "noted"})
    return weights, "uncertain", ("none of my three panel rules applies; the fact that would settle it — the "
                                  "documented prior grade — lives in the notes, not on the panel")


def render(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    c = criterion(payload)
    weights, conf, why = variables_for(c)
    block = V.variable_block(weights, V.case_values(payload), conf, why,
                             scope="panel only; 'decisive' marks the variable the rule turns on")
    c["variable_weights"], c["confidence"] = weights, conf
    if c["verdict"] is None:
        body = f"""This patient's situation: {c["bucket"]}. The panel alone does not answer, and that is the finding.

The criterion here is that {c["rule"]}. Measured on the labelled series: none of the three panel
rules I carry for this situation (PSA >= 20, age >= 78, PI-RADS <= 2) applies to him, and among the
{c["n"]} remaining labelled men in this situation no structured variable separates the two answers.

REGISTRAR: the previous notes are where this case is decided. Read them for the grade of the prior
biopsy (Gleason or ISUP), the number of biopsy sessions and their dates, and whether he is on a
surveillance protocol with a confirmatory biopsy due. Do not read this as 'defer' and do not read it
as 'biopsy'.

{block}"""
        c["gist"] = f"cohort criterion abstains ({c['bucket']}): decided on the documented grade and the notes"
    else:
        verdict = "BIOPSY" if c["verdict"] == "yes" else "DEFER"
        track = (f"In the labelled series this criterion matched the reading urologist in {c['hits']} "
                 f"of {c['n']} cases in exactly this situation."
                 if c["hits"] is not None else
                 "This situation does not appear in the labelled series, so the criterion is unvalidated here.")
        body = f"""This patient's situation: {c["bucket"]}. My criterion answers {verdict}.

The criterion: {c["rule"]}. {track}

Like Expert 1, I have read ONLY the visible panel — not the mpMRI prose, the PSA trajectory, the
previous notes or the laboratory panel. Departing from me needs a specific finding from a document
somebody actually opened, named out loud; not a restatement of the panel numbers I already used.

{block}"""
        c["gist"] = (f"cohort criterion answers {verdict} ({c['bucket']}, rule {c['fired']}"
                     + (f", {c['hits']}/{c['n']} in the labelled series)" if c["hits"] is not None else ")"))
    return body, c
