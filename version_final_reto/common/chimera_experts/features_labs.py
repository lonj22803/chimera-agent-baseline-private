"""Bloque B — analítica de ``laboratory_results``.

De los once analitos presentes en todos los casos, el que tiene fundamento
directo en la decisión de biopsia es el **porcentaje de PSA libre**: por debajo
de ~10 % la probabilidad de cáncer en el rango de PSA 4-10 ng/mL sube de forma
marcada (Catalona et al., *JAMA* 1998, estudio multicéntrico de 773 hombres).
El resto de analitos entra como contexto de comorbilidad y de aptitud para el
procedimiento (función renal, anemia, plaquetas) más que como marcadores
tumorales; la fosfatasa alcalina y la LDH se incluyen porque son los marcadores
clásicos de enfermedad ósea diseminada.

Se conservan también las banderas ``H``/``L`` del laboratorio, que son la
lectura del propio laboratorio sobre su rango de referencia local y por tanto
información que no se puede reconstruir desde el valor numérico.
"""

from __future__ import annotations

import math
import re

NAN = float("nan")

#: Nombre en el JSON -> nombre corto de la característica.
ANALYTES = {
    "PSA": "lab_psa",
    "Free PSA": "lab_free_psa",
    "%Free PSA": "lab_pct_free_psa",
    "Haemoglobin": "lab_haemoglobin",
    "WBC": "lab_wbc",
    "Platelets": "lab_platelets",
    "Creatinine": "lab_creatinine",
    "eGFR": "lab_egfr",
    "Testosterone": "lab_testosterone",
    "Alkaline phosphatase": "lab_alp",
    "LDH": "lab_ldh",
    "HbA1c": "lab_hba1c",
}

#: Analitos con cobertura < 50 % en el corpus. Se extraen igual, pero el
#: estudio de ablación los aísla para poder medir si aportan o sólo añaden
#: ruido de imputación.
SPARSE_ANALYTES = ("lab_hba1c",)


def _num(val) -> float:
    """Extrae el número de cadenas tipo ``'>60 mL/min/1.73m2'`` o ``'26%'``."""
    if val is None:
        return NAN
    if isinstance(val, (int, float)):
        return float(val)
    m = re.search(r"[-+]?\d*\.?\d+", str(val))
    return float(m.group()) if m else NAN


def extract(clinical: dict) -> dict[str, float]:
    """Bloque B para un caso."""
    rows = (clinical or {}).get("laboratory_results") or []
    vals: dict[str, float] = {}
    flags: dict[str, str] = {}
    for r in rows:
        name = str(r.get("name", "")).strip()
        key = ANALYTES.get(name)
        if key is None:
            continue
        vals[key] = _num(r.get("val"))
        flags[key] = str(r.get("flag", "") or "").strip().upper()

    out: dict[str, float] = {k: vals.get(k, NAN) for k in ANALYTES.values()}

    # Recomputar el %fPSA cuando falta pero se tienen ambos componentes.
    if out["lab_pct_free_psa"] != out["lab_pct_free_psa"]:
        fp, tp = out["lab_free_psa"], out["lab_psa"]
        if fp == fp and tp == tp and tp > 0:
            out["lab_pct_free_psa"] = 100.0 * fp / tp

    pct = out["lab_pct_free_psa"]
    # Umbral de Catalona 1998: %fPSA < 10 % -> ~56 % de probabilidad de cáncer.
    out["fpsa_lt10"] = float(pct < 10.0) if pct == pct else NAN
    out["fpsa_lt15"] = float(pct < 15.0) if pct == pct else NAN
    out["log_lab_alp"] = math.log1p(out["lab_alp"]) if out["lab_alp"] == out["lab_alp"] else NAN
    out["log_lab_ldh"] = math.log1p(out["lab_ldh"]) if out["lab_ldh"] == out["lab_ldh"] else NAN

    # Carga global de anormalidad marcada por el laboratorio.
    marked = [f for f in flags.values() if f in ("H", "L")]
    out["lab_n_flagged"] = float(len(marked)) if rows else NAN
    out["lab_n_reported"] = float(len(rows))
    out["lab_egfr_low"] = float(out["lab_egfr"] < 60) if out["lab_egfr"] == out["lab_egfr"] else NAN
    out["lab_anaemia"] = float(out["lab_haemoglobin"] < 13.0) if out["lab_haemoglobin"] == out["lab_haemoglobin"] else NAN
    # Un testosterona bajo desinfla el PSA y desplaza cualquier umbral.
    out["lab_hypogonadal"] = (
        float(out["lab_testosterone"] < 8.0) if out["lab_testosterone"] == out["lab_testosterone"] else NAN
    )
    return out
