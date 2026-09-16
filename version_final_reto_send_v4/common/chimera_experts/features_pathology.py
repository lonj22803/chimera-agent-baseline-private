"""Bloque H — informe de anatomía patológica de la biopsia (tarea 2).

Es la fuente que la tarea 2 añade y la tarea 1 no tiene. El informe trae tres
cosas que ``structured-prompt.json`` no codifica:

1. **La trayectoria.** Un ISUP 1 con dos biopsias estables no es el mismo
   paciente que un ISUP 1 recién diagnosticado: el primero lleva vigilancia y
   la etiqueta lo distingue (``continued_surveillance`` frente a
   ``active_surveillance``). El número de *timepoints* y la dirección del
   cambio entre ellos sólo están aquí.
2. **Los patrones adversos.** Cribiforme e intraductal cambian el manejo de un
   ISUP 2 aunque el grade group no cambie: son el argumento para tratar a quien
   la cifra mandaría a vigilancia.
3. **El grado que predice el modelo de patología digital.** El informe cierra
   con ``AI-predicted ISUP grade group``, que es la salida del modelo de
   *Gleason grading* automático del reto. Su **discrepancia** con el ISUP
   clínico es la variable de riesgo de *upgrade*.

La negación se resuelve con el mismo NegEx del bloque D
(`features_radiology.concept_status`), porque el corpus escribe "No cribriform
or intraductal patterns identified" con la misma frecuencia con que lo afirma:
sin negación, la variable mediría la longitud del informe.

Referencias
-----------
* Chapman W.W. et al., *A Simple Algorithm for Identifying Negated Findings*,
  J Biomed Inform 2001 — NegEx.
* Kweldam C.F. et al., *Cribriform growth is highly predictive for postoperative
  metastasis and disease-specific death*, Mod Pathol 2015.
* van Leenders G.J.L.H. et al., *ISUP Consensus Conference on Grading of
  Prostatic Carcinoma*, Am J Surg Pathol 2020 — cribiforme e intraductal.
* Bulten W. et al., *Artificial intelligence for diagnosis and Gleason grading
  of prostate cancer (PANDA)*, Nat Med 2022 — el tipo de cabeza que produce
  ``AI-predicted ISUP grade group``.
"""

from __future__ import annotations

import re

from . import features_radiology as rad

NAN = float("nan")

#: Conceptos histológicos con valor ternario (afirmado / negado / no mencionado).
CONCEPTS: dict[str, str] = {
    "cribriform": r"cribriform",
    "intraductal": r"intraductal",
    "perineural": r"perineural\s+invasion",
    "extraprostatic": r"(extraprostatic|extracapsular)\s+(extension|spread)",
    "seminal_vesicle": r"seminal\s+vesicle",
    "lymphovascular": r"(lymphovascular|angiolymphatic)\s+invasion",
    "adenocarcinoma": r"adenocarcinoma",
    "benign_only": r"(benign\s+prostatic\s+tissue|no\s+evidence\s+of\s+malignancy)",
}

#: Zona anatómica del tumor. La transicional responde peor a la biopsia
#: sistemática y suele acompañar a próstatas grandes con LUTS.
_ZONES = {
    "peripheral_zone": r"peripheral\s+zone",
    "transition_zone": r"transition(al)?\s+zone",
    "anterior": r"\banterior\b",
    "apex": r"\bapex|apical\b",
    "base": r"\bbase\b",
}

_TRAJ_STABLE = r"(stable|remains?\s+(consistent|at\s+this)|unchanged|persistent|no\s+(histological\s+)?progression|consistent\s+with\s+the\s+prior)"
_TRAJ_PROGRESS = r"(progress\w*|upgrad\w*|increase\s+in\s+grade|higher\s+grade\s+than|deterioration)"
_TRAJ_DOWN = r"(downgrad\w*|lower\s+grade\s+than|regress\w*)"


def _isup_mentions(text: str) -> list[float]:
    """Todos los ISUP grade group citados en el cuerpo del informe, en orden.

    Se excluye la línea del predictor automático: ese valor se lee aparte y
    mezclarlo con los grados humanos inventaría una trayectoria que no existe.
    """
    body = re.split(r"AI-predicted", text, flags=re.I)[0]
    return [float(m) for m in re.findall(r"(?:ISUP\s+)?grade\s+group\s+(\d)", body, flags=re.I)]


