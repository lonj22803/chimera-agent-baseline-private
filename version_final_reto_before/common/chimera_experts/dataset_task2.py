"""Ensamblado de bloques y etiquetas para la tarea 2.

La tarea 1 decide *si biopsiar*; la 2 decide *qué hacer con una biopsia que ya
existe*. Cambian la etiqueta (cuatro clases en vez de dos) y las fuentes (entra
la anatomía patológica, entran las preparaciones de biopsia), así que el
registro de bloques es propio en lugar de un parámetro de ``dataset.py``.

Los bloques A-E se reutilizan tal cual del paquete de la tarea 1: leen ficheros
con el mismo esquema y no hay motivo para duplicarlos.
"""

from __future__ import annotations

import numpy as np

from . import (
    dataset,
    features_frailty,
    features_grading,
    features_labs,
    features_pathology,
    features_psa,
    features_radiology,
    features_structured,
    features_wsi,
)
from .io import Case

NAN = float("nan")

#: Las cuatro clases del reto, en el orden en que se codifican.
CLASSES = (
    "active_surveillance",
    "continued_surveillance",
    "active_treatment",
    "watchful_waiting",
)
CLASS_TO_INDEX = {c: i for i, c in enumerate(CLASSES)}


def _pathology(case: Case) -> dict[str, float]:
    feats = features_pathology.extract(case.clinical)
    feats.update(features_pathology.upgrade_gap(case.clinical, case.prompt))
    return feats


#: Registro de bloques. La clave es la letra que usan los scripts de
#: entrenamiento; el valor es ``(nombre, extractor)``.
BLOCKS = {
    "A": ("structured", lambda c: features_structured.extract(c.prompt)),
    "B": ("labs", lambda c: features_labs.extract(c.clinical)),
    "C": ("psa_trend", lambda c: features_psa.extract(c.clinical)),
    "D": ("radiology_nlp", lambda c: features_radiology.extract(c.clinical)),
    "E": ("notes", dataset.extract_notes),
    "G": ("grading", lambda c: features_grading.extract(c.prompt)),
    "H": ("pathology", _pathology),
    "I": ("frailty", lambda c: features_frailty.extract(c.prompt, c.clinical)),
    "J": ("embedding_summary", features_wsi.extract),
}

#: ``K`` necesita una proyección ajustada sobre la cohorte, así que se inyecta
#: en ``build_matrix`` en lugar de vivir en el registro estático.
PROJECTED_BLOCK = "K"


def build_matrix(
    cases: list[Case],
    blocks: str = "AG",
    projector: features_wsi.EmbeddingProjector | None = None,
    drop_constant: bool = True,
    min_observed: int = 6,
    min_observed_frac: float = 0.08,
) -> tuple[np.ndarray, list[str]]:
    """Construye ``(X, nombres)``. Misma poda que la tarea 1, umbral más bajo.

    El umbral de observaciones mínimas baja de 8 a 6 porque la cohorte
    etiquetada de la tarea 2 es de 72 casos y no de 91: mantener el umbral
    absoluto tiraría columnas que aquí sí son estimables.
    """
    rows: list[dict[str, float]] = []
    for c in cases:
        feat: dict[str, float] = {}
        for key in blocks:
            if key == PROJECTED_BLOCK:
                if projector is None:
                    raise ValueError("el bloque K requiere un EmbeddingProjector ajustado")
                feat.update(projector.transform_case(c))
                continue
            _, fn = BLOCKS[key]
            feat.update(fn(c))
        rows.append(feat)

    names = sorted({k for r in rows for k in r})
    X = np.array([[r.get(n, NAN) for n in names] for r in rows], dtype=float)

    if drop_constant:
        floor = max(int(min_observed), int(np.ceil(min_observed_frac * len(cases))))
        keep = []
        for j in range(X.shape[1]):
            col = X[:, j]
            obs = col[~np.isnan(col)]
            if obs.size >= floor and np.nanstd(obs) > 1e-12:
                keep.append(j)
        X = X[:, keep]
        names = [names[j] for j in keep]
    return X, names


def label_index(case: Case) -> int | None:
    """Etiqueta como entero 0-3. ``None`` si el caso no la trae."""
    if case.label is None:
        return None
    return CLASS_TO_INDEX.get(str(case.label).strip().lower())


def build_labels(cases: list[Case]) -> np.ndarray:
    y = [label_index(c) for c in cases]
    if any(v is None for v in y):
        missing = [c.case_id for c, v in zip(cases, y) if v is None]
        raise ValueError(f"casos sin etiqueta válida: {missing[:5]}")
    return np.asarray(y, dtype=int)


def completeness_vector(cases: list[Case]) -> np.ndarray:
    """Fracción de fuentes presentes, ponderada para la tarea 2.

    La patología pesa más que en la tarea 1 porque la etiqueta se derivó de
    ella; las notas previas pesan poco porque la ablación de la tarea 1 mostró
    que restan.
    """
    weights = {
        "structured_prompt": 1.0,
        "radiology_report": 0.8,
        "psa_trend": 0.6,
        "laboratory_results": 0.5,
        "previous_notes": 0.2,
        "family_history": 0.2,
        "mri_embedding": 0.4,
        "pathology_report": 1.2,
        "biopsy_slide": 0.6,
    }
    out = []
    for c in cases:
        src = dict(c.available_sources)
        src["pathology_report"] = bool((c.clinical or {}).get("pathology_report"))
        src["biopsy_slide"] = bool((c.embeddings or {}).get("Biopsy slide"))
        total = sum(weights.values())
        got = sum(w for k, w in weights.items() if src.get(k))
        out.append(got / total)
    return np.asarray(out, dtype=float)
