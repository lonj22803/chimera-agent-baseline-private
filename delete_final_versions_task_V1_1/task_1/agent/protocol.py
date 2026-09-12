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
presidente escribe la nota clínica y firma la decisión del protocolo.

**El peldaño 1 va apagado en la configuración de entrega.** Cuando el caso que
se está decidiendo pertenece a la serie etiquetada, la biblioteca encuentra su
propio panel a distancia cero y devuelve la decisión que el urólogo tomó con
él. Sobre el conjunto de test eso **no puede ocurrir nunca** —ningún caso de
test está etiquetado—, así que el peldaño no aporta ni un punto en el reto y a
cambio hace que la nota local sobre los 91 deje de medir nada. Se conserva
implementado y se puede encender (``--self-match``) para comprobar el techo del
mecanismo, pero la entrega corre con la biblioteca en *leave-one-out*: el mismo
programa que correrá en el test, y un número que sí significa algo.

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
    # La biblioteca NO vota. Fuera del caso idéntico su acierto en el cubo
    # positivo es 0.47 —azar—, y darle medio voto costaba 0.033 de ranking en la
    # configuración de entrega (0.8054 con 0.5, 0.8384 con 0.0). Sigue hablando:
    # sus precedentes son evidencia para la sala y su moda por cubo alimenta los
    # pesos. Lo que se le quita es el voto, que es lo que no se ganó.
    "library_weight": 0.0,
    # Carga de la prueba: diferir a un hombre con cáncer conocido y PSA en
    # ascenso exige una razón positiva. Elegido sobre los 91 con el evaluador
    # oficial (0.8215 a 0.50, 0.8384 a 0.45, 0.8222 a 0.40): ver README §5, que
    # publica la rejilla entera porque el umbral se ajustó sobre el mismo
    # conjunto con el que se mide.
    "threshold": 0.45,
    "grade_rule": True,
    # 'agreement' produce una confianza que varía con el caso —acuerdo entre
    # expertos y tramo del que hablan— en vez de la moda constante 'clear' de
    # la política 'trace'. Empata en ranking (0.8390 vs 0.8384) y gana en el
    # componente que mide (0.765 vs 0.759), así que se prefiere la que informa.
    "confidence_policy": "agreement",
    # Qué pesos van al formulario. 'trace': los del Experto 4, entrenado contra
    # la traza del urólogo (0.8506 de variable_weight_score). 'board': los del
    # Experto 4 subidos a 'important' donde al menos dos expertos marcan la
    # variable important/decisive y su sección está abierta. Se mide en
    # analysis/simulate.py antes de elegir; ver README §5.
    "form_weights": "trace",
    "board_min_votes": 2,
}


def _w(params: dict, verdict: dict | None, mult: float = 1.0) -> float:
    if not verdict or not verdict.get("available", True) or verdict.get("p") is None:
        return 0.0
    return params["tier_weight"].get(verdict.get("tier"), 1.0) * mult


VARIABLES = ["bx", "fh", "age", "dre", "psa", "vol", "psad", "cspca", "pirads", "comorbidity"]
_SECTION_OF = {"pirads": "radiology_report", "psad": "radiology_report", "vol": "radiology_report",
               "cspca": "radiology_report", "dre": "laboratory_results", "fh": "family_history"}


def variable_view(payload: dict[str, Any], views: dict[str, dict[str, Any]], trace: dict[str, Any],
                  opened: list[str], *, min_votes: int = 2, policy: str = "trace") -> list[dict[str, Any]]:
    """La tabla de variables de la sala: valor, nivel por experto, y nivel a registrar.

    Es lo que convierte cinco opiniones en una vista: para cada variable del
    formulario, qué dijo cada experto en el vocabulario del formulario, cuántos
    la marcaron important/decisive, y el nivel que se entrega. El nivel que se
    entrega es el del Experto 4 —está entrenado contra la traza del urólogo—
    salvo con la política 'board', que lo sube a 'important' donde el panel
    coincide y la sección que aterriza la variable está abierta.
    """
    from delete_final_versions_task_V1_1.common.vocab import case_values  # noqa: PLC0415
    values = case_values(payload)
    rows: list[dict[str, Any]] = []
    tw = trace.get("variable_weights") or {}
    for v in VARIABLES:
        levels = {who: (d.get("variable_weights") or {}).get(v, "not_used") for who, d in views.items()
                  if d and d.get("variable_weights")}
        strong = [who for who, lvl in levels.items() if lvl in ("important", "decisive")]
        record = tw.get(v, "not_used")
        grounded = (v in ("psa", "age", "bx", "comorbidity")) or (_SECTION_OF.get(v) in (opened or []))
        if policy == "board" and record == "noted" and len(strong) >= min_votes and grounded:
            record = "important"
        # La vista de la sala ya lleva el aterrizaje aplicado: lo que el presidente
        # ve como «record» es exactamente lo que se entrega, y la guardia de
        # aterrizaje del cierre queda como doble comprobación.
        if not grounded and record != "not_used":
            record = "not_used"
        rows.append({"variable": v, "value": values.get(v), "levels": levels, "n_strong": len(strong),
                     "strong_by": strong, "trace": tw.get(v, "not_used"), "record": record,
                     "grounded": grounded})
    return rows


