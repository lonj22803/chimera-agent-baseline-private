"""¿Una cabeza de cuatro salidas, tres cabezas encadenadas, o un panel por fuente?

Las tres formas se miden con el mismo protocolo —leave-one-out sobre los 72
casos etiquetados— y con la misma métrica que puntúa el reto, el acierto
exacto. Las diferencias se contrastan con bootstrap **pareado**, porque con 72
casos dos intervalos que se solapan no dicen nada sobre cuál de los dos modelos
es mejor caso a caso.

    plano       un clasificador de 4 salidas sobre el conjunto de bloques
    cascada     ¿hay cáncer? -> ¿tratar? -> ¿se beneficia?  (una fuente por nodo)
    panel       un clasificador independiente por fuente + combinación
                (voto blando, producto de expertos, y apilado con regresión
                 logística multinomial sobre las probabilidades fuera de pliegue)

El panel se evalúa con **doble validación**: las probabilidades que alimentan
al combinador son fuera de pliegue dentro del entrenamiento de cada iteración
LOO. Apilar sobre probabilidades ajustadas en los mismos datos que entrenaron
a los miembros infla el resultado y es el error clásico del *stacking*
(Wolpert 1992, §4).
"""

from __future__ import annotations

import csv
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "delete_expert_modelate"))

from chimera_experts import dataset_task2 as d2  # noqa: E402
from chimera_experts import evaluation_multiclass as ev  # noqa: E402
from chimera_experts import features_wsi, io, models_multiclass as mm  # noqa: E402
from chimera_experts.cascade_task2 import CLASSES, GuidelineCascade  # noqa: E402

DATA = ROOT / "data" / "task2"
ART = Path(__file__).resolve().parent / "artifacts"
warnings.filterwarnings("ignore")

#: Qué bloque contesta cada pregunta de la cascada.
NODE_BLOCKS = {"cancer": "GH", "treat": "AGH", "fit": "AGI"}

#: Las fuentes que forman el panel de especialistas.
PANEL_BLOCKS = {"grading": "G", "pathology": "H", "frailty": "I",
                "clinical": "A", "radiology": "D", "psa": "C", "embedding": "JK"}


class SoftVote(BaseEstimator, ClassifierMixin):
    def __init__(self, members: dict, columns: dict):
        self.members, self.columns = members, columns

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        self.fitted_ = {k: clone(m).fit(X[:, self.columns[k]], y) for k, m in self.members.items()}
        return self

    def _stack(self, X):
        return np.stack([self._align(e, e.predict_proba(X[:, self.columns[k]]))
                         for k, e in self.fitted_.items()])

    def _align(self, est, P):
        out = np.zeros((P.shape[0], len(self.classes_)))
        for j, c in enumerate(est.classes_):
            out[:, int(np.flatnonzero(self.classes_ == c)[0])] = P[:, j]
        return out

    def predict_proba(self, X):
        return self._stack(X).mean(axis=0)

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]


class ProductOfExperts(SoftVote):
    """Media geométrica. Un experto que descarta una clase la descarta para todos.

    Frente al voto blando, penaliza el desacuerdo en lugar de promediarlo: es la
    combinación adecuada cuando cada miembro ve una fuente distinta y su
    ignorancia sobre las demás no debe contar como voto (Hinton, Neural Comput
    2002).
    """

    def predict_proba(self, X):
        P = np.clip(self._stack(X), 1e-6, None)
        G = np.exp(np.log(P).mean(axis=0))
        return G / G.sum(axis=1, keepdims=True)


class Stacked(SoftVote):
    """Apilado con logística multinomial sobre probabilidades fuera de pliegue."""

    def __init__(self, members: dict, columns: dict, n_splits: int = 4, seed: int = 0):
        super().__init__(members, columns)
        self.n_splits, self.seed = n_splits, seed

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        k = len(self.classes_)
        Z = np.zeros((len(y), len(self.members) * k))
        skf = StratifiedKFold(n_splits=self.n_splits, shuffle=True, random_state=self.seed)
        for tr, te in skf.split(X, y):
            for i, (name, m) in enumerate(self.members.items()):
                est = clone(m).fit(X[tr][:, self.columns[name]], y[tr])
                Z[np.ix_(te, range(i * k, (i + 1) * k))] = self._align(est, est.predict_proba(X[te][:, self.columns[name]]))
        self.fitted_ = {n: clone(m).fit(X[:, self.columns[n]], y) for n, m in self.members.items()}
        self.meta_ = LogisticRegression(C=0.5, max_iter=5000, random_state=self.seed).fit(Z, y)
        return self

    def predict_proba(self, X):
        Z = np.concatenate([self._align(e, e.predict_proba(X[:, self.columns[n]]))
                            for n, e in self.fitted_.items()], axis=1)
        return self._align(self.meta_, self.meta_.predict_proba(Z))


