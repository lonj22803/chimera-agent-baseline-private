#!/usr/bin/env python3
"""Ablación por bloques de variables y sonda sobre el vector neuronal de RM.

Responde a dos preguntas de diseño que no se pueden contestar por criterio:

1. **¿Qué aporta cada fichero de entrada?** Se evalúa el modelo campeón sobre
   todos los subconjuntos de bloques que tienen sentido clínico, en orden de
   coste de obtención: primero lo estructurado, luego el texto libre. Se
   reporta también la ablación *leave-one-block-out*, que es la que detecta
   redundancia: si quitar un bloque no baja la métrica, ese bloque no aporta
   nada que los otros no tengan ya.

2. **¿Hace falta un experto sobre ``prostate-modality-level-neural-representations.json``?**
   Se entrena una sonda lineal (regresión logística con PCA previa, el
   protocolo habitual de *linear probing* de Alain y Bengio, ICLR 2017) sobre
   el vector de 1024 dimensiones y se compara con el escalar ``cspca`` que ya
   viene resuelto en ``structured-prompt.json``. Si la sonda no bate al escalar,
   construir un experto de imagen sería gastar 91 casos en reaprender algo que
   el organizador ya entregó calibrado.

Salidas: ``ablation_blocks.csv``, ``ablation_leave_one_out.csv``,
``embedding_probe.csv``.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
# Los procesos hijo de joblib no heredan el filtro; sin esto el log se llena.
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from sklearn.decomposition import PCA  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from chimera_experts.dataset import BLOCKS, build_labels, build_matrix  # noqa: E402
from chimera_experts.evaluation import SEED, bootstrap_ci, evaluate, paired_bootstrap  # noqa: E402
from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.models import build_catalog  # noqa: E402

ART = Path(__file__).resolve().parent / "artifacts"

#: Subconjuntos evaluados. "A" es el mínimo (sólo el prompt estructurado);
#: "ABCDE" es todo el texto disponible sin tocar las representaciones neuronales.
BLOCK_COMBOS = ["A", "AB", "AC", "AD", "AE", "ABC", "ABD", "ACD", "ABCD", "ABCE", "ABDE", "ACDE", "BCDE", "ABCDE"]


def _model(name: str, names: list[str]):
    pirads_col = names.index("pirads") if "pirads" in names else 0
    psad_col = names.index("psad_calc") if "psad_calc" in names else (names.index("psad") if "psad" in names else 1)
    return build_catalog(seed=SEED, pirads_col=pirads_col, psad_col=psad_col)[name]


def ablate(cases, model_name: str, repeats: int) -> pd.DataFrame:
    y = build_labels(cases)
    rows = []
    for combo in BLOCK_COMBOS:
        X, names = build_matrix(cases, combo)
        res = evaluate(_model(model_name, names), X, y, model_name, n_repeats=repeats, with_loo=False)
        auc, lo, hi = bootstrap_ci(y, res["oof_mean"], "auc", n_boot=1000)
        rows.append(
            {
                "blocks": combo,
                "block_names": "+".join(BLOCKS[b][0] for b in combo),
                "n_features": X.shape[1],
                "nan_rate": float(np.isnan(X).mean()),
                "cv_auc": res["cv_auc"],
                "ci_lo": lo,
                "ci_hi": hi,
                "cv_balanced_accuracy": res["cv_balanced_accuracy"],
                "cv_brier": res["cv_brier"],
                "cv_ece": res["cv_ece"],
            }
        )
        print(f"  {combo:6s} ({X.shape[1]:3d} vars) AUC={res['cv_auc']:.3f} [{lo:.3f},{hi:.3f}]", flush=True)
    return pd.DataFrame(rows).sort_values("cv_auc", ascending=False)


def leave_one_block_out(cases, model_name: str, repeats: int, full: str = "ABCDE") -> pd.DataFrame:
    """Cuánto se pierde al quitar cada bloque del conjunto completo."""
    y = build_labels(cases)
    Xf, nf = build_matrix(cases, full)
    ref = evaluate(_model(model_name, nf), Xf, y, model_name, n_repeats=repeats, with_loo=False)
    rows = [{"removed": "(none)", "removed_name": "conjunto completo", "n_features": Xf.shape[1],
             "cv_auc": ref["cv_auc"], "delta_auc": 0.0, "ci_lo": np.nan, "ci_hi": np.nan, "p_value": np.nan}]
    for b in full:
        rest = full.replace(b, "")
        X, names = build_matrix(cases, rest)
        res = evaluate(_model(model_name, names), X, y, model_name, n_repeats=repeats, with_loo=False)
        d = paired_bootstrap(y, res["oof_mean"], ref["oof_mean"], "auc", n_boot=1000)
        rows.append(
            {
                "removed": b,
                "removed_name": BLOCKS[b][0],
                "n_features": X.shape[1],
                "cv_auc": res["cv_auc"],
                "delta_auc": d["delta"],
                "ci_lo": d["ci_lo"],
                "ci_hi": d["ci_hi"],
                "p_value": d["p_value"],
            }
        )
        print(f"  sin {BLOCKS[b][0]:14s} AUC={res['cv_auc']:.3f}  delta={d['delta']:+.3f} p={d['p_value']:.3f}", flush=True)
    return pd.DataFrame(rows)


def embedding_probe(cases, repeats: int) -> pd.DataFrame:
    """Sonda lineal sobre el vector de RM frente al escalar ``cspca``."""
    y = build_labels(cases)
    Xe, _ = build_matrix(cases, "F", drop_constant=False)
    has = ~np.isnan(Xe).all(axis=1)
    print(f"  casos con vector de RM: {int(has.sum())}/{len(y)}")

    Xa, na = build_matrix(cases, "A")
    cspca = Xa[:, na.index("cspca")].reshape(-1, 1)

    rows = []
    for k in (4, 8, 16, 32, 64):
        pipe = Pipeline(
            [
                ("impute", SimpleImputer(strategy="mean")),
                ("scale", StandardScaler()),
                ("pca", PCA(n_components=k, random_state=SEED)),
                ("clf", LogisticRegression(C=0.1, max_iter=5000, random_state=SEED)),
            ]
        )
        res = evaluate(pipe, Xe[has], y[has], f"probe_pca{k}", n_repeats=repeats, with_loo=False)
        auc, lo, hi = bootstrap_ci(y[has], res["oof_mean"], "auc", n_boot=1000)
        rows.append({"predictor": f"linear_probe_pca{k}", "n": int(has.sum()), "cv_auc": auc, "ci_lo": lo, "ci_hi": hi})
        print(f"  probe PCA{k:<3d} AUC={auc:.3f} [{lo:.3f},{hi:.3f}]", flush=True)

    pipe = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=5000, random_state=SEED))])
    res = evaluate(pipe, cspca[has], y[has], "cspca", n_repeats=repeats, with_loo=False)
    auc, lo, hi = bootstrap_ci(y[has], res["oof_mean"], "auc", n_boot=1000)
    rows.append({"predictor": "cspca_scalar_from_prompt", "n": int(has.sum()), "cv_auc": auc, "ci_lo": lo, "ci_hi": hi})
    print(f"  cspca escalar  AUC={auc:.3f} [{lo:.3f},{hi:.3f}]", flush=True)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data_filtered" / "task1"))
    ap.add_argument("--model", default=None, help="por defecto, el campeón de run_bakeoff.py")
    ap.add_argument("--repeats", type=int, default=10)
    args = ap.parse_args()

    ART.mkdir(parents=True, exist_ok=True)
    cases = [c for c in load_cases(args.data, task=1) if c.has_label]

    model = args.model
    if model is None:
        summary = ART / "bakeoff_summary.json"
        if summary.exists():
            import json

            model = json.loads(summary.read_text())["champion"].split("|", 1)[1]
        else:
            model = "logreg_l2"
    print(f"Modelo de la ablación: {model}\n")

    print("=== Ablación por combinación de bloques ===")
    ablate(cases, model, args.repeats).to_csv(ART / "ablation_blocks.csv", index=False)

    print("\n=== Leave-one-block-out sobre ABCDE ===")
    leave_one_block_out(cases, model, args.repeats).to_csv(ART / "ablation_leave_one_out.csv", index=False)

    print("\n=== Sonda sobre el vector neuronal de RM ===")
    embedding_probe(cases, args.repeats).to_csv(ART / "embedding_probe.csv", index=False)
    print("\nListo.")


if __name__ == "__main__":
    main()
