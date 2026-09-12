"""Experto 2 — proyección del PSA con intervalo de cobertura garantizada.

El problema: dada una serie de 3-5 medidas de PSA y el contexto clínico del
paciente, ¿dónde estará el PSA dentro de ``h`` meses, con qué incertidumbre, y
está subiendo o bajando?

Dos piezas separadas, porque resuelven cosas distintas:

**Punto** — un ensemble de regresores sobre ``log(PSA)``. Se trabaja en escala
logarítmica porque el PSA en enfermedad activa crece de forma aproximadamente
exponencial (Pound et al., *JAMA* 1999) y porque su distribución es fuertemente
asimétrica: en este corpus va de 0.2 a 190 ng/mL, de modo que un error
cuadrático en escala natural estaría dominado por media docena de pacientes.

**Intervalo** — predicción conforme *jackknife+* (Barber, Candès, Ramdas y
Tibshirani, *Predictive inference with the jackknife+*, Ann Statist 2021). A
diferencia del intervalo de Student de una regresión lineal, no supone que el
modelo sea correcto ni que los residuos sean normales: garantiza una cobertura
de al menos ``1 - 2·alpha`` en muestra finita bajo el único supuesto de
intercambiabilidad. Con 195 series y un modelo no lineal, esa garantía es lo
único que hace honesto el ``±`` que se le entrega al deliberador.

El conjunto de entrenamiento no necesita la etiqueta de biopsia: se construye
por *prefijos* de cada serie (predecir el punto ``k`` a partir de los ``k-1``
anteriores), de modo que los 195 casos —etiquetados o no— aportan ejemplos.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from . import features_labs, features_psa
from .io import Case

NAN = float("nan")


@dataclass
class PSAProjection:
    """Proyección del PSA a un horizonte, con su incertidumbre y su tendencia."""

    horizon_months: float
    psa_last: float
    psa_projected: float
    ci_lo: float
    ci_hi: float
    log_sigma: float
    direction: str          # "rising" | "falling" | "indeterminate"
    direction_confidence: str  # "clear" | "borderline" | "uncertain"
    doubling_time_months: float
    velocity_ng_ml_year: float
    n_points: int
    span_months: float
    fit_r2_log: float
    method: str

    def to_dict(self) -> dict:
        return asdict(self)


def prefix_features(points: list[tuple[float, float]], t_target: float, context: dict) -> dict[str, float]:
    """Características de una serie parcial para predecir un punto futuro.

    ``points`` son los ``(t, psa)`` observados; ``t_target`` el instante a
    predecir. Todo lo que describe la serie va en escala logarítmica salvo el
    número de puntos y los intervalos temporales.
    """
    t = [p[0] for p in points]
    v = [max(p[1], 1e-3) for p in points]
    ly = [math.log(x) for x in v]
    b, a, sigma, sxx, n = features_psa._ols(t, ly)
    gap = t_target - t[-1]

    f = {
        "n_points": float(n),
        "gap_months": float(gap),
        "span_months": float(t[-1] - t[0]),
        "log_last": ly[-1],
        "log_first": ly[0],
        "log_mean": float(np.mean(ly)),
        "log_sd": float(np.std(ly)) if n > 1 else 0.0,
        "log_min": float(min(ly)),
        "log_max": float(max(ly)),
        "slope_log_per_month": b if b == b else 0.0,
        "resid_sigma_log": sigma if sigma == sigma else 0.0,
        # Extrapolación log-lineal: la predicción del modelo clásico entra como
        # variable, de modo que el regresor sólo tiene que aprender su *sesgo*.
        # Es el encuadre de "boosting sobre un modelo mecanicista", y evita que
        # el aprendizaje tenga que redescubrir la exponencial desde cero.
        "loglinear_forecast": (a + b * t_target) if b == b else ly[-1],
        "last_step_log": ly[-1] - ly[-2] if n > 1 else 0.0,
        "last_step_months": t[-1] - t[-2] if n > 1 else NAN,
        "monotonic_up": float(all(v[i + 1] >= v[i] for i in range(n - 1))),
        "nadir_ratio_log": ly[-1] - min(ly),
    }
    f.update(
        {
            "age": context.get("age", NAN),
            "log_vol": context.get("log_vol", NAN),
            "pct_free_psa": context.get("pct_free_psa", NAN),
            "testosterone": context.get("testosterone", NAN),
            "on_5ari": context.get("on_5ari", 0.0),
            "on_alpha_blocker": context.get("on_alpha_blocker", 0.0),
            "pirads": context.get("pirads", NAN),
        }
    )
    return f


def case_context(case: Case) -> dict[str, float]:
    """Covariables del paciente que modulan la trayectoria del PSA.

    El volumen prostático y la edad fijan el nivel basal esperado; los
    inhibidores de la 5-alfa-reductasa lo reducen a la mitad (Thompson et al.,
    *NEJM* 2003) y por tanto rompen cualquier extrapolación que los ignore.
    """
    from .features_structured import extract as struct_extract

    s = struct_extract(case.prompt)
    labs = features_labs.extract(case.clinical)
    return {
        "age": s.get("age", NAN),
        "log_vol": s.get("log_vol", NAN),
        "pirads": s.get("pirads", NAN),
        "on_5ari": s.get("on_5ari", 0.0),
        "on_alpha_blocker": s.get("on_alpha_blocker", 0.0),
        "pct_free_psa": labs.get("lab_pct_free_psa", NAN),
        "testosterone": labs.get("lab_testosterone", NAN),
    }


def build_training_set(cases: list[Case], min_history: int = 2) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Ejemplos ``(X, y_log, grupo_caso, nombres)`` por prefijos de cada serie.

    Un caso con ``k`` medidas aporta ``k - min_history`` ejemplos. El vector de
    grupos es el ``case_id``, y **debe** usarse como agrupación en la validación
    cruzada: dos prefijos del mismo paciente comparten casi toda la información,
    de modo que separarlos entre train y test inflaría la métrica.
    """
    rows, ys, groups = [], [], []
    for c in cases:
        pts = features_psa.series(c.clinical)
        if len(pts) <= min_history:
            continue
        ctx = case_context(c)
        for k in range(min_history, len(pts)):
            hist = pts[:k]
            t_target, v_target = pts[k]
            rows.append(prefix_features(hist, t_target, ctx))
            ys.append(math.log(max(v_target, 1e-3)))
            groups.append(c.case_id)
    names = list(rows[0].keys())
    X = np.array([[r.get(n, NAN) for n in names] for r in rows], dtype=float)
    return X, np.array(ys, dtype=float), np.array(groups), names


