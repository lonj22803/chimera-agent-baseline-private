"""Catálogo de clasificadores candidatos y el envoltorio de incertidumbre.

El catálogo cubre las tres familias que tienen sentido con 91 casos y ~40
variables, muchas de ellas ausentes:

* **Lineales regularizados** — la forma funcional de las calculadoras de riesgo
  validadas (ERSPC/RPCRC, PBCG). Son el punto de comparación obligatorio: si un
  bosque no bate a una regresión logística con estos datos, el bosque sobra.
* **Ensembles de árboles** — bosque aleatorio (Breiman, *Mach Learn* 2001),
  Extra-Trees (Geurts, Ernst y Wehenkel, *Mach Learn* 2006) y *boosting* por
  histogramas. Toleran no linealidades y, en el caso del boosting por
  histogramas, ausencias sin imputar.
* **Basados en instancias y en márgenes** — kNN, kNN probabilístico, SVM con
  escalado de Platt, Naive Bayes gaussiano.

Más el **deep ensemble** de perceptrones multicapa de Lakshminarayanan et al.
(NeurIPS 2017), que es el método de referencia para incertidumbre epistémica
en redes y aquí sirve de control: si su barra de error no es mejor que la del
bagging clásico, no compensa su coste.

Y dos **reglas de guía clínica** sin entrenamiento, que son el suelo real
contra el que hay que medirse:

* PI-RADS >= 3 -> biopsia (la lectura literal de PI-RADS v2.1).
* PI-RADS >= 4, o PI-RADS 3 con PSAD >= 0.15 -> biopsia (la regla de la guía
  EAU 2024 y de PRECISION, Kasivisvanathan et al., *NEJM* 2018).
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.calibration import CalibratedClassifierCV
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
from sklearn.linear_model import BayesianRidge, LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from .uncertainty import Verdict, make_verdict

SEED = 20260907


# --------------------------------------------------------------------------
# Estimadores propios.
# --------------------------------------------------------------------------


class ProbabilisticKNN(BaseEstimator, ClassifierMixin):
    """kNN con probabilidades suavizadas por Laplace y ponderadas por distancia.

    El ``predict_proba`` de ``KNeighborsClassifier`` con ``k`` vecinos sólo puede
    tomar ``k + 1`` valores distintos y produce ceros y unos exactos, que son
    probabilidades imposibles de calibrar y que rompen cualquier log-verosimilitud.
    Aquí la probabilidad es la frecuencia de clase entre los vecinos ponderada
    por ``1/(d + eps)`` y suavizada con un prior de Laplace ``alpha``, que es la
    estimación de Bayes bajo un prior Beta(alpha, alpha) y nunca satura.
    """

    def __init__(self, n_neighbors: int = 15, alpha: float = 1.0, eps: float = 1e-6):
        self.n_neighbors = n_neighbors
        self.alpha = alpha
        self.eps = eps

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        self.classes_ = np.unique(y)
        self._X = X
        self._y = np.asarray(y, dtype=int)
        self._k = min(self.n_neighbors, len(self._y))
        self._nn = KNeighborsClassifier(n_neighbors=self._k).fit(X, self._y)
        return self

    def predict_proba(self, X):
        X = np.asarray(X, dtype=float)
        dist, idx = self._nn.kneighbors(X, n_neighbors=self._k)
        w = 1.0 / (dist + self.eps)
        lab = self._y[idx]
        pos = (w * (lab == 1)).sum(axis=1)
        tot = w.sum(axis=1)
        p1 = (pos + self.alpha) / (tot + 2.0 * self.alpha)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


class GuidelineRule(BaseEstimator, ClassifierMixin):
    """Regla de guía clínica, sin entrenamiento, expresada como clasificador.

    ``mode='pirads3'`` reproduce la lectura literal de PI-RADS v2.1 (>= 3 ->
    biopsia). ``mode='eau'`` reproduce la recomendación EAU 2024: biopsia si
    PI-RADS >= 4, o si PI-RADS = 3 con densidad de PSA >= 0.15 ng/mL/mL.

    Las probabilidades que emite son las frecuencias empíricas de la clase en
    cada rama, aprendidas en ``fit`` — es decir, la regla decide, pero su
    confianza se calibra con los datos, que es lo que la hace comparable con el
    resto de candidatos en Brier y ECE.
    """

    def __init__(self, mode: str = "eau", pirads_col: int = 0, psad_col: int = 1, psad_threshold: float = 0.15):
        self.mode = mode
        self.pirads_col = pirads_col
        self.psad_col = psad_col
        self.psad_threshold = psad_threshold

    def _rule(self, X):
        X = np.asarray(X, dtype=float)
        pirads = X[:, self.pirads_col]
        psad = X[:, self.psad_col]
        # Un PI-RADS ausente se trata como el valor mediano observado en fit,
        # que es la conducta menos comprometida ante la falta de información.
        pirads = np.where(np.isnan(pirads), self._pirads_median, pirads)
        psad = np.where(np.isnan(psad), self._psad_median, psad)
        if self.mode == "pirads3":
            return pirads >= 3
        return (pirads >= 4) | ((pirads >= 3) & (psad >= self.psad_threshold))

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=int)
        self.classes_ = np.array([0, 1])
        self._pirads_median = float(np.nanmedian(X[:, self.pirads_col]))
        self._psad_median = float(np.nanmedian(X[:, self.psad_col]))
        m = self._rule(X)
        # Frecuencia empírica por rama, con suavizado de Laplace.
        self._p_pos = (y[m].sum() + 1.0) / (m.sum() + 2.0) if m.any() else 0.5
        self._p_neg = (y[~m].sum() + 1.0) / ((~m).sum() + 2.0) if (~m).any() else 0.5
        return self

    def predict_proba(self, X):
        m = self._rule(X)
        p1 = np.where(m, self._p_pos, self._p_neg)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


class PriorOnly(BaseEstimator, ClassifierMixin):
    """Predice siempre la prevalencia. El suelo absoluto de cualquier métrica."""

    def fit(self, X, y):
        self.classes_ = np.array([0, 1])
        self._p = float(np.mean(y))
        return self

    def predict_proba(self, X):
        p1 = np.full(len(X), self._p)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


# --------------------------------------------------------------------------
# Catálogo.
# --------------------------------------------------------------------------


def _prep(strategy: str = "iterative", seed: int = SEED):
    """Bloque de preprocesado: imputación + red de seguridad + estandarización.

    La segunda imputación no es redundante. ``IterativeImputer`` sólo construye
    un modelo de imputación para las columnas que tenían ausencias **durante el
    ajuste**; si un caso nuevo trae un NaN en una columna que estaba completa en
    entrenamiento, lo deja pasar tal cual y el estimador de abajo revienta. En
    este reto eso no es hipotético: las modalidades faltan a propósito y el
    patrón de ausencias del test no tiene por qué haberse visto antes. La
    mediana de entrenamiento es el relleno de último recurso.
    """
    if strategy == "median":
        imp = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
    else:
        imp = IterativeImputer(
            estimator=BayesianRidge(),
            max_iter=15,
            sample_posterior=False,
            random_state=seed,
            add_indicator=True,
            # Cada regresión condicional usa sólo los 10 predictores más
            # correlacionados. Sin esta restricción, con ~100 columnas
            # colineales y ~70 filas por partición el diseño es casi singular y
            # BayesianRidge devuelve NaN, que se propagan al resto de la
            # imputación: 11 de 20 particiones fallaban. Es el remedio que la
            # documentación de scikit-learn prescribe para datos anchos.
            n_nearest_features=10,
        )
    safety = SimpleImputer(strategy="median", keep_empty_features=True)
    return [("impute", imp), ("impute_safety", safety), ("scale", StandardScaler())]


def build_catalog(seed: int = SEED, pirads_col: int = 0, psad_col: int = 1) -> dict[str, object]:
    """Devuelve ``{nombre: estimador}`` con todos los candidatos del bakeoff."""
    p = lambda est, strategy="iterative": Pipeline(_prep(strategy, seed) + [("clf", est)])  # noqa: E731

    catalog: dict[str, object] = {
        # --- suelos ---
        "prior_only": PriorOnly(),
        "rule_pirads3": GuidelineRule("pirads3", pirads_col, psad_col),
        "rule_eau_psad": GuidelineRule("eau", pirads_col, psad_col),
        # --- lineales ---
        "logreg_l2": p(LogisticRegression(penalty="l2", C=1.0, max_iter=5000, random_state=seed)),
        "logreg_l1": p(LogisticRegression(penalty="l1", C=0.5, solver="liblinear", max_iter=5000, random_state=seed)),
        "logreg_elasticnet": p(
            LogisticRegression(
                penalty="elasticnet", l1_ratio=0.5, C=0.5, solver="saga", max_iter=8000, random_state=seed
            )
        ),
        "lda": p(LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")),
        # --- árboles ---
        "decision_tree": p(DecisionTreeClassifier(max_depth=3, min_samples_leaf=8, random_state=seed)),
        "random_forest": p(
            RandomForestClassifier(
                n_estimators=1000, min_samples_leaf=3, max_features="sqrt", random_state=seed, n_jobs=-1
            )
        ),
        "extra_trees": p(
            ExtraTreesClassifier(
                n_estimators=1000, min_samples_leaf=3, max_features="sqrt", random_state=seed, n_jobs=-1
            )
        ),
        "random_forest_calibrated": p(
            CalibratedClassifierCV(
                RandomForestClassifier(n_estimators=500, min_samples_leaf=3, random_state=seed, n_jobs=-1),
                method="isotonic",
                cv=5,
            )
        ),
        "grad_boosting": p(GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.05, random_state=seed)),
        # El boosting por histogramas admite NaN de forma nativa: no se le
        # impone imputación, para poder medir si imputar ayuda o estorba.
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0, random_state=seed
        ),
        # --- instancias y márgenes ---
        "knn": p(KNeighborsClassifier(n_neighbors=15, weights="distance")),
        "knn_probabilistic": p(ProbabilisticKNN(n_neighbors=15, alpha=1.0)),
        "svm_rbf": p(SVC(C=1.0, gamma="scale", probability=True, random_state=seed)),
        "svm_linear": p(SVC(kernel="linear", C=0.5, probability=True, random_state=seed)),
        "gaussian_nb": p(GaussianNB()),
        # --- deep ensemble ---
        "deep_ensemble_mlp": p(
            BaggingClassifier(
                estimator=MLPClassifier(
                    hidden_layer_sizes=(32, 16), alpha=1e-2, max_iter=3000, early_stopping=False, random_state=seed
                ),
                n_estimators=15,
                max_samples=0.8,
                bootstrap=True,
                random_state=seed,
                n_jobs=-1,
            )
        ),
    }
    return catalog


# --------------------------------------------------------------------------
# Envoltorio de incertidumbre: bagging + imputación múltiple.
# --------------------------------------------------------------------------


class UncertaintyExpert(BaseEstimator, ClassifierMixin):
    """Convierte cualquier clasificador en un experto con veredicto e incertidumbre.

    Entrena ``n_members`` copias del estimador base sobre remuestras bootstrap
    (Breiman, *Bagging Predictors*, Mach Learn 1996), cada una precedida de su
    propio imputador estocástico. En inferencia se piden ``n_imputations``
    pasadas por miembro, de modo que la matriz de probabilidades resultante
    ``(n_imputations, n_members)`` separa dos fuentes de variación:

    * entre columnas — el modelo (incertidumbre epistémica clásica);
    * entre filas — los valores que faltan (término *between* de Rubin).

    Un caso completo produce filas idénticas y por tanto ``epistemic_missing``
    exactamente cero: la barra sólo se ensancha cuando de verdad falta
    información.
    """

    def __init__(
        self,
        base_estimator=None,
        n_members: int = 40,
        n_imputations: int = 10,
        max_samples: float = 0.8,
        threshold: float = 0.5,
        seed: int = SEED,
    ):
        self.base_estimator = base_estimator
        self.n_members = n_members
        self.n_imputations = n_imputations
        self.max_samples = max_samples
        self.threshold = threshold
        self.seed = seed

    def _member(self, k: int):
        base = clone(self.base_estimator) if self.base_estimator is not None else LogisticRegression(max_iter=5000)
        return Pipeline(
            [
                (
                    "impute",
                    IterativeImputer(
                        estimator=BayesianRidge(),
                        max_iter=15,
                        sample_posterior=True,
                        random_state=self.seed + k,
                        add_indicator=True,
                        n_nearest_features=10,  # estabilidad: véase la nota en _prep
                    ),
                ),
                # Red de seguridad ante patrones de ausencia no vistos en fit;
                # véase la nota en ``_prep``.
                ("impute_safety", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scale", StandardScaler()),
                ("clf", base),
            ]
        )

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=int)
        self.classes_ = np.array([0, 1])
        self.n_features_in_ = X.shape[1]
        rng = np.random.default_rng(self.seed)
        n = len(y)
        size = max(int(self.max_samples * n), 10)
        self.members_ = []
        for k in range(self.n_members):
            # Remuestra estratificada: con 35 negativos, una bootstrap simple
            # puede dejar un miembro sin apenas casos de una clase.
            idx = np.concatenate(
                [
                    rng.choice(np.flatnonzero(y == c), size=max(int(size * (y == c).mean()), 5), replace=True)
                    for c in (0, 1)
                ]
            )
            m = self._member(k)
            m.fit(X[idx], y[idx])
            self.members_.append(m)
        return self

    def _probability_matrix(self, X) -> np.ndarray:
        """Tensor ``(n_imputations, n_members, n_casos)`` de probabilidades.

        Se procesa **todo el lote de una vez** por cada par (miembro,
        imputacion). Hacerlo caso a caso multiplica por ``n_casos`` el numero de
        transformaciones del imputador, que es la parte cara: con 30 miembros y
        10 imputaciones son 300 pases por lote frente a 300 por *caso*.

        Ademas, si ninguna fila tiene valores ausentes, las imputaciones son
        identicas por construccion y se ejecuta una sola: el termino
        *between-imputation* de Rubin vale cero de todas formas.
        """
        X = np.atleast_2d(np.asarray(X, dtype=float))
        n_cases = X.shape[0]
        n_imp = 1 if not np.isnan(X).any() else self.n_imputations
        out = np.empty((n_imp, len(self.members_), n_cases))
        for j, m in enumerate(self.members_):
            for i in range(n_imp):
                out[i, j, :] = m.predict_proba(X)[:, 1]
        return out

    def predict_proba(self, X):
        p1 = self._probability_matrix(X).mean(axis=(0, 1))
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= self.threshold).astype(int)

    def verdicts(self, X, completeness: np.ndarray | None = None) -> list[Verdict]:
        """Un :class:`Verdict` por caso, con la incertidumbre descompuesta."""
        cube = self._probability_matrix(X)
        n_cases = cube.shape[2]
        comp = completeness if completeness is not None else np.ones(n_cases)
        return [make_verdict(cube[:, :, i], float(comp[i]), self.threshold) for i in range(n_cases)]
