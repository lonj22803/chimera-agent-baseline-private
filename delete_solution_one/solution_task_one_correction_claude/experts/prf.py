"""Probabilistic Random Forest (Reis, Baron & Shahaf 2019, AJ 157:16).

Un Random Forest clásico trata cada valor como un número exacto. El PRF trata
cada valor como una **distribución**: ``x_ij ~ N(mu_ij, sigma_ij)``. En un nodo
con corte ``(j, t)``, el objeto no baja por una rama, baja por **las dos** con
pesos

    p_izq = Phi((t - mu_ij) / sigma_ij)        p_der = 1 - p_izq

y la impureza se calcula sobre las cuentas de clase **ponderadas**. Predecir es
el mismo recorrido: la probabilidad de la hoja se promedia con el peso con que
el objeto llegó a ella.

Por qué encaja en esta tarea concreta
-------------------------------------
1. **Los ausentes dejan de necesitar imputación.** ``sigma = inf`` reparte al
   objeto 50/50 en cada corte de esa variable, que es exactamente lo que
   significa "no documentado". En T1 hay ausencias reales (PI-RADS ``NA``,
   ``dre = Not done``, antecedente familiar ``Unknown``) y la mediana las
   convierte en una afirmación falsa: dice que el paciente es "el del medio".
2. **Varias variables del reto son estimaciones con error conocido.** ``vol``
   sale de una segmentación automática, ``psad = psa/vol`` hereda ese error,
   ``cspca`` es la salida de un modelo, y el PI-RADS tiene variabilidad
   inter-lector documentada de aproximadamente medio grado. Meter esa
   incertidumbre en el modelo es más honesto que fingir precisión infinita.
3. **La probabilidad de salida sale mejor calibrada**, que es lo que le sirve
   al LLM: un número sobreconfiado es peor que ninguno porque el presidente de
   la mesa no puede ponderarlo.

Implementación: numpy puro, sin dependencias nuevas. Con n <= 200 y ~50
variables es de sobra rápido y evita meter un paquete más en la imagen del
contenedor (que va sin red).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

_EPS = 1e-12


def _gini(counts: np.ndarray) -> float:
    total = counts.sum()
    if total <= _EPS:
        return 0.0
    p = counts / total
    return float(1.0 - np.sum(p * p))


class ProbabilisticDecisionTree:
    """Un árbol del PRF. Se ajusta sobre pesos, no sobre índices."""

    def __init__(self, n_classes: int, max_depth: int = 6, min_weight_leaf: float = 2.0,
                 max_features: int | None = None, n_thresholds: int = 12, rng=None):
        self.n_classes = n_classes
        self.max_depth = max_depth
        self.min_weight_leaf = min_weight_leaf
        self.max_features = max_features
        self.n_thresholds = n_thresholds
        self.rng = rng or np.random.default_rng(0)
        self.tree_: dict = {}

    # -- probabilidad de caer a la izquierda del corte -----------------------

    @staticmethod
    def _p_left(mu: np.ndarray, sigma: np.ndarray, t: float) -> np.ndarray:
        """``P(x < t)`` con x ~ N(mu, sigma). NaN -> 0.5 (el objeto se reparte)."""
        p = np.full(mu.shape, 0.5)
        finite = np.isfinite(mu)
        s = np.where(np.isfinite(sigma) & (sigma > _EPS), sigma, _EPS)
        # sigma ~ 0 degenera en el corte duro del RF clásico
        p[finite] = norm.cdf((t - mu[finite]) / s[finite])
        return p

    def fit(self, X: np.ndarray, S: np.ndarray, Y: np.ndarray, w: np.ndarray) -> "ProbabilisticDecisionTree":
        """*X* medias, *S* desviaciones, *Y* one-hot (n, C), *w* pesos iniciales."""
        self.tree_ = self._build(X, S, Y, w, depth=0)
        return self

    def _build(self, X, S, Y, w, depth: int) -> dict:
        counts = Y.T @ w
        total = counts.sum()
        leaf = {"leaf": True, "p": (counts + 1.0) / (total + self.n_classes)}  # Laplace

        if depth >= self.max_depth or total < 2 * self.min_weight_leaf or _gini(counts) <= _EPS:
            return leaf

        n_feat = X.shape[1]
        k = self.max_features or max(1, int(np.sqrt(n_feat)))
        cand = self.rng.choice(n_feat, size=min(k, n_feat), replace=False)

        best = None
        parent_imp = _gini(counts)
        for j in cand:
            col = X[:, j]
            obs = col[np.isfinite(col) & (w > _EPS)]
            if obs.size < 2:
                continue
            qs = np.unique(np.quantile(obs, np.linspace(0.1, 0.9, self.n_thresholds)))
            for t in qs:
                pl = self._p_left(col, S[:, j], t)
                wl, wr = w * pl, w * (1.0 - pl)
                tl, tr = wl.sum(), wr.sum()
                if tl < self.min_weight_leaf or tr < self.min_weight_leaf:
                    continue
                gain = parent_imp - (tl * _gini(Y.T @ wl) + tr * _gini(Y.T @ wr)) / total
                if best is None or gain > best[0]:
                    best = (gain, j, float(t), wl, wr)

        if best is None or best[0] <= _EPS:
            return leaf

        _, j, t, wl, wr = best
        return {
            "leaf": False,
            "j": j,
            "t": t,
            "left": self._build(X, S, Y, wl, depth + 1),
            "right": self._build(X, S, Y, wr, depth + 1),
        }

    def predict_proba(self, X: np.ndarray, S: np.ndarray) -> np.ndarray:
        out = np.zeros((X.shape[0], self.n_classes))
        self._descend(self.tree_, X, S, np.ones(X.shape[0]), out)
        return out

    def _descend(self, node, X, S, w, out) -> None:
        if w.sum() <= _EPS:
            return
        if node["leaf"]:
            out += w[:, None] * node["p"][None, :]
            return
        pl = self._p_left(X[:, node["j"]], S[:, node["j"]], node["t"])
        self._descend(node["left"], X, S, w * pl, out)
        self._descend(node["right"], X, S, w * (1.0 - pl), out)


class ProbabilisticRandomForest:
    """El bosque: bagging de :class:`ProbabilisticDecisionTree`.

    Interfaz compatible con scikit-learn en lo que usa este proyecto
    (``fit`` / ``predict_proba`` / ``predict``), pero ``fit`` acepta además la
    matriz de desviaciones típicas por variable.
    """

    def __init__(self, n_estimators: int = 200, max_depth: int = 6, min_weight_leaf: float = 2.0,
                 max_features: int | None = None, random_state: int = 0, bootstrap: bool = True):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_weight_leaf = min_weight_leaf
        self.max_features = max_features
        self.random_state = random_state
        self.bootstrap = bootstrap

    def fit(self, X, y, sigma=None):
        X = np.asarray(X, float)
        S = np.zeros_like(X) if sigma is None else np.asarray(sigma, float)
        S = np.where(np.isfinite(X), S, np.inf)  # ausente == totalmente incierto
        self.classes_ = np.unique(y)
        Y = (np.asarray(y)[:, None] == self.classes_[None, :]).astype(float)
        n = X.shape[0]
        rng = np.random.default_rng(self.random_state)

        self.trees_ = []
        for b in range(self.n_estimators):
            if self.bootstrap:
                idx = rng.integers(0, n, n)
                w = np.bincount(idx, minlength=n).astype(float)
            else:
                w = np.ones(n)
            tree = ProbabilisticDecisionTree(
                n_classes=len(self.classes_), max_depth=self.max_depth,
                min_weight_leaf=self.min_weight_leaf, max_features=self.max_features,
                rng=np.random.default_rng(rng.integers(1 << 31)),
            )
            self.trees_.append(tree.fit(X, S, Y, w))
        return self

    def predict_proba(self, X, sigma=None):
        X = np.asarray(X, float)
        S = np.zeros_like(X) if sigma is None else np.asarray(sigma, float)
        S = np.where(np.isfinite(X), S, np.inf)
        P = np.zeros((X.shape[0], len(self.classes_)))
        for tree in self.trees_:
            P += tree.predict_proba(X, S)
        P /= len(self.trees_)
        return P

    def predict(self, X, sigma=None):
        return self.classes_[self.predict_proba(X, sigma).argmax(1)]

    def predict_proba_per_tree(self, X, sigma=None) -> np.ndarray:
        """(n_arboles, n, C) — para separar incertidumbre epistémica de aleatoria."""
        X = np.asarray(X, float)
        S = np.zeros_like(X) if sigma is None else np.asarray(sigma, float)
        S = np.where(np.isfinite(X), S, np.inf)
        return np.stack([t.predict_proba(X, S) for t in self.trees_])
