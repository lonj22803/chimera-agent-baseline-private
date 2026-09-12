"""Campos del formulario, sin decidir la clase clínica.

Las varianzas de modelo, imputación y panel describen la misma probabilidad
bajo fuentes distintas de variación. Se suman en cuadratura bajo la hipótesis
operativa de independencia (Rubin, 1987); no es una identidad si los expertos
están correlacionados. La entropía aleatoria se informa aparte: tiene otra
escala y no disminuye añadiendo modelos (Depeweg et al., 2018).

Los veredictos originales contienen desviaciones típicas, no varianzas.
La imputación ya incluye la corrección finita de Rubin: no se aplica dos veces.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from .chimera_experts.uncertainty import (
    rubin_pool, ladder, completeness_score, brier_score,
    expected_calibration_error, ladder_table,
)


@dataclass
class VarianceBudget:
    model: float
    missing: float
    panel: float
    aleatoric: float

    def __post_init__(self):
        if any(not math.isfinite(v) or v < 0 for v in
               (self.model, self.missing, self.panel, self.aleatoric)):
            raise ValueError("Las componentes deben ser finitas y no negativas")

    @property
    def epistemic(self) -> float:
        return math.sqrt(self.model + self.missing + self.panel)


def pool_variance(expert_verdicts: list[dict]) -> VarianceBudget:
    usable = []
    for v in expert_verdicts:
        if not v or not v.get("available", True) or v.get("abstained") or v.get("abstain"):
            continue
        p = v.get("p", v.get("probability"))
        if p is None:
            continue
        if not math.isfinite(float(p)) or not 0 <= float(p) <= 1:
            raise ValueError("Probabilidad inválida")
        components = [float(v[k]) for k in ("epistemic_model", "epistemic_missing", "aleatoric")]
        if any(not math.isfinite(x) or x < 0 for x in components):
            raise ValueError("Incertidumbre inválida")
        usable.append((float(p), *components))
    if not usable:
        return VarianceBudget(0., 0., 0., 0.)
    a = np.asarray(usable)
    # Rubin con una imputación y los expertos como miembros da la varianza
    # muestral del panel; no vuelve a ajustar la imputación de cada experto.
    _, panel_sigma, _ = rubin_pool(a[:, 0][None, :])
    return VarianceBudget(float(np.mean(a[:, 1] ** 2)), float(np.mean(a[:, 2] ** 2)),
                          panel_sigma ** 2, float(a[:, 3].mean()))


RUNG_CEILING: dict[str, str] = {
    "no_prior_biopsy": "clear", "negative_biopsy": "clear",
    "positive_extreme": "clear", "grade_ge2": "clear", "grade_1": "clear",
    "weighted_panel": "borderline", "burden_of_proof": "uncertain",
}

RUNG_CEILING_TASK2: dict[str, str] = {
    "cancer": "clear", "treat": "borderline", "fit": "uncertain",
}
"""Techos de la cascada task2, derivados del LOO de sus tres nodos.

