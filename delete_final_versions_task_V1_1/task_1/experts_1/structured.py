"""Intervención 3 — Experto 1, el clasificador sobre el panel estructurado.

Extra-Trees sobre el bloque A (``structured-prompt.json``), envuelto en
bagging × imputación múltiple, con la escalera de fiabilidad medida
out-of-fold. Es el experto barato: no lee texto libre y sigue funcionando
cuando falta todo lo demás. Aquí dice lo que un colega diría —qué sugiere, con
cuánta incertidumbre, con qué acierto en ese tramo, y qué NO ha mirado— y los
números íntegros van en ``data``.
"""

from __future__ import annotations

from typing import Any

from delete_final_versions_task_V1_1.common import vocab as V

_TIER_WORD = {"firm": "HIGH", "supports": "MODERATE", "discuss": "LOW"}
_READABLE = {
    "bx_positive": "prior positive biopsy", "bx_none": "no prior biopsy", "bx_negative": "prior negative biopsy",
    "pirads_ge4": "PI-RADS >= 4", "pirads_ge3": "PI-RADS >= 3", "pirads": "PI-RADS", "log_psa": "PSA",
    "psa": "PSA", "psad": "PSA density", "psad_calc": "PSA density", "log_psad": "PSA density",
    "age": "age", "dre_suspicious": "suspicious DRE", "vol": "prostate volume", "log_vol": "prostate volume",
    "n_comorbidities": "number of comorbidities", "cspca": "csPCa probability", "bmi": "BMI",
}


def _track(ladder: dict, tier: str) -> tuple[str, dict]:
    row = (ladder or {}).get(tier) or {}
    n, acc = row.get("n"), row.get("acc")
    if acc is None or not n:
        return "its out-of-fold track record in this tier is not established", row
    return f"out-of-fold it was right {acc:.0%} of the time over the {n} labelled cases in this tier", row


def render(panel: Any, case_id: str, mode: str, payload: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    if panel is None or not panel.has(case_id):
        return ("No trained classifier scored this case, so there is no opening bid to react to.",
                {"available": False})
    v = panel.verdicts(case_id, mode)["structured"]
    meta = panel.experts["structured"]
    ladder = panel.ladder("structured", mode)
    track, row = _track(ladder, v["tier"])
    word = _TIER_WORD.get(v["tier"], "LOW")
    verdict = "BIOPSY" if v["decision"] == "yes" else "NO BIOPSY"
    top = ", ".join(_READABLE.get(f, f) for f, _ in (meta.get("top_features") or [])[:6])
    m = meta.get("metrics") or {}
    weights = dict(meta.get("form_weights") or {})
    block = V.variable_block(
        weights, V.case_values(payload or {}), v["confidence"],
        f"'{v['tier']}' tier; {track}",
        share=meta.get("variable_importance_share"), features=meta.get("variable_features"),
        scope="panel only; the levels are what moved my prediction across the series, not what a urologist would mark")
    body = f"""Expert 1 here — the classifier that reads the structured panel and nothing else. My bid:

SUGGESTION: {verdict}   p(biopsy) = {v["p"]:.2f}
  uncertainty  +/- {v["sigma"]:.2f} epistemic (95% band {v["ci95"][0]:.2f}-{v["ci95"][1]:.2f}); \
among patients I cannot tell apart the outcome was {v["entropy"]:.2f} of 1.00 mixed
  reliability  {word} ('{v["tier"]}' tier) — {track}

{block}

I read {meta.get("n_features")} raw variables, all from the panel — nothing from the mpMRI prose, the PSA
trajectory, the previous notes or the laboratory. Out-of-fold over 91 labelled cases: AUC
{m.get("cv_auc", float("nan")):.3f}, balanced accuracy {m.get("cv_balanced_accuracy", float("nan")):.3f}.
The final call is the chair's."""
    data = {**v, "available": True, "mode": mode, "tier_track": row, "variable_weights": weights,
            "variable_importance_share": meta.get("variable_importance_share"),
            "gist": f"Expert 1 suggests {verdict}, p={v['p']:.2f} +/- {v['sigma']:.2f}, {word} reliability ({v['tier']}); "
                    f"weighs {', '.join(k for k, l in weights.items() if l in ('decisive', 'important')) or 'nothing above noted'}"}
    return body, data
