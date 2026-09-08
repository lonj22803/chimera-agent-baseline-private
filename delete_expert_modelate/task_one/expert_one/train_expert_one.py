#!/usr/bin/env python3
"""Entrenamiento del Experto 1 — clasificador sobre ``structured-prompt.json``.

Sólo el bloque A. Es el experto "barato": no lee texto libre, no depende de que
el informe radiológico venga bien redactado, y por tanto es el que sigue
funcionando cuando falta todo lo demás. Su papel en la deliberación es el de
voto de referencia.

Uso::

    python train_expert_one.py
"""

from __future__ import annotations

import argparse
import os
import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
# Los procesos hijo de joblib no heredan el filtro; sin esto el log se llena.
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.train_expert import fit_expert  # noqa: E402

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "train" / "artifacts"
BLOCKS = "A"
NAME = "expert_one_structured"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data_filtered" / "task1"))
    ap.add_argument("--model", default=None, help="fuerza un candidato; por defecto se selecciona")
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--members", type=int, default=30)
    ap.add_argument("--imputations", type=int, default=10)
    args = ap.parse_args()

    (HERE / "model").mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)

    cases = [c for c in load_cases(args.data, task=1) if c.has_label]
    print(f"Experto 1 | bloques {BLOCKS} | {len(cases)} casos etiquetados\n")

    bundle = fit_expert(
        cases,
        blocks=BLOCKS,
        name=NAME,
        model_name=args.model,
        n_repeats=args.repeats,
        n_members=args.members,
        n_imputations=args.imputations,
    )

    print(f"Modelo elegido: {bundle['model_name']}  ({len(bundle['feature_names'])} variables)")
    m = bundle["metrics"]
    print(f"  AUC  CV  = {m['cv_auc']:.3f}  IC95 [{m['cv_auc_ci'][0]:.3f}, {m['cv_auc_ci'][1]:.3f}]")
    print(f"  AUC  LOO = {m['loo_auc']:.3f}")
    print(f"  bal.acc  = {m['cv_balanced_accuracy']:.3f}  IC95 [{m['cv_bal_acc_ci'][0]:.3f}, {m['cv_bal_acc_ci'][1]:.3f}]")
    print(f"  Brier    = {m['cv_brier']:.3f}   ECE = {m['cv_ece']:.3f}")
    print(f"  ensemble out-of-fold: AUC={m['ensemble_oof']['auc']:.3f}  acc={m['ensemble_oof']['accuracy']:.3f}")

    print("\nEscalera de fiabilidad (out-of-fold):")
    for r in bundle["ladder"]:
        print(f"  {r['rung']:9s} ({r['confidence']:10s}) n={r['n']:3d}  cobertura={r['coverage']:.2f}  acierto={r['accuracy']:.3f}")

    print("\nImportancia agregada por variable del formulario:")
    from chimera_experts.expert_classifier import weights_from_importance

    for k, v in weights_from_importance(bundle["importance"], BLOCKS).items():
        print(f"  {k:12s} {v}")

    top = sorted(bundle["importance"].items(), key=lambda kv: -kv[1])[:12]
    print("\nTop 12 variables por importancia de permutación (caída de AUC):")
    for k, v in top:
        print(f"  {k:26s} {v:+.4f}")

    out = HERE / "model" / "expert_one.joblib"
    joblib.dump(bundle, out, compress=3)  # ~3x menos disco, carga igual de rápida
    pd.DataFrame(bundle["selection_table"]).to_csv(ART / "expert_one_selection.csv", index=False)
    pd.DataFrame(sorted(bundle["importance"].items(), key=lambda kv: -kv[1]), columns=["feature", "auc_drop"]).to_csv(
        ART / "expert_one_importance.csv", index=False
    )
    pd.DataFrame(bundle["oof"]).to_csv(ART / "expert_one_oof.csv", index=False)
    (ART / "expert_one_summary.json").write_text(
        json.dumps(
            {k: v for k, v in bundle.items() if k not in ("model", "oof", "selection_table", "importance")},
            indent=2,
            default=float,
        )
    )
    print(f"\nGuardado en {out}")


if __name__ == "__main__":
    main()
