"""Bloque I — estado funcional, comorbilidad y expectativa de vida (tarea 2).

Este bloque existe por una sola clase: ``watchful_waiting``. Las guías la
reservan a quien **no se beneficiaría** de un tratamiento con intención
curativa por esperanza de vida corta o comorbilidad competitiva, no a quien
tiene poco cáncer. Es decir, la separan del resto variables que no describen el
tumor. Ninguna de ellas está en el bloque A con la forma que hace falta:

* ``ipss`` llega como texto (``"IPSS score: 12/35 (moderate LUTS)"``). Los LUTS
  graves aparecen en esta cohorte como argumento explícito para tratar —
  cirugía que resuelve a la vez el cáncer de bajo riesgo y la obstrucción.
* ``exercise``, ``living`` y ``vitals.smoking`` son texto libre que codifica
  capacidad funcional, soporte social y carga tabáquica.
* La analítica (Hb, eGFR, albúmina) marca la reserva fisiológica.

El índice de comorbilidad se calcula con los pesos de Charlson y se convierte
a una probabilidad de supervivencia a 10 años con la ecuación original; **no**
es una predicción clínica, es una variable ordenada que resume edad y
comorbilidad en la escala en la que la guía razona.

Referencias
-----------
* Charlson M.E. et al., *A new method of classifying prognostic comorbidity*,
  J Chronic Dis 1987 — pesos e integración con la edad.
* Barry M.J. et al., *The American Urological Association symptom index for
  benign prostatic hyperplasia*, J Urol 1992 — IPSS y sus tramos (0-7 leve,
  8-19 moderado, 20-35 grave).
* Mottet N. et al., EAU Guidelines 2021 — *watchful waiting* frente a
  vigilancia activa: el criterio es la esperanza de vida, no el grado.
* Droz J.P. et al., *Management of prostate cancer in older patients*
  (SIOG), BJU Int 2010 — evaluación geriátrica en cáncer de próstata.
"""

from __future__ import annotations

import math
import re

NAN = float("nan")

#: Pesos de Charlson para las condiciones presentes en el vocabulario del corpus.
CHARLSON = {
    "myocardial infarction": 1, "coronary artery disease": 1, "congestive heart failure": 1,
    "atrial fibrillation": 1, "peripheral vascular disease": 1, "cerebrovascular": 1,
    "stroke": 1, "dementia": 1, "copd": 1, "asthma": 1, "connective tissue": 1,
    "peptic ulcer": 1, "liver disease": 1, "type 2 diabetes": 1, "diabetes": 1,
    "hemiplegia": 2, "chronic kidney disease": 2, "renal": 2, "leukaemia": 2,
    "lymphoma": 2, "tumour": 2, "cancer": 2, "cirrhosis": 3, "metastatic": 6, "aids": 6,
}

#: Capacidad funcional aproximada a partir del texto de ``exercise``.
#: 0 = limitado a silla, 3 = deporte regular de intensidad moderada-alta.
_EXERCISE_LEVEL = [
    (r"limited\s+mobility|chair[-\s]based|wheelchair", 0.0),
    (r"sedentary|no\s+structured\s+exercise|gardening", 1.0),
    (r"walking\s+20|light\s+weight|swimming\s+1x|golf", 2.0),
    (r"walking\s+45|cycling|hiking|tennis|running|swimming\s+[2-9]x", 3.0),
]

#: Soporte social y entorno. Vivir en institución es la señal más fuerte.
_LIVING_SUPPORT = [
    (r"assisted[-\s]living|nursing", 0.0),
    (r"retirement\s+community", 1.0),
    (r"lives\s+alone(?!;)", 1.0),
    (r"lives\s+alone;", 1.5),
    (r"ground[-\s]floor", 1.5),
    (r"partner|sister|adult\s+child|multi[-\s]generational|farm", 2.0),
]


def _f(x) -> float:
    try:
        if x is None or x == "":
            return NAN
        return float(x)
    except (TypeError, ValueError):
        m = re.search(r"-?\d+(?:\.\d+)?", str(x))
        return float(m.group()) if m else NAN


def _first_match(text: str, table) -> float:
    for pat, val in table:
        if re.search(pat, text, flags=re.I):
            return val
    return NAN


def _lab(clinical: dict, name: str) -> float:
    for row in (clinical or {}).get("laboratory_results") or []:
        if str(row.get("name", "")).strip().lower() == name:
            return _f(row.get("val"))
    return NAN


