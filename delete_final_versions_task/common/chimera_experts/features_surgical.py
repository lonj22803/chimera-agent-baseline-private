"""Patología quirúrgica: separar ausencia de hallazgo de ausencia de evidencia.

CAPRA-S (Cooperberg 2011) es el ancla auditable del riesgo. Un pNx puntúa
como pN0 sólo por convención: la bandera separada obliga al llamador a
ensanchar la incertidumbre, sin inventar una disección ganglionar negativa.
"""
from __future__ import annotations

import re
import numpy as np

NAN = float('nan')


def biopsy_prompt(clinical: dict) -> dict:
    """El grado humano de biopsia evita confundirlo con el predictor digital."""
    text = (clinical or {}).get('pathology_report') or ''
    if 'Gleason pattern and ISUP report missing' in text:
        return {}
    gl = re.search(r'Gleason (\d)\s*\+\s*(\d)', text, re.I)
    grade = re.search(r'ISUP grade group (\d)', text, re.I)
    out = {'bx_isup': float(grade[1])} if grade else {}
    if gl:
        out.update(bx_gl_prim=float(gl[1]), bx_gl_sec=float(gl[2]), bx='Positive')
    return out


def extract(clinical: dict) -> dict[str, float]:
    """Conserva NaN cuando la plantilla no afirma ni niega un concepto."""
    text = (clinical or {}).get('surgical_pathology_report') or ''
    def number(pattern):
        m = re.search(pattern, text, re.I)
        return float(m[1]) if m else NAN
    def status(yes, no):
        if re.search(no, text, re.I):
            return 0.0
        return 1.0 if re.search(yes, text, re.I) else NAN
    pt = re.search(r'pathological stage (pT\w+)', text, re.I)
    stage = pt[1].lower() if pt else ''
    f = {
        'prim': number(r'Gleason (\d)\s*\+\s*\d'),
        'sec': number(r'Gleason \d\s*\+\s*(\d)'),
        'isup_rp': number(r'ISUP grade group (\d)'),
        'pt': float(stage[2]) if re.match(r'pt[1-4]', stage) else NAN,
        'epe': status(r'extraprostatic extension was present', r'no extraprostatic extension'),
        'margins': status(r'surgical margins were positive', r'surgical margins were negative'),
        'svi': status(r'seminal vesicles were invaded', r'seminal vesicles were not invaded'),
        'lvi': status(r'lymphovascular invasion was present', r'lymphovascular invasion was absent'),
        'ln': status(r'lymph node metastasis was present', r'no lymph node metastasis'),
        'tertiary': number(r'with tertiary pattern (\d)'),
    }
    unknown = bool(re.search(r'no lymph nodes were removed', text, re.I))
    f['ln_unknown'] = 1.0 if unknown else (0.0 if np.isfinite(f['ln']) else NAN)
    if unknown:
        f['ln'] = NAN
    f['pt_ge_t3'] = float(f['pt'] >= 3) if np.isfinite(f['pt']) else NAN
    f['tertiary_pattern_5'] = float(f['tertiary'] == 5) if np.isfinite(f['tertiary']) else NAN
    f['upgrade_bx_to_rp'] = f['isup_rp'] - biopsy_prompt(clinical).get('bx_isup', NAN)
    return f


def capra_s(psa: float, surgical: dict[str, float]) -> dict:
    """Tabla original 0–12; grupo bajo/intermedio/alto y pNx por separado.

    Los límites decimales publicados se interpretan como >6 y >10; así no
    quedan huecos para PSA medido con más de un decimal. Sólo pNx explícito
    se sustituye por cero; cualquier otro dato ausente deja el total en NaN.
    """
    f = surgical
    prim, sec = f['prim'], f['sec']
    gl = prim + sec
    g = (0 if gl <= 6 else 1 if (prim, sec) == (3, 4) else
         2 if (prim, sec) == (4, 3) else 3 if 8 <= gl <= 10 else NAN)
    p = float(psa > 6) + float(psa > 10) + float(psa > 20) if np.isfinite(psa) else NAN
    ln = 0.0 if f['ln_unknown'] == 1 else f['ln']
    score = p + g + f['epe'] + 2*f['svi'] + 2*f['margins'] + ln
    return {'score': score, 'group': ('bajo' if score <= 2 else 'intermedio' if score <= 5
                                     else 'alto') if np.isfinite(score) else None,
            'ln_unknown': f['ln_unknown']}
