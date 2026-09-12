"""Bloque A — características de ``structured-prompt.json``.

Estas son las variables que la guía EAU 2024 y las calculadoras de riesgo
validadas (ERSPC/RPCRC, PBCG) usan para decidir biopsia: PSA, volumen
prostático, PSA density, tacto rectal, biopsia previa, edad y categoría
PI-RADS. Se añade la probabilidad csPCa producida por el modelo de detección
del reto, que es el único resumen de la imagen que el organizador expone ya
calibrado.

Convención de valores ausentes: ``float('nan')``. No se imputa aquí. La
imputación es parte del pipeline del modelo para que el fold de validación
nunca vea estadísticos del fold de test.
"""

from __future__ import annotations

import math
import re

NAN = float("nan")

#: PI-RADS v2.1 es ordinal 1-5. ``NA``/ausente -> NaN (el modelo lo imputa y el
#: contador de completitud lo registra).
_PIRADS_MAP = {"1": 1.0, "2": 2.0, "3": 3.0, "4": 4.0, "5": 5.0}

#: Tacto rectal -> sospecha binaria. ``Not done`` es ausencia de información,
#: no ausencia de hallazgo: va a NaN, que es distinto de "normal".
_DRE_SUSPICIOUS = {"normal": 0.0, "nodus": 1.0, "abnormal": 1.0, "suspicious": 1.0}

#: Estado de biopsia previa. Se codifica como dos indicadores en lugar de un
#: ordinal porque "sin biopsia previa" y "biopsia previa negativa" son ramas
#: distintas de la ERSPC (RC3 vs RC4), no grados de una misma escala.
_BX_STATES = ("None", "Negative", "Positive")

#: Comorbilidades observadas en el corpus (vocabulario cerrado de 10 términos).
_PMHX_VOCAB = [
    "Hypertension",
    "Hypercholesterolaemia",
    "Benign prostatic hyperplasia",
    "Osteoarthritis",
    "Chronic kidney disease",
    "Type 2 diabetes",
    "Obesity (BMI >30)",
    "COPD",
    "Coronary artery disease",
    "Atrial fibrillation",
]

#: Índice de Charlson simplificado: peso 1 a las condiciones con peso 1 en
#: Charlson et al. (1987) presentes en el vocabulario; el resto no puntúa.
_CHARLSON_WEIGHTS = {
    "Chronic kidney disease": 2,
    "Type 2 diabetes": 1,
    "COPD": 1,
    "Coronary artery disease": 1,
    "Atrial fibrillation": 1,
}


def _f(x) -> float:
    """Coerción numérica tolerante: cualquier cosa no numérica -> NaN."""
    if x is None:
        return NAN
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        return NAN if (isinstance(x, float) and math.isnan(x)) else float(x)
    m = re.search(r"[-+]?\d*\.?\d+", str(x))
    return float(m.group()) if m else NAN


def _safe_log1p(x: float) -> float:
    return math.log1p(x) if x == x and x > -1 else NAN


def _safe_div(a: float, b: float) -> float:
    if a != a or b != b or b == 0:
        return NAN
    return a / b


def extract(prompt: dict) -> dict[str, float]:
    """Devuelve el vector de características del bloque A para un caso."""
    p = prompt or {}

    psa = _f(p.get("psa"))
    psap = _f(p.get("psap"))
    vol = _f(p.get("vol"))
    psad = _f(p.get("psad"))
    psav = _f(p.get("psav"))
    age = _f(p.get("age"))
    cspca = _f(p.get("cspca"))

    # PSAD recalculada: en algunos casos la publicada está redondeada a 2
    # decimales, lo que colapsa próstatas grandes. Se conservan ambas.
    psad_calc = _safe_div(psa, vol)

    pirads_raw = str(p.get("pirads", "")).strip()
    pirads = _PIRADS_MAP.get(pirads_raw, NAN)

    dre_raw = str(p.get("dre", "")).strip().lower()
    dre_susp = _DRE_SUSPICIOUS.get(dre_raw, NAN)

    bx_raw = str(p.get("bx", "")).strip()
    bx = {f"bx_{s.lower()}": float(bx_raw == s) for s in _BX_STATES}
    if bx_raw not in _BX_STATES:
        bx = {k: NAN for k in bx}

    pmhx = p.get("pmhx") or []
    pmhx_set = {str(x).strip() for x in pmhx}
    # ``medhx``/``pmhx`` vacío significa "no reportado", no "sin comorbilidad":
    # se marca la ausencia explícitamente en lugar de asumir cero.
    comorbidity_reported = float(bool(pmhx) or str(p.get("medhx", "")).strip() not in ("", "Not reported"))

    vitals = p.get("vitals") or {}
    bmi = _f(vitals.get("bmi"))
    ipss = _f(p.get("ipss"))

    meds_raw = str(p.get("meds", "")).strip().lower()
    n_meds = 0.0 if meds_raw in ("", "none") else float(len([m for m in meds_raw.split(",") if m.strip()]))
    # Los 5-ARI (finasterida/dutasterida) reducen el PSA ~50 % y son el
    # confusor clásico de cualquier regla basada en PSA (Thompson et al. 2003).
    on_5ari = float(bool(re.search(r"finasterid|dutasterid", meds_raw)))
    on_alpha_blocker = float(bool(re.search(r"tamsulosin|alfuzosin|silodosin|doxazosin", meds_raw)))

    feats: dict[str, float] = {
        "psa": psa,
        "log_psa": _safe_log1p(psa),
        "psa_prev": psap,
        "psa_ratio_prev": _safe_div(psa, psap),
        "psa_delta_prev": psa - psap if (psa == psa and psap == psap) else NAN,
        "psav": psav,
        "psav_positive": float(psav > 0) if psav == psav else NAN,
        "vol": vol,
        "log_vol": _safe_log1p(vol),
        "psad": psad,
        "psad_calc": psad_calc,
        "log_psad": _safe_log1p(psad_calc if psad_calc == psad_calc else psad),
        "age": age,
        "pirads": pirads,
        "pirads_ge4": float(pirads >= 4) if pirads == pirads else NAN,
        "pirads_ge3": float(pirads >= 3) if pirads == pirads else NAN,
        "dre_suspicious": dre_susp,
        "cspca": cspca,
        "months_since_mri": _f(p.get("months")),
        "bmi": bmi,
        "ipss": ipss,
        "n_comorbidities": float(len(pmhx_set)) if comorbidity_reported else NAN,
        "charlson_like": (
            float(sum(_CHARLSON_WEIGHTS.get(c, 0) for c in pmhx_set)) if comorbidity_reported else NAN
        ),
        "comorbidity_reported": comorbidity_reported,
        "n_meds": n_meds,
        "on_5ari": on_5ari,
        "on_alpha_blocker": on_alpha_blocker,
    }
    feats.update(bx)
    for c in _PMHX_VOCAB:
        key = "pmhx_" + re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_")
        feats[key] = float(c in pmhx_set) if comorbidity_reported else NAN

    return feats


#: Subconjunto "núcleo EAU/ERSPC": las siete variables que las calculadoras
#: validadas usan. Sirve como bloque mínimo en el estudio de ablación.
CORE_KEYS = ["log_psa", "log_vol", "log_psad", "age", "pirads", "dre_suspicious", "bx_negative", "bx_none"]
