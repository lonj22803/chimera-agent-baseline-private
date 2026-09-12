"""Protocolo de evaluación para muestras pequeñas.

Con 91 casos etiquetados, la elección de modelo se decide en la tercera cifra
decimal y es fácil auto-engañarse. Este módulo fija un protocolo y lo aplica
igual a todos los candidatos:

1. **Validación cruzada estratificada repetida** (5 particiones × 20 semillas)
   como métrica primaria. Es el estimador recomendado para n pequeño porque
   promedia sobre la partición, que en LOOCV es la fuente dominante de varianza
   (Kohavi, *A Study of Cross-Validation and Bootstrap*, IJCAI 1995; Varma y
   Simon, *BMC Bioinformatics* 2006, sobre el sesgo de seleccionar y evaluar en
   el mismo bucle).
2. **Leave-One-Out** como métrica secundaria, porque es lo que el usuario de un
   clasificador con 91 casos espera ver y porque su predicción out-of-fold es
   determinista, lo que la hace comparable entre ejecuciones.
3. **Bootstrap sobre los casos** (2000 réplicas) para el intervalo de confianza
   de cada métrica, y bootstrap **pareado** sobre las mismas réplicas para la
   diferencia entre dos modelos: es la comparación correcta cuando ambos
   modelos se evalúan sobre los mismos casos, y evita la falacia de comparar
   dos intervalos que se solapan.

Ninguna de las tres toca el conjunto de test del reto: todo se calcula sobre
los 91 casos con ground truth publicados.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import clone
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneOut, RepeatedStratifiedKFold, StratifiedKFold

from .uncertainty import expected_calibration_error

#: Semilla global. Todo resultado de este paquete es reproducible con ella.
SEED = 20260907


def out_of_fold_probabilities(
    estimator,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
    n_repeats: int = 20,
    seed: int = SEED,
) -> np.ndarray:
    """Matriz ``(n_repeats, n_casos)`` de probabilidades out-of-fold.

    Cada fila es una repetición completa de la validación cruzada con una
    partición distinta. Mantenerlas separadas (en lugar de promediarlas) es lo
    que permite después estimar la varianza *debida a la partición*.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    out = np.full((n_repeats, len(y)), np.nan)
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    for i, (tr, te) in enumerate(cv.split(X, y)):
        rep = i // n_splits
        est = clone(estimator)
        est.fit(X[tr], y[tr])
        out[rep, te] = est.predict_proba(X[te])[:, 1]
    return out


def loo_probabilities(estimator, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Probabilidades leave-one-out (una por caso)."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    p = np.empty(len(y))
    for tr, te in LeaveOneOut().split(X):
        est = clone(estimator)
        est.fit(X[tr], y[tr])
        p[te] = est.predict_proba(X[te])[:, 1]
    return p


def metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict[str, float]:
    """Panel de métricas de discriminación, calibración y decisión."""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    pred = (p >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return {
        "auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else float("nan"),
        "ap": float(average_precision_score(y, p)),
        "accuracy": float((pred == y).mean()),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "sensitivity": tp / (tp + fn) if (tp + fn) else float("nan"),
        "specificity": tn / (tn + fp) if (tn + fp) else float("nan"),
        "ppv": tp / (tp + fp) if (tp + fp) else float("nan"),
        "npv": tn / (tn + fn) if (tn + fn) else float("nan"),
        "brier": float(brier_score_loss(y, p)),
        "ece": expected_calibration_error(y, p),
    }


def bootstrap_ci(
    y: np.ndarray,
    p: np.ndarray,
    stat: str = "auc",
    n_boot: int = 2000,
    seed: int = SEED,
    threshold: float = 0.5,
) -> tuple[float, float, float]:
    """``(estimado, ic_lo, ic_hi)`` por bootstrap percentil sobre los casos."""
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    rng = np.random.default_rng(seed)
    point = metrics(y, p, threshold)[stat]
    vals = []
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(set(y[idx])) < 2:
            continue
        vals.append(metrics(y[idx], p[idx], threshold)[stat])
    if not vals:
        return point, float("nan"), float("nan")
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(point), float(lo), float(hi)


def paired_bootstrap(
    y: np.ndarray,
    p_a: np.ndarray,
    p_b: np.ndarray,
    stat: str = "auc",
    n_boot: int = 2000,
    seed: int = SEED,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Compara dos modelos sobre los mismos casos.

    Devuelve la diferencia ``A - B``, su intervalo al 95 % y el valor p
    bilateral, estimado como la proporción de réplicas cuyo signo contradice al
    de la diferencia observada (equivalente al test de inversión del intervalo
    percentil). Es el análogo no paramétrico del test de DeLong, sin asumir la
    forma asintótica del estadístico U.
    """
    y = np.asarray(y, dtype=int)
    p_a = np.asarray(p_a, dtype=float)
    p_b = np.asarray(p_b, dtype=float)
    rng = np.random.default_rng(seed)
    obs = metrics(y, p_a, threshold)[stat] - metrics(y, p_b, threshold)[stat]
    diffs = []
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if len(set(y[idx])) < 2:
            continue
        diffs.append(metrics(y[idx], p_a[idx], threshold)[stat] - metrics(y[idx], p_b[idx], threshold)[stat])
    diffs = np.asarray(diffs)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    # p bilateral por inversión del intervalo, con corrección de continuidad.
    p_val = 2.0 * min((diffs <= 0).mean(), (diffs >= 0).mean())
    return {"delta": float(obs), "ci_lo": float(lo), "ci_hi": float(hi), "p_value": float(min(1.0, p_val))}


def evaluate(
    estimator,
    X: np.ndarray,
    y: np.ndarray,
    name: str = "model",
    n_splits: int = 5,
    n_repeats: int = 20,
    seed: int = SEED,
    with_loo: bool = True,
) -> dict:
    """Evalúa un candidato con el protocolo completo.

    ``oof_mean`` es la probabilidad promediada sobre repeticiones y es la que se
    usa para las métricas primarias; ``oof_std_across_repeats`` mide cuánto
    depende la predicción de un caso de qué otros casos cayeron en su fold, que
    es una forma directa de leer la inestabilidad del modelo con n pequeño.
    """
    y = np.asarray(y, dtype=int)
    oof = out_of_fold_probabilities(estimator, X, y, n_splits, n_repeats, seed)
    p_mean = np.nanmean(oof, axis=0)
    res = {
        "name": name,
        "n": int(len(y)),
        "n_pos": int(y.sum()),
        "cv_repeats": n_repeats,
        "cv_splits": n_splits,
        "oof_mean": p_mean,
        "oof_matrix": oof,
        "oof_std_across_repeats": float(np.nanmean(np.nanstd(oof, axis=0))),
    }
    res.update({f"cv_{k}": v for k, v in metrics(y, p_mean).items()})
    # Dispersión de la métrica entre repeticiones: el error de la propia
    # estimación por validación cruzada, que suele ser mayor de lo que se cree.
    per_rep = [metrics(y, oof[r])["auc"] for r in range(oof.shape[0])]
    res["cv_auc_sd_across_repeats"] = float(np.std(per_rep))
    if with_loo:
        p_loo = loo_probabilities(estimator, X, y)
        res["loo_probabilities"] = p_loo
        res.update({f"loo_{k}": v for k, v in metrics(y, p_loo).items()})
    return res
