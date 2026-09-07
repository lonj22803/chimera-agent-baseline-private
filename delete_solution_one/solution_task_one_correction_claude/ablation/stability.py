"""Estabilidad del ganador de la ablación entre semillas de validación cruzada.

Elegir el máximo de una tabla de 90 filas medida sobre 91 casos es una forma
conocida de auto-engañarse: el ganador puede serlo por la partición concreta.
Aquí se repite la comparación de los finalistas con **10 semillas distintas** de
la validación cruzada repetida y se mira la media, la desviación y cuántas veces
cada configuración queda primera.

    python .../ablation/stability.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_ablation import (  # noqa: E402
    SEED, catalogue, evaluate, feature_sets, load, make_pipe, protocol_verdict, sigma_matrix,
)
from sklearn.model_selection import RepeatedStratifiedKFold  # noqa: E402

from delete_solution_one.solution_task_one_correction_claude.experts.prf import (  # noqa: E402
    ProbabilisticRandomForest,
)

FINALISTAS = [
    ("A-core (8v)", "ExtraTrees"),
    ("A-core+B(PCA8)", "ExtraTrees"),
    ("A-core (8v)", "GaussianNB"),
    ("A-core+B(PCA8)", "GaussianNB"),
    ("A-core (8v)", "RF-balanceado"),
    ("A-core (8v)", "RF"),
    ("A-core (8v)", "kNN-10-dist"),
    ("A-core (8v)", "kNN-5"),
    ("A-core (8v)", "PRF"),
    ("A-full (19v)", "PRF"),
    ("A-core+C (42v)", "RF-balanceado"),
]


def one(D, set_name, model_name, seed, n_splits=5, n_repeats=3, prf_trees=120):
    Xtab, names, Xemb = feature_sets(D)[set_name]
    Xfull = Xtab if Xemb is None else np.hstack([Xtab, Xemb])
    n_tab = None if Xemb is None else Xtab.shape[1]
    S = sigma_matrix(Xtab, names)
    y, bx = D["y"], D["bx"]
    oof, cnt = np.zeros(len(y)), np.zeros(len(y))
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    for tr, te in cv.split(Xfull, y):
        if model_name == "PRF":
            m = ProbabilisticRandomForest(n_estimators=prf_trees, max_depth=6, random_state=seed)
            m.fit(Xtab[tr], y[tr], S[tr])
            p = m.predict_proba(Xtab[te], S[te])[:, list(m.classes_).index("yes")]
        else:
            pipe = make_pipe(catalogue()[model_name](), n_tab)
            pipe.fit(Xfull[tr], y[tr])
            p = pipe.predict_proba(Xfull[te])[:, list(pipe.classes_).index("yes")]
        oof[te] += p
        cnt[te] += 1
    oof /= np.maximum(cnt, 1)
    proto = protocol_verdict(Xtab, names, bx)
    return evaluate(np.where(np.isnan(proto), oof, proto), y, bx)


def main() -> None:
    from joblib import Parallel, delayed

    D = load()
    seeds = list(range(10))
    jobs = [(s, m, sd) for s, m in FINALISTAS for sd in seeds]
    print(f"{len(jobs)} corridas ({len(FINALISTAS)} finalistas x {len(seeds)} semillas)...", flush=True)
    res = Parallel(n_jobs=-1, verbose=1)(delayed(one)(D, s, m, sd) for s, m, sd in jobs)

    df = pd.DataFrame([{"conjunto": s, "modelo": m, "semilla": sd, **r}
                       for (s, m, sd), r in zip(jobs, res)])
    df.to_csv(Path(__file__).resolve().parent / "stability_task1.csv", index=False)

    g = df.groupby(["conjunto", "modelo"]).agg(
        proxy_media=("ranking_proxy", "mean"), proxy_sd=("ranking_proxy", "std"),
        acc_media=("acc", "mean"), f1_media=("f1_yes", "mean"),
        auc_media=("auc", "mean"), ece_media=("ece", "mean"),
        pos_media=("acc_Positive", "mean"),
    ).sort_values("proxy_media", ascending=False)
    ganador_por_semilla = df.loc[df.groupby("semilla")["ranking_proxy"].idxmax()]
    g["veces_1o"] = ganador_por_semilla.groupby(["conjunto", "modelo"]).size().reindex(g.index).fillna(0).astype(int)
    print("\n=== Estabilidad entre 10 semillas (con criterio de protocolo) ===")
    print(g.round(4).to_string())
    print("\nGanador por semilla:")
    print(ganador_por_semilla[["semilla", "conjunto", "modelo", "ranking_proxy"]].to_string(index=False))


if __name__ == "__main__":
    main()
