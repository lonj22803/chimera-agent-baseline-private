#!/usr/bin/env python3
"""Entrenamiento del Experto 3 — clasificador de fusión multi-fuente.

Lee los dos ficheros de texto además del prompt estructurado:

* bloque A — ``structured-prompt.json``
* bloque B — analítica de ``prostate-biopsy-decision-clinical-data.json``
* bloque C — trayectoria de PSA de la misma fuente
* bloque D — hallazgos extraídos del informe radiológico por NegEx
* bloque E — historia familiar y notas previas

y, si se le pasa ``--with-expert-two``, añade como bloque G la proyección del
Experto 2. Ese bloque se evalúa por separado precisamente porque su aportación
no está garantizada: las variables de trayectoria del bloque C ya contienen las
mismas cifras sin pasar por el regresor, de modo que el bloque G sólo aporta si
la *proyección aprendida* añade algo sobre la *tendencia observada*.

Uso::

    python train_expert_three.py --with-expert-two
"""

from __future__ import annotations

import argparse
import os
import json
import sys
import warnings
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
# Los procesos hijo de joblib no heredan el filtro; sin esto el log se llena.
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from chimera_experts.dataset import BLOCKS as BLOCK_TABLE  # noqa: E402
from chimera_experts.expert_classifier import weights_from_importance  # noqa: E402
from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.train_expert import fit_expert  # noqa: E402

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "train" / "artifacts"
NAME = "expert_three_fusion"
E2_MODEL = HERE.parent / "expert_two" / "model" / "expert_two_psa_projector.joblib"


def register_expert_two_block(horizon: float = 6.0) -> None:
    """Registra la salida del Experto 2 como bloque ``G`` del ensamblador."""
    from chimera_experts.psa_projector import PSAProjectorExpert

    projector = PSAProjectorExpert.load(E2_MODEL)
    BLOCK_TABLE["G"] = ("expert_two_projection", lambda c: projector.features_for_fusion(c, horizon))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data_filtered" / "task1"))
    ap.add_argument("--blocks", default="ABCDE")
    ap.add_argument("--with-expert-two", action="store_true", help="añade el bloque G (proyección del Experto 2)")
    ap.add_argument("--model", default=None)
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--members", type=int, default=30)
    ap.add_argument("--imputations", type=int, default=10)
    args = ap.parse_args()

    blocks = args.blocks
    if args.with_expert_two:
        if not E2_MODEL.exists():
            raise SystemExit(f"Falta el modelo del Experto 2 en {E2_MODEL}; ejecuta antes train_expert_two.py")
        register_expert_two_block()
        blocks = blocks + "G"

    (HERE / "model").mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)

    cases = [c for c in load_cases(args.data, task=1) if c.has_label]
    print(f"Experto 3 | bloques {blocks} | {len(cases)} casos etiquetados\n")

    bundle = fit_expert(
        cases,
        blocks=blocks,
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
    for k, v in weights_from_importance(bundle["importance"], blocks).items():
        print(f"  {k:12s} {v}")

    print("\nTop 15 variables por importancia de permutación (caída de AUC):")
    for k, v in sorted(bundle["importance"].items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {k:30s} {v:+.4f}")

    suffix = "_with_e2" if args.with_expert_two else ""
    out = HERE / "model" / f"expert_three{suffix}.joblib"
    joblib.dump(bundle, out, compress=3)  # ~3x menos disco, carga igual de rápida
    pd.DataFrame(bundle["selection_table"]).to_csv(ART / f"expert_three_selection{suffix}.csv", index=False)
    pd.DataFrame(
        sorted(bundle["importance"].items(), key=lambda kv: -kv[1]), columns=["feature", "auc_drop"]
    ).to_csv(ART / f"expert_three_importance{suffix}.csv", index=False)
    pd.DataFrame(bundle["oof"]).to_csv(ART / f"expert_three_oof{suffix}.csv", index=False)
    (ART / f"expert_three_summary{suffix}.json").write_text(
        json.dumps(
            {k: v for k, v in bundle.items() if k not in ("model", "oof", "selection_table", "importance")},
            indent=2,
            default=float,
        )
    )
    print(f"\nGuardado en {out}")


if __name__ == "__main__":
    main()
