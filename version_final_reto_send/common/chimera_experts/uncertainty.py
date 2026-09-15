"""Cuantificación de incertidumbre para los expertos clásicos.

Un veredicto sin incertidumbre no le sirve a un deliberador posterior: si no
sabe cuánto fiarse, no puede integrarlo. Este módulo produce tres magnitudes
**separadas**, porque responden a preguntas distintas y se reducen por vías
distintas:

``epistemic_model`` (σ_modelo)
    Desviación típica de la probabilidad entre los miembros del ensemble: cuánto
    se movería la respuesta si se hubiera entrenado con otra muestra. Es la
    receta de los *deep ensembles* (Lakshminarayanan, Pritzel y Blundell,
    *Simple and Scalable Predictive Uncertainty Estimation using Deep
    Ensembles*, NeurIPS 2017) aplicada a estimadores clásicos. Baja con más
    datos de entrenamiento.

``epistemic_missing`` (σ_imputación)
    Desviación típica entre imputaciones múltiples del mismo caso: cuánto se
    movería la respuesta si los valores que faltan hubieran salido distintos.
    Es exactamente el término *between-imputation* de las reglas de Rubin
    (Rubin, *Multiple Imputation for Nonresponse in Surveys*, Wiley 1987;
    van Buuren y Groothuis-Oudshoorn, *mice*, J Stat Softw 2011). Vale cero
    cuando el caso está completo y crece con cada variable ausente — que es
    justo la propiedad que exige el reto, donde faltan modalidades a propósito.

``aleatoric`` (H)
    Entropía normalizada de la probabilidad media: cuánto se contradicen entre
    sí los desenlaces de pacientes que el modelo no distingue. No baja con más
    datos del mismo tipo. La separación epistémica / aleatoria sigue a Depeweg,
    Hernández-Lobato, Doshi-Velez y Udluft, *Decomposition of Uncertainty in
    Bayesian Deep Learning for Efficient and Risk-sensitive Learning*, ICML
    2018.

Las dos componentes epistémicas **sí** se combinan en cuadratura, porque son
varianzas de la misma cantidad (la probabilidad predicha) bajo dos fuentes
independientes de variación, que es la condición bajo la que las reglas de
Rubin autorizan la suma. La aleatoria **no** se suma a ellas: mezclar una
varianza de Bernoulli con un error típico produce una barra de anchura casi
constante que no discrimina entre casos, y por tanto no informa de nada.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

#: Etiquetas de la escalera operativa, y su traducción al vocabulario
#: ``confidence`` que exige el esquema de salida de CHIMERA-agent.
LADDER_TO_CHIMERA = {"firm": "clear", "supports": "borderline", "discuss": "uncertain"}


@dataclass
class Verdict:
    """Veredicto de un experto binario, con su incertidumbre descompuesta."""

    probability: float
    decision: int
    epistemic_model: float
    epistemic_missing: float
    epistemic_total: float
    aleatoric: float
    completeness: float
    ladder: str
    confidence: str
    n_members: int
    n_imputations: int

    def to_dict(self) -> dict:
        return asdict(self)

    def interval(self, k: float = 1.96) -> tuple[float, float]:
        """Intervalo ``p ± k·σ_epistémica`` recortado a [0, 1]."""
        lo = max(0.0, self.probability - k * self.epistemic_total)
        hi = min(1.0, self.probability + k * self.epistemic_total)
        return lo, hi


def binary_entropy(p: float) -> float:
    """Entropía de Bernoulli normalizada a [0, 1] (base 2, dividida por 1 bit)."""
    p = min(max(float(p), 1e-12), 1 - 1e-12)
    return float(-(p * math.log2(p) + (1 - p) * math.log2(1 - p)))


def rubin_pool(probs: np.ndarray) -> tuple[float, float, float]:
    """Agrega una matriz ``(n_imputaciones, n_miembros)`` de probabilidades.

    Devuelve ``(p_media, sigma_modelo, sigma_imputacion)`` según las reglas de
    Rubin: la varianza *within* es la dispersión entre miembros promediada sobre
    imputaciones; la *between* es la dispersión de las medias por imputación,
    corregida por el factor ``1 + 1/M`` que compensa el número finito de
    imputaciones.
    """
    probs = np.atleast_2d(np.asarray(probs, dtype=float))
    m, k = probs.shape
    p_bar = float(probs.mean())

    # Within: variabilidad del modelo, promediada sobre imputaciones.
    within = float(np.mean(probs.std(axis=1, ddof=1) ** 2)) if k > 1 else 0.0

    # Between: variabilidad entre imputaciones de la media del ensemble.
    if m > 1:
        per_imp = probs.mean(axis=1)
        between = float(per_imp.var(ddof=1)) * (1.0 + 1.0 / m)
    else:
        between = 0.0

    return p_bar, math.sqrt(max(within, 0.0)), math.sqrt(max(between, 0.0))


def make_verdict(
    probs: np.ndarray,
    completeness: float = 1.0,
    threshold: float = 0.5,
) -> Verdict:
    """Construye el veredicto a partir de la matriz de probabilidades."""
    probs = np.atleast_2d(np.asarray(probs, dtype=float))
    p, s_model, s_miss = rubin_pool(probs)
    s_tot = math.sqrt(s_model**2 + s_miss**2)
    rung = ladder(p, s_tot, threshold)
    return Verdict(
        probability=p,
        decision=int(p >= threshold),
        epistemic_model=s_model,
        epistemic_missing=s_miss,
        epistemic_total=s_tot,
        aleatoric=binary_entropy(p),
        completeness=float(completeness),
        ladder=rung,
        confidence=LADDER_TO_CHIMERA[rung],
        n_members=int(probs.shape[1]),
        n_imputations=int(probs.shape[0]),
    )


def ladder(p: float, sigma: float, threshold: float = 0.5) -> str:
    """Escalera operativa de abstención informada.

    * ``firm``     — ``p ± 1.96σ`` no cruza el umbral: el experto se moja.
    * ``supports`` — ``p ± σ`` no cruza el umbral: inclina, no decide.
    * ``discuss``  — ``p ± σ`` cruza el umbral: el experto declara que no
      distingue, y la decisión tiene que salir de otra evidencia.

    La abstención informada es la propiedad que separa una probabilidad útil de
    un número: véase Guo, Pleiss, Sun y Weinberger, *On Calibration of Modern
    Neural Networks*, ICML 2017, y Niculescu-Mizil y Caruana, *Predicting Good
    Probabilities With Supervised Learning*, ICML 2005.
    """
    if sigma != sigma:
        return "discuss"
    d = abs(p - threshold)
    if d > 1.96 * sigma:
        return "firm"
    if d > sigma:
        return "supports"
    return "discuss"


def completeness_score(sources: dict[str, bool], weights: dict[str, float] | None = None) -> float:
    """Fracción ponderada de las fuentes de evidencia realmente presentes.

    No entra en el modelo: es un descriptor que acompaña al veredicto para que
    el deliberador sepa sobre cuánta evidencia se construyó. El ensanchamiento
    real de la barra lo produce ``epistemic_missing``, que se mide, no se
    postula.
    """
    if not sources:
        return 0.0
    w = weights or {k: 1.0 for k in sources}
    tot = sum(w.get(k, 1.0) for k in sources)
    got = sum(w.get(k, 1.0) for k, v in sources.items() if v)
    return got / tot if tot else 0.0


# --------------------------------------------------------------------------
# Calibración.
# --------------------------------------------------------------------------


def brier_score(y: np.ndarray, p: np.ndarray) -> float:
    """Puntuación de Brier (Brier, *Mon Weather Rev* 1950). Menor es mejor."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2))


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """ECE con binning de anchura uniforme (Guo et al., ICML 2017)."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p > lo) & (p <= hi) if lo > 0 else (p >= lo) & (p <= hi)
        if not m.any():
            continue
        ece += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(ece)


def reliability_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> list[dict]:
    """Tabla de fiabilidad: frecuencia observada frente a probabilidad predicha."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p > lo) & (p <= hi) if lo > 0 else (p >= lo) & (p <= hi)
        rows.append(
            {
                "bin_lo": float(lo),
                "bin_hi": float(hi),
                "n": int(m.sum()),
                "mean_predicted": float(p[m].mean()) if m.any() else float("nan"),
                "observed_rate": float(y[m].mean()) if m.any() else float("nan"),
            }
        )
    return rows


def ladder_table(y: np.ndarray, p: np.ndarray, sigma: np.ndarray, threshold: float = 0.5) -> list[dict]:
    """Rendimiento por peldaño de la escalera: cuántos casos y con qué acierto."""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    rungs = np.array([ladder(pi, si, threshold) for pi, si in zip(p, sigma)])
    pred = (p >= threshold).astype(int)
    rows = []
    for name in ("firm", "supports", "discuss"):
        m = rungs == name
        rows.append(
            {
                "rung": name,
                "confidence": LADDER_TO_CHIMERA[name],
                "n": int(m.sum()),
                "coverage": float(m.mean()),
                "accuracy": float((pred[m] == y[m]).mean()) if m.any() else float("nan"),
            }
        )
    return rows
