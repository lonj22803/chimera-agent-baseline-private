"""Catálogo de candidatos y envoltorio de incertidumbre para la tarea 2.

Se separa de ``models.py`` en vez de parametrizarlo porque cambian las tres
piezas que definen un catálogo: los suelos (aquí la regla es de guía y de
cuatro salidas, no de umbral), la métrica de desempate y la envoltura de
incertidumbre, que en varias clases no es la binaria con otro nombre.

Los estimadores de scikit-learn manejan varias clases de forma nativa, así que
la lista de candidatos es reconocible; lo que no se reutiliza son los suelos,
que son los que dicen si un modelo aprendido merece existir.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import (
    BaggingClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer, SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from .models import _prep  # imputación + escalado, idénticos a la tarea 1

SEED = 20260101


# --------------------------------------------------------------------------
# Suelos. Un modelo aprendido que no los bate no es un resultado.
# --------------------------------------------------------------------------

class PriorOnly(BaseEstimator, ClassifierMixin):
    """Devuelve siempre la distribución de clases del entrenamiento."""

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        counts = np.array([(y == c).sum() for c in self.classes_], dtype=float)
        self.prior_ = counts / counts.sum()
        return self

    def predict_proba(self, X):
        return np.tile(self.prior_, (len(X), 1))

    def predict(self, X):
        return np.full(len(X), self.classes_[int(np.argmax(self.prior_))])


class GradeRule(BaseEstimator, ClassifierMixin):
    """Regla de guía: la conducta la fija el ISUP grade group de la biopsia.

    Es el suelo que de verdad importa en esta tarea. La etiqueta se derivó
    retrospectivamente de la histopatología, de modo que un mapa
    ``ISUP → conducta`` explica la mayor parte de la cohorte. La regla **no**
    trae el mapa escrito: lo estima en cada partición de entrenamiento por
    clase mayoritaria dentro de cada grado. Así el suelo se mide con el mismo
    protocolo que los modelos aprendidos, y no queda inflado por haber mirado
    las etiquetas de la partición de prueba.

    ``isup_col`` es el índice de la columna ``bx_isup`` en la matriz.
    """

    def __init__(self, isup_col: int = 0, laplace: float = 0.5):
        self.isup_col = isup_col
        self.laplace = laplace

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        self.classes_ = np.unique(y)
        k = len(self.classes_)
        g = X[:, self.isup_col]
        self.table_: dict[float, np.ndarray] = {}
        for grade in np.unique(g[~np.isnan(g)]):
            m = g == grade
            counts = np.array([(y[m] == c).sum() for c in self.classes_], dtype=float)
            self.table_[float(grade)] = (counts + self.laplace) / (counts.sum() + self.laplace * k)
        counts = np.array([(y == c).sum() for c in self.classes_], dtype=float)
        self.fallback_ = (counts + self.laplace) / (counts.sum() + self.laplace * k)
        return self

    def predict_proba(self, X):
        X = np.asarray(X, dtype=float)
        g = X[:, self.isup_col]
        return np.array([self.table_.get(float(v), self.fallback_) if v == v else self.fallback_ for v in g])

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


def build_catalog(seed: int = SEED, isup_col: int = 0) -> dict[str, object]:
    p = lambda est, strategy="iterative": Pipeline(_prep(strategy, seed) + [("clf", est)])  # noqa: E731

    return {
        # --- suelos ---
        "prior_only": PriorOnly(),
        "grade_rule": GradeRule(isup_col=isup_col),
        # --- lineales ---
        "logreg_l2": p(LogisticRegression(penalty="l2", C=1.0, max_iter=8000, random_state=seed)),
        "logreg_l1": p(LogisticRegression(penalty="l1", C=0.5, solver="saga", max_iter=12000, random_state=seed)),
        "logreg_balanced": p(
            LogisticRegression(penalty="l2", C=1.0, max_iter=8000, class_weight="balanced", random_state=seed)
        ),
        "lda": p(LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")),
        # --- árboles ---
        "decision_tree": p(DecisionTreeClassifier(max_depth=3, min_samples_leaf=5, random_state=seed)),
        "random_forest": p(
            RandomForestClassifier(n_estimators=1000, min_samples_leaf=2, max_features="sqrt",
                                   random_state=seed, n_jobs=-1)
        ),
        "random_forest_balanced": p(
            RandomForestClassifier(n_estimators=1000, min_samples_leaf=2, max_features="sqrt",
                                   class_weight="balanced_subsample", random_state=seed, n_jobs=-1)
        ),
        "extra_trees": p(
            ExtraTreesClassifier(n_estimators=1000, min_samples_leaf=2, max_features="sqrt",
                                 random_state=seed, n_jobs=-1)
        ),
        "extra_trees_balanced": p(
            ExtraTreesClassifier(n_estimators=1000, min_samples_leaf=2, max_features="sqrt",
                                 class_weight="balanced", random_state=seed, n_jobs=-1)
        ),
        "grad_boosting": p(GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.05,
                                                      random_state=seed)),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0, random_state=seed
        ),
        # --- instancias y márgenes ---
        "knn": p(KNeighborsClassifier(n_neighbors=10, weights="distance")),
        "svm_rbf": p(SVC(C=1.0, gamma="scale", probability=True, random_state=seed)),
        "gaussian_nb": p(GaussianNB()),
        # --- deep ensemble ---
        "deep_ensemble_mlp": p(
            BaggingClassifier(
                estimator=MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-2, max_iter=3000, random_state=seed),
                n_estimators=15, max_samples=0.8, bootstrap=True, random_state=seed, n_jobs=-1,
            )
        ),
    }


# --------------------------------------------------------------------------
# Envoltorio de incertidumbre multiclase.
# --------------------------------------------------------------------------

class MulticlassUncertaintyExpert(BaseEstimator, ClassifierMixin):
    """Convierte cualquier clasificador en un experto probabilístico de 4 salidas.

    Entrena ``n_members`` copias sobre remuestras bootstrap (Breiman 1996) y en
    inferencia pide ``n_imputations`` pasadas por miembro. La matriz resultante
    ``(imputaciones, miembros, clases)`` separa las dos fuentes de variación que
    el deliberador tiene que poder distinguir: el desacuerdo entre modelos y el
    desacuerdo causado por los valores que faltan.

    El remuestreo bootstrap es **estratificado** cuando puede serlo. Con una
    clase de dos casos, un bootstrap ordinario deja fuera esa clase en el 45 %
    de los miembros y el ensemble deja de saber que existe; forzar al menos un
    ejemplar por clase en cada remuestra es lo que impide que la clase rara
    desaparezca por construcción y no por evidencia.
    """

    def __init__(
        self,
        base_estimator=None,
        n_members: int = 40,
        n_imputations: int = 10,
        max_samples: float = 0.8,
        stratified_bootstrap: bool = True,
        random_state: int = SEED,
    ):
        self.base_estimator = base_estimator
        self.n_members = n_members
        self.n_imputations = n_imputations
        self.max_samples = max_samples
        self.stratified_bootstrap = stratified_bootstrap
        self.random_state = random_state

    @staticmethod
    def _iterative_imputers(est):
        """Los ``IterativeImputer`` del estimador, buscando dentro de cascadas."""
        found = []
        for name, step in getattr(est, "named_steps", {}).items():
            if isinstance(step, IterativeImputer):
                found.append(step)
        for head in (getattr(est, "heads", None) or {}).values():
            found.extend(MulticlassUncertaintyExpert._iterative_imputers(head))
        return found

    def _member(self, k: int):
        est = clone(self.base_estimator)
        # Cada miembro recibe su propia semilla de imputación: si todos imputan
        # igual, la varianza *between* de Rubin sale cero por construcción y la
        # incertidumbre por datos ausentes deja de existir.
        for name, step in getattr(est, "named_steps", {}).items():
            if name.startswith("impute") and hasattr(step, "random_state"):
                step.set_params(random_state=self.random_state + 1000 * k)
            if name.startswith("impute") and isinstance(step, SimpleImputer):
                continue
        # Y cada **pasada** tiene que poder diferir de la anterior. Un
        # ``IterativeImputer`` ajustado es determinista en ``transform``:
        # pedirle diez imputaciones del mismo caso devuelve diez copias
        # idénticas, la varianza *between* de Rubin sale exactamente cero y el
        # término de incertidumbre por datos ausentes deja de medir nada
        # mientras multiplica el coste de inferencia por diez. ``sample_posterior``
        # hace que cada pasada muestree de la posterior predictiva de la
        # ``BayesianRidge`` interna, que es lo que la imputación múltiple pide
        # (Rubin 1987; van Buuren y Groothuis-Oudshoorn, J Stat Softw 2011).
        for imp in self._iterative_imputers(est):
            imp.set_params(sample_posterior=True)
        if hasattr(est, "random_state"):
            est.set_params(random_state=self.random_state + k)
        return est

    def _stochastic_imputation(self) -> bool:
        """¿Difieren de verdad las pasadas de imputación de este ensemble?

        Un modelo entrenado antes de activar ``sample_posterior`` sigue siendo
        determinista en ``transform``. Pedirle varias pasadas no aporta
        dispersión: sólo tiempo. Se comprueba en el propio ensemble en vez de
        asumirlo, para que un artefacto antiguo se abarate en lugar de mentir.
        """
        for est in getattr(self, "members_", []):
            for imp in self._iterative_imputers(est):
                if getattr(imp, "sample_posterior", False):
                    return True
        return False

    def _resample(self, rng, y):
        n = len(y)
        size = max(int(round(self.max_samples * n)), len(np.unique(y)))
        idx = rng.choice(n, size=size, replace=True)
        if not self.stratified_bootstrap:
            return idx
        present = set(y[idx].tolist())
        for c in np.unique(y):
            if c not in present:
                pool = np.flatnonzero(y == c)
                idx[rng.integers(len(idx))] = rng.choice(pool)
        return idx

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        self.classes_ = np.unique(y)
        rng = np.random.default_rng(self.random_state)
        self.members_ = []
        for k in range(self.n_members):
            idx = self._resample(rng, y)
            est = self._member(k)
            est.fit(X[idx], y[idx])
            self.members_.append(est)
        return self

    def _align(self, est, P_local: np.ndarray) -> np.ndarray:
        """Recoloca las columnas de un miembro que no vio todas las clases."""
        out = np.zeros((P_local.shape[0], len(self.classes_)))
        for j, c in enumerate(est.classes_):
            out[:, int(np.flatnonzero(self.classes_ == c)[0])] = P_local[:, j]
        return out

    def probability_tensor(self, X) -> np.ndarray:
        """Tensor ``(imputaciones, miembros, clases)``."""
        X = np.asarray(X, dtype=float)
        n_imp = self.n_imputations if np.isnan(X).any() else 1
        # Sin imputación estocástica las pasadas son copias exactas: se pide
        # una sola y el resultado es idéntico a diez, con la décima parte del
        # trabajo.
        if n_imp > 1 and not self._stochastic_imputation():
            n_imp = 1
        out = np.empty((n_imp, len(self.members_), len(self.classes_), len(X)))
        for i in range(n_imp):
            for k, est in enumerate(self.members_):
                out[i, k] = self._align(est, est.predict_proba(X)).T
        return np.moveaxis(out, 3, 0)      # (casos, imputaciones, miembros, clases)

    def predict_proba(self, X):
        T = self.probability_tensor(X)
        return T.reshape(T.shape[0], -1, T.shape[-1]).mean(axis=1)

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]

    def verdicts(self, X, class_names, completeness=None):
        from .uncertainty_multiclass import make_verdict

        T = self.probability_tensor(X)
        comp = np.ones(len(X)) if completeness is None else np.asarray(completeness, dtype=float)
        return [make_verdict(T[i], class_names, float(comp[i])) for i in range(T.shape[0])]
