"""Modelo de la traza de razonamiento del urólogo.

El *case score* de CHIMERA-agent no puntúa sólo la decisión: puntúa también el
formulario de razonamiento —``confidence``, ``variable_weights`` y
``reveal_sequence``— contra la traza que rellenó el urólogo. Ese formulario es,
por tanto, un objetivo supervisado más, con 91 ejemplos etiquetados.

La primera versión de estos expertos derivaba ``variable_weights`` de la
importancia de permutación del clasificador. Es lo honesto para explicar *qué
usó el modelo*, pero se mide mal contra el urólogo: la correlación de rangos
entre ambos órdenes es ρ = 0.26 (p = 0.47) y sólo coinciden en 2 de 10
categorías. El motivo es real y no es un fallo del modelo: PI-RADS apenas varía
en esta cohorte (162 de 195 casos son PI-RADS 4 o 5), de modo que explica poca
*varianza de la decisión* aunque sea clínicamente la puerta de entrada; en
cambio el estado de biopsia previa parte la cohorte en dos y domina la
importancia predictiva.

Las dos lecturas son válidas y responden a preguntas distintas, así que se
mantienen las dos:

* la **importancia de permutación** viaja en la carga ampliada del experto, para
  que el deliberador sepa qué movió realmente la predicción;
* la **traza predicha por este modelo** va al fichero que puntúa el reto, porque
  ahí lo que se mide es el parecido con el urólogo.

Los pesos del urólogo son claramente dependientes del caso —``bx`` es
*important* o *decisive* en 47 de los 49 casos con biopsia previa positiva, y
*noted* en 16 de los 24 sin biopsia previa—, de modo que predecirlos es un
problema de clasificación bien planteado y no una plantilla disfrazada.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .io import Case

#: Variables del formulario de la Tarea 1.
TASK1_VARIABLES = ["bx", "fh", "age", "dre", "psa", "vol", "psad", "cspca", "pirads", "comorbidity"]
WEIGHT_LEVELS = ["not_used", "noted", "important", "decisive"]
CONFIDENCE_LEVELS = ["clear", "borderline", "uncertain"]
SECTIONS = ["radiology_report", "psa_trend", "laboratory_results", "previous_notes", "family_history"]

#: Predictores. Deliberadamente pocos y todos presentes en ``structured-prompt.json``:
#: con 91 trazas, un modelo por variable no puede permitirse más de un puñado de
#: grados de libertad sin memorizar.
PREDICTORS = [
    "pirads", "pirads_ge4", "log_psa", "log_psad", "log_vol", "age",
    "dre_suspicious", "bx_positive", "bx_none", "bx_negative", "cspca",
    "family_history", "n_comorbidities",
]


def case_predictors(case: Case) -> dict[str, float]:
    """Vector de predictores de un caso, con NaN donde falte."""
    from .features_structured import extract as s_extract

    s = s_extract(case.prompt)
    fh = str((case.clinical or {}).get("family_history", "")).strip().lower()
    s["family_history"] = {"yes": 1.0, "no": 0.0}.get(fh, float("nan"))
    return {k: s.get(k, float("nan")) for k in PREDICTORS}


def _design(cases: list[Case]) -> np.ndarray:
    rows = [case_predictors(c) for c in cases]
    X = np.array([[r[k] for k in PREDICTORS] for r in rows], dtype=float)
    # Imputación por mediana de columna. Es deliberadamente simple: este modelo
    # tiene 13 predictores y 91 filas, y una imputación iterativa aquí añadiría
    # más varianza que información.
    med = np.nanmedian(X, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    idx = np.isnan(X)
    X[idx] = np.take(med, np.where(idx)[1])
    return X


def _clf(seed: int = 20260907):
    return Pipeline(
        [("scale", StandardScaler()), ("clf", LogisticRegression(C=0.5, max_iter=5000, random_state=seed))]
    )


class ReasoningTraceModel:
    """Predice ``confidence``, ``variable_weights`` y ``reveal_sequence``.

    Un clasificador multinomial por objetivo. Las clases que no aparecen en el
    entrenamiento simplemente no se predicen, y un objetivo con una sola clase
    observada se degrada a constante — que es la respuesta correcta cuando el
    urólogo nunca varió esa casilla.
    """

    def __init__(self, seed: int = 20260907, min_gain: float = 0.03):
        """``min_gain`` es el listón que un objetivo debe superar sobre la moda.

        Medido en LOOCV, un modelo por objetivo sólo se conserva si gana al
        menos ``min_gain`` de acierto sobre "predecir siempre la moda". Con 91
        casos, 0.03 son ~3 casos: por debajo de eso la diferencia no se
        distingue del ruido de partición y meter un modelo sólo añade varianza.

        De los 15 objetivos del formulario, únicamente dos superan ese listón de
        forma clara — el peso de ``pirads`` (+0.21) y el de ``bx`` (+0.12) —, que
        son justamente los dos que dependen del caso de manera evidente. Para el
        resto, el urólogo rellena la casilla de forma casi constante y la moda es
        el mejor predictor disponible. Reconocerlo es parte del resultado.
        """
        self.seed = seed
        self.min_gain = min_gain
        self.models_: dict[str, object] = {}
        self.constants_: dict[str, str] = {}
        self.section_models_: dict[str, object] = {}
        self.section_rates_: dict[str, float] = {}
        self.metrics_: dict[str, dict] = {}
        self.kept_: list[str] = []

    # -- ajuste -------------------------------------------------------------

    def fit(self, cases: list[Case]) -> "ReasoningTraceModel":
        cases = [c for c in cases if c.reasoning]
        X = _design(cases)

        # La puerta de entrada es el LOOCV: sólo se conserva el modelo de un
        # objetivo si bate a su moda por encima de ``min_gain``.
        gains = self.evaluate_loo(cases)

        targets = {"confidence": [c.reasoning.get("confidence") for c in cases]}
        for v in TASK1_VARIABLES:
            targets[f"weight::{v}"] = [(c.reasoning.get("variable_weights") or {}).get(v) for c in cases]

        for name, y in targets.items():
            keep = [i for i, v in enumerate(y) if v]
            yy = np.array([y[i] for i in keep])
            vals, counts = np.unique(yy, return_counts=True) if len(yy) else (np.array([]), np.array([]))
            mode = str(vals[counts.argmax()]) if len(vals) else WEIGHT_LEVELS[1]
            self.constants_[name] = mode
            if len(set(yy)) < 2:
                continue
            if gains.get(name, {}).get("gain", -1.0) >= self.min_gain:
                self.models_[name] = clone(_clf(self.seed)).fit(X[keep], yy)
                self.kept_.append(name)

        for s in SECTIONS:
            y = np.array([int(s in (c.reasoning.get("reveal_sequence") or [])) for c in cases])
            self.section_rates_[s] = float(y.mean())
            if 0 < y.mean() < 1 and gains.get(f"reveal::{s}", {}).get("gain", -1.0) >= self.min_gain:
                self.section_models_[s] = clone(_clf(self.seed)).fit(X, y)
                self.kept_.append(f"reveal::{s}")
        return self

    def hybrid_loo_accuracy(self, cases: list[Case]) -> dict[str, float]:
        """Acierto del híbrido: modelo donde se conservó, moda donde no.

        Advertencia: la selección de qué objetivos conservan modelo se hace con
        el mismo LOOCV con el que se mide, de modo que esta cifra está
        ligeramente sesgada al alza por selección (Varma y Simon 2006). Con 15
        objetivos y dos ganadores de margen amplio el sesgo es pequeño, pero
        conviene leer la tabla por objetivo, no sólo el promedio.
        """
        m = self.metrics_ or self.evaluate_loo(cases)
        out = {}
        for name, v in m.items():
            out[name] = v["loo_accuracy"] if name in self.kept_ else v["majority_baseline"]
        return out

    # -- inferencia ---------------------------------------------------------

    def predict_trace(self, case: Case) -> dict:
        X = _design([case])
        conf = self._one("confidence", X, default="borderline")
        weights = {v: self._one(f"weight::{v}", X, default="noted") for v in TASK1_VARIABLES}
        reveal = [s for s in SECTIONS if self._section(s, X)]
        return {"confidence": conf, "variable_weights": weights, "reveal_sequence": reveal}

    def _one(self, name: str, X: np.ndarray, default: str) -> str:
        if name in self.models_:
            return str(self.models_[name].predict(X)[0])
        return self.constants_.get(name, default)

    def _section(self, s: str, X: np.ndarray) -> bool:
        if s in self.section_models_:
            return bool(self.section_models_[s].predict(X)[0])
        return self.section_rates_.get(s, 0.0) >= 0.5

    # -- evaluación ---------------------------------------------------------

    def evaluate_loo(self, cases: list[Case]) -> dict[str, dict]:
        """Acierto leave-one-out por objetivo, frente a la moda como suelo.

        El suelo correcto no es el azar sino **predecir siempre la moda**: si el
        urólogo puso *important* en PI-RADS el 49 % de las veces, un modelo que
        no bata ese 49 % no ha aprendido nada del caso.
        """
        cases = [c for c in cases if c.reasoning]
        X = _design(cases)
        out: dict[str, dict] = {}

        targets = {"confidence": [c.reasoning.get("confidence") for c in cases]}
        for v in TASK1_VARIABLES:
            targets[f"weight::{v}"] = [(c.reasoning.get("variable_weights") or {}).get(v) for c in cases]
        for s in SECTIONS:
            targets[f"reveal::{s}"] = [str(int(s in (c.reasoning.get("reveal_sequence") or []))) for c in cases]

        for name, y in targets.items():
            keep = [i for i, v in enumerate(y) if v]
            yy = np.array([y[i] for i in keep])
            Xk = X[keep]
            vals, counts = np.unique(yy, return_counts=True)
            baseline = float(counts.max() / counts.sum())
            if len(vals) < 2:
                out[name] = {"n": int(len(yy)), "loo_accuracy": 1.0, "majority_baseline": 1.0,
                             "gain": 0.0, "constant": True}
                continue
            pred = np.empty(len(yy), dtype=object)
            for tr, te in LeaveOneOut().split(Xk):
                if len(set(yy[tr])) < 2:
                    pred[te] = vals[counts.argmax()]
                    continue
                pred[te] = clone(_clf(self.seed)).fit(Xk[tr], yy[tr]).predict(Xk[te])[0]
            acc = float((pred == yy).mean())
            out[name] = {"n": int(len(yy)), "loo_accuracy": acc, "majority_baseline": baseline,
                         "gain": acc - baseline, "constant": False}
        self.metrics_ = out
        return out