Cancer: AUC 0.9569; treat: AUC 0.8739; fit: AUC 0.5645 y acierto
0.9394 igual a la moda, sin evidencia de discriminación sobre ese suelo.
Treat no llega a clear aunque su acierto 0.8966 supere clear_min_acc=0.75:
un peldaño más abajo hereda el error del anterior. El umbral sólo mira el
nodo, no la cadena, igual que weighted_panel no tiene el techo de
no_prior_biopsy en task1. Fit nunca puede ser clear ni borderline.
Estos techos no validan la política confidence_from_rung frente a la constante.
"""


def confidence_from_rung(rung: str, budget: VarianceBudget,
                        rung_accuracy: dict[str, float], *, clear_min_acc: float = 0.75,
                        cohort_sigma_q66: float = math.inf) -> tuple[str, str]:
    """Techo medido y descenso por dispersión; el acierto perfecto prevalece.

    El plan omite q66 en la firma pero lo exige en la regla: se añade como
    keyword opcional, sin romper llamadas. Sin cohorte no se inventa un cuantil.
    Un peldaño no observado se considera incierto. El acierto perfecto sólo
    prevalece dentro del techo explícito del peldaño.
    """
    acc = rung_accuracy.get(rung)
    if acc is None:
        return "uncertain", "No hay experiencia comparable suficiente para una conclusión firme."
    if not math.isfinite(acc) or not 0 <= acc <= 1 or not 0 <= clear_min_acc <= 1:
        raise ValueError("Acierto fuera de [0, 1]")
    if math.isnan(cohort_sigma_q66) or cohort_sigma_q66 < 0:
        raise ValueError("Cuantil inválido")
    levels = ["clear", "borderline", "uncertain"]
    index = max(0 if acc >= clear_min_acc else 1,
                levels.index(RUNG_CEILING_TASK2.get(rung, RUNG_CEILING.get(rung, "clear"))))
    if acc < 1 and budget.epistemic > cohort_sigma_q66:
        index = min(2, index + 1)
    reasons = ["La evidencia comparable respalda una conclusión firme.",
               "La evidencia orienta la conducta, aunque persisten dudas relevantes.",
               "La información disponible no permite una conclusión firme."]
    return levels[index], reasons[index]


def arbitrate_cells(learned: dict[str, str], mode: dict[str, str],
                    cell_report: dict[str, dict]) -> tuple[dict[str, str], dict[str, bool]]:
    weights, adopted = {}, {}
    for var in sorted(mode.keys() | learned.keys()):
        row = cell_report.get(var, {})
        win = (var in learned and row.get("loo") is not None and row.get("moda") is not None
               and row["loo"] > row["moda"])
        if not win and var not in mode:
            raise ValueError(f"Falta la constante para {var}")
        adopted[var] = bool(win)
        weights[var] = learned[var] if win else mode[var]
    return weights, adopted


def expected_f1_set(posterior: dict[str, float]) -> set[str]:
    """F1 esperado exacto con Bernoulli independientes, incluidos ambos vacíos.

    Evalúa los prefijos ordenados (Ye et al., ICML 2012). Las convoluciones
    calculan la distribución de cardinalidad dentro y fuera de cada prefijo;
    no se sustituye la esperanza del cociente por un cociente de esperanzas.
    En empates se conserva el conjunto menor; las claves desempatan por nombre.
    """
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in posterior.values()):
        raise ValueError("Posterior fuera de [0, 1]")
    items = sorted(posterior, key=lambda v: (-posterior[v], v))
    probs = [posterior[v] for v in items]
    def distribution(ps):
        dist = np.array([1.])
        for p in ps:
            dist = np.convolve(dist, [1 - p, p])
        return dist
    best, best_k = float(np.prod([1 - p for p in probs])), 0
    for k in range(1, len(items) + 1):
        inside, outside = distribution(probs[:k]), distribution(probs[k:])
        a, b = np.arange(k + 1)[:, None], np.arange(len(outside))[None, :]
        score = float(np.sum(inside[:, None] * outside[None, :] * (2 * a / (k + a + b))))
        if score > best + 1e-12:
            best, best_k = score, k
    return set(items[:best_k])


def project_feasible(weights: dict[str, str], opened: list[str],
                     section_of: dict[str, str], named_in_text: set[str],
                     decisive_var: str | None) -> tuple[dict[str, str], list[str]]:
    """Proyecta con prioridad al aterrizaje si el texto nombra una fuente cerrada.

    En ese conflicto no hay pesos que satisfagan ambas restricciones: se deja
    not_used y se informa de que también debe corregirse el texto. Las variables
    sin sección asignada son información basal; no se inventa una revelación.
    """
    out, corrections = dict(weights), []
    for var in sorted(weights.keys() | named_in_text):
        before = out.get(var, "not_used")
        if before not in ("not_used", "noted", "important", "decisive"):
            raise ValueError(f"Peso inválido: {before}")
        after = before
        closed = var in section_of and section_of[var] not in opened
        if closed:
            after = "not_used"
        else:
            if var in named_in_text and after == "not_used":
                after = "noted"
            if decisive_var is not None and var != decisive_var and after == "decisive":
                after = "important"
        out[var] = after
        if before != after or (closed and var in named_in_text):
            detail = "; retirar la mención del texto: fuente no abierta" if closed and var in named_in_text else ""
            corrections.append(f"{var}: {before} → {after}{detail}.")
    return out, corrections
