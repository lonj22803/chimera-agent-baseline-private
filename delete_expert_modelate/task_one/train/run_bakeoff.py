#!/usr/bin/env python3
"""Comparación de clasificadores para la Tarea 1 (decisión de biopsia).

Protocolo, idéntico para todos los candidatos:

* **Etapa 1** — los 19 candidatos sobre dos conjuntos de variables (bloque A
  solo, y A-E completo), con validación cruzada estratificada 5x10.
* **Etapa 2** — los finalistas repiten con 5x20 repeticiones, más leave-one-out
  y bootstrap de 2000 réplicas para los intervalos de confianza; se comparan
  por bootstrap pareado contra el mejor y contra la regla de guía EAU.

Salidas en ``artifacts/``:

``bakeoff_stage1.csv``      métricas de los 19 candidatos x 2 conjuntos
``bakeoff_stage2.csv``      finalistas con IC bootstrap y LOOCV
``bakeoff_pairwise.csv``    comparaciones pareadas contra el mejor y contra EAU
``bakeoff_oof.npz``         probabilidades out-of-fold, para reutilizarlas

Uso::

    python run_bakeoff.py --data ../../../data_filtered/task1
"""

from __future__ import annotations

import argparse
import os
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
# Los procesos hijo de joblib no heredan el filtro; sin esto el log se llena.
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from chimera_experts.dataset import build_labels, build_matrix, missingness_report  # noqa: E402
from chimera_experts.evaluation import SEED, bootstrap_ci, evaluate, metrics, paired_bootstrap  # noqa: E402
from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.models import build_catalog  # noqa: E402

ART = Path(__file__).resolve().parent / "artifacts"

#: Conjuntos de variables comparados en la etapa 1.
BLOCK_SETS = {
    "A_structured": "A",
    "ABCDE_all_text": "ABCDE",
}

N_FINALISTS = 6


def _catalog_for(names: list[str]):
    """Catálogo con las columnas de la regla clínica resueltas por nombre."""
    pirads_col = names.index("pirads") if "pirads" in names else 0
    psad_col = names.index("psad_calc") if "psad_calc" in names else (names.index("psad") if "psad" in names else 1)
    return build_catalog(seed=SEED, pirads_col=pirads_col, psad_col=psad_col)


def stage1(cases, repeats: int) -> tuple[pd.DataFrame, dict]:
    rows, oof = [], {}
    y = build_labels(cases)
    for set_name, blocks in BLOCK_SETS.items():
        X, names = build_matrix(cases, blocks)
        print(f"\n=== {set_name}: X{X.shape}, NaN {np.isnan(X).mean():.3f} ===", flush=True)
        for model_name, est in _catalog_for(names).items():
            res = evaluate(est, X, y, model_name, n_repeats=repeats, with_loo=False)
            oof[f"{set_name}|{model_name}"] = res["oof_mean"]
            rows.append(
                {
                    "feature_set": set_name,
                    "n_features": X.shape[1],
                    "model": model_name,
                    **{k: v for k, v in res.items() if k.startswith("cv_")},
                    "oof_std_across_repeats": res["oof_std_across_repeats"],
                }
            )
            print(
                f"  {model_name:26s} AUC={res['cv_auc']:.3f} (sd {res['cv_auc_sd_across_repeats']:.3f})"
                f"  bal_acc={res['cv_balanced_accuracy']:.3f}  Brier={res['cv_brier']:.3f}  ECE={res['cv_ece']:.3f}",
                flush=True,
            )
    return pd.DataFrame(rows), oof


