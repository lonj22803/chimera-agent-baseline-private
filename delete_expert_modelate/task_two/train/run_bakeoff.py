"""Bakeoff de la tarea 2: qué clasificador, sobre qué bloques, y con qué forma.

Tres preguntas, en este orden:

1. **¿Qué modelo?** 17 candidatos —incluidos los dos suelos— sobre un conjunto
   fijo de variables.
2. **¿Qué fuentes?** El ganador contra cada combinación de bloques.
3. **¿Una cabeza o varias?** El clasificador plano de cuatro salidas contra la
   descomposición jerárquica que la propia etiqueta sugiere.

Todo con leave-one-out sobre los 72 casos etiquetados. El criterio es el
acierto exacto, porque es lo único que el evaluador del reto puntúa.
"""

from __future__ import annotations

import argparse
import csv
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "delete_expert_modelate"))

from chimera_experts import dataset_task2 as d2  # noqa: E402
from chimera_experts import evaluation_multiclass as ev  # noqa: E402
from chimera_experts import features_wsi, io, models_multiclass as mm  # noqa: E402

DATA = ROOT / "data" / "task2"
ART = Path(__file__).resolve().parent / "artifacts"
warnings.filterwarnings("ignore")


def load(blocks: str, projector=None):
    all_cases = io.load_cases(DATA, task=2)
    labelled = [c for c in all_cases if c.has_label]
    if projector is None and "K" in blocks:
        projector = features_wsi.EmbeddingProjector(8).fit(all_cases)
    X, names = d2.build_matrix(labelled, blocks, projector=projector)
    y = d2.build_labels(labelled)
    return labelled, X, names, y


def isup_column(names: list[str]) -> int:
    for cand in ("bx_isup", "path_isup_last"):
        if cand in names:
            return names.index(cand)
    return 0


def stage1(blocks: str, out: Path) -> list[dict]:
    """Comparación de candidatos sobre un conjunto fijo de variables."""
    _, X, names, y = load(blocks)
    catalog = mm.build_catalog(isup_col=isup_column(names))
    rows = []
    for name, est in catalog.items():
        P = ev.loo_probabilities(est, X, y)
        m = ev.metrics(y, P)
        lo, hi = ev.bootstrap_ci(y, P)
        rows.append({"model": name, "blocks": blocks, "n_features": X.shape[1],
                     **{k: round(v, 4) for k, v in m.items()},
                     "acc_lo": round(lo, 4), "acc_hi": round(hi, 4)})
        print(f"  {name:26s} acc={m['accuracy']:.4f} [{lo:.3f},{hi:.3f}] "
              f"f1M={m['f1_macro']:.3f} bal={m['balanced_accuracy']:.3f} brier={m['brier']:.3f}")
    rows.sort(key=lambda r: -r["accuracy"])
    _write(out, rows)
    return rows


def stage2(model: str, combos: list[str], out: Path) -> list[dict]:
    """El modelo ganador contra cada combinación de bloques."""
    all_cases = io.load_cases(DATA, task=2)
    projector = features_wsi.EmbeddingProjector(8).fit(all_cases)
    rows = []
    for blocks in combos:
        _, X, names, y = load(blocks, projector)
        est = mm.build_catalog(isup_col=isup_column(names))[model]
        P = ev.loo_probabilities(est, X, y)
        m = ev.metrics(y, P)
        lo, hi = ev.bootstrap_ci(y, P)
        rows.append({"blocks": blocks, "sources": "+".join(d2.BLOCKS[b][0] for b in blocks if b in d2.BLOCKS),
                     "model": model, "n_features": X.shape[1],
                     **{k: round(v, 4) for k, v in m.items()},
                     "acc_lo": round(lo, 4), "acc_hi": round(hi, 4)})
        print(f"  {blocks:12s} n={X.shape[1]:4d} acc={m['accuracy']:.4f} [{lo:.3f},{hi:.3f}] "
              f"f1M={m['f1_macro']:.3f} brier={m['brier']:.3f}")
    rows.sort(key=lambda r: -r["accuracy"])
    _write(out, rows)
    return rows


def _write(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  -> {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="1", choices=["1", "2"])
    ap.add_argument("--blocks", default="AG")
    ap.add_argument("--model", default="extra_trees")
    args = ap.parse_args()

    if args.stage == "1":
        print(f"### Etapa 1 — candidatos sobre bloques {args.blocks}")
        stage1(args.blocks, ART / f"bakeoff_stage1_{args.blocks}.csv")
    else:
        combos = ["A", "G", "H", "I", "J", "K", "AG", "GH", "GI", "GHI", "AGH", "AGI", "AGHI",
                  "AGHIJ", "AGHIK", "ACGHI", "ABGHI", "ADGHI", "ABCDGHI", "ABCDEGHIJK"]
        print(f"### Etapa 2 — bloques, modelo {args.model}")
        stage2(args.model, combos, ART / f"bakeoff_stage2_{args.model}.csv")
