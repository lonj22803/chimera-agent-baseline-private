"""Sólo la sección de panel de `run_architecture.py`.

Un clasificador independiente por fuente, y las tres formas de combinarlos.
Responde a la pregunta que el diseño de la junta necesita: **qué sabe cada
especialista por su cuenta**, que no es lo mismo que cuánto aporta dentro de
un modelo que ya ve todo lo demás.

Se separa del script grande porque las secciones de suelos, plano y cascada ya
están medidas y volver a calcularlas cuesta veinte minutos sin cambiar nada.
"""

from __future__ import annotations

import csv
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.base import clone

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "delete_expert_modelate"))
warnings.filterwarnings("ignore")

from run_architecture import PANEL_BLOCKS, ProductOfExperts, SoftVote, Stacked, build  # noqa: E402

from chimera_experts import evaluation_multiclass as ev  # noqa: E402

ART = Path(__file__).resolve().parent / "artifacts"


def main(base: str = "extra_trees") -> None:
    labelled, X, names, y, projector, cat, cols_for, model = build(base)
    print(f"matriz {X.shape}, modelo base {base}\n")

    rows, results = [], {}
    pcols = {k: cols_for(b) for k, b in PANEL_BLOCKS.items()}

    print("### cada especialista por su cuenta")
    for k, b in PANEL_BLOCKS.items():
        P = ev.loo_probabilities(cat[base], X[:, pcols[k]], y)
        results[f"solo_{k}"] = P
        m = ev.metrics(y, P)
        lo, hi = ev.bootstrap_ci(y, P)
        rows.append({"arquitectura": f"solo_{k}", "bloques": b, "n_features": len(pcols[k]),
                     **{kk: round(v, 4) for kk, v in m.items()},
                     "acc_lo": round(lo, 4), "acc_hi": round(hi, 4)})
        print(f"  solo {k:12s} ({b:4s}) n={len(pcols[k]):3d} acc={m['accuracy']:.4f} "
              f"[{lo:.3f},{hi:.3f}] f1M={m['f1_macro']:.3f} brier={m['brier']:.3f}")

    print("\n### las tres formas de combinarlos")
    members = {k: clone(model) for k in PANEL_BLOCKS}
    for name, cls in (("voto_blando", SoftVote), ("producto_expertos", ProductOfExperts), ("apilado", Stacked)):
        P = ev.loo_probabilities(cls(members=members, columns=pcols), X, y)
        results[name] = P
        m = ev.metrics(y, P)
        lo, hi = ev.bootstrap_ci(y, P)
        rows.append({"arquitectura": name, "bloques": "+".join(PANEL_BLOCKS.values()),
                     "n_features": X.shape[1], **{kk: round(v, 4) for kk, v in m.items()},
                     "acc_lo": round(lo, 4), "acc_hi": round(hi, 4)})
        print(f"  {name:20s} acc={m['accuracy']:.4f} [{lo:.3f},{hi:.3f}] "
              f"f1M={m['f1_macro']:.3f} brier={m['brier']:.3f}")

    # Contraste pareado contra el suelo de guía, con el mismo protocolo.
    isup = names.index("bx_isup") if "bx_isup" in names else 0
    P_rule = ev.loo_probabilities(cat["grade_rule"], X, y)
    print("\n### contraste pareado contra la regla de guía")
    for r in rows:
        cmp = ev.paired_bootstrap(y, results[r["arquitectura"]], P_rule)
        r["delta_vs_regla"] = round(cmp["delta"], 4)
        r["p"] = round(cmp["p_two_sided"], 4)
        print(f"  {r['arquitectura']:20s} Δ={r['delta_vs_regla']:+.4f}  p={r['p']:.3f}")

    rows.sort(key=lambda r: -r["accuracy"])
    ART.mkdir(parents=True, exist_ok=True)
    out = ART / f"panel_{base}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"\n  -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "extra_trees")
