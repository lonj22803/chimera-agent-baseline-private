"""Ensamblado de matrices de características por bloques.

Cada bloque procede de un fichero de entrada distinto, y el estudio de ablación
los enciende y apaga para medir qué aporta cada fuente:

======  ==========================================  =========================
Bloque  Origen                                      Módulo
======  ==========================================  =========================
A       ``structured-prompt.json``                  ``features_structured``
B       ``*-clinical-data.json`` -> laboratorio     ``features_labs``
C       ``*-clinical-data.json`` -> serie de PSA    ``features_psa``
D       ``*-clinical-data.json`` -> informe RM      ``features_radiology``
E       ``*-clinical-data.json`` -> notas / familia  (aquí)
======  ==========================================  =========================

El bloque F (``prostate-modality-level-neural-representations.json``) se define
pero **no** se usa por defecto: el análisis empírico del cuaderno de
``train/`` muestra que una sonda lineal sobre el vector de 1024 dimensiones no
discrimina la etiqueta de esta tarea, mientras que el escalar ``cspca`` —que ya
viene en el bloque A y procede del propio detector de csPCa del reto— sí. Se
deja implementado para que la ablación pueda demostrarlo en lugar de que haya
que creerlo.
"""

from __future__ import annotations

import numpy as np

from . import features_labs, features_psa, features_radiology, features_structured
from .io import Case, binary_label

NAN = float("nan")

#: Vocabulario de historia familiar del corpus.
_FH_MAP = {"yes": 1.0, "no": 0.0, "unknown": NAN}


def extract_notes(case: Case) -> dict[str, float]:
    """Bloque E — historia familiar y contexto de las notas previas.

    La historia familiar de primer grado multiplica por ~2 el riesgo de cáncer
    de próstata (Kicinski, Vangronsveld y Nawrot, *PLoS One* 2011, metanálisis
    de 33 estudios) y es una de las variables que el formulario del urólogo
    puntúa explícitamente, de modo que entra aunque su señal marginal sea débil.
    """
    cl = case.clinical or {}
    fh = str(cl.get("family_history", "")).strip().lower()
    notes = cl.get("previous_notes") or []
    txt = " ".join(str(n.get("text", "")) for n in notes).lower()
    p = case.prompt or {}
    enc = str(p.get("enc_type", "")).lower()
    return {
        "family_history": _FH_MAP.get(fh, NAN),
        "n_previous_notes": float(len(notes)),
        "notes_mention_referral": float("referr" in txt),
        "notes_mention_surveillance": float(bool("surveillance" in txt or "monitoring" in txt)),
        "notes_mention_rising": float(bool("rising" in txt or "upward" in txt or "increase" in txt)),
        "enc_prior_pca": float("prior pca" in enc or "prior prostate" in enc),
        "enc_prior_negative_bx": float("negative biopsy" in enc),
        "enc_followup": float("follow-up" in enc),
    }


def extract_embedding(case: Case, n_dims: int = 1024) -> dict[str, float]:
    """Bloque F — vector neuronal de RM, crudo.

    Sólo se usa en el estudio de ablación. Un caso sin fichero de
    representaciones devuelve todo NaN, que es el comportamiento correcto ante
    una modalidad ausente.
    """
    vec = case.mri_embedding
    if vec is None:
        return {f"emb_{i}": NAN for i in range(n_dims)}
    return {f"emb_{i}": float(v) for i, v in enumerate(vec[:n_dims])}


#: Constructores por bloque. La clave es la letra usada en la ablación.
BLOCKS = {
    "A": ("structured", lambda c: features_structured.extract(c.prompt)),
    "B": ("labs", lambda c: features_labs.extract(c.clinical)),
    "C": ("psa_trend", lambda c: features_psa.extract(c.clinical)),
    "D": ("radiology_nlp", lambda c: features_radiology.extract(c.clinical)),
    "E": ("notes", extract_notes),
    "F": ("mri_embedding", extract_embedding),
}


def build_matrix(
    cases: list[Case],
    blocks: str = "A",
    drop_constant: bool = True,
    min_observed: int = 8,
    min_observed_frac: float = 0.08,
) -> tuple[np.ndarray, list[str]]:
    """Construye ``(X, nombres)`` para los bloques pedidos.

    Dos filtros, ambos por la misma razón —con 91 casos, una columna que no
    puede aportar señal sí puede desestabilizar el imputador:

    * ``drop_constant`` elimina las columnas cuya única variación es la
      ausencia. Una columna constante entre sus valores observados no
      discrimina nada.
    * ``min_observed`` / ``min_observed_frac`` eliminan las columnas
      demasiado dispersas. Además de no ser estimables, una columna con 8
      observaciones sobre 91 puede quedar **entera ausente** dentro de una
      partición de entrenamiento, y ahí el imputador iterativo no tiene con qué
      construir su modelo y falla. El umbral se aplica sobre la cohorte
      completa, antes de partir, de modo que no depende de la partición.
    """
    rows = []
    for c in cases:
        feat: dict[str, float] = {}
        for key in blocks:
            _, fn = BLOCKS[key]
            feat.update(fn(c))
        rows.append(feat)

    names = list(rows[0].keys())
    X = np.array([[r.get(n, NAN) for n in names] for r in rows], dtype=float)

    if drop_constant:
        floor = max(int(min_observed), int(np.ceil(min_observed_frac * len(cases))))
        keep = []
        for j, n in enumerate(names):
            col = X[:, j]
            obs = col[~np.isnan(col)]
            if obs.size >= floor and np.nanstd(obs) > 1e-12:
                keep.append(j)
        X = X[:, keep]
        names = [names[j] for j in keep]
    return X, names


def build_labels(cases: list[Case]) -> np.ndarray:
    """Vector de etiquetas binarias. Falla si algún caso no la tiene."""
    y = [binary_label(c) for c in cases]
    if any(v is None for v in y):
        raise ValueError("build_labels requiere casos con ground truth")
    return np.array(y, dtype=int)


def completeness_vector(cases: list[Case], weights: dict[str, float] | None = None) -> np.ndarray:
    """Completitud de la evidencia por caso, en [0, 1]."""
    from .uncertainty import completeness_score

    return np.array([completeness_score(c.available_sources, weights) for c in cases], dtype=float)


def missingness_report(X: np.ndarray, names: list[str]) -> list[dict]:
    """Tasa de ausencia por columna, ordenada de mayor a menor."""
    rows = [
        {"feature": n, "missing_rate": float(np.isnan(X[:, j]).mean()), "n_observed": int((~np.isnan(X[:, j])).sum())}
        for j, n in enumerate(names)
    ]
    return sorted(rows, key=lambda r: -r["missing_rate"])
