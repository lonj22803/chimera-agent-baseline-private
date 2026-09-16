"""Orden y horizonte se ajustan separados para no sacrificar concordancia.

Breslow permite empates sin dependencias de supervivencia. La calibración
isotónica minimiza la pérdida truncada y asimétrica del reto, no cuadrados:
un censurado sólo impone un límite inferior al horizonte.
"""
from __future__ import annotations

from collections.abc import Callable
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp


def _outcomes(t, e):
    t, e = np.asarray(t, float), np.asarray(e, float)
    if t.ndim != 1 or t.size == 0 or e.shape != t.shape:
        raise ValueError('tiempos y eventos deben ser vectores alineados no vacíos')
    if not np.all(np.isfinite(t)) or np.any(t < 0) or not np.all(np.isin(e, [0, 1])):
        raise ValueError('tiempos finitos no negativos y eventos binarios requeridos')
    return t, e


class CoxPH:
    """Cox regularizado: la penalización limita el ajuste con pocos eventos.

    La pérdida parcial se divide por el número de eventos para que alpha no
    cambie de significado al cambiar el tamaño del fold. El L1 se representa
    con partes positivas y negativas, evitando suavizar su esquina en cero.
    """
    def __init__(self, alpha: float = 1.0, l1_ratio: float = 0.0):
        if not np.isfinite(alpha) or alpha < 0 or not 0 <= l1_ratio <= 1:
            raise ValueError('alpha >= 0 y l1_ratio en [0, 1]')
        self.alpha, self.l1_ratio = alpha, l1_ratio

    def fit(self, X, t, e):
        t, e = _outcomes(t, e)
        X = np.asarray(X, float)
        if X.ndim != 2 or len(X) != len(t) or not np.all(np.isfinite(X)) or X.shape[1] == 0:
            raise ValueError('X debe ser una matriz finita alineada')
        if not e.sum():
            raise ValueError('Cox necesita al menos un evento')
        times = np.unique(t[e == 1])
        groups = [(X[(t == u) & (e == 1)].sum(axis=0), int(((t == u) & (e == 1)).sum()), X[t >= u]) for u in times]
        p = X.shape[1]
        l1, l2 = self.alpha*self.l1_ratio, self.alpha*(1-self.l1_ratio)
        def objective(z):
            beta = z[:p] - z[p:] if l1 else z
            loss, grad = 0.0, np.zeros(p)
            for observed, d, at_risk in groups:
                eta = at_risk @ beta
                denom = logsumexp(eta)
                loss += d*denom - observed @ beta
                grad += d*(np.exp(eta-denom) @ at_risk) - observed
            loss = loss/e.sum() + 0.5*l2*(beta @ beta)
            grad = grad/e.sum() + l2*beta
            if l1:
                return loss + l1*z.sum(), np.r_[grad+l1, -grad+l1]
            return loss, grad
        result = minimize(objective, np.zeros(2*p if l1 else p), jac=True,
                          method='L-BFGS-B', bounds=[(0, None)]*(2*p) if l1 else None,
                          options={'maxiter': 2000, 'ftol': 1e-12, 'gtol': 1e-8})
        if not result.success:
            raise RuntimeError(f'Cox no convergió: {result.message}')
        self.beta = result.x[:p]-result.x[p:] if l1 else result.x
        eta = X @ self.beta
        increments = [np.exp(np.log(((t == u) & (e == 1)).sum()) - logsumexp(eta[t >= u])) for u in times]
        self._baseline = times, np.exp(-np.cumsum(increments))
        return self

    def risk(self, X) -> np.ndarray:
        """Mayor exp(X beta) significa recurrencia más temprana."""
        return np.exp(np.asarray(X, float) @ self.beta)

    def baseline_survival(self) -> tuple:
        """Escalones de Breslow en los tiempos de evento, para riesgo unidad."""
        return tuple(a.copy() for a in self._baseline)


