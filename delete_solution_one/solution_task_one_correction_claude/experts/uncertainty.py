"""Incertidumbre por variable: la sigma que necesita el Probabilistic Random Forest.

El PRF necesita, para cada valor, una desviación típica. Ponerla a cero lo
degrada exactamente a un Random Forest; ponerla a ojo lo convierte en ruido. Se
declara aquí, por variable y con su motivo, para que sea auditable y discutible
en vez de un número escondido en el código.

Tres orígenes de incertidumbre, y cómo se traducen:

* **Error de medida analítico.** El PSA sérico tiene un coeficiente de
  variación inter-ensayo de ~5 % en los inmunoensayos de uso clínico, y esa
  variabilidad es la razón por la que la propia guía EAU recomienda repetir un
  PSA elevado antes de indicar biopsia.
* **Error de estimación de un modelo.** ``vol`` viene de una segmentación
  automática de la próstata; ``psad = psa / vol`` **propaga** los dos errores
  en cuadratura; ``cspca`` es la salida de un detector de csPCa, no una medida.
* **Variabilidad inter-observador.** El PI-RADS es una lectura humana con
  concordancia inter-lector moderada — del orden de medio grado de desacuerdo
  típico —, y el tacto rectal es todavía más subjetivo.

Lo ausente NO se modela aquí: ``NaN`` se traduce a ``sigma = inf`` dentro del
PRF, que es lo que reparte al objeto a partes iguales por las dos ramas.
"""

from __future__ import annotations

import numpy as np

#: sigma **relativa** (fracción del valor) por variable.
RELATIVE = {
    "psa": 0.05,          # CV inter-ensayo del inmunoensayo de PSA
    "psap": 0.05,
    "psav": 0.10,         # derivada de dos PSA, propaga ambos
    "vol": 0.10,          # segmentación automática de la próstata
    "psad": 0.11,         # sqrt(0.05^2 + 0.10^2), propagación de psa/vol
    "psa_ratio": 0.07,
    "ehr_psa_first": 0.05, "ehr_psa_last": 0.05, "ehr_psa_max": 0.05,
    "ehr_psa_delta": 0.10, "ehr_psa_slope": 0.15, "ehr_psa_rise_last": 0.10,
    "ehr_psa_rel_rise": 0.15,
    "ehr_fpsa": 0.08, "ehr_fpsa_pct": 0.08, "ehr_testo": 0.08,
    "ehr_hb": 0.03, "ehr_creat": 0.05, "ehr_alp": 0.07, "ehr_ldh": 0.07,
    "bmi": 0.03,
}

#: sigma **absoluta** por variable, en sus propias unidades.
ABSOLUTE = {
    "pirads": 0.5,        # concordancia inter-lector del PI-RADS v2.1
    "dre_ord": 0.5,       # tacto rectal: lectura subjetiva
    "cspca": 0.10,        # salida de un detector, no una medida
    "ipss": 2.0,          # cuestionario auto-referido
    "alcohol": 3.0,       # consumo declarado por el paciente
    "ehr_rad_lesion_mm": 2.0,   # medida de una lesión mal delimitada
    "ehr_note_isup_grade": 0.3,
}

#: Variables extraídas con expresiones regulares: pueden fallar el patrón.
#: Una sigma pequeña pero no nula representa ese riesgo de extracción.
REGEX_FLAG_SIGMA = 0.10

#: Exactas por construcción (recuento, registro administrativo, categoría).
EXACT_PREFIXES = ("age", "months", "n_pmhx", "n_allerg", "bx_ord", "meds_none",
                  "ex_smoker", "ehr_psa_n", "ehr_n_notes", "ehr_n_lab_flag", "nemb_")


def sigma_matrix(X: np.ndarray, names: list[str]) -> np.ndarray:
    """Matriz de desviaciones típicas, misma forma que *X*."""
    X = np.asarray(X, float)
    S = np.zeros_like(X)
    for j, name in enumerate(names):
        if name in RELATIVE:
            S[:, j] = np.abs(X[:, j]) * RELATIVE[name]
        elif name in ABSOLUTE:
            S[:, j] = ABSOLUTE[name]
        elif name.startswith(EXACT_PREFIXES) or name.startswith("emb_"):
            S[:, j] = 0.0
        elif name.startswith("ehr_"):
            # bandera booleana obtenida por regex: incertidumbre de extracción
            col = X[:, j]
            binary = np.all(np.isin(col[np.isfinite(col)], (0.0, 1.0)))
            S[:, j] = REGEX_FLAG_SIGMA if binary else np.abs(col) * 0.05
        else:
            S[:, j] = np.abs(X[:, j]) * 0.02
    return np.where(np.isfinite(S), S, 0.0)
