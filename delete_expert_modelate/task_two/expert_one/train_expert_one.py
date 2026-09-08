#!/usr/bin/env python3
"""Experto 1 — el patólogo: grado, estadio y grupo de riesgo de guía.

Lee sólo lo que la guía lee para estratificar: ISUP grade group, patrones de
Gleason, estadio clínico T, PSA y densidad. Es el experto que reproduce el
razonamiento con el que se derivó el ground truth, y por eso es el ancla del
panel: barato, auditable y el único que sigue en pie cuando falta el texto
libre.

Uso::

    python train_expert_one.py"""

from __future__ import annotations

import argparse, json, os, sys, warnings
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from chimera_experts import features_wsi  # noqa: E402
from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.train_expert_task2 import fit_expert  # noqa: E402

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "train" / "artifacts"
BLOCKS = "G"
NAME = "expert_one"
ROLE = "grado y riesgo de guía"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data" / "task2"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--blocks", default=BLOCKS)
    ap.add_argument("--members", type=int, default=25)
    ap.add_argument("--imputations", type=int, default=10)
    ap.add_argument("--candidates", nargs="*", default=["extra_trees", "random_forest", "extra_trees_balanced", "logreg_l1", "grade_rule"],
                    help="lista corta heredada del ranking de la etapa 1")
    args = ap.parse_args()

    (HERE / "model").mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)

    all_cases = load_cases(args.data, task=2)
    cases = [c for c in all_cases if c.has_label]
    projector = features_wsi.EmbeddingProjector(8).fit(all_cases)
    print(f"{NAME} | {ROLE} | bloques {args.blocks} | {len(cases)} casos etiquetados\n")

    bundle = fit_expert(cases, blocks=args.blocks, name=NAME, role=ROLE,
                        model_name=args.model, projector=projector,
                        n_members=args.members, n_imputations=args.imputations,
                        candidates=list(args.candidates))

    m = bundle["metrics"]
    print(f"Modelo elegido: {bundle['model_name']}  ({len(bundle['feature_names'])} variables)")
    print(f"  acierto LOO  = {m['loo']['accuracy']:.4f}  IC95 {m['loo_accuracy_ci']}")
    print(f"  F1 macro     = {m['loo']['f1_macro']:.4f}   acierto equilibrado = {m['loo']['balanced_accuracy']:.4f}")
    print(f"  Brier        = {m['loo']['brier']:.4f}   ECE = {m['loo']['ece']:.4f}")
    print(f"  acierto CV   = {m['cv']['accuracy']:.4f}")
    print(f"  suelo regla  = {m['grade_rule_floor']['accuracy']:.4f}   "
          f"delta = {m['vs_rule']['delta']:+.4f}  p = {m['vs_rule']['p_two_sided']:.3f}")
    print("\n  escalera de fiabilidad (fuera de muestra)")
    for row in bundle["ladder"]:
        print(f"    {row['ladder']:9s} {row['confidence']:11s} n={row['n']:3d} "
              f"acierto={row['accuracy']}  margen medio={row.get('mean_margin')}")
    print("\n" + bundle["confusion"])

    joblib.dump(bundle, HERE / "model" / f"{NAME}.joblib")
    (ART / f"{NAME}_report.json").write_text(json.dumps(
        {k: v for k, v in bundle.items() if k not in ("model", "loo_probabilities")},
        indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\n  -> {HERE / 'model' / (NAME + '.joblib')}")


if __name__ == "__main__":
    main()