def build(base: str = "extra_trees"):
    all_cases = io.load_cases(DATA, task=2)
    labelled = [c for c in all_cases if c.has_label]
    projector = features_wsi.EmbeddingProjector(8).fit(all_cases)

    union = "ACDGHIJK"
    X, names = d2.build_matrix(labelled, union, projector=projector)
    y = d2.build_labels(labelled)

    def cols_for(blocks: str) -> list[int]:
        sub, sub_names = d2.build_matrix(labelled, blocks, projector=projector)
        return [names.index(n) for n in sub_names if n in names]

    isup = names.index("bx_isup") if "bx_isup" in names else 0
    cat = mm.build_catalog(isup_col=isup)
    return labelled, X, names, y, projector, cat, cols_for, cat[base]


def main(base: str = "extra_trees") -> None:
    labelled, X, names, y, projector, cat, cols_for, model = build(base)
    print(f"matriz de trabajo: {X.shape}, modelo base: {base}\n")

    results: dict[str, np.ndarray] = {}

    print("### suelos")
    for name in ("prior_only", "grade_rule"):
        P = ev.loo_probabilities(cat[name], X, y)
        results[name] = P
        print(f"  {name:26s} acc={ev.metrics(y, P)['accuracy']:.4f}")

    print("\n### plano — un clasificador de 4 salidas")
    for blocks in ("G", "AG", "AGH", "AGHI", "ACDGHIJK"):
        P = ev.loo_probabilities(cat[base], X[:, cols_for(blocks)], y)
        results[f"plano_{blocks}"] = P
        m = ev.metrics(y, P)
        print(f"  plano {blocks:10s} acc={m['accuracy']:.4f} f1M={m['f1_macro']:.3f} brier={m['brier']:.3f}")

    print("\n### cascada — tres preguntas encadenadas")
    node_cols = {n: cols_for(b) for n, b in NODE_BLOCKS.items()}
    casc = GuidelineCascade(heads={n: clone(model) for n in NODE_BLOCKS}, columns=node_cols)
    P = ev.loo_probabilities(casc, X, y)
    results["cascada"] = P
    m = ev.metrics(y, P)
    print(f"  cascada {'/'.join(NODE_BLOCKS.values()):14s} acc={m['accuracy']:.4f} f1M={m['f1_macro']:.3f} brier={m['brier']:.3f}")

    casc_all = GuidelineCascade(heads={n: clone(model) for n in NODE_BLOCKS},
                                columns={n: cols_for("ACDGHIJK") for n in NODE_BLOCKS})
    P = ev.loo_probabilities(casc_all, X, y)
    results["cascada_todo"] = P
    m = ev.metrics(y, P)
    print(f"  cascada {'todos los bloques':14s} acc={m['accuracy']:.4f} f1M={m['f1_macro']:.3f} brier={m['brier']:.3f}")

    print("\n### panel — un especialista por fuente")
    members = {k: clone(model) for k in PANEL_BLOCKS}
    pcols = {k: cols_for(b) for k, b in PANEL_BLOCKS.items()}
    for k, b in PANEL_BLOCKS.items():
        P = ev.loo_probabilities(cat[base], X[:, pcols[k]], y)
        results[f"solo_{k}"] = P
        mm_ = ev.metrics(y, P)
        print(f"  solo {k:12s} ({b:4s}) acc={mm_['accuracy']:.4f} f1M={mm_['f1_macro']:.3f}")
    for name, cls in (("voto_blando", SoftVote), ("producto_expertos", ProductOfExperts), ("apilado", Stacked)):
        comb = cls(members=members, columns=pcols)
        P = ev.loo_probabilities(comb, X, y)
        results[name] = P
        mm_ = ev.metrics(y, P)
        print(f"  {name:26s} acc={mm_['accuracy']:.4f} f1M={mm_['f1_macro']:.3f} brier={mm_['brier']:.3f}")

    print("\n### contraste pareado contra la regla de guía")
    ref = results["grade_rule"]
    rows = []
    for name, P in results.items():
        m = ev.metrics(y, P)
        lo, hi = ev.bootstrap_ci(y, P)
        cmp = ev.paired_bootstrap(y, P, ref)
        rows.append({"arquitectura": name, **{k: round(v, 4) for k, v in m.items()},
                     "acc_lo": round(lo, 4), "acc_hi": round(hi, 4),
                     "delta_vs_regla": round(cmp["delta"], 4), "p": round(cmp["p_two_sided"], 4)})
    rows.sort(key=lambda r: -r["accuracy"])
    for r in rows:
        print(f"  {r['arquitectura']:26s} acc={r['accuracy']:.4f} [{r['acc_lo']:.3f},{r['acc_hi']:.3f}] "
              f"Δ={r['delta_vs_regla']:+.4f} p={r['p']:.3f}")

    ART.mkdir(parents=True, exist_ok=True)
    out = ART / f"architecture_{base}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"\n  -> {out}")

    best = rows[0]["arquitectura"]
    print(f"\n### matriz de confusión — {best}")
    print(ev.confusion(y, results[best], CLASSES))
    np.save(ART / f"loo_probs_{base}.npy", np.stack([results[k] for k in sorted(results)]))
    with (ART / f"loo_probs_{base}_index.txt").open("w") as fh:
        fh.write("\n".join(sorted(results)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "extra_trees")