def extract(prompt: dict, clinical: dict | None = None) -> dict[str, float]:
    p = prompt or {}
    cl = clinical or {}

    age = _f(p.get("age"))

    # --- IPSS: severidad de los síntomas del tracto urinario inferior ---
    ipss_raw = str(p.get("ipss", ""))
    m = re.search(r"(\d+)\s*/\s*35", ipss_raw)
    ipss = float(m.group(1)) if m else _f(ipss_raw)
    ipss_severe = float(ipss >= 20) if ipss == ipss else NAN
    ipss_moderate = float(8 <= ipss < 20) if ipss == ipss else NAN

    # --- carga de comorbilidad ---
    pmhx = [str(x).strip().lower() for x in (p.get("pmhx") or [])]
    medhx = str(p.get("medhx", "")).strip().lower()
    reported = bool(pmhx) or medhx not in ("", "not reported")
    charlson = 0.0
    for cond in pmhx:
        for key, w in CHARLSON.items():
            if key in cond:
                charlson += w
                break
    # Puntos por edad de Charlson: +1 por década a partir de 50.
    age_points = max(0.0, math.floor((age - 40) / 10.0)) if age == age else NAN
    cci = charlson + age_points if age_points == age_points else NAN
    # Supervivencia estimada a 10 años, Charlson 1987: exp(-e^{0.9·CCI}·0.983^{-1}).
    surv10 = float(0.983 ** math.exp(cci * 0.9)) if cci == cci else NAN

    # --- capacidad funcional y soporte ---
    exercise = _first_match(str(p.get("exercise", "")), _EXERCISE_LEVEL)
    support = _first_match(str(p.get("living", "")), _LIVING_SUPPORT)

    vitals = p.get("vitals") or {}
    smoking = str(vitals.get("smoking", ""))
    pack_years = _f(re.search(r"(\d+)\s*pack[-\s]?yr", smoking).group(1)) if re.search(r"pack[-\s]?yr", smoking) else (
        0.0 if re.search(r"non[-\s]?smoker", smoking, flags=re.I) else NAN
    )
    current_smoker = float(bool(re.search(r"current\s+smoker", smoking, flags=re.I)))
    bmi = _f(vitals.get("bmi"))

    # --- señales de fragilidad en las citas recientes ---
    recent = " ; ".join(str(x) for x in (p.get("recent_other") or [])).lower()
    cognitive = float("memory clinic" in recent or "dementia" in medhx)
    cardiac_workup = float("cardiology" in recent)
    pain_clinic = float("pain clinic" in recent)
    physio = float("physiotherapy" in recent)

    # --- reserva fisiológica en la analítica ---
    hb = _lab(cl, "haemoglobin")
    egfr = _lab(cl, "egfr")
    creat = _lab(cl, "creatinine")
    alp = _lab(cl, "alkaline phosphatase")
    testo = _lab(cl, "testosterone")

    meds_raw = str(p.get("meds", "")).strip().lower()
    n_meds = 0.0 if meds_raw in ("", "none") else float(len([m for m in meds_raw.split(",") if m.strip()]))

    return {
        "frl_age": age,
        "frl_age_ge70": float(age >= 70) if age == age else NAN,
        "frl_age_ge75": float(age >= 75) if age == age else NAN,
        "frl_ipss": ipss,
        "frl_ipss_severe": ipss_severe,
        "frl_ipss_moderate": ipss_moderate,
        "frl_n_comorbid": float(len(pmhx)) if reported else NAN,
        "frl_charlson": charlson if reported else NAN,
        "frl_cci_age_adjusted": cci if reported else NAN,
        "frl_surv10y": surv10 if reported else NAN,
        "frl_exercise_level": exercise,
        "frl_social_support": support,
        "frl_pack_years": pack_years,
        "frl_current_smoker": current_smoker,
        "frl_bmi": bmi,
        "frl_cognitive_flag": cognitive,
        "frl_cardiac_workup": cardiac_workup,
        "frl_pain_clinic": pain_clinic,
        "frl_physiotherapy": physio,
        "frl_haemoglobin": hb,
        "frl_anaemia": float(hb < 13.0) if hb == hb else NAN,
        "frl_egfr": egfr,
        "frl_creatinine": creat,
        "frl_alp": alp,
        "frl_testosterone": testo,
        "frl_n_meds": n_meds,
        "frl_polypharmacy": float(n_meds >= 5),
    }
