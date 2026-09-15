"""Intervención 12 — Experto 3, el clasificador de fusión multi-fuente.

Extra-Trees sobre los bloques A + B + D: el panel, la analítica y el informe
radiológico procesado con reglas (NegEx). Es el mejor clasificador del panel
(AUC 0.794 out-of-fold) y el único que lee el texto de la RM. Dos reglas de la
junta que lo distinguen de cómo se usó en ``run_experts.py``:

1. **Sólo habla sobre lo que el registrador abrió.** Si el informe radiológico
   no está sobre la mesa, se abstiene: no puede citar un documento que nadie
   abrió. Si la analítica no está, habla con la variante entrenada con ese
   bloque en blanco, y su incertidumbre por datos ausentes lo refleja.
2. **Habla después de los documentos, no antes**, para que el acta muestre en
   qué evidencia se apoya.
"""

from __future__ import annotations

from typing import Any

from version_final_reto.common import vocab as V

_TIER_WORD = {"firm": "HIGH", "supports": "MODERATE", "discuss": "LOW"}
_READABLE = {
    "bx_positive": "prior positive biopsy", "bx_none": "no prior biopsy", "fpsa_lt15": "free PSA < 15%",
    "fpsa_lt10": "free PSA < 10%", "rad_dwi_restriction": "DWI restriction in the report",
    "rad_lesion_ge15mm": "lesion >= 15 mm in the report", "dre_suspicious": "suspicious DRE",
    "rad_dwi_severity": "DWI severity wording", "log_vol": "prostate volume", "pirads_ge4": "PI-RADS >= 4",
    "lab_pct_free_psa": "% free PSA", "rad_epe": "extraprostatic extension wording",
}


def render(panel: Any, case_id: str, mode: str, opened: list[str],
           payload: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    if "radiology_report" not in opened:
        return ("The mpMRI report was not opened in this session. I was trained on its prose and I will "
                "not score a document nobody put on the table, so I abstain.",
                {"available": False, "reason": "radiology_report not opened",
                 "gist": "abstains: radiology_report not opened"})
    if panel is None or not panel.has(case_id):
        return ("No fusion classifier is deployed for this case.", {"available": False})
    with_labs = "laboratory_results" in opened
    key = "fusion_full" if with_labs else "fusion_nolab"
    v = panel.verdicts(case_id, mode)[key]
    meta = panel.experts["fusion"]
    ladder = panel.ladder(key, mode)
    row = (ladder or {}).get(v["tier"]) or {}
    track = (f"out-of-fold it was right {row['acc']:.0%} of the time over the {row['n']} labelled cases in this tier"
             if row.get("acc") is not None else "its out-of-fold track record in this tier is not established")
    word = _TIER_WORD.get(v["tier"], "LOW")
    verdict = "BIOPSY" if v["decision"] == "yes" else "NO BIOPSY"
    top = ", ".join(_READABLE.get(f, f) for f, _ in (meta.get("top_features") or [])[:6])
    read = "the panel, the mpMRI report" + (" and the laboratory panel" if with_labs else
                                            " — the laboratory panel was not opened, so that block is imputed and my band is wider for it")
    m = meta.get("metrics") or {}
    weights = dict(meta.get("form_weights") or {})
    if not with_labs:
        # sin la analítica sobre la mesa, el DRE y lo que viene del laboratorio
        # no se pueden declarar como leídos: se imputaron.
        weights["dre"] = "not_used"
    block = V.variable_block(
        weights, V.case_values(payload or {}), v["confidence"],
        f"'{v['tier']}' tier; {track}",
        share=meta.get("variable_importance_share"), features=meta.get("variable_features"),
        scope="panel + the documents that were opened; PI-RADS here means the report's own wording — DWI restriction, lesion size — not the score")
    body = f"""Expert 3 here — the fusion classifier. I read {read}; nothing from the previous notes or the PSA series.

SUGGESTION: {verdict}   p(biopsy) = {v["p"]:.2f}
  uncertainty  +/- {v["sigma"]:.2f} epistemic (95% band {v["ci95"][0]:.2f}-{v["ci95"][1]:.2f}), \
of which {v["sigma_missing"]:.2f} comes from values that had to be imputed
  reliability  {word} ('{v["tier"]}' tier) — {track}

{block}

Out-of-fold AUC {m.get("cv_auc", float("nan")):.3f}. I am the only expert that has read the report's
wording, and I still cannot see the prior grade or the surveillance history: those are in the notes, and
the registrar has to carry them."""
    data = {**v, "available": True, "mode": mode, "variant": key, "tier_track": row, "variable_weights": weights,
            "variable_importance_share": meta.get("variable_importance_share"),
            "gist": f"Expert 3 suggests {verdict}, p={v['p']:.2f} +/- {v['sigma']:.2f}, {word} reliability ({v['tier']}, {key}); "
                    f"weighs {', '.join(k for k, l in weights.items() if l in ('decisive', 'important')) or 'nothing above noted'}"}
    return body, data
