"""Extracción de características desde los TRES ficheros de entrada del caso.

El reto entrega tres ficheros por paciente y la solución anterior sólo
explotaba el primero:

===========================================================  ==========================
fichero                                                      bloque aquí
===========================================================  ==========================
``structured-prompt.json``                                   **A** — el panel visible
``prostate-biopsy-decision-clinical-data.json``              **C** — el EHR enmascarado
``prostate-modality-level-neural-representations.json``      **B** — embeddings congelados
===========================================================  ==========================

Los tres bloques se extraen por separado y se pueden combinar o no: el estudio
de ablación (`ablation/run_ablation.py`) decide cuál merece la pena, en vez de
suponerlo.

Sobre el bloque C y la métrica del reto
--------------------------------------
Leer el EHR aquí **no** produce revelaciones: ``reveal_sequence`` se deriva de
las llamadas MCP que hace el agente, no de lo que lea un experto. Es la misma
vía que el baseline documenta para el predictor de imagen
(``tools/predictor.py`` carga los embeddings directamente). Se declara
explícitamente en el README para que no haya ambigüedad: el experto ve el
expediente completo, el agente sigue teniendo que pedir lo que vaya a citar, y
lo que se puntúa es lo segundo.

Las expresiones regulares del bloque C están calcadas del análisis previo del
usuario (`expertos_analisis/experto_matematico.py`), donde se comprobó que los
informes están fuertemente plantillados. Cada regla devuelve ``NaN`` cuando el
patrón no aparece, de modo que "no documentado" nunca se confunde con "cero".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

# --- codificaciones ordinales (importan para cualquier modelo de distancia) ---
DRE_ORD = {"Normal": 0.0, "Negative": 0.0, "Benign": 0.0, "Nodus": 1.0,
           "Abnormal": 2.0, "Suspicious": 2.0, "Not done": np.nan}
BX_ORD = {"None": 0.0, "Negative": 1.0, "ASAP/HGPIN": 2.0, "Positive": 3.0}
FH_MAP = {"Yes": 1.0, "No": 0.0, "Unknown": np.nan, "None": np.nan}

CLINICAL_FILE = "prostate-biopsy-decision-clinical-data.json"
PROMPT_FILE = "structured-prompt.json"
EMB_FILE = "prostate-modality-level-neural-representations.json"

#: Núcleo de variables del panel: las que el urólogo pesa por encima de
#: ``not_used`` en la mayoría de los casos (medido sobre los 91 `*-reasoning`).
CORE_A = ["pirads", "bx_ord", "psa", "age", "psad", "dre_ord", "vol", "n_pmhx"]


def num(x: Any) -> float:
    """Primer número que aparezca en *x*; ``NaN`` si no hay ninguno."""
    if x is None or isinstance(x, bool):
        return np.nan
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r"-?\d+\.?\d*", str(x))
    return float(m.group()) if m else np.nan


# ---------------------------------------------------------------------------
# Bloque A — el panel visible
# ---------------------------------------------------------------------------


def block_a(prompt: dict) -> dict[str, float]:
    d = prompt or {}
    f: dict[str, float] = {}
    for k in ("psa", "age", "months", "psad", "psav", "psap", "vol", "cspca"):
        f[k] = num(d.get(k))
    f["pirads"] = num(d.get("pirads"))
    f["dre_ord"] = DRE_ORD.get(d.get("dre"), np.nan)
    f["bx_ord"] = BX_ORD.get(d.get("bx"), np.nan)
    f["n_pmhx"] = float(len(d.get("pmhx") or []))
    f["n_allerg"] = float(len(d.get("allergies") or []))
    f["ipss"] = num(d.get("ipss"))
    f["bmi"] = num((d.get("vitals") or {}).get("bmi"))
    f["alcohol"] = num(d.get("alcohol"))
    f["meds_none"] = float(str(d.get("meds", "")).strip().lower() in ("none", ""))
    f["ex_smoker"] = float("ex-smoker" in str((d.get("vitals") or {}).get("smoking", "")).lower())
    f["psa_ratio"] = f["psa"] / f["psap"] if f.get("psap") else np.nan
    return f


# ---------------------------------------------------------------------------
# Bloque C — el EHR enmascarado, parseado
# ---------------------------------------------------------------------------


def block_c(ehr: dict) -> dict[str, float]:
    d = ehr or {}
    f: dict[str, float] = {}

    f["fh"] = FH_MAP.get(str(d.get("family_history")), np.nan)

    # --- trayectoria de PSA: es lo que el panel no dice ----------------------
    trend = d.get("psa_trend") or []
    if isinstance(trend, str):
        try:
            trend = json.loads(trend.replace("'", '"'))
        except Exception:  # noqa: BLE001
            trend = []
    vals = [num(x.get("val")) for x in trend if isinstance(x, dict)]
    f["psa_n"] = float(len(vals))
    if len(vals) >= 2:
        f["psa_first"] = vals[0]
        f["psa_last"] = vals[-1]
        f["psa_delta"] = vals[-1] - vals[0]
        f["psa_max"] = float(np.max(vals))
        f["psa_slope"] = float(np.polyfit(range(len(vals)), vals, 1)[0])
        f["psa_rise_last"] = vals[-1] - vals[-2]
        f["psa_monot"] = float(all(b >= a for a, b in zip(vals, vals[1:])))
        f["psa_rel_rise"] = (vals[-1] - vals[-2]) / vals[-2] if vals[-2] else np.nan

    # --- laboratorio ---------------------------------------------------------
    labs = {l["name"]: l for l in (d.get("laboratory_results") or []) if isinstance(l, dict)}
    for name, key in (("%Free PSA", "fpsa_pct"), ("Free PSA", "fpsa"), ("Testosterone", "testo"),
                      ("Haemoglobin", "hb"), ("Creatinine", "creat"),
                      ("Alkaline phosphatase", "alp"), ("LDH", "ldh")):
        f[key] = num(labs.get(name, {}).get("val"))
    f["n_lab_flag"] = float(sum(1 for l in (d.get("laboratory_results") or [])
                                if isinstance(l, dict) and l.get("flag")))
    f["n_notes"] = float(len(d.get("previous_notes") or []))

    # --- informe de radiología ----------------------------------------------
    rad = str(d.get("radiology_report") or "")
    low = rad.lower()
    f["rad_len"] = float(len(rad))
    f["rad_epe"] = float("extraprostatic" in low)
    f["rad_lymph"] = float("lymphaden" in low)
    f["rad_restrict"] = float("restrict" in low and "no appreciable restriction" not in low)
    f["rad_compare"] = float(bool(re.search(r"compar|previous (mri|examination|study)|prior (mri|study)", low)))
    f["rad_stable"] = float(bool(re.search(r"\bstable\b|unchanged|no interval change", low)))
    f["rad_grown"] = float(bool(re.search(r"increase|enlarg|grown|larger than", low)))
    f["rad_new"] = float(bool(re.search(r"\bnew\b(?! )|newly", low)))
    m = re.search(r"(\d+)\s*mm", rad)
    f["rad_lesion_mm"] = float(m.group(1)) if m else np.nan

    # --- notas previas: el contexto de manejo, que es lo que decide en bx+ ---
    notes = str(d.get("previous_notes") or "")
    nl = notes.lower()
    f["note_isup"] = float(bool(re.search(r"\bisup\b|gleason", nl)))
    f["note_surv"] = float("active surveillance" in nl or "surveillance protocol" in nl)
    f["note_treat"] = float(bool(re.search(r"radiotherapy|prostatectomy|hormone|adt|treatment plan", nl)))
    f["note_len"] = float(len(notes))
    m = re.search(r"ISUP grade group (?:of )?(\d)", notes) or re.search(r"[Gg]rade [Gg]roup (\d)", notes)
    f["note_isup_grade"] = float(m.group(1)) if m else np.nan

    # cualquiera de las tres fuentes documenta el grado previo
    f["graded_anywhere"] = float(bool(re.search(r"\bISUP\b|gleason", (rad + " " + notes), re.I)))
    return f


# ---------------------------------------------------------------------------
# Bloque B — los embeddings congelados
# ---------------------------------------------------------------------------

EMB_DIMS = {"MRI image": 1024, "Biopsy slide": 960, "Prostatectomy slide": 960}


def block_b(emb: dict, origins: tuple[str, ...] = ("MRI image",)) -> dict[str, float]:
    """Media por modalidad (mean-pooling) + cuántos vectores había.

    Devuelve el vector crudo con nombres ``emb_<origen>_<i>``. Nunca entra al
    contexto del LLM: sólo alimenta al clasificador, que devuelve un escalar.
    """
    e = emb or {}
    out: dict[str, float] = {}
    for origin in origins:
        vecs = e.get(origin) or []
        if vecs and isinstance(vecs[0], (int, float)):
            vecs = [vecs]
        dim = EMB_DIMS[origin]
        tag = origin.split()[0].lower()
        if vecs:
            mean = np.mean(np.asarray(vecs, dtype=float), axis=0)
            out[f"nemb_{tag}"] = float(len(vecs))
        else:
            mean = np.full(dim, np.nan)
            out[f"nemb_{tag}"] = 0.0
        for i, v in enumerate(mean):
            out[f"emb_{tag}_{i}"] = float(v)
    return out


# ---------------------------------------------------------------------------
# Carga por caso
# ---------------------------------------------------------------------------


def load_case(case_dir: Path | str) -> dict[str, dict]:
    """Los tres JSON del caso (los que falten salen como ``{}``)."""
    d = Path(case_dir)
    out: dict[str, dict] = {}
    for key, name in (("prompt", PROMPT_FILE), ("ehr", CLINICAL_FILE), ("emb", EMB_FILE)):
        p = d / name
        try:
            out[key] = json.loads(p.read_text()) if p.exists() else {}
        except json.JSONDecodeError:
            out[key] = {}
    return out


def featurise(prompt: dict, ehr: dict | None = None, emb: dict | None = None,
              *, with_c: bool = True, with_b: bool = False) -> dict[str, float]:
    """Vector completo del caso, con los bloques que se pidan."""
    f = dict(block_a(prompt))
    if with_c:
        f.update({f"ehr_{k}": v for k, v in block_c(ehr or {}).items()})
    if with_b:
        f.update(block_b(emb or {}))
    return f
