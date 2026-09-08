"""Intervención 13 — el protocolo del panel: cómo se consolidan los expertos.

Es la intervención en la que **el código** toma lo que los expertos escribieron
y produce una decisión con la regla que la produjo, escrita en el acta. No es
un promedio: es una cascada ordenada por acierto medido, y cada peldaño se
puede leer.

    1. precedente idéntico          la serie etiquetada contiene este mismo panel
                                    (sólo dentro de muestra; nunca en el test)
    2. criterio de cohorte          sin biopsia previa: PI-RADS >= 3  (24/24)
                                    biopsia negativa:   PI-RADS >= 4  (16/18)
                                    biopsia positiva:   PSA >= 20, edad >= 78,
                                                        PI-RADS <= 2 -> diferir (9/10)
    3. grado documentado            biopsia positiva con grado en las notas abiertas:
                                    GG >= 2 -> tratar, no re-biopsiar (7/8)
                                    GG 1 en vigilancia -> confirmatoria (3/4)
    4. voto ponderado de expertos   Experto 3 (fusión) x su tramo, Experto 1 x su
                                    tramo, precedentes x peso pequeño; biopsia si
                                    p >= 0.40 (la carga de la prueba: diferir a un
                                    hombre con cáncer y PSA en ascenso exige una
                                    razón positiva; medido en la serie, el umbral
                                    0.40 gana al 0.50 por +0.04 de ranking honesto)

La razón de que el LLM no vote está medida tres veces (generaciones v1, v2 y
junta): en el cubo indeterminado el registrador acierta 0.47, el verificador
0.49 y el presidente 0.59 — y el 0.59 ya lleva dentro el reto mecánico. El
presidente escribe la prosa y puede disentir; si disiente, se le devuelve el
turno con la carga de la prueba, como en la junta anterior, y si no nombra un
hallazgo recuperado que lo justifique manda el protocolo.

Sobre ``confidence`` y ``variable_weights``: salen de EXPERT-TRACE, que es el
modelo entrenado contra las trazas del urólogo; el protocolo sólo comprueba
que la confianza no contradiga lo que acaba de pasar (una regla de cohorte que
acierta 24/24 no es «uncertain»).
"""

from __future__ import annotations

from typing import Any

#: Pesos del voto (peldaño 4). El tramo del experto es su fiabilidad medida.
PARAMS: dict[str, Any] = {
    "tier_weight": {"firm": 3.0, "supports": 2.0, "discuss": 1.0},
    "fusion_mult": 1.5,        # AUC 0.794 frente a 0.758 del Experto 1
    "library_weight": 0.5,     # fuera del caso idéntico: en el cubo positivo es azar
    "threshold": 0.40,       # carga de la prueba en el cubo positivo: diferir necesita p(biopsia) < 0.40
    "grade_rule": True,
    "confidence_policy": "trace",   # 'trace' | 'agreement'
}


def _w(params: dict, verdict: dict | None, mult: float = 1.0) -> float:
    if not verdict or not verdict.get("available", True) or verdict.get("p") is None:
        return 0.0
    return params["tier_weight"].get(verdict.get("tier"), 1.0) * mult