def jackknife_plus_interval(
    residuals: np.ndarray, prediction: float, alpha: float = 0.05
) -> tuple[float, float]:
    """Intervalo conforme a partir de residuos leave-one-out.

    Implementa la variante simétrica del jackknife+ (Barber et al. 2021,
    ecuación 5): el intervalo es la predicción más/menos el cuantil
    ``1 - alpha`` de los residuos absolutos out-of-fold, ajustado por el factor
    de muestra finita ``ceil((n+1)(1-alpha))/n``. La cobertura resultante es de
    al menos ``1 - 2·alpha`` sin ningún supuesto distribucional.
    """
    r = np.abs(np.asarray(residuals, dtype=float))
    r = r[np.isfinite(r)]
    n = len(r)
    if n == 0:
        return NAN, NAN
    rank = min(int(math.ceil((n + 1) * (1 - alpha))), n)
    q = float(np.sort(r)[rank - 1])
    return prediction - q, prediction + q


class PSAProjectorExpert:
    """API de inferencia del Experto 2, cargada desde el ``.joblib`` entrenado."""

    def __init__(self, bundle: dict):
        self.model = bundle.get("model")
        self.fallback = bundle.get("fallback")
        self.feature_names = bundle["feature_names"]
        self.residuals = np.asarray(bundle["calibration_residuals_log"], dtype=float)
        self.champion = bundle.get("champion", "unknown")
        self.meta = {k: v for k, v in bundle.items() if k not in ("model", "calibration_residuals_log")}

    @classmethod
    def load(cls, path) -> "PSAProjectorExpert":
        import joblib

        return cls(joblib.load(path))

    def _vector(self, points, t_target, ctx) -> np.ndarray:
        f = prefix_features(points, t_target, ctx)
        return np.array([[f.get(n, NAN) for n in self.feature_names]], dtype=float)

    def project(self, case: Case, horizon_months: float = 6.0, alpha: float = 0.05) -> PSAProjection:
        """Proyecta el PSA de un caso a ``horizon_months`` del último punto.

        Ante una serie de menos de dos puntos no se inventa una tendencia: se
        devuelve el último valor con dirección ``indeterminate`` y el intervalo
        conforme global, que es lo más honesto que se puede decir sin historia.
        """
        pts = features_psa.series(case.clinical)
        traj = features_psa.fit_trajectory(case.clinical)
        if not pts:
            return PSAProjection(
                horizon_months, NAN, NAN, NAN, NAN, NAN, "indeterminate", "uncertain",
                NAN, NAN, 0, NAN, NAN, "no_data",
            )

        last = pts[-1][1]
        t_target = pts[-1][0] + horizon_months
        ctx = case_context(case)

        if len(pts) < 2 or self.model is None:
            log_pred = math.log(max(last, 1e-3))
            method = "last_value_carried_forward"
        else:
            log_pred = float(self.model.predict(self._vector(pts, t_target, ctx))[0])
            method = self.champion

        lo_log, hi_log = jackknife_plus_interval(self.residuals, log_pred, alpha)
        proj = math.exp(log_pred)
        lo, hi = math.exp(lo_log), math.exp(hi_log)

        # La dirección se declara sólo si la banda completa cae a un lado del
        # último valor. Con el intervalo conforme, que es ancho por
        # construcción, esto es deliberadamente conservador: el experto
        # prefiere decir "no lo sé" a firmar una tendencia que no sostiene.
        if lo > last:
            direction, conf = "rising", "clear"
        elif hi < last:
            direction, conf = "falling", "clear"
        else:
            direction = "rising" if proj > last else ("falling" if proj < last else "indeterminate")
            # Si el punto se mueve más de un 25 % pero la banda cruza, la
            # tendencia es sugerente pero no concluyente.
            conf = "borderline" if abs(math.log(max(proj, 1e-9) / max(last, 1e-9))) > 0.22 else "uncertain"
            if conf == "uncertain":
                direction = "indeterminate"

        return PSAProjection(
            horizon_months=float(horizon_months),
            psa_last=float(last),
            psa_projected=float(proj),
            ci_lo=float(lo),
            ci_hi=float(hi),
            log_sigma=float((hi_log - lo_log) / (2 * 1.96)),
            direction=direction,
            direction_confidence=conf,
            doubling_time_months=float(traj["psa_doubling_time_months"]),
            velocity_ng_ml_year=float(traj["psa_velocity"]),
            n_points=int(len(pts)),
            span_months=float(traj["psa_span_months"]),
            fit_r2_log=float(traj["psa_r2_log"]),
            method=method,
        )

    def features_for_fusion(self, case: Case, horizon_months: float = 6.0) -> dict[str, float]:
        """Salida del Experto 2 en forma de variables para el Experto 3.

        Es el bloque G de la ablación: permite medir si la proyección aprendida
        aporta algo por encima de las variables de trayectoria del bloque C,
        que son las mismas cifras sin pasar por el regresor.
        """
        p = self.project(case, horizon_months)
        last = p.psa_last
        proj = p.psa_projected
        rel = (math.log(max(proj, 1e-9)) - math.log(max(last, 1e-9))) if (proj == proj and last == last) else NAN
        return {
            "e2_log_projected_psa": math.log(max(proj, 1e-9)) if proj == proj else NAN,
            "e2_log_change_vs_last": rel,
            "e2_projected_over_last": (proj / last) if (proj == proj and last and last > 0) else NAN,
            "e2_interval_width_log": (math.log(max(p.ci_hi, 1e-9)) - math.log(max(p.ci_lo, 1e-9)))
            if p.ci_hi == p.ci_hi
            else NAN,
            "e2_direction_rising": 1.0 if p.direction == "rising" else (0.0 if p.direction == "falling" else NAN),
            "e2_direction_is_clear": float(p.direction_confidence == "clear"),
            "e2_fit_r2_log": p.fit_r2_log,
        }


