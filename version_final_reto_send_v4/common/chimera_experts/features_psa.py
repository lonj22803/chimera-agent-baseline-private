"""Bloque C — trayectoria de PSA a partir de ``psa_trend``.

La serie de PSA es la única variable longitudinal del caso. Se modela de dos
formas complementarias:

* **Escala lineal** — velocidad de PSA (PSAV, ng/mL/año), la definición de
  Carter et al., *JAMA* 1992.
* **Escala logarítmica** — el PSA crece de forma aproximadamente exponencial en
  enfermedad activa, de modo que ``log(PSA)`` es lineal en el tiempo y su
  pendiente da el *PSA doubling time* (PSADT = ln 2 / pendiente), la
  formulación de Pound et al., *JAMA* 1999, y el estándar operativo de
  Memorial Sloan Kettering.

De la regresión sobre ``log(PSA)`` sale también el intervalo de predicción
clásico de Student, que es la incertidumbre M ± ΔM de la proyección: no un
número inventado sino el error típico de predicción de un ajuste por mínimos
cuadrados con ``n - 2`` grados de libertad.
"""

from __future__ import annotations

import math
import re

NAN = float("nan")

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}


def parse_date_months(text: str) -> float:
    """Convierte ``'Feb 2022'`` o ``'22 Dec 2024'`` a meses absolutos desde el año 0.

    Devuelve NaN si no se reconoce. El origen es arbitrario: sólo se usan
    diferencias entre fechas.
    """
    if not text:
        return NAN
    s = str(text).lower()
    mon = None
    for name, idx in _MONTHS.items():
        if name in s:
            mon = idx
            break
    ym = re.search(r"(19|20)\d{2}", s)
    if mon is None or ym is None:
        return NAN
    year = int(ym.group())
    day = 15.0
    dm = re.match(r"\s*(\d{1,2})\s+[a-z]", s)
    if dm:
        day = float(dm.group(1))
    return year * 12.0 + (mon - 1) + (day - 1) / 30.44


def series(clinical: dict) -> list[tuple[float, float]]:
    """Serie ``(t_meses, psa)`` ordenada y saneada.

    Se descartan puntos sin fecha reconocible o con PSA no positivo (el log no
    está definido y un PSA de 0 ng/mL no es una medida real).
    """
    pts = []
    for p in (clinical or {}).get("psa_trend") or []:
        t = parse_date_months(p.get("date"))
        v = p.get("val")
        if t == t and isinstance(v, (int, float)) and v > 0:
            pts.append((float(t), float(v)))
    pts.sort()
    return pts


def _ols(x: list[float], y: list[float]) -> tuple[float, float, float, float, int]:
    """OLS simple. Devuelve (pendiente, intercepto, sigma_residual, Sxx, n)."""
    n = len(x)
    if n < 2:
        return NAN, (y[0] if y else NAN), NAN, NAN, n
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        return NAN, my, NAN, 0.0, n
    b = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / sxx
    a = my - b * mx
    if n > 2:
        rss = sum((yi - (a + b * xi)) ** 2 for xi, yi in zip(x, y))
        sigma = math.sqrt(rss / (n - 2))
    else:
        sigma = 0.0
    return b, a, sigma, sxx, n


#: Cuantil 0.975 de la t de Student por grados de libertad, para el intervalo
#: de predicción al 95 %. Evita depender de scipy en el punto de inferencia.
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}


def t_quantile_975(df: int) -> float:
    if df <= 0:
        return NAN
    return _T975.get(df, 1.96 + 2.4 / max(df, 1))


