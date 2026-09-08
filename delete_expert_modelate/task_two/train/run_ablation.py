"""Ablación por bloques: qué fuente aporta y cuál sobra.

Dos vistas del mismo conjunto de bloques, porque responden a preguntas
distintas y con 72 casos ninguna basta sola:

* **leave-one-block-out** — se retira un bloque del conjunto completo. Mide
  redundancia: un bloque cuya retirada no mueve nada está duplicando
  información que ya está en otro sitio.
* **block-only** — se entrena sólo con ese bloque. Mide contenido: un bloque
  que solo rinde a nivel de suelo no tiene señal propia aunque en compañía
  parezca aportar.

Las diferencias se contrastan con bootstrap pareado sobre los mismos casos.
Con esta muestra casi ninguna será significativa, y eso también es un
resultado: sirve para **ordenar** candidatos, no para afirmar que uno es mejor.
"""

from __future__ import annotations

import csv
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "delete_expert_modelate"))

from chimera_experts import dataset_task2 as d2  # noqa: E402
from chimera_experts import evaluation_multiclass as ev  # noqa: E402
from chimera_experts import features_wsi, io, models_multiclass as mm  # noqa: E402

DATA = ROOT / "data" / "task2"
ART = Path(__file__).resolve().parent / "artifacts"
warnings.filterwarnings("ignore")

FULL = "ACDGHIJK"


def main(model: str = "extra_trees") -> None:
    all_cases = io.load_cases(DATA, task=2)
    labelled = [c for c in all_cases if c.has_label]
    projector = features_wsi.EmbeddingProjector(8).fit(all_cases)
    y = d2.build_labels(labelled)

    def probs(blocks: str):
        X, names = d2.build_matrix(labelled, blocks, projector=projector)
        isup = names.index("bx_isup") if "bx_isup" in names else 0
        est = mm.build_catalog(isup_col=isup)[model]
        return ev.loo_probabilities(est, X, y), X.shape[1]

    P_full, n_full = probs(FULL)
    base = ev.metrics(y, P_full)["accuracy"]
    print(f"conjunto completo {FULL} ({n_full} vars): acc={base:.4f}\n")

    rows = []
    print("### leave-one-block-out")
    for b in FULL:
        rest = FULL.replace(b, "")
        P, n = probs(rest)
        m = ev.metrics(y, P)
        cmp = ev.paired_bootstrap(y, P, P_full)
        rows.append({"vista": "leave_one_out", "bloque": b, "nombre": d2.BLOCKS.get(b, ("proyeccion_pca",))[0],
                     "n_features": n, "accuracy": round(m["accuracy"], 4), "f1_macro": round(m["f1_macro"], 4),
                     "delta": round(cmp["delta"], 4), "p": round(cmp["p_two_sided"], 4)})
        print(f"  sin {b} ({rows[-1]['nombre']:18s}) acc={m['accuracy']:.4f} Δ={cmp['delta']:+.4f} p={cmp['p_two_sided']:.3f}")

    print("\n### block-only")
    for b in FULL:
        P, n = probs(b)
        m = ev.metrics(y, P)
        cmp = ev.paired_bootstrap(y, P, P_full)
        rows.append({"vista": "block_only", "bloque": b, "nombre": d2.BLOCKS.get(b, ("proyeccion_pca",))[0],
                     "n_features": n, "accuracy": round(m["accuracy"], 4), "f1_macro": round(m["f1_macro"], 4),
                     "delta": round(cmp["delta"], 4), "p": round(cmp["p_two_sided"], 4)})
        print(f"  sólo {b} ({rows[-1]['nombre']:18s}) acc={m['accuracy']:.4f} Δ={cmp['delta']:+.4f} p={cmp['p_two_sided']:.3f}")

    ART.mkdir(parents=True, exist_ok=True)
    out = ART / f"ablation_{model}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"\n  -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "extra_trees")