class AnchoredRegressor:
    """Regresor que aprende el *cambio* respecto a un ancla, no el nivel.

    Un ensemble de árboles no puede extrapolar fuera del rango de su
    entrenamiento: promedia hojas, de modo que un paciente con PSA 187 ng/mL
    —muy por encima de la masa de la cohorte— recibe una predicción arrastrada
    hacia el centro. En una serie de PSA eso es un fallo grave y silencioso: el
    modelo proyecta un descenso justo en los pacientes cuyo PSA se dispara.

    La corrección estándar es reparametrizar el objetivo como incremento sobre
    un ancla conocida (aquí ``log(PSA)`` de la última medida) y devolver
    ``ancla + incremento``. La regresión a la media pasa entonces a tirar del
    *cambio* hacia cero —"sin cambio", que es el prior conservador correcto— en
    lugar de tirar del *nivel* hacia la media de la cohorte.

    Es la misma idea que subyace al modelado de residuos sobre un modelo
    mecanicista y a la práctica de predecir diferencias en series temporales no
    estacionarias (Box y Jenkins, *Time Series Analysis*, 1970, cap. 4).
    """

    def __init__(self, estimator, anchor_index: int):
        self.estimator = estimator
        self.anchor_index = anchor_index

    def get_params(self, deep: bool = True) -> dict:
        return {"estimator": self.estimator, "anchor_index": self.anchor_index}

    def set_params(self, **params):
        for k, v in params.items():
            setattr(self, k, v)
        return self

    def fit(self, X, y):
        from sklearn.base import clone as _clone

        X = np.asarray(X, dtype=float)
        anchor = X[:, self.anchor_index]
        self.estimator_ = _clone(self.estimator).fit(X, np.asarray(y, dtype=float) - anchor)
        return self

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        return X[:, self.anchor_index] + self.estimator_.predict(X)
