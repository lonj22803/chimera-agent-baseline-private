"""Cascada de guía: tres preguntas binarias en lugar de una de cuatro salidas.

Un clasificador plano de cuatro clases tiene que aprender, con 72 casos, una
frontera entre ``watchful_waiting`` (2 casos) y el resto. No hay forma de que
eso salga bien: el modelo aprende a no predecir nunca esa clase, que es la
respuesta óptima bajo acierto y la respuesta inútil bajo cualquier otro
criterio.

La alternativa no es reponderar; es **descomponer la etiqueta por la costura
que la guía ya tiene**. EAU y NCCN no eligen entre cuatro conductas de un
tirón: encadenan tres preguntas, y cada una se contesta con una fuente
distinta.

    1. ¿Hay cáncer confirmado?      histopatología  ->  no: continued_surveillance
    2. ¿Está indicado tratar?       grado y riesgo  ->  no: active_surveillance
    3. ¿El paciente se beneficia?   comorbilidad    ->  no: watchful_waiting
                                                        sí: active_treatment

Cada nodo ve **su** bloque de variables y ninguno tiene que aprender la clase
rara: ``watchful_waiting`` sale de una pregunta con 33 casos a favor y en
contra, no de 2 contra 70. Y como las tres respuestas son probabilidades, la
composición devuelve una distribución sobre las cuatro conductas, no una
etiqueta, que es lo que la junta necesita.

La composición es la regla de la cadena, sin más:

    P(continued_surveillance) = 1 − P(cáncer)
    P(active_surveillance)    = P(cáncer) · (1 − P(tratar))
    P(active_treatment)       = P(cáncer) · P(tratar) · P(apto)
    P(watchful_waiting)       = P(cáncer) · P(tratar) · (1 − P(apto))

Referencias
-----------
* Silla C.N., Freitas A.A., *A survey of hierarchical classification across
  different application domains*, Data Min Knowl Discov 2011 — clasificación
  jerárquica local por nodo padre.
* Mottet N. et al., EAU Guidelines on Prostate Cancer 2021 — el orden de las
  tres preguntas y el criterio de esperanza de vida del nodo 3.
* Kesselheim J.C. et al. y la práctica de *watchful waiting*: la tercera
  pregunta no es sobre el tumor.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone

from .dataset_task2 import CLASSES, CLASS_TO_INDEX

I_AS = CLASS_TO_INDEX["active_surveillance"]
I_CS = CLASS_TO_INDEX["continued_surveillance"]
I_AT = CLASS_TO_INDEX["active_treatment"]
I_WW = CLASS_TO_INDEX["watchful_waiting"]


def node_targets(y: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Etiquetas y máscaras de cada nodo, derivadas de la etiqueta de cuatro clases.

    Cada nodo se entrena sólo con los casos que en el árbol le llegarían: el
    nodo 2 no ve a quien no tiene cáncer, y el nodo 3 no ve a quien no se
    plantea tratar. Entrenar un nodo con casos que nunca lo alcanzan es
    enseñarle una frontera que en inferencia no usa.
    """
    cancer = (y != I_CS).astype(int)

    m_treat = y != I_CS
    treat = np.isin(y[m_treat], [I_AT, I_WW]).astype(int)

    m_fit = np.isin(y, [I_AT, I_WW])
    fit = (y[m_fit] == I_AT).astype(int)

    return {
        "cancer": (cancer, np.ones(len(y), dtype=bool)),
        "treat": (treat, m_treat),
        "fit": (fit, m_fit),
    }


class GuidelineCascade(BaseEstimator, ClassifierMixin):
    """Tres cabezas binarias compuestas por la regla de la cadena.

    ``heads`` es ``{nodo: estimador}``; ``columns`` es ``{nodo: índices}``, de
    modo que cada nodo puede leer un subconjunto distinto de la matriz. Si un
    nodo no recibe columnas, ve la matriz entera.
    """

    def __init__(self, heads: dict | None = None, columns: dict | None = None, floor: float = 1e-4):
        self.heads = heads
        self.columns = columns
        self.floor = floor

    def _cols(self, node: str, X):
        idx = (self.columns or {}).get(node)
        return X if idx is None else X[:, idx]

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        self.classes_ = np.arange(len(CLASSES))
        targets = node_targets(y)
        self.fitted_: dict[str, object] = {}
        self.priors_: dict[str, float] = {}
        for node, (t, mask) in targets.items():
            self.priors_[node] = float(t.mean()) if len(t) else 0.5
            if len(np.unique(t)) < 2:
                self.fitted_[node] = None      # nodo degenerado: se usa el prior
                continue
            est = clone(self.heads[node])
            est.fit(self._cols(node, X[mask]), t)
            self.fitted_[node] = est
        return self

    def _p_node(self, node: str, X) -> np.ndarray:
        est = self.fitted_.get(node)
        if est is None:
            return np.full(len(X), self.priors_[node])
        P = est.predict_proba(self._cols(node, X))
        j = int(np.flatnonzero(est.classes_ == 1)[0]) if 1 in est.classes_ else None
        return P[:, j] if j is not None else np.zeros(len(X))

    def predict_proba(self, X):
        X = np.asarray(X, dtype=float)
        p_cancer = self._p_node("cancer", X)
        p_treat = self._p_node("treat", X)
        p_fit = self._p_node("fit", X)

        P = np.zeros((len(X), len(CLASSES)))
        P[:, I_CS] = 1.0 - p_cancer
        P[:, I_AS] = p_cancer * (1.0 - p_treat)
        P[:, I_AT] = p_cancer * p_treat * p_fit
        P[:, I_WW] = p_cancer * p_treat * (1.0 - p_fit)
        # Suelo: una clase con probabilidad exactamente cero rompe cualquier
        # métrica logarítmica y le niega a la junta la posibilidad de discutirla.
        P = np.clip(P, self.floor, None)
        return P / P.sum(axis=1, keepdims=True)

    def predict(self, X):
        return np.argmax(self.predict_proba(X), axis=1)

    def node_probabilities(self, X) -> dict[str, np.ndarray]:
        """Las tres respuestas por separado. Es lo que se lleva a la junta:
        un veredicto compuesto sin sus tres pasos no se puede rebatir."""
        X = np.asarray(X, dtype=float)
        return {n: self._p_node(n, X) for n in ("cancer", "treat", "fit")}