def _gleason_mentions(text: str) -> list[tuple[float, float]]:
    body = re.split(r"AI-predicted", text, flags=re.I)[0]
    return [(float(a), float(b)) for a, b in re.findall(r"(\d)\s*\+\s*(\d)", body)]


def _ai_grades(text: str) -> list[float]:
    """Grados del modelo de patología digital, en orden de *timepoint*."""
    m = re.search(r"AI-predicted\s+ISUP\s+grade\s+group[^:]*:(.+?)(?:\n\n|$)", text, flags=re.I | re.S)
    if not m:
        return []
    return [float(g) for g in re.findall(r"grade\s+group\s+(\d)", m.group(1), flags=re.I)]


def _n_timepoints(text: str) -> float:
    body = re.split(r"AI-predicted", text, flags=re.I)[0]
    tp = re.findall(r"(?:timepoint|biopsy)\s*(\d)\b", body, flags=re.I)
    if tp:
        return float(max(int(t) for t in tp))
    # Sin numeración explícita: se cuenta por fechas de espécimen.
    dates = re.findall(r"\b(?:19|20)\d{2}\b", body)
    return float(len(set(dates))) if dates else 1.0


def extract(clinical: dict) -> dict[str, float]:
    text = (clinical or {}).get("pathology_report") or ""
    if not text.strip():
        return {f"path_{k}": NAN for k in list(CONCEPTS) + list(_ZONES) + [
            "n_timepoints", "isup_first", "isup_last", "isup_max", "isup_delta",
            "gleason_prim_last", "gleason_sec_last", "traj_stable", "traj_progress",
            "traj_down", "ai_isup_last", "ai_isup_max", "ai_isup_n", "report_chars",
        ]}

    feats: dict[str, float] = {}
    for name, pat in CONCEPTS.items():
        feats[f"path_{name}"] = rad.concept_status(text, pat, name)
    for name, pat in _ZONES.items():
        feats[f"path_{name}"] = float(bool(re.search(pat, text, flags=re.I)))

    isups = _isup_mentions(text)
    gls = _gleason_mentions(text)
    ai = _ai_grades(text)
    ntp = _n_timepoints(text)

    feats["path_n_timepoints"] = ntp
    feats["path_multi_timepoint"] = float(ntp >= 2)
    feats["path_isup_first"] = isups[0] if isups else NAN
    feats["path_isup_last"] = isups[-1] if isups else NAN
    feats["path_isup_max"] = max(isups) if isups else NAN
    feats["path_isup_delta"] = (isups[-1] - isups[0]) if len(isups) >= 2 else (0.0 if isups else NAN)
    feats["path_gleason_prim_last"] = gls[-1][0] if gls else NAN
    feats["path_gleason_sec_last"] = gls[-1][1] if gls else NAN

    feats["path_traj_stable"] = float(bool(re.search(_TRAJ_STABLE, text, flags=re.I)))
    feats["path_traj_progress"] = float(bool(re.search(_TRAJ_PROGRESS, text, flags=re.I)))
    feats["path_traj_down"] = float(bool(re.search(_TRAJ_DOWN, text, flags=re.I)))

    feats["path_ai_isup_last"] = ai[-1] if ai else NAN
    feats["path_ai_isup_max"] = max(ai) if ai else NAN
    feats["path_ai_isup_n"] = float(len(ai))
    feats["path_ai_traj_up"] = float(ai[-1] > ai[0]) if len(ai) >= 2 else NAN
    feats["path_report_chars"] = float(len(text))
    return feats


def upgrade_gap(clinical: dict, prompt: dict) -> dict[str, float]:
    """Discrepancia entre el ISUP clínico y el que predice la patología digital.

    Se calcula fuera de ``extract`` porque necesita las dos fuentes. Es la única
    variable del bloque que cruza modalidades, y la que responde a la pregunta
    que la decisión de tratamiento realmente hace: *¿el grado de la biopsia se
    queda corto?*
    """
    ai = _ai_grades((clinical or {}).get("pathology_report") or "")
    try:
        clin = float((prompt or {}).get("bx_isup"))
    except (TypeError, ValueError):
        clin = NAN
    if not ai or clin != clin:
        return {"path_ai_gap": NAN, "path_ai_upgrades": NAN, "path_ai_agrees": NAN}
    gap = max(ai) - clin
    return {
        "path_ai_gap": gap,
        "path_ai_upgrades": float(gap >= 1),
        "path_ai_agrees": float(gap == 0),
    }
