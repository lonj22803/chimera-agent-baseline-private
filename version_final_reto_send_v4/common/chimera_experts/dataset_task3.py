"""Bloques de supervivencia sin aprender transformaciones de toda la cohorte.

Los embeddings se promedian sólo dentro de cada caso. Imputación, escalado y
reducción de dimensión corresponden al pipeline de cada fold; aquí no se
ajusta ninguna proyección con información del conjunto de validación.
"""
from __future__ import annotations

import re
import numpy as np

from . import features_structured, features_surgical, features_grading, features_radiology
from .io import Case

NAN = float('nan')
SOURCES = {'mri': ('MRI image', 1024), 'rp': ('Prostatectomy slide', 960),
           'bx': ('Biopsy slide', 960)}


def _structured(case: Case) -> dict[str, float]:
    p = dict(case.prompt)
    dre = str(p.get('dre') or '')
    m = re.search(r'\b(abnormal|normal|suspicious|nodus|nodule)\b', dre, re.I)
    p['dre'] = ('nodus' if m[1].lower() == 'nodule' else m[1].lower()) if m else None
    all_features = features_structured.extract(p)
    out = {k: all_features[k] for k in ('age', 'psa', 'log_psa', 'dre_suspicious')}
    treatment = case.prompt.get('active_treatment_prior_to_surgery')
    # No se infiere una negativa a partir de un campo nulo.
    if treatment is None:
        value = NAN
    elif isinstance(treatment, (bool, int, float)):
        value = float(treatment)
    else:
        value = 0.0 if str(treatment).strip().lower() in ('no', 'none', 'false') else 1.0
    out['active_treatment_prior_to_surgery'] = value
    return out


def _surgical(case: Case) -> dict[str, float]:
    f = features_surgical.extract(case.clinical)
    result = features_surgical.capra_s(features_structured._f(case.prompt.get('psa')), f)
    f['capra_s'] = result['score']
    f['capra_s_group'] = {'bajo': 0.0, 'intermedio': 1.0, 'alto': 2.0}.get(result['group'], NAN)
    return f


def _grading(case: Case) -> dict[str, float]:
    p = dict(case.prompt)
    # El informe de biopsia manda: no se sustituye por el grado de la pieza.
    for key in ('bx_isup', 'bx_gl_prim', 'bx_gl_sec', 'bx'):
        p.pop(key, None)
    p.update(features_surgical.biopsy_prompt(case.clinical))
    return features_grading.extract(p)


def _embeddings(case: Case) -> dict[str, float]:
    out = {}
    for tag, (source, dim) in SOURCES.items():
        vectors = case.embeddings.get(source) or []
        if vectors:
            a = np.asarray(vectors, float)
            if a.ndim == 1:
                a = a[None, :]
            if a.ndim != 2 or a.shape[1] != dim:
                raise ValueError(f'{case.case_id}: dimensión incorrecta en {source}')
            mean = a.mean(axis=0)
        else:
            mean = np.full(dim, NAN)
        out.update({f'emb_{tag}_{j:04d}': float(v) for j, v in enumerate(mean)})
    return out


def _radiology(case: Case) -> dict[str, float]:
    """La plantilla de tarea 3 añade cifras que el NLP de lesiones no leía."""
    out = features_radiology.extract(case.clinical)
    text = case.clinical.get('radiology_report') or ''
    patterns = {
        'rad_volume': r'Prostate volume:\s*([\d.]+)',
        'rad_psad': r'PSA density:\s*([\d.]+)',
        'rad_pirads': r'PI-RADS:\s*(\d)',
        'rad_cspca': r'probability of clinically significant prostate cancer[^:]*:\s*([\d.]+)',
    }
    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        out[name] = float(match[1].rstrip('.')) if match else NAN
    return out


BLOCKS = {
    'A': ('structured', _structured),
    'S': ('surgical', _surgical),
    'G': ('grading', _grading),
    'D': ('radiology', _radiology),
    'E': ('embeddings', _embeddings),
}


def build_matrix(cases: list[Case], blocks: str = 'ASG', drop_constant: bool = True,
                 min_observed: int = 6, min_observed_frac: float = 0.08
                 ) -> tuple[np.ndarray, list[str]]:
    """Misma poda que tarea 2; al validar se determina sólo con el fold train."""
    rows = []
    for case in cases:
        row = {}
        for block in blocks:
            row.update(BLOCKS[block][1](case))
        rows.append(row)
    names = sorted({name for row in rows for name in row})
    X = np.asarray([[row.get(name, NAN) for name in names] for row in rows], float).reshape(len(cases), len(names))
    if drop_constant:
        floor = max(int(min_observed), int(np.ceil(min_observed_frac*len(cases))))
        keep = []
        for j in range(len(names)):
            observed = X[:, j][~np.isnan(X[:, j])]
            if len(observed) >= floor and np.std(observed) > 1e-12:
                keep.append(j)
        X, names = X[:, keep], [names[j] for j in keep]
    return X, names


def build_labels(cases: list[Case]) -> tuple[np.ndarray, np.ndarray]:
    """Tiempo y evento viajan juntos para no tratar censura como recurrencia."""
    t, e = [], []
    for case in cases:
        label = case.label
        if not isinstance(label, dict):
            raise ValueError(f'{case.case_id}: falta etiqueta de supervivencia')
        time, event = label.get('months_to_recurrence'), label.get('event')
        if time is None or not np.isfinite(float(time)) or float(time) < 0 or event not in (0, 1):
            raise ValueError(f'{case.case_id}: etiqueta de supervivencia inválida')
        t.append(float(time))
        e.append(int(event))
    return np.asarray(t, float), np.asarray(e, int)


def completeness_vector(cases: list[Case]) -> np.ndarray:
    """Fracción ponderada de fuentes; patología quirúrgica es la fuente ancla.

    pNx se conserva aparte en S: un informe presente puede carecer de ganglios.
    """
    weights = {'structured_prompt': 1.0, 'radiology_report': 0.8,
               'pathology_report': 1.2, 'surgical_pathology_report': 1.2,
               'mri_embedding': 0.4, 'biopsy_slide': 0.6, 'prostatectomy_slide': 0.6}
    out = []
    for case in cases:
        src = dict(case.available_sources)
        for name in ('pathology_report', 'surgical_pathology_report'):
            src[name] = bool(case.clinical.get(name))
        src['biopsy_slide'] = bool(case.embeddings.get('Biopsy slide'))
        src['prostatectomy_slide'] = bool(case.embeddings.get('Prostatectomy slide'))
        out.append(sum(w for k, w in weights.items() if src.get(k))/sum(weights.values()))
    return np.asarray(out, float)