def fit_trajectory(clinical: dict) -> dict[str, float]:
    """Ajusta la trayectoria de PSA y devuelve sus parámetros descriptivos."""
    pts = series(clinical)
    out: dict[str, float] = {
        "psa_n_points": float(len(pts)),
        "psa_span_months": NAN,
        "psa_last": NAN,
        "psa_first": NAN,
        "psa_min": NAN,
        "psa_max": NAN,
        "psa_last_delta": NAN,
        "psa_velocity": NAN,
        "psa_slope_log": NAN,
        "psa_doubling_time_months": NAN,
        "psa_log_resid_sigma": NAN,
        "psa_r2_log": NAN,
        "psa_monotonic_up": NAN,
        "psa_nadir_ratio": NAN,
    }
    if not pts:
        return out

    t = [p[0] for p in pts]
    v = [p[1] for p in pts]
    out["psa_last"] = v[-1]
    out["psa_first"] = v[0]
    out["psa_min"] = min(v)
    out["psa_max"] = max(v)
    out["psa_span_months"] = t[-1] - t[0]
    out["psa_nadir_ratio"] = v[-1] / min(v) if min(v) > 0 else NAN
    if len(v) > 1:
        out["psa_last_delta"] = v[-1] - v[-2]
        out["psa_monotonic_up"] = float(all(v[i + 1] >= v[i] for i in range(len(v) - 1)))

    if len(pts) >= 2:
        b_lin, _, _, _, _ = _ols(t, v)
        out["psa_velocity"] = b_lin * 12.0 if b_lin == b_lin else NAN  # ng/mL/año

        ly = [math.log(x) for x in v]
        b, a, sigma, sxx, n = _ols(t, ly)
        out["psa_slope_log"] = b
        out["psa_log_resid_sigma"] = sigma
        if b == b and b > 1e-9:
            out["psa_doubling_time_months"] = math.log(2.0) / b
        elif b == b and b < -1e-9:
            # PSA en descenso: se codifica como tiempo de duplicación negativo,
            # que es la convención de MSKCC (un PSADT negativo = PSA cayendo).
            out["psa_doubling_time_months"] = math.log(2.0) / b
        if n > 2 and sigma == sigma:
            my = sum(ly) / n
            tss = sum((yi - my) ** 2 for yi in ly)
            rss = sigma**2 * (n - 2)
            out["psa_r2_log"] = 1.0 - rss / tss if tss > 0 else NAN
    return out


def project(clinical: dict, horizon_months: float = 6.0) -> dict[str, float]:
    """Proyecta el PSA a ``horizon_months`` del último punto observado.

    Devuelve la media geométrica proyectada y su intervalo de predicción al
    95 % en escala natural, obtenido del intervalo de Student en escala log.
    ``direction`` es +1 si la banda completa está por encima del último valor,
    -1 si está por debajo y 0 si la cruza (tendencia no resoluble).
    """
    pts = series(clinical)
    out = {
        "proj_psa": NAN,
        "proj_psa_lo": NAN,
        "proj_psa_hi": NAN,
        "proj_rel_halfwidth": NAN,
        "proj_direction": NAN,
        "proj_horizon_months": float(horizon_months),
    }
    if len(pts) < 2:
        if len(pts) == 1:
            out["proj_psa"] = pts[0][1]
            out["proj_direction"] = 0.0
        return out

    t = [p[0] for p in pts]
    ly = [math.log(p[1]) for p in pts]
    b, a, sigma, sxx, n = _ols(t, ly)
    if b != b:
        return out

    t_star = t[-1] + horizon_months
    mu = a + b * t_star
    df = n - 2
    if df >= 1 and sigma == sigma and sxx and sxx > 0:
        mt = sum(t) / n
        se_pred = sigma * math.sqrt(1.0 + 1.0 / n + (t_star - mt) ** 2 / sxx)
        half = t_quantile_975(df) * se_pred
    else:
        # Con n = 2 no hay grados de libertad para estimar la dispersión: se usa
        # una sigma por defecto conservadora (0.35 en log ~ ±40 %) para no
        # emitir un intervalo de anchura cero, que sería una mentira estadística.
        half = 1.96 * 0.35 * math.sqrt(1.0 + 1.0 / n)

    out["proj_psa"] = math.exp(mu)
    out["proj_psa_lo"] = math.exp(mu - half)
    out["proj_psa_hi"] = math.exp(mu + half)
    out["proj_rel_halfwidth"] = math.expm1(half)
    last = pts[-1][1]
    out["proj_direction"] = 1.0 if out["proj_psa_lo"] > last else (-1.0 if out["proj_psa_hi"] < last else 0.0)
    return out


def extract(clinical: dict, horizon_months: float = 6.0) -> dict[str, float]:
    """Bloque C completo: parámetros de trayectoria + proyección."""
    f = fit_trajectory(clinical)
    f.update(project(clinical, horizon_months))
    return f
