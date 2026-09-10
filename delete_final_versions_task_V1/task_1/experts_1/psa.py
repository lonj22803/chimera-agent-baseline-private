"""Intervención 11 — Experto 2, la proyección del PSA.

Regresor Extra-Trees anclado sobre la serie de PSA, con intervalo conforme
(jackknife+). No vota sobre la biopsia: responde a otra pregunta —hacia dónde
va el PSA y con qué certeza— y la ablación del Experto 3 midió que como
variable del clasificador no añade nada (AUC 0.794 frente a 0.792). Aquí es
una **salida independiente para el deliberador**, y sólo habla si el
registrador abrió la serie de PSA: sin ella sobre la mesa no hay serie que
proyectar.
"""

from __future__ import annotations

from typing import Any

from delete_final_versions_task_V1.common import vocab as V


def render(panel: Any, case_id: str, opened: list[str], payload: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    if "psa_trend" not in opened:
        return ("The serial PSA was not opened in this session, so I have no trajectory to project. "
                "I say nothing rather than project a headline value.",
                {"available": False, "reason": "psa_trend not opened", "gist": "abstains: psa_trend not opened"})
    if panel is None or not panel.has(case_id):
        return ("No PSA projector is deployed for this case.", {"available": False})
    p = panel.projection(case_id)
    if not p or p.get("n_points", 0) == 0 or p.get("psa_last") is None:
        return ("The serial PSA on file has no usable points, so there is nothing to project.",
                {"available": False, "reason": "no points", "gist": "abstains: no PSA series"})
    d = p.get("direction") or "indeterminate"
    conf = p.get("direction_confidence") or "uncertain"
    dt = p.get("doubling_time_months")
    dt_line = (f"doubling time about {dt:.0f} months" if isinstance(dt, (int, float)) and dt and dt > 0 and dt < 600
               else "no meaningful doubling time")
    vel = p.get("velocity_ng_ml_year")
    vel_line = f"{vel:+.2f} ng/mL per year" if isinstance(vel, (int, float)) else "velocity not estimable"
    # Sólo lee la serie de PSA: es la única variable que puede declarar, y el
    # nivel sigue a la firmeza de la dirección que la banda conforme sostiene.
    weights = {v: "not_used" for v in V.VARIABLES_BY_TASK[1]}
    weights["psa"] = {"clear": "important", "borderline": "noted", "uncertain": "noted"}.get(conf, "noted")
    block = V.variable_block(weights, V.case_values(payload or {}), conf,
                             f"the conformal band {'clears' if conf == 'clear' else 'does not clear'} the last value",
                             scope="the serial PSA only")
    body = f"""Expert 2 here — the PSA projector. I read only the serial PSA the registrar opened.

TRAJECTORY: {d.upper()} ({conf}). Last value {p["psa_last"]:.2f} ng/mL over {p["n_points"]} points spanning \
{p.get("span_months") or 0:.0f} months; velocity {vel_line}; {dt_line}.
PROJECTION at 6 months: {p["psa_projected"]:.1f} ng/mL, conformal 95% band {p["ci_lo"]:.1f}-{p["ci_hi"]:.1f}.

Read the band before the point: it is wide by construction, and I only call a direction when the whole
band clears the last value. This does not vote on the biopsy — a rising PSA in a man with a known
diagnosis is the disease behaving as known — it tells the chair how fast the number is moving.

{block}"""
    data = {**p, "available": True, "variable_weights": weights, "confidence": conf,
            "gist": f"PSA {d} ({conf}), 6-month projection {p['psa_projected']:.1f} [{p['ci_lo']:.1f}-{p['ci_hi']:.1f}]"}
    return body, data