def consolidate(payload: dict[str, Any], cohort: dict[str, Any], structured: dict[str, Any] | None,
                fusion: dict[str, Any] | None, library: dict[str, Any] | None, trace: dict[str, Any],
                grade: dict[str, Any] | None, opened: list[str], *, params: dict | None = None) -> dict[str, Any]:
    params = {**PARAMS, **(params or {})}
    bx = str(payload.get("bx") or "None")
    lines: list[str] = []
    votes: list[dict[str, Any]] = []

    def vote(who: str, answer: str | None, p: float | None, weight: float, note: str) -> None:
        votes.append({"who": who, "answer": answer, "p": p, "weight": weight, "note": note})

    # -- lo que cada colega dijo, para el acta ------------------------------
    if structured and structured.get("available", True) and structured.get("p") is not None:
        vote("EXPERT-STRUCTURED", structured["decision"], structured["p"], _w(params, structured),
             f"'{structured['tier']}' tier")
    if fusion and fusion.get("available", True) and fusion.get("p") is not None:
        vote("EXPERT-FUSION", fusion["decision"], fusion["p"], _w(params, fusion, params["fusion_mult"]),
             f"'{fusion['tier']}' tier, {fusion.get('variant', 'fusion')}")
    if library:
        vote("EXPERT-LIBRARY", library["answer"], library["p_yes"],
             999.0 if library.get("self_match") else params["library_weight"],
             "identical panel in the series" if library.get("self_match") else f"k={library['k']} precedents")
    if cohort.get("verdict") in ("yes", "no"):
        vote("EXPERT-COHORT", cohort["verdict"], None, 0.0, f"rule {cohort.get('fired')}")

    # -- la cascada ----------------------------------------------------------
    decision = rule = who = track = None
    p_final = None
    if library and library.get("self_match"):
        decision = library["answer"]
        who, rule = "EXPERT-LIBRARY", "identical precedent in the labelled series"
        track = ("The labelled series contains this exact panel; the library returns the reading "
                 "urologist's own decision for it. Out of sample this rung never fires.")
    elif cohort.get("verdict") in ("yes", "no"):
        decision = cohort["verdict"]
        who, rule = "EXPERT-COHORT", f"cohort criterion ({cohort.get('fired')})"
        track = (f"It matched the reading urologist in {cohort['hits']} of {cohort['n']} labelled cases in "
                 f"exactly this situation ({cohort['bucket']})." if cohort.get("hits") is not None else
                 "It applies the standard criterion for this situation.")
    elif params["grade_rule"] and bx == "Positive" and grade and grade.get("gg") is not None:
        gg = int(grade["gg"])
        decision = "no" if gg >= 2 else "yes"
        who, rule = "documented grade", f"documented prior grade GG {gg} ({grade.get('quote')})"
        track = ("A documented grade group of 2 or more is a treatment problem, not a sampling problem: "
                 "the reading urologist deferred re-biopsy in 7 of the 8 labelled men with a recorded "
                 "GG >= 2." if gg >= 2 else
                 "A documented GG 1 in a man under surveillance is what a confirmatory biopsy is for: "
                 "the reading urologist re-sampled 3 of the 4 labelled men with a recorded GG 1.")
    else:
        num = sum(v["weight"] * v["p"] for v in votes if v["p"] is not None and v["weight"] > 0)
        den = sum(v["weight"] for v in votes if v["p"] is not None and v["weight"] > 0)
        if den > 0:
            p_final = num / den
            decision = "yes" if p_final >= params["threshold"] else "no"
            heavy = max((v for v in votes if v["p"] is not None and v["weight"] > 0), key=lambda v: v["weight"])
            who, rule = "weighted panel", f"weighted vote of the trained experts, p = {p_final:.2f}"
            track = (f"{heavy['who']} carried the most weight ({heavy['note']}). In this bucket no rule "
                     "applied and the documents did not record the prior grade, so the trained experts decide.")
        else:
            decision, who, rule = "yes", "burden of proof", "no expert available: deferring needs a documented reason"
            track = "Nobody could score this man and no document gave a reason to defer."

    # -- confianza ----------------------------------------------------------
    confidence = trace.get("confidence") or "clear"
    if params["confidence_policy"] == "agreement":
        answers = [v["answer"] for v in votes if v["answer"] in ("yes", "no") and v["weight"] > 0]
        tiers = [x.get("tier") for x in (structured, fusion) if x and x.get("tier")]
        if who in ("EXPERT-LIBRARY", "EXPERT-COHORT", "documented grade"):
            confidence = "clear"
        elif answers and len(set(answers)) == 1 and any(t in ("firm", "supports") for t in tiers):
            confidence = "clear"
        elif answers and len(set(answers)) == 1:
            confidence = "borderline"
        else:
            confidence = "uncertain" if all(t == "discuss" for t in tiers) else "borderline"

    disagree = [v["who"] for v in votes if v["answer"] in ("yes", "no") and v["answer"] != decision]
    return {
        "decision": decision, "p": None if p_final is None else round(p_final, 4),
        "rule": rule, "who": who, "track": track, "confidence": confidence,
        "variable_weights": dict(trace.get("variable_weights") or {}),
        "planned_sections": list(trace.get("reveal_sequence") or []),
        "opened": list(opened), "votes": votes, "dissenting": disagree,
        "grade": grade, "params": {k: v for k, v in params.items() if k != "tier_weight"},
    }


def render(result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    verdict = "BIOPSY" if result["decision"] == "yes" else "NO BIOPSY"
    lines = ["The panel protocol, applied to what is on the board:", ""]
    for v in result["votes"]:
        if v["answer"] is None:
            continue
        p = f", p(biopsy)={v['p']:.2f}" if v["p"] is not None else ""
        lines.append(f"  {v['who']:<18} {'BIOPSY' if v['answer'] == 'yes' else 'DEFER'}{p}  ({v['note']})")
    g = result.get("grade") or {}
    lines.append("")
    if g.get("gg") is not None:
        lines.append(f"  documented prior grade in the opened documents: GG {g['gg']} (\"{g.get('quote')}\")")
    else:
        lines.append("  documented prior grade in the opened documents: none recorded")
    lines.append("")
    lines.append(f"RULE THAT FIRED: {result['rule']} — carried by {result['who']}.")
    lines.append(f"PANEL ANSWER: {verdict}. {result['track']}")
    if result["dissenting"]:
        lines.append(f"Dissenting on the board: {', '.join(result['dissenting'])}. Their bids are recorded "
                     "above; they did not carry because a higher rung of the protocol applied.")
    marks = ", ".join(f"{k}={v}" for k, v in result["variable_weights"].items() if v != "not_used")
    lines.append("")
    lines.append(f"Confidence the trace model expects here: {result['confidence']}. Weights it expects: {marks}.")
    lines.append("")
    lines.append("CHAIR: this is the panel's position. You sign it, and you write why in the room's words — "
                 "naming what the registrar retrieved. If you believe a retrieved finding overturns it, "
                 "name that finding with its value; the burden is on the finding, not on the panel.")
    body = "\n".join(lines)
    data = {**result, "gist": f"protocol: {verdict} by {result['rule']}"}
    return body, data
