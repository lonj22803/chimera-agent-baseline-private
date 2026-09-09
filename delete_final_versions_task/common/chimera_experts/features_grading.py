"""Bloque G — grado, estadio y grupo de riesgo de guía (tarea 2).

El bloque A (`features_structured`) se escribió para la tarea 1, donde la
biopsia todavía no existe. En la tarea 2 la biopsia **ya está hecha**, y sus
cuatro campos —``bx_isup``, ``bx_gl_prim``, ``bx_gl_sec``, ``ct``— son la
columna vertebral de la decisión: la etiqueta se derivó retrospectivamente de
la histopatología y del PSA según EAU/NCCN. Este módulo los codifica y añade
las reglas de guía como variables explícitas, no como post-proceso.

Que las reglas entren *como variables* y no como un `if` final es deliberado:
así el clasificador puede aprender **cuándo la guía no se cumplió**, que es
exactamente donde están los casos difíciles de esta cohorte.

Referencias
-----------
* Mottet N. et al., *EAU-EANM-ESTRO-ESUR-SIOG Guidelines on Prostate Cancer*,
  Eur Urol 2021 — grupos de riesgo D'Amico/EAU y criterios de vigilancia activa.
* NCCN Clinical Practice Guidelines in Oncology: Prostate Cancer, v4.2024 —
  estratificación muy-bajo/bajo/intermedio favorable/intermedio desfavorable/alto.
* Epstein J.I. et al., *A Contemporary Prostate Cancer Grading System*,
  Eur Urol 2016 — ISUP grade groups.
* D'Amico A.V. et al., JAMA 1998 — definición original de los tres grupos.
"""

from __future__ import annotations

import re

NAN = float("nan")

#: Estadio clínico T ordenado. ``cTx`` es desconocido, no un valor bajo.
_CT_ORDER = {
    "ct1": 1.0, "ct1a": 1.0, "ct1b": 1.0, "ct1c": 1.0,
    "ct2": 2.0, "ct2a": 2.0, "ct2b": 2.5, "ct2c": 2.8,
    "ct3": 3.0, "ct3a": 3.0, "ct3b": 3.5, "ct4": 4.0,
}


def _f(x) -> float:
    try:
        if x is None or x == "":
            return NAN
        return float(x)
    except (TypeError, ValueError):
        m = re.search(r"-?\d+(?:\.\d+)?", str(x))
        return float(m.group()) if m else NAN


def extract(prompt: dict) -> dict[str, float]:
    p = prompt or {}

    isup = _f(p.get("bx_isup"))
    gl1 = _f(p.get("bx_gl_prim"))
    gl2 = _f(p.get("bx_gl_sec"))
    psa = _f(p.get("psa"))
    psad = _f(p.get("psad"))
    vol = _f(p.get("vol"))
    age = _f(p.get("age"))

    ct_raw = str(p.get("ct", "")).strip().lower()
    ct = _CT_ORDER.get(ct_raw, NAN)
    ct_unknown = float(ct_raw in ("ctx", "tx"))

    bx_positive = float(str(p.get("bx", "")).strip().lower() == "positive")
    bx_negative = float(str(p.get("bx", "")).strip().lower() == "negative")

    gleason_sum = gl1 + gl2 if (gl1 == gl1 and gl2 == gl2) else NAN
    # Un 4+3 pesa más que un 3+4 con la misma suma: el patrón primario manda.
    pattern4_primary = float(gl1 >= 4) if gl1 == gl1 else NAN
    any_pattern5 = float(gl1 >= 5 or gl2 >= 5) if (gl1 == gl1 and gl2 == gl2) else NAN

    # --- grupos de riesgo EAU (enfermedad localizada) ---
    have = isup == isup and psa == psa and ct == ct
    if have:
        eau_high = float(psa > 20 or isup >= 4 or ct >= 2.8)
        eau_low = float(psa < 10 and isup <= 1 and ct <= 2.0 and isup >= 1)
        eau_intermediate = float(not eau_high and not eau_low and isup >= 1)
    else:
        eau_high = eau_low = eau_intermediate = NAN

    # --- intermedio favorable vs desfavorable (NCCN) ---
    # Factores intermedios: PSA 10-20, ISUP 2-3, cT2b-c. Favorable = ISUP 2
    # (3+4) con un solo factor; desfavorable = 4+3 o dos o más factores.
    if have:
        n_ir_factors = float((10 <= psa <= 20) + (2 <= isup <= 3) + (2.5 <= ct < 3))
        ir_favourable = float(eau_intermediate == 1 and isup == 2 and gl1 == 3 and n_ir_factors <= 1)
        ir_unfavourable = float(eau_intermediate == 1 and not ir_favourable)
    else:
        n_ir_factors = ir_favourable = ir_unfavourable = NAN

    # --- elegibilidad de vigilancia activa (EAU) ---
    # ISUP 1, PSA < 10, cT1c/T2a, PSAD < 0.15. La variante "extendida" admite
    # ISUP 2 de bajo volumen, que es justo la zona gris de esta cohorte.
    psad_eff = psad if psad == psad else (psa / vol if (psa == psa and vol == vol and vol > 0) else NAN)
    if isup == isup and psa == psa and ct == ct and psad_eff == psad_eff:
        as_strict = float(isup == 1 and psa < 10 and ct <= 2.0 and psad_eff < 0.15)
        as_extended = float(isup <= 2 and gl1 <= 3 and psa < 20 and ct <= 2.0 and psad_eff < 0.20)
    else:
        as_strict = as_extended = NAN

    # --- eje de expectativa de vida (watchful waiting) ---
    # WW se reserva a quien no se beneficiaría de un tratamiento radical por
    # esperanza de vida < 10 años (EAU). Aquí sólo la parte demográfica; la
    # carga de comorbilidad va en el bloque I.
    life_exp_short = float(age >= 75) if age == age else NAN

    return {
        "bx_isup": isup,
        "bx_isup_ge2": float(isup >= 2) if isup == isup else NAN,
        "bx_isup_ge3": float(isup >= 3) if isup == isup else NAN,
        "bx_isup_ge4": float(isup >= 4) if isup == isup else NAN,
        "bx_isup_zero": float(isup == 0) if isup == isup else NAN,
        "gleason_prim": gl1,
        "gleason_sec": gl2,
        "gleason_sum": gleason_sum,
        "gleason_pattern4_primary": pattern4_primary,
        "gleason_any_pattern5": any_pattern5,
        "ct_stage": ct,
        "ct_unknown": ct_unknown,
        "ct_ge_t2": float(ct >= 2.0) if ct == ct else NAN,
        "ct_ge_t3": float(ct >= 3.0) if ct == ct else NAN,
        "bx_positive": bx_positive,
        "bx_negative": bx_negative,
        "eau_low": eau_low,
        "eau_intermediate": eau_intermediate,
        "eau_high": eau_high,
        "nccn_ir_factors": n_ir_factors,
        "nccn_ir_favourable": ir_favourable,
        "nccn_ir_unfavourable": ir_unfavourable,
        "as_eligible_strict": as_strict,
        "as_eligible_extended": as_extended,
        "psa_ge10": float(psa >= 10) if psa == psa else NAN,
        "psa_ge20": float(psa >= 20) if psa == psa else NAN,
        "psad_ge015": float(psad_eff >= 0.15) if psad_eff == psad_eff else NAN,
        "life_exp_short": life_exp_short,
    }


#: Las cuatro variables de las que la etiqueta se derivó retrospectivamente.
CORE_KEYS = ["bx_isup", "gleason_prim", "gleason_sec", "ct_stage"]