def stage2(cases, df1: pd.DataFrame, repeats: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    y = build_labels(cases)
    # Finalistas: mejores por AUC, más las reglas clínicas y la logística como
    # referencias obligadas aunque no entren en el top.
    best = df1.sort_values("cv_auc", ascending=False).head(N_FINALISTS)
    forced = df1[df1["model"].isin(["rule_eau_psad", "rule_pirads3", "logreg_l2", "prior_only"])]
    sel = pd.concat([best, forced]).drop_duplicates(subset=["feature_set", "model"])

    rows, oof, probs = [], {}, {}
    for _, r in sel.iterrows():
        blocks = BLOCK_SETS[r["feature_set"]]
        X, names = build_matrix(cases, blocks)
        est = _catalog_for(names)[r["model"]]
        key = f"{r['feature_set']}|{r['model']}"
        res = evaluate(est, X, y, r["model"], n_repeats=repeats, with_loo=True)
        oof[key] = res["oof_mean"]
        probs[key] = res["loo_probabilities"]
        auc, lo, hi = bootstrap_ci(y, res["oof_mean"], "auc")
        ba, blo, bhi = bootstrap_ci(y, res["oof_mean"], "balanced_accuracy")
        rows.append(
            {
                "feature_set": r["feature_set"],
                "model": r["model"],
                "n_features": int(r["n_features"]),
                "cv_auc": res["cv_auc"],
                "cv_auc_ci_lo": lo,
                "cv_auc_ci_hi": hi,
                "cv_auc_sd_across_repeats": res["cv_auc_sd_across_repeats"],
                "cv_balanced_accuracy": ba,
                "cv_bal_acc_ci_lo": blo,
                "cv_bal_acc_ci_hi": bhi,
                "cv_sensitivity": res["cv_sensitivity"],
                "cv_specificity": res["cv_specificity"],
                "cv_brier": res["cv_brier"],
                "cv_ece": res["cv_ece"],
                "loo_auc": res["loo_auc"],
                "loo_balanced_accuracy": res["loo_balanced_accuracy"],
                "loo_brier": res["loo_brier"],
                "loo_ece": res["loo_ece"],
            }
        )
        print(f"  [stage2] {key:44s} AUC={res['cv_auc']:.3f} [{lo:.3f},{hi:.3f}]  LOO={res['loo_auc']:.3f}", flush=True)

    df2 = pd.DataFrame(rows).sort_values("cv_auc", ascending=False).reset_index(drop=True)

    # Comparaciones pareadas contra el mejor y contra la regla EAU.
    champ = f"{df2.iloc[0]['feature_set']}|{df2.iloc[0]['model']}"
    eau = next((k for k in oof if k.endswith("rule_eau_psad")), None)
    comp = []
    for key, p in oof.items():
        for ref_name, ref_key in (("champion", champ), ("rule_eau_psad", eau)):
            if ref_key is None or key == ref_key:
                continue
            d = paired_bootstrap(y, p, oof[ref_key], "auc")
            comp.append({"model": key, "reference": f"{ref_name}={ref_key}", **d})
    return df2, pd.DataFrame(comp), {"oof": oof, "loo": probs, "champion": champ}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data_filtered" / "task1"))
    ap.add_argument("--repeats-stage1", type=int, default=10)
    ap.add_argument("--repeats-stage2", type=int, default=20)
    args = ap.parse_args()

    ART.mkdir(parents=True, exist_ok=True)
    cases = [c for c in load_cases(args.data, task=1) if c.has_label]
    y = build_labels(cases)
    print(f"Casos etiquetados: {len(cases)}  (yes={int(y.sum())}, no={int((1 - y).sum())})")

    X, names = build_matrix(cases, "ABCDE")
    pd.DataFrame(missingness_report(X, names)).to_csv(ART / "missingness_ABCDE.csv", index=False)

    df1, _ = stage1(cases, args.repeats_stage1)
    df1.sort_values(["feature_set", "cv_auc"], ascending=[True, False]).to_csv(ART / "bakeoff_stage1.csv", index=False)

    df2, comp, store = stage2(cases, df1, args.repeats_stage2)
    df2.to_csv(ART / "bakeoff_stage2.csv", index=False)
    comp.to_csv(ART / "bakeoff_pairwise.csv", index=False)
    np.savez(
        ART / "bakeoff_oof.npz",
        y=y,
        case_ids=np.array([c.case_id for c in cases]),
        **{f"oof__{k}": v for k, v in store["oof"].items()},
        **{f"loo__{k}": v for k, v in store["loo"].items()},
    )
    (ART / "bakeoff_summary.json").write_text(
        json.dumps(
            {
                "n_cases": len(cases),
                "n_positive": int(y.sum()),
                "champion": store["champion"],
                "seed": SEED,
                "repeats_stage1": args.repeats_stage1,
                "repeats_stage2": args.repeats_stage2,
            },
            indent=2,
        )
    )
    print("\n=== ETAPA 2 ===")
    print(df2.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\nCampeón: {store['champion']}")


if __name__ == "__main__":
    main()
