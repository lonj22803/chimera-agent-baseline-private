"""Incertidumbre descompuesta para veredictos de varias clases (tarea 2).

``uncertainty.py`` resuelve el caso binario: una probabilidad, una entropía de
Bernoulli, una escalera sobre la distancia al umbral 0.5. Con cuatro clases
ninguna de las tres cosas se traslada directamente, y la que peor se traslada es
la escalera: en un problema de cuatro salidas lo que decide si el veredicto se
sostiene no es la distancia a un umbral sino el **margen** entre la clase más
votada y la siguiente.

Este módulo entrega, por caso, exactamente los tres números que el deliberador
necesita:

* **la media** — el vector posterior promediado sobre miembros e imputaciones,
  ``p̄``, del que sale la clase recomendada;
* **el margen y su dispersión** — ``Δ = p̄(1ª) − p̄(2ª)`` y la desviación de ese
  mismo margen entre miembros, que es lo que dice si la segunda opción podría
  adelantar a la primera;
* **la confianza** — la descomposición de la entropía en su parte irreducible y
  su parte de desconocimiento, traducida a la escala ``clear`` / ``borderline``
  / ``uncertain`` que el formulario del reto exige.

La descomposición es la canónica: la entropía de la predictiva media es la
incertidumbre **total**; la media de las entropías de cada miembro es la parte
**aleatoria** (el ruido que ningún dato adicional quitaría); su diferencia —la
información mutua entre la predicción y los parámetros— es la parte
**epistémica**, la que sí se reduciría con más datos o más modalidades.

Referencias
-----------
* Depeweg S., Hernández-Lobato J.M., Doshi-Velez F., Udluft S., *Decomposition
  of Uncertainty in Bayesian Deep Learning*, ICML 2018 — total = aleatoria +
  información mutua.
* Kendall A., Gal Y., *What Uncertainties Do We Need in Bayesian Deep Learning
  for Computer Vision?*, NeurIPS 2017.
* Lakshminarayanan B., Pritzel A., Blundell C., *Simple and Scalable Predictive
  Uncertainty Estimation using Deep Ensembles*, NeurIPS 2017 — el ensemble como
  aproximación barata a la posterior.
* Rubin D.B., *Multiple Imputation for Nonresponse in Surveys*, Wiley 1987 —
  la varianza *between* que separa el desconocimiento por datos ausentes.
* Malinin A., Gales M., *Predictive Uncertainty Estimation via Prior Networks*,
  NeurIPS 2018 — por qué el margen, y no el máximo, es la magnitud a vigilar.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

#: Traducción de la escalera operativa al vocabulario del formulario CHIMERA.
LADDER_TO_CHIMERA = {"firm": "clear", "supports": "borderline", "discuss": "uncertain"}


@dataclass
class MulticlassVerdict:
    """Veredicto de un experto de varias clases, con su incertidumbre abierta."""

    classes: tuple[str, ...]
    probabilities: list[float]          # la media
    decision: str
    runner_up: str
    margin: float                       # delta de la media
    margin_sigma: float                 # dispersión del margen entre miembros
    entropy_total: float                # incertidumbre total (normalizada)
    aleatoric: float                    # irreducible
    epistemic_model: float              # información mutua
    epistemic_missing: float            # término *between* de Rubin
    epistemic_total: float
    completeness: float
    ladder: str
    confidence: str
    n_members: int
    n_imputations: int

    def to_dict(self) -> dict:
        return asdict(self)

    def top(self, k: int = 2) -> list[tuple[str, float]]:
        order = np.argsort(self.probabilities)[::-1][:k]
        return [(self.classes[i], float(self.probabilities[i])) for i in order]

    def interval(self, z: float = 1.96) -> tuple[float, float]:
        """Intervalo del margen. Si cruza 0, la segunda opción es alcanzable."""
        lo = self.margin - z * self.margin_sigma
        hi = self.margin + z * self.margin_sigma
        return float(lo), float(hi)


def _norm_entropy(p: np.ndarray) -> np.ndarray:
    """Entropía de Shannon normalizada a [0, 1] por ``log(n_clases)``."""
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1.0)
    p = p / p.sum(axis=-1, keepdims=True)
    h = -(p * np.log(p)).sum(axis=-1)
    return h / math.log(p.shape[-1])


def decompose(probs: np.ndarray) -> dict[str, float | np.ndarray]:
    """Descompone una matriz ``(n_imputaciones, n_miembros, n_clases)``.

    Devuelve la predictiva media y las tres varianzas separadas. Un caso sin
    valores ausentes produce imputaciones idénticas y por tanto
    ``epistemic_missing`` exactamente cero: la barra sólo se ensancha cuando de
    verdad falta información, no por construcción.
    """
    P = np.asarray(probs, dtype=float)
    if P.ndim == 2:                      # (miembros, clases)
        P = P[None, ...]
    m, k, _ = P.shape

    p_bar = P.reshape(-1, P.shape[-1]).mean(axis=0)
    p_bar = p_bar / p_bar.sum()

    total = float(_norm_entropy(p_bar))
    aleatoric = float(_norm_entropy(P.reshape(-1, P.shape[-1])).mean())
    # La información mutua no puede ser negativa; el redondeo numérico sí puede
    # hacerla salir de -1e-15, y ahí se recorta en lugar de propagarse.
    mutual_info = max(0.0, total - aleatoric)

    # Rubin: dispersión entre imputaciones de la media del ensemble, corregida
    # por el número finito de imputaciones.
    if m > 1:
        per_imp = P.mean(axis=1)                       # (imputaciones, clases)
        between = per_imp.var(axis=0, ddof=1) * (1.0 + 1.0 / m)
        s_missing = float(np.sqrt(max(between.max(), 0.0)))
    else:
        s_missing = 0.0

    # Margen y su dispersión: se recalcula el margen dentro de cada miembro,
    # respecto de las dos clases que gana la media, para que la dispersión mida
    # desacuerdo sobre *esta* decisión y no sobre la etiqueta de cada miembro.
    order = np.argsort(p_bar)[::-1]
    i1, i2 = int(order[0]), int(order[1])
    flat = P.reshape(-1, P.shape[-1])
    margins = flat[:, i1] - flat[:, i2]

    return {
        "p_bar": p_bar,
        "top": i1,
        "second": i2,
        "margin": float(p_bar[i1] - p_bar[i2]),
        "margin_sigma": float(margins.std(ddof=1)) if margins.size > 1 else 0.0,
        "entropy_total": total,
        "aleatoric": aleatoric,
        "mutual_info": mutual_info,
        "epistemic_missing": s_missing,
        "n_imputations": m,
        "n_members": k,
    }


def ladder(margin: float, sigma: float) -> str:
    """Escalera de abstención informada sobre el margen entre las dos primeras.

    * ``firm``     — ``Δ − 1.96σ > 0``: la segunda opción no alcanza a la primera.
    * ``supports`` — ``Δ − σ > 0``: inclina, no cierra.
    * ``discuss``  — el intervalo cruza cero: el experto declara que no separa
      las dos primeras y la decisión tiene que salir de otra evidencia.

    El caso ``σ = 0`` con margen no nulo —un ensemble unánime— se resuelve como
    ``firm`` sólo si el margen es sustantivo; un margen de 0.02 unánime es un
    empate, no una certeza.
    """
    if margin != margin or sigma != sigma:
        return "discuss"
    if sigma <= 1e-9:
        return "firm" if margin >= 0.15 else ("supports" if margin >= 0.05 else "discuss")
    if margin > 1.96 * sigma:
        return "firm"
    if margin > sigma:
        return "supports"
    return "discuss"


def make_verdict(
    probs: np.ndarray,
    classes: tuple[str, ...],
    completeness: float = 1.0,
) -> MulticlassVerdict:
    d = decompose(probs)
    s_model = float(math.sqrt(max(d["mutual_info"], 0.0)))
    s_miss = float(d["epistemic_missing"])
    rung = ladder(d["margin"], math.sqrt(d["margin_sigma"] ** 2 + s_miss**2))
    return MulticlassVerdict(
        classes=tuple(classes),
        probabilities=[float(x) for x in d["p_bar"]],
        decision=classes[d["top"]],
        runner_up=classes[d["second"]],
        margin=d["margin"],
        margin_sigma=float(math.sqrt(d["margin_sigma"] ** 2 + s_miss**2)),
        entropy_total=d["entropy_total"],
        aleatoric=d["aleatoric"],
        epistemic_model=s_model,
        epistemic_missing=s_miss,
        epistemic_total=float(math.sqrt(s_model**2 + s_miss**2)),
        completeness=float(completeness),
        ladder=rung,
        confidence=LADDER_TO_CHIMERA[rung],
        n_members=int(d["n_members"]),
        n_imputations=int(d["n_imputations"]),
    )


# --------------------------------------------------------------------------
# Métricas de calidad de la probabilidad, no sólo del acierto.
# --------------------------------------------------------------------------

def multiclass_brier(y: np.ndarray, P: np.ndarray) -> float:
    """Brier multiclase (Brier 1950, forma de Murphy): media de ``‖p − e_y‖²``."""
    Y = np.zeros_like(P)
    Y[np.arange(len(y)), y] = 1.0
    return float(((P - Y) ** 2).sum(axis=1).mean())


def expected_calibration_error(y: np.ndarray, P: np.ndarray, n_bins: int = 10) -> float:
    """ECE sobre la confianza de la clase predicha (Guo et al., ICML 2017)."""
    conf = P.max(axis=1)
    pred = P.argmax(axis=1)
    correct = (pred == y).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.sum() == 0:
            continue
        ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def ladder_table(y: np.ndarray, verdicts: list[MulticlassVerdict], class_to_index: dict) -> list[dict]:
    """Acierto por tramo de la escalera. Si no cae de forma monótona, la
    incertidumbre no está midiendo nada y hay que decirlo."""
    rows = []
    for rung in ("firm", "supports", "discuss"):
        idx = [i for i, v in enumerate(verdicts) if v.ladder == rung]
        if not idx:
            rows.append({"ladder": rung, "confidence": LADDER_TO_CHIMERA[rung], "n": 0, "accuracy": None})
            continue
        acc = float(np.mean([class_to_index[verdicts[i].decision] == y[i] for i in idx]))
        rows.append({
            "ladder": rung,
            "confidence": LADDER_TO_CHIMERA[rung],
            "n": len(idx),
            "accuracy": round(acc, 4),
            "mean_margin": round(float(np.mean([verdicts[i].margin for i in idx])), 4),
        })
    return rows