def consolidate(payload: dict[str, Any], cohort: dict[str, Any], structured: dict[str, Any] | None,
                fusion: dict[str, Any] | None, library: dict[str, Any] | None, trace: dict[str, Any],
                grade: dict[str, Any] | None, opened: list[str], *, params: dict | None = None,
                psa: dict[str, Any] | None = None) -> dict[str, Any]:
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
        vote("EXPERT-EXPERIENCE", library["answer"], library["p_yes"],
             999.0 if library.get("self_match") else params["library_weight"],
             "identical panel in the series" if library.get("self_match") else f"k={library['k']} precedents")
    if cohort.get("verdict") in ("yes", "no"):
        vote("EXPERT-COHORT", cohort["verdict"], None, 0.0, f"rule {cohort.get('fired')}")

    # -- la cascada ----------------------------------------------------------
    decision = rule = who = track = None
    p_final = None
    if library and library.get("self_match"):
        decision = library["answer"]
        who, rule = "EXPERT-EXPERIENCE", "identical precedent in the labelled series"
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
        if who in ("EXPERT-EXPERIENCE", "EXPERT-COHORT", "documented grade"):
            confidence = "clear"
        elif answers and len(set(answers)) == 1 and any(t in ("firm", "supports") for t in tiers):
            confidence = "clear"
        elif answers and len(set(answers)) == 1:
            confidence = "borderline"
        else:
            confidence = "uncertain" if all(t == "discuss" for t in tiers) else "borderline"

    disagree = [v["who"] for v in votes if v["answer"] in ("yes", "no") and v["answer"] != decision]
    view = variable_view(payload, {"EXPERT-STRUCTURED": structured or {}, "EXPERT-FUSION": fusion or {},
                                   "EXPERT-COHORT": cohort or {}, "EXPERT-EXPERIENCE": library or {},
                                   "EXPERT-PSA": psa or {}},
                         trace, opened, min_votes=int(params.get("board_min_votes", 2)),
                         policy=str(params.get("form_weights", "trace")))
    form_weights = {r["variable"]: r["record"] for r in view}
    return {
        "decision": decision, "p": None if p_final is None else round(p_final, 4),
        "rule": rule, "who": who, "track": track, "confidence": confidence,
        "variable_weights": form_weights, "variable_view": view,
        "planned_sections": list(trace.get("reveal_sequence") or []),
        "opened": list(opened), "votes": votes, "dissenting": disagree,
        "grade": grade, "params": {k: v for k, v in params.items() if k != "tier_weight"},
    }


