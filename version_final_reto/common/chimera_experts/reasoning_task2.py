"""Experto de la traza de razonamiento de la tarea 2.

El ``case_score`` no premia sólo acertar la conducta. Una vez pasada la puerta
de la decisión, el 82.5 % restante sale de cuatro componentes que se miden
contra la traza que rellenó el urólogo. Este módulo los predice, y lo hace
mirando lo que las 72 trazas de esta tarea realmente contienen —que no es lo
mismo que contenían las de la tarea 1:

* **``reveal_sequence`` está vacío en los 72 casos.** No es un descuido: en la
  tarea 2 el clínico recibe el expediente completo, no lo va destapando. El
  ``tool_score`` premia la *precisión* de las herramientas declaradas, de modo
  que declarar cualquier sección cuando el patrón no declaró ninguna la puntúa
  a cero. La predicción correcta de este campo es la lista vacía, y no hay nada
  que aprender.
* **``confidence`` sólo toma dos valores**, ``clear`` (58) y ``borderline``
  (14). ``uncertain`` no aparece nunca, así que emitirlo sólo puede restar: la
  distancia a ``clear`` es 2 sobre 2 y anula el componente.
* **``variable_weights`` tiene once claves, y tres de ellas están
  condicionadas.** ``bx_isup``, ``bx_gl_prim`` y ``bx_gl_sec`` aparecen en 52
  de las 72 trazas, y aparecen exactamente cuando la biopsia dio grado. Emitir
  una clave que el urólogo no escribió no penaliza el
  ``variable_weight_score`` —ese recorre las claves del patrón— pero sí el
  ``important_decisive_factor_score``, que es un F1 de conjuntos y cuenta como
  falso positivo toda variable marcada *important* o *decisive* de más.

De ahí la forma del modelo: una **puerta** que decide si las tres claves de
biopsia se emiten, un clasificador por casilla para el peso, y un clasificador
binario para la confianza. Cada uno con su suelo declarado —la moda— y una
puerta LOOCV que lo adopta sólo si lo bate.

Referencias
-----------
* Guo C. et al., *On Calibration of Modern Neural Networks*, ICML 2017 — por
  qué una confianza sin calibrar es peor que una constante bien elegida.
* Varma S., Simon R., *Bias in error estimation when using cross-validation for
  model selection*, BMC Bioinformatics 2006 — por qué la puerta se decide con
  LOOCV y no con el ajuste.

Nota sobre el criterio de la puerta
-----------------------------------
La puerta **no** compara aciertos exactos. El evaluador puntúa cada casilla por
la distancia ordinal ``1 − |W(patrón) − W(predicho)| / 3``, de modo que fallar
un *decisive* por *important* cuesta un tercio de lo que cuesta fallarlo por
*not_used*. Un modelo puede acertar más casillas exactas y aun así puntuar
peor, si sus errores son más lejanos. La puerta usa por tanto la métrica del
reto, y la constante contra la que compite no es la moda sino la que minimiza
esa distancia —que en esta cohorte coincide con la moda en las once casillas,
pero eso es un hecho medido, no una suposición.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .io import Case

#: Las once casillas del formulario de la tarea 2, en el orden del ground truth.
TASK2_VARIABLES = [
    "pirads", "ct", "fh", "comorbidity", "psa", "age", "psad", "cspca",
    "bx_isup", "bx_gl_prim", "bx_gl_sec",
]

#: Las tres que sólo se escriben cuando la biopsia dio grado.
GATED_VARIABLES = ["bx_isup", "bx_gl_prim", "bx_gl_sec"]

WEIGHT_LEVELS = ["not_used", "noted", "important", "decisive"]
WEIGHT_VALUE = {w: i for i, w in enumerate(WEIGHT_LEVELS)}

#: ``uncertain`` existe en el vocabulario del reto pero no en esta cohorte.
CONFIDENCE_LEVELS = ["clear", "borderline"]

#: ``reveal_sequence`` correcto de la tarea 2. Constante, y por un motivo
#: medible: el patrón no declara ninguna sección en ninguno de los 72 casos.
EMPTY_REVEAL: list[str] = []

#: Predictores. Pocos, y todos presentes en ``structured-prompt.json``: con 72
#: trazas, un modelo por casilla no aguanta más grados de libertad.
PREDICTORS = [
    "bx_isup", "bx_isup_ge2", "gleason_prim", "gleason_sum", "ct_stage",
    "pirads", "log_psa", "log_psad", "age", "cspca", "eau_high", "eau_low",
    "as_eligible_strict", "family_history", "n_comorbidities", "frl_ipss",
]


def case_predictors(case: Case) -> dict[str, float]:
    from . import features_frailty, features_grading, features_structured

    a = features_structured.extract(case.prompt)
    g = features_grading.extract(case.prompt)
    f = features_frailty.extract(case.prompt, case.clinical)
    fh_raw = str((case.clinical or {}).get("family_history", "")).strip().lower()
    merged = {**a, **g, **f, "family_history": {"yes": 1.0, "no": 0.0}.get(fh_raw, float("nan"))}
    return {k: merged.get(k, float("nan")) for k in PREDICTORS}


def _matrix(cases: list[Case]) -> np.ndarray:
    return np.array([[case_predictors(c)[k] for k in PREDICTORS] for c in cases], dtype=float)


def _pipeline(seed: int = 0):
    from sklearn.impute import SimpleImputer

    return Pipeline([
        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(penalty="l2", C=0.5, max_iter=5000, random_state=seed)),
    ])


def gate_target(case: Case) -> int:
    """¿Debe la traza incluir las claves de biopsia? Regla observada: sí cuando
    la biopsia dio grado. Acierta 66 de 72; los 6 restantes son casos con grado
    en los que el urólogo no rellenó esas casillas, y no hay variable que los
    distinga."""
    try:
        return int(float(case.prompt.get("bx_isup", 0)) > 0)
    except (TypeError, ValueError):
        return 0


class ReasoningTraceModel:
    """Un clasificador por casilla, más uno para la confianza, más la puerta.

    ``fit`` compara cada casilla contra su moda con LOOCV y **sólo adopta el
    modelo aprendido si la bate**. Con 72 trazas, la mayoría de las casillas no
    la baten: ``fh`` es *noted* en 51 de 72 y no hay señal que mejore eso. Dejar
    la moda donde el modelo no aporta es lo que impide que el formulario empeore
    por añadir parámetros.
    """

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.weight_models: dict[str, object] = {}
        self.weight_mode: dict[str, str] = {}
        self.weight_learned: dict[str, bool] = {}
        self.weight_loo: dict[str, tuple[float, float]] = {}
        self.confidence_model = None
        self.confidence_mode = "clear"
        self.confidence_learned = False
        self.confidence_loo: tuple[float, float] = (0.0, 0.0)

    # -- ajuste -----------------------------------------------------------
    def fit(self, cases: list[Case]) -> "ReasoningTraceModel":
        cases = [c for c in cases if c.reasoning]
        X = _matrix(cases)

        for var in TASK2_VARIABLES:
            labels, rows = [], []
            for i, c in enumerate(cases):
                w = (c.reasoning.get("variable_weights") or {}).get(var)
                if w in WEIGHT_VALUE:
                    labels.append(w)
                    rows.append(i)
            if len(labels) < 10:
                continue
            y = np.array(labels)
            Xi = X[rows]
            const = self._best_constant(y)
            self.weight_mode[var] = const
            base = self._cell_score(y, np.full(len(y), const, dtype=object))
            learned = (
                self._cell_score(y, self._loo_predictions(Xi, y)) if len(np.unique(y)) > 1 else 0.0
            )
            self.weight_loo[var] = (round(learned, 4), round(base, 4))
            if learned > base and len(np.unique(y)) > 1:
                self.weight_models[var] = _pipeline(self.seed).fit(Xi, y)
                self.weight_learned[var] = True
            else:
                self.weight_learned[var] = False

        conf = [c.reasoning.get("confidence") for c in cases]
        keep = [i for i, v in enumerate(conf) if v in CONFIDENCE_LEVELS]
        if len(keep) >= 10:
            y = np.array([conf[i] for i in keep])
            Xi = X[keep]
            self.confidence_mode = max(set(y.tolist()), key=list(y).count)
            # La confianza se puntúa igual, por distancia: |CONF(g) − CONF(p)| / 2.
            conf_val = {"clear": 0, "borderline": 1, "uncertain": 2}
            cs = lambda t, p: float(1.0 - np.abs(  # noqa: E731
                np.array([conf_val[v] for v in t], dtype=float)
                - np.array([conf_val[v] for v in p], dtype=float)).mean() / 2.0)
            base = cs(y, np.full(len(y), self.confidence_mode, dtype=object))
            learned = cs(y, self._loo_predictions(Xi, y)) if len(np.unique(y)) > 1 else 0.0
            self.confidence_loo = (round(learned, 4), round(base, 4))
            if learned > base and len(np.unique(y)) > 1:
                self.confidence_model = _pipeline(self.seed).fit(Xi, y)
                self.confidence_learned = True
        return self

    @staticmethod
    def _cell_score(truth: np.ndarray, pred: np.ndarray) -> float:
        """La métrica del reto para una casilla: distancia ordinal normalizada."""
        t = np.array([WEIGHT_VALUE[v] for v in truth], dtype=float)
        p = np.array([WEIGHT_VALUE[v] for v in pred], dtype=float)
        return float(1.0 - np.abs(t - p).mean() / 3.0)

    @staticmethod
    def _best_constant(y: np.ndarray) -> str:
        """Nivel constante que minimiza la distancia ordinal media."""
        t = np.array([WEIGHT_VALUE[v] for v in y], dtype=float)
        return WEIGHT_LEVELS[int(np.argmin([np.abs(t - c).mean() for c in range(len(WEIGHT_LEVELS))]))]

    def _loo_predictions(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        out = np.empty(len(y), dtype=object)
        for tr, te in LeaveOneOut().split(X):
            if len(np.unique(y[tr])) < 2:
                out[te[0]] = y[tr][0]
                continue
            est = clone(_pipeline(self.seed)).fit(X[tr], y[tr])
            out[te[0]] = est.predict(X[te])[0]
        return out

    # -- inferencia -------------------------------------------------------
    def predict_trace(self, case: Case) -> dict:
        x = np.array([[case_predictors(case)[k] for k in PREDICTORS]], dtype=float)
        gated = gate_target(case) == 1

        weights: dict[str, str] = {}
        for var in TASK2_VARIABLES:
            if var in GATED_VARIABLES and not gated:
                continue
            if var not in self.weight_mode:
                continue
            if self.weight_learned.get(var) and var in self.weight_models:
                weights[var] = str(self.weight_models[var].predict(x)[0])
            else:
                weights[var] = self.weight_mode[var]

        if self.confidence_learned and self.confidence_model is not None:
            confidence = str(self.confidence_model.predict(x)[0])
        else:
            confidence = self.confidence_mode

        return {
            "confidence": confidence,
            "variable_weights": weights,
            "reveal_sequence": list(EMPTY_REVEAL),
        }

    # -- informe ----------------------------------------------------------
    def report(self) -> list[dict]:
        rows = [{"campo": v, "loo": self.weight_loo.get(v, (None, None))[0],
                 "moda": self.weight_loo.get(v, (None, None))[1],
                 "moda_valor": self.weight_mode.get(v),
                 "aprendido": self.weight_learned.get(v)}
                for v in TASK2_VARIABLES if v in self.weight_mode]
        rows.append({"campo": "confidence", "loo": self.confidence_loo[0], "moda": self.confidence_loo[1],
                     "moda_valor": self.confidence_mode, "aprendido": self.confidence_learned})
        return rows
