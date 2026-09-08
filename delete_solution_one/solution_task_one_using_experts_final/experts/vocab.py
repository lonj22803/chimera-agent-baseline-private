"""El vocabulario compartido de la junta: variables, pesos y confianza.

El formulario del reto puntúa diez variables con cuatro niveles
(``not_used`` / ``noted`` / ``important`` / ``decisive``) y una confianza con
tres (``clear`` / ``borderline`` / ``uncertain``). Hasta esta versión sólo el
Experto 4 y el protocolo hablaban en ese vocabulario; el resto decía «lo que
más me movió» como una lista de rasgos internos (``pirads_ge4``,
``pmhx_hypercholesterolaemia``) que ningún colega podía comparar con nada.

Aquí **todos los expertos declaran lo mismo, de la misma forma**: qué
variables pesaron y a qué nivel, con el valor del paciente al lado, y con qué
confianza hablan. Es lo que permite que la sala compare —«el Experto 3 marca
``pirads`` como *important* y el criterio de cohorte lo marca *decisive*; ¿qué
dice la guía?»— y lo que da al presidente una tabla en vez de una lista de
adjetivos. Y como es el vocabulario del formulario, lo que la sala discute es
exactamente lo que después se entrega.

Una advertencia que vale para todos: el nivel que un experto entrenado da a
una variable mide **cuánto movió su predicción** (importancia de permutación
out-of-fold), no cuánto la pesaría un urólogo. Las dos lecturas divergen —para
los clasificadores el estado de biopsia previa es lo que parte la cohorte; para
el urólogo, PI-RADS es la puerta de entrada— y la divergencia es informativa.
El peso que se entrega lo fija el Experto 4, que está entrenado contra la traza
del urólogo; los demás pesos alimentan el razonamiento.
"""

from __future__ import annotations

from typing import Any

VARIABLES = ["bx", "fh", "age", "dre", "psa", "vol", "psad", "cspca", "pirads", "comorbidity"]
LEVELS = ["decisive", "important", "noted", "not_used"]
CONFIDENCE = ["clear", "borderline", "uncertain"]
TIER_TO_CONFIDENCE = {"firm": "clear", "supports": "borderline", "discuss": "uncertain"}

#: Cómo se lee cada variable del formulario en la sala.
LABEL = {
    "bx": "prior biopsy", "fh": "family history", "age": "age", "dre": "DRE", "psa": "PSA",
    "vol": "prostate volume", "psad": "PSA density", "cspca": "csPCa probability", "pirads": "PI-RADS",
    "comorbidity": "comorbidity",
}


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def case_values(payload: dict[str, Any]) -> dict[str, str]:
    """El valor de cada variable del formulario en este paciente, como texto corto."""
    p = payload or {}
    pmhx = p.get("pmhx") or []
    comorb = (f"{len(pmhx)} on the problem list" if pmhx else
              ("none recorded" if str(p.get("medhx") or "").lower() in ("", "not reported", "none") else str(p.get("medhx"))))
    psa = _num(p.get("psa"))
    psad = _num(p.get("psad"))
    vol = _num(p.get("vol"))
    cs = _num(p.get("cspca"))
    return {
        "bx": str(p.get("bx") or "not recorded"),
        "fh": "not opened (0 of 91)",
        "age": f"{p.get('age')}" if p.get("age") is not None else "not recorded",
        "dre": str(p.get("dre") or "not recorded"),
        "psa": f"{psa:g} ng/mL" if psa is not None else "not recorded",
        "vol": f"{vol:g} mL" if vol is not None else "not recorded",
        "psad": f"{psad:g}" if psad is not None else "not recorded",
        "cspca": f"{cs:.2f}" if cs is not None else "not recorded",
        "pirads": str(p.get("pirads") or "not recorded"),
        "comorbidity": comorb,
    }


def variable_block(
    weights: dict[str, str],
    values: dict[str, str],
    confidence: str,
    why_confidence: str,
    *,
    share: dict[str, float] | None = None,
    features: dict[str, list] | None = None,
    heading: str = "VARIABLES I WEIGHED",
    scope: str | None = None,
) -> str:
    """El bloque estándar con el que todo experto declara sus variables.

    Agrupado por nivel, de más a menos, con el valor del paciente al lado y —si
    el experto es un modelo— la parte de su señal que cada variable explica y
    los rasgos concretos que la sostienen.
    """
    lines = [f"{heading} — in the form's vocabulary, with this man's values" + (f" ({scope})" if scope else "")]
    for level in LEVELS:
        vars_ = [v for v in VARIABLES if (weights or {}).get(v, "not_used") == level]
        if not vars_:
            continue
        if level == "not_used":
            lines.append(f"  not used   {', '.join(LABEL[v] for v in vars_)}")
            continue
        parts = []
        for v in vars_:
            item = f"{LABEL[v]} = {values.get(v, '?')}"
            extra = []
            if share and share.get(v):
                extra.append(f"{share[v]:.0%} of my signal")
            if features and features.get(v):
                extra.append("from " + ", ".join(f for f, _ in features[v][:2]))
            if extra:
                item += " (" + "; ".join(extra) + ")"
            parts.append(item)
        lines.append(f"  {level:<10} " + " · ".join(parts))
    lines.append(f"CONFIDENCE: {confidence} — {why_confidence}")
    return "\n".join(lines)


def confidence_from_rate(hits: int | None, n: int | None) -> tuple[str, str]:
    """Confianza de una regla a partir de su acierto medido."""
    if not n or hits is None:
        return "uncertain", "this situation has no measured track record"
    rate = hits / n
    if rate >= 0.95:
        return "clear", f"the rule matched the reading urologist in {hits} of {n} labelled cases"
    if rate >= 0.85:
        return "borderline", f"the rule matched the reading urologist in {hits} of {n} labelled cases"
    return "uncertain", f"the rule matched the reading urologist in only {hits} of {n} labelled cases"
