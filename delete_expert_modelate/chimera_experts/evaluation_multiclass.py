"""Protocolo de evaluación para la tarea 2.

La métrica que manda no se elige: el evaluador oficial del reto puntúa la
recomendación con **acierto exacto** y, si falla, pone el ``case_score`` del
caso a cero sin mirar el resto del razonamiento. No hay crédito parcial entre
``active_surveillance`` y ``continued_surveillance``. De ahí que el criterio
principal aquí sea el acierto de las cuatro clases y no el F1 macro, que
premiaría un modelo mejor repartido pero peor puntuado.

Se reportan además el F1 macro y el acierto equilibrado, porque un modelo que
sólo acierta la clase mayoritaria es una respuesta distinta a la misma cifra, y
el Brier multiclase y el ECE, porque un experto que va a una junta con una
probabilidad mal calibrada estropea la deliberación aunque acierte.

Protocolo principal: **leave-one-out**. Con 72 casos etiquetados y una clase de
dos, cualquier partición en k pliegues deja pliegues sin esa clase; LOO es la
única que la conserva siempre en entrenamiento y además no depende de una
semilla. El coste —72 ajustes— es asumible con estos modelos.
"""

from __future__ import annotations

import warnings

import numpy as np
from sklearn.base import clone
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import LeaveOneOut, RepeatedStratifiedKFold

from .uncertainty_multiclass import expected_calibration_error, multiclass_brier


def _fit_predict(estimator, X_tr, y_tr, X_te, n_classes: int) -> np.ndarray:
    est = clone(estimator)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est.fit(X_tr, y_tr)
        P_local = est.predict_proba(X_te)
    P = np.zeros((len(X_te), n_classes))
    for j, c in enumerate(est.classes_):
        P[:, int(c)] = P_local[:, j]
    return P


def loo_probabilities(estimator, X: np.ndarray, y: np.ndarray, n_classes: int = 4) -> np.ndarray:
    """Matriz ``(n, n_clases)`` de probabilidades leave-one-out."""
    P = np.zeros((len(y), n_classes))
    for tr, te in LeaveOneOut().split(X):
        P[te] = _fit_predict(estimator, X[tr], y[tr], X[te], n_classes)
    return P


def cv_probabilities(
    estimator, X: np.ndarray, y: np.ndarray, n_classes: int = 4,
    n_splits: int = 4, n_repeats: int = 5, seed: int = 0,
) -> np.ndarray:
    """Probabilidades fuera de pliegue, promediadas sobre repeticiones.

    Complementa a LOO: da una estimación con particiones de entrenamiento más
    pequeñas, que es la situación real del reto, y su dispersión entre
    repeticiones dice cuánto de lo medido depende de la partición.
    """
    acc = np.zeros((len(y), n_classes))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        splitter = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
        for tr, te in splitter.split(X, y):
            acc[te] += _fit_predict(estimator, X[tr], y[tr], X[te], n_classes)
    return acc / n_repeats


def metrics(y: np.ndarray, P: np.ndarray) -> dict[str, float]:
    pred = P.argmax(axis=1)
    return {
        "accuracy": float((pred == y).mean()),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "f1_macro": float(f1_score(y, pred, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y, pred, average="weighted", zero_division=0)),
        "brier": multiclass_brier(y, P),
        "ece": expected_calibration_error(y, P),
    }


def bootstrap_ci(y: np.ndarray, P: np.ndarray, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Percentil 2.5-97.5 del acierto por remuestreo de casos."""
    rng = np.random.default_rng(seed)
    pred = P.argmax(axis=1)
    hits = (pred == y).astype(float)
    boots = [hits[rng.integers(0, len(hits), len(hits))].mean() for _ in range(n_boot)]
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def paired_bootstrap(y: np.ndarray, P_a: np.ndarray, P_b: np.ndarray,
                     n_boot: int = 2000, seed: int = 0) -> dict[str, float]:
    """Diferencia de acierto entre dos modelos sobre los **mismos** casos.

    Pareado, porque comparar dos intervalos marginales que se solapan no dice
    nada sobre si un modelo es mejor que el otro caso a caso.
    """
    rng = np.random.default_rng(seed)
    a = (P_a.argmax(axis=1) == y).astype(float)
    b = (P_b.argmax(axis=1) == y).astype(float)
    d = a - b
    boots = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)])
    # El p bilateral se recorta a 1.0: cuando los dos modelos aciertan
    # exactamente los mismos casos, cada cola vale 1.0 y el doble del mínimo se
    # saldría del rango. Un delta idéntico en cero es p = 1, no p = 2.
    p_two = min(1.0, 2 * min((boots <= 0).mean(), (boots >= 0).mean()))
    return {
        "delta": float(d.mean()),
        "lo": float(np.percentile(boots, 2.5)),
        "hi": float(np.percentile(boots, 97.5)),
        "p_two_sided": float(p_two),
    }


def confusion(y: np.ndarray, P: np.ndarray, classes) -> str:
    """Matriz de confusión legible. Con cuatro clases desbalanceadas, el
    acierto agregado esconde exactamente lo que hay que ver."""
    pred = P.argmax(axis=1)
    k = len(classes)
    M = np.zeros((k, k), dtype=int)
    for t, p in zip(y, pred):
        M[t, p] += 1
    w = max(len(c) for c in classes) + 1
    head = " " * (w + 2) + "".join(f"{c[:10]:>12s}" for c in classes) + f"{'n':>6s}"
    lines = [head]
    for i, c in enumerate(classes):
        lines.append(f"{c:<{w}s}  " + "".join(f"{M[i, j]:>12d}" for j in range(k)) + f"{M[i].sum():>6d}")
    lines.append(f"{'pred n':<{w}s}  " + "".join(f"{M[:, j].sum():>12d}" for j in range(k)))
    return "\n".join(lines)