def c_index(t, risk, e) -> float | None:
    """Semántica literal oficial: `risk` son meses, menor es más riesgo.

    Para evaluar Cox se pasa -modelo.risk(X). Sin pares comparables devuelve
    None, exactamente como el evaluador, aunque el nombre sugiera lo contrario.
    """
    num = den = 0.0
    for i in range(len(t)):
        if e[i] != 1:
            continue
        for j in range(len(t)):
            if i == j or not t[i] < t[j]:
                continue
            den += 1.0
            if risk[i] < risk[j]:
                num += 1.0
            elif risk[i] == risk[j]:
                num += 0.5
    return num / den if den else None


def monotone_calibrate(risk_train, t_train, e_train) -> Callable[[np.ndarray], np.ndarray]:
    """Isotónica exacta para la pérdida del reto mediante programación dinámica.

    La pérdida truncada no es convexa: PAVA con medias o medianas no basta.
    Sus quiebres (0, t y t+max(t,1)) contienen un óptimo isotónico débil.
    Una perturbación relativa de 1e-9 rompe las mesetas sin invertir el orden;
    el óptimo estrictamente monótono puede tener sólo un supremo. Interpolamos
    en arctan(riesgo), también fuera del entrenamiento, sin colas constantes.
    Riesgos iguales conservan meses iguales. La igualdad de c-index se compara
    entre -riesgo y meses, porque el evaluador recibe horizontes.
    """
    t, e = _outcomes(t_train, e_train)
    r = np.asarray(risk_train, float)
    if r.shape != t.shape or not np.all(np.isfinite(r)):
        raise ValueError('riesgos finitos alineados requeridos')
    knots, inverse = np.unique(r, return_inverse=True)
    levels = np.unique(np.r_[0, t, t+np.maximum(t, 1)])
    costs = np.zeros((len(knots), len(levels)))
    for i in range(len(t)):
        error = np.abs(levels-t[i]) if e[i] else np.maximum(t[i]-levels, 0)
        costs[inverse[i]] += np.minimum(error/max(t[i], 1), 1)
    dp = costs[0].copy()
    parents = []
    for cost in costs[1:]:
        best = np.empty(len(levels), int)
        k = len(levels)-1
        for j in range(len(levels)-1, -1, -1):
            if dp[j] <= dp[k]:
                k = j
            best[j] = k
        parents.append(best)
        dp = cost + dp[best]
    indices = [int(np.argmin(dp))]
    for parent in reversed(parents):
        indices.append(int(parent[indices[-1]]))
    values = levels[indices[::-1]]
    x = np.arctan(knots)
    epsilon = max(float(t.max()), 1)*1e-9
    y = values + epsilon*(np.pi/2-x)
    xp = np.r_[-np.pi/2, x, np.pi/2]
    yp = np.r_[y[0]+epsilon*(x[0]+np.pi/2), y, y[-1]-epsilon*(np.pi/2-x[-1])]
    def predict(risk):
        a = np.asarray(risk, float)
        if not np.all(np.isfinite(a)):
            raise ValueError('riesgos finitos requeridos')
        return np.interp(np.arctan(a), xp, yp)
    return predict


def bootstrap_ci(fn, *args, n: int = 1000, seed: int = 0) -> tuple[float, float]:
    """Remuestreo pareado: los casos sin pares comparables no inventan un score."""
    arrays = [np.asarray(a) for a in args]
    if not arrays or not len(arrays[0]) or n < 1 or any(len(a) != len(arrays[0]) for a in arrays):
        raise ValueError('arrays alineados no vacíos y n positivo requeridos')
    rng = np.random.default_rng(seed)
    scores = []
    for _ in range(n):
        idx = rng.integers(len(arrays[0]), size=len(arrays[0]))
        score = fn(*(a[idx] for a in arrays))
        if score is not None and np.isfinite(score):
            scores.append(score)
    return tuple(np.quantile(scores, [0.025, 0.975])) if scores else (float('nan'), float('nan'))
