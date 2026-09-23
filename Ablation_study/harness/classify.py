"""Regla mecanica de veredicto pre-registrada."""

from __future__ import annotations

from typing import Mapping

DELTA_RANK = 0.010
DELTA_GATE = 1 / 91
DELTA_F = 0.010


def _single(
    delta: float,
    interval: tuple[float, float],
    *,
    level: str,
    margin: float,
    p_value: float | None,
    exact_zero: bool,
    same_sign: bool,
) -> str:
    if exact_zero and delta == 0:
        return "SOBRA"
    low, high = interval
    significant = level != "D" or (p_value is not None and p_value < 0.05)
    if low > 0 and delta >= margin and significant:
        return f"NECESARIA_FRAGIL_{level}" if not same_sign else f"NECESARIA_{level}"
    if -margin < low and high < margin:
        return f"SOBRA_{level}"
    if high < 0 and delta <= -margin:
        return f"PERJUDICIAL_{level}"
    return f"INDETERMINADA_{level}"


def classify(
    deltas: float | Mapping[str, float],
    ci: tuple[float, float] | Mapping[str, tuple[float, float]],
    *,
    level: str = "D",
    p_value: float | None = None,
    exact_zero: bool = False,
    same_sign: bool = True,
    margin: float | None = None,
) -> str:
    """Clasifica D, F o N sin juicio manual."""
    level = level.upper()
    if level not in {"D", "F", "N"}:
        raise ValueError(f"Nivel desconocido: {level}.")
    default_margin = {"D": DELTA_RANK, "F": DELTA_F, "N": 0.030}[level]
    selected_margin = default_margin if margin is None else margin

    if isinstance(deltas, Mapping):
        if not isinstance(ci, Mapping) or set(deltas) != set(ci):
            raise ValueError("Los componentes de deltas e IC deben coincidir.")
        verdicts = [
            _single(
                float(delta),
                ci[name],
                level=level,
                margin=selected_margin,
                p_value=p_value,
                exact_zero=exact_zero,
                same_sign=same_sign,
            )
            for name, delta in deltas.items()
        ]
        if any(verdict.startswith("NECESARIA") for verdict in verdicts):
            return f"NECESARIA_FRAGIL_{level}" if not same_sign else f"NECESARIA_{level}"
        if all(verdict in {"SOBRA", f"SOBRA_{level}"} for verdict in verdicts):
            return "SOBRA" if exact_zero and all(delta == 0 for delta in deltas.values()) else f"SOBRA_{level}"
        if any(verdict == f"PERJUDICIAL_{level}" for verdict in verdicts):
            return f"PERJUDICIAL_{level}"
        return f"INDETERMINADA_{level}"

    if isinstance(ci, Mapping):
        raise ValueError("Un delta escalar necesita un IC escalar.")
    return _single(
        float(deltas),
        ci,
        level=level,
        margin=selected_margin,
        p_value=p_value,
        exact_zero=exact_zero,
        same_sign=same_sign,
    )


def global_verdict(levels: Mapping[str, str], *, measured: tuple[str, ...]) -> str:
    """Aplica la prioridad global D, F, N, perjuicio, sobra, indeterminacion."""
    for level in ("D", "F", "N"):
        verdict = levels.get(level, "")
        if verdict.startswith("NECESARIA"):
            return verdict
    harmful = [verdict for verdict in levels.values() if verdict.startswith("PERJUDICIAL")]
    if harmful:
        return "PERJUDICIAL"
    if all(
        levels.get(level) in {"SOBRA", f"SOBRA_{level}"}
        for level in measured
    ):
        return "SOBRA" if set(measured) == {"D", "F", "N"} else "SOBRA_DF (N sin medir)"
    return "INDETERMINADA"