def _num(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def clinical_reason(payload: dict[str, Any], grade: dict[str, Any] | None, opened: list[str],
                    decision: str) -> tuple[str, str | None, str | None]:
    """Por qué, qué tira en contra, y qué alternativa admite el caso.

    No menciona la cascada ni al colega que la carga: traduce los HECHOS del
    caso a la justificación clínica de la decisión que se firma. Es lo que entra
    en el parte del presidente (:func:`prompts.clinical_digest`) y en la nota de
    respaldo (:func:`decide.clinical_note`), y por eso ninguna de las dos puede
    nombrar la maquinaria: no la tienen delante.
    """
    p = payload or {}
    g = grade or {}
    bx = str(p.get("bx") or "None").strip()
    pirads = _num(p.get("pirads"))
    psa = _num(p.get("psa"))
    psad = _num(p.get("psad"))
    age = _num(p.get("age"))
    yes = decision == "yes"
    pi = f"PI-RADS {p.get('pirads')}" if pirads is not None else "the imaging"

    because, against, alternative = "", None, None

    if bx == "None":
        if yes:
            because = f"a {pi} lesion in a man who has never been biopsied is an indication to sample"
            if psad is not None and psad >= 0.15:
                because += f", and the PSA density of {psad:g} supports it"
            elif psad is not None and psad < 0.10:
                against = f"the PSA density is low at {psad:g}"
        else:
            because = f"there is no target worth sampling on the current scan ({pi})"
            if psa is not None:
                because += f" and the PSA of {psa:g} ng/mL is only modestly raised"
            alternative = "re-check the PSA, and biopsy only if it keeps rising"
    elif bx == "Negative":
        if yes:
            because = (f"a {pi} lesion after a negative biopsy is an indication for a repeat, targeted "
                       "biopsy of the visible lesion")
            if psad is not None and psad < 0.10:
                against = f"the previous biopsy was benign and the PSA density is low at {psad:g}"
                alternative = ("there is no rush: waiting a year is tolerable if he prefers, with a new "
                               "biopsy within a few years")
        else:
            because = (f"{pi} without a rising PSA density does not justify repeating a biopsy that was "
                       "already benign")
            alternative = "re-image in a year, with a low threshold for biopsy if the lesion changes"
    else:  # Positive / atypical
        if psa is not None and psa >= 20:
            because = (f"with a PSA of {psa:g} ng/mL and a tissue diagnosis already made, the next step is "
                       "staging and treatment rather than more tissue")
            if pirads is not None and pirads >= 4:
                against = f"the {pi} lesion"
            # Sin alternativa: un hombre con esa carga de enfermedad no admite
            # «retrasarlo un año», y ofrecerlo contradice la propia decision.
        elif age is not None and age >= 78:
            because = f"at {age:g} further diagnostics would not change what is offered to him"
        elif pirads is not None and pirads <= 2:
            because = "there is nothing to target on the current scan"
            alternative = "follow the PSA, and re-image if it rises"
        elif g.get("gg") is not None and int(g["gg"]) >= 2:
            because = (f"the prior biopsy is documented as {g.get('quote')}, so the disease is already "
                       "characterised and a repeat biopsy would not change management")
            if pirads is not None and pirads >= 4:
                against = f"the {pi} lesion"
        elif g.get("gg") is not None and int(g["gg"]) == 1:
            because = (f"low-grade disease ({g.get('quote')}) with only one previous biopsy session: a "
                       "confirmatory biopsy is what is due here")
            alternative = "delaying it a year and sampling then is defensible"
        elif yes:
            because = ("the grade of the previous biopsy is nowhere recorded, so sampling is what would let "
                       "treatment be chosen")
            if psad is not None and psad < 0.10:
                against = f"the low PSA density of {psad:g}"
                alternative = "delaying it a year is defensible if he prefers"
        else:
            because = "the picture is unchanged and a repeat biopsy would add risk without adding information"
            if pirads is not None and pirads >= 4:
                against = f"the {pi} lesion"
            alternative = "re-image in two years, with a low threshold for biopsy then"

    if not because:
        because = "biopsy is indicated" if yes else "biopsy can be deferred"
    if "radiology_report" in (opened or []) and g.get("comparison_missing"):
        against = (against + "; " if against else "") + "there is no earlier scan to compare against"
    return because, against, alternative


def render(result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    verdict = "BIOPSY" if result["decision"] == "yes" else "NO BIOPSY"
    lines = ["The panel protocol, applied to what is on the board:", ""]
    for v in result["votes"]:
        if v["answer"] is None:
            continue
        p = f", p(biopsy)={v['p']:.2f}" if v["p"] is not None else ""
        w = ("does not vote" if not v["weight"] else f"weight {v['weight']:.1f}")
        lines.append(f"  {v['who']:<18} {'BIOPSY' if v['answer'] == 'yes' else 'DEFER'}{p}  ({v['note']}; {w})")
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
    lines.append("")
    lines.append("THE BOARD'S VARIABLES — value · what each expert marked · what goes on the form")
    who_order = ["EXPERT-STRUCTURED", "EXPERT-FUSION", "EXPERT-COHORT", "EXPERT-EXPERIENCE", "EXPERT-PSA"]
    short = {"EXPERT-STRUCTURED": "E1", "EXPERT-FUSION": "E3", "EXPERT-COHORT": "cohort",
             "EXPERT-EXPERIENCE": "library", "EXPERT-PSA": "E2"}
    abbrev = {"decisive": "DEC", "important": "IMP", "noted": "not", "not_used": "—"}
    for r in result.get("variable_view") or []:
        marks = " ".join(f"{short[w]}:{abbrev.get(r['levels'].get(w, 'not_used'), '?')}"
                         for w in who_order if w in r["levels"])
        tag = "" if r["record"] == r["trace"] else f" (raised from {r['trace']} by the board)"
        lines.append(f"  {r['variable']:<12} {str(r['value'])[:28]:<28} {marks:<52} -> {r['record']}{tag}")
    lines.append("  (DEC decisive · IMP important · not noted · — not used; the last column is the level recorded, "
                 "from the trace of the reading urologist)")
    lines.append("")
    lines.append(f"Confidence to record: {result['confidence']}.")
    lines.append("")
    lines.append("CHAIR: this is the panel's position. You sign it, and you write why in the room's words — "
                 "naming what the registrar retrieved. If you believe a retrieved finding overturns it, "
                 "name that finding with its value; the burden is on the finding, not on the panel.")
    body = "\n".join(lines)
    data = {**result, "gist": f"protocol: {verdict} by {result['rule']}"}
    return body, data
