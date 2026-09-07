"""Estudio de ablación del experto de clasificación de la tarea 1.

Responde tres preguntas con el mismo protocolo, para que sean comparables:

1. **¿Qué bloques de información merecen la pena?** El panel visible (A), el
   EHR enmascarado parseado (C) y los embeddings congelados (B), solos y
   combinados.
2. **¿Qué familia de clasificador?** Desde la clase mayoritaria hasta el
   Probabilistic Random Forest, pasando por el kNN que usa la solución
   anterior.
3. **¿Qué métrica hay que mirar?** No la exactitud: el `ranking_score` de la
   tarea 1 es ``(mean_case_score + F1(yes)) / 2``, así que se reporta también
   un **proxy de ranking** que pesa las dos mitades como el evaluador oficial.

Protocolo: validación cruzada estratificada **repetida** (5 particiones x 5
repeticiones), out-of-fold, con imputación y escalado ajustados **dentro** de
cada partición. Nada se elige mirando el resultado: el catálogo de modelos y
sus hiperparámetros se fija antes de correr.

    python delete_solution_one/solution_task_one_correction_claude/ablation/run_ablation.py
    python .../run_ablation.py --quick     # 3x3, para iterar
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
warnings.filterwarnings("ignore")

from sklearn.calibration import CalibratedClassifierCV  # noqa: E402
from sklearn.gaussian_process import GaussianProcessClassifier  # noqa: E402
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel  # noqa: E402
from sklearn.naive_bayes import GaussianNB  # noqa: E402
from sklearn.neural_network import MLPClassifier  # noqa: E402
from sklearn.base import BaseEstimator, ClassifierMixin  # noqa: E402
from sklearn.svm import SVC  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.dummy import DummyClassifier  # noqa: E402
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss, roc_auc_score  # noqa: E402
from sklearn.model_selection import RepeatedStratifiedKFold  # noqa: E402
from sklearn.neighbors import KNeighborsClassifier  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from delete_solution_one.solution_task_one_correction_claude import features as F  # noqa: E402
from delete_solution_one.solution_task_one_correction_claude.experts.prf import (  # noqa: E402
    ProbabilisticRandomForest,
)
from delete_solution_one.solution_task_one_correction_claude.experts.uncertainty import (  # noqa: E402
    sigma_matrix,
)

DATA = REPO / "data" / "task1"
SEED = 0

#: Factor que convierte exactitud en `mean_case_score`: es la media de los cinco
#: componentes del razonamiento entre los casos que pasan la puerta, medida en la
#: corrida 2 de la solución anterior (0.5499 / 0.6923).
COMPONENT_FACTOR = 0.794


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------


def load() -> dict:
    ids, rows, embs, ys = [], [], [], []
    for d in sorted((DATA / "ground_truth").iterdir()):
        if not d.is_dir():
            continue
        cid = d.name
        case = F.load_case(DATA / "agent_input" / cid)
        ids.append(cid)
        ys.append(json.loads((d / "prostate-biopsy-decision.json").read_text()))
        rows.append(F.featurise(case["prompt"], case["ehr"], with_c=True, with_b=False))
        embs.append(F.block_b(case["emb"]))
    X = pd.DataFrame(rows, index=ids)
    E = pd.DataFrame(embs, index=ids)
    y = np.array(ys)
    bx = np.array([r["bx_ord"] for r in rows])
    return {"ids": np.array(ids), "X": X, "E": E, "y": y, "bx": bx}


#: Los cuatro conjuntos de variables que se comparan.
def feature_sets(D: dict) -> dict[str, tuple[np.ndarray, list[str], np.ndarray | None]]:
    X, E = D["X"], D["E"]
    core = [c for c in F.CORE_A if c in X.columns]
    a_full = [c for c in X.columns if not c.startswith("ehr_")]
    c_cols = [c for c in X.columns if c.startswith("ehr_")]
    emb_cols = [c for c in E.columns if c.startswith("emb_")]
    return {
        "A-core (8v)": (X[core].to_numpy(float), core, None),
        "A-full (%dv)" % len(a_full): (X[a_full].to_numpy(float), a_full, None),
        "A-core+C (%dv)" % (len(core) + len(c_cols)): (
            X[core + c_cols].to_numpy(float), core + c_cols, None),
        "A-full+C (%dv)" % len(X.columns): (X.to_numpy(float), list(X.columns), None),
        "A-core+B(PCA8)": (X[core].to_numpy(float), core, E[emb_cols].to_numpy(float)),
        "A-core+C+B(PCA8)": (X[core + c_cols].to_numpy(float), core + c_cols,
                             E[emb_cols].to_numpy(float)),
    }


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class DeepEnsemble(ClassifierMixin, BaseEstimator):
    """Ensemble de MLP pequeños — la receta de Lakshminarayanan et al. (2017).

    La incertidumbre sale del **desacuerdo entre miembros** entrenados con
    inicializaciones distintas: la media de las probabilidades es la
    predicción, su varianza es la parte epistémica. Es la alternativa no
    bayesiana estándar cuando no se quiere pagar el coste de una posterior.
    """

    def __init__(self, n_members: int = 10, hidden: tuple[int, ...] = (16,), random_state: int = SEED):
        self.n_members = n_members
        self.hidden = hidden
        self.random_state = random_state

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        self.members_ = []
        for m in range(self.n_members):
            clf = MLPClassifier(hidden_layer_sizes=self.hidden, max_iter=2000, alpha=1e-2,
                                random_state=self.random_state + m)
            clf.fit(X, y)
            self.members_.append(clf)
        return self

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.members_], axis=0)

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(1)]


def catalogue() -> dict:
    """Catálogo fijado a priori. Ninguno se afina mirando el resultado.

    Todos devuelven una probabilidad, que es el requisito: al presidente de la
    mesa no le sirve una etiqueta sin incertidumbre. Se cubren las cuatro vías
    por las que un clasificador puede producirla — frecuencia de vecinos,
    verosimilitud paramétrica, desacuerdo de un ensemble, y posterior bayesiana.
    """
    return {
        "0-dummy": lambda: DummyClassifier(strategy="most_frequent"),
        "kNN-5": lambda: KNeighborsClassifier(n_neighbors=5),
        "kNN-10-dist": lambda: KNeighborsClassifier(n_neighbors=10, weights="distance"),
        "logreg": lambda: LogisticRegression(max_iter=2000, C=1.0),
        "RF": lambda: RandomForestClassifier(n_estimators=400, min_samples_leaf=2,
                                             random_state=SEED, n_jobs=1),
        "RF-calibrado": lambda: CalibratedClassifierCV(
            RandomForestClassifier(n_estimators=200, min_samples_leaf=2,
                                   random_state=SEED, n_jobs=1),
            method="isotonic", cv=3),
        "ExtraTrees": lambda: ExtraTreesClassifier(n_estimators=400, min_samples_leaf=2,
                                                   random_state=SEED, n_jobs=-1),
        "HistGB": lambda: HistGradientBoostingClassifier(max_iter=200, random_state=SEED),
        "GaussianNB": lambda: GaussianNB(),
        "SVC-RBF-cal": lambda: CalibratedClassifierCV(
            SVC(kernel="rbf", C=1.0), method="sigmoid", cv=3),
        "GP-RBF": lambda: GaussianProcessClassifier(
            kernel=ConstantKernel(1.0) * RBF(length_scale=2.0) + WhiteKernel(1e-2),
            random_state=SEED, max_iter_predict=100),
        "DeepEnsemble-MLP": lambda: DeepEnsemble(n_members=10, hidden=(16,)),
        "RF-balanceado": lambda: RandomForestClassifier(
            n_estimators=500, min_samples_leaf=2, class_weight="balanced_subsample",
            random_state=SEED, n_jobs=-1),
        "logreg-balanceado": lambda: LogisticRegression(
            max_iter=2000, C=1.0, class_weight="balanced"),
    }


def make_pipe(model, n_tab: int, k_pca: int = 8):
    """Imputación + escalado dentro del fold; PCA sólo sobre las columnas de embedding."""
    if n_tab is None:
        return Pipeline([("imp", SimpleImputer(strategy="median")),
                         ("sc", StandardScaler()), ("clf", model)])
    from sklearn.compose import ColumnTransformer  # noqa: PLC0415

    tab = slice(0, n_tab)
    emb = slice(n_tab, None)
    ct = ColumnTransformer([
        ("tab", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
         list(range(tab.start, tab.stop))),
        ("emb", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value=0.0)),
                          ("sc", StandardScaler()),
                          ("pca", PCA(n_components=k_pca, random_state=SEED))]),
         emb),
    ])
    return Pipeline([("ct", ct), ("clf", model)])


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


def ece(conf: np.ndarray, ok: np.ndarray, n_bins: int = 8) -> float:
    e, edges = 0.0, np.linspace(0.5, 1.0, n_bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.sum():
            e += m.mean() * abs(ok[m].mean() - conf[m].mean())
    return float(e)


def evaluate(p_yes: np.ndarray, y: np.ndarray, bx: np.ndarray) -> dict:
    yb = (y == "yes").astype(int)
    pred = np.where(p_yes >= 0.5, "yes", "no")
    ok = pred == y
    conf = np.where(p_yes >= 0.5, p_yes, 1 - p_yes)
    order = np.argsort(-np.abs(p_yes - 0.5))
    acc_cov = np.cumsum(ok[order]) / np.arange(1, len(y) + 1)
    acc = float(ok.mean())
    f1 = float(f1_score(yb, (pred == "yes").astype(int), zero_division=0))
    out = {
        "acc": round(acc, 4),
        "bal_acc": round(float(balanced_accuracy_score(y, pred)), 4),
        "f1_yes": round(f1, 4),
        "ranking_proxy": round((COMPONENT_FACTOR * acc + f1) / 2, 4),
        "auc": round(float(roc_auc_score(yb, p_yes)), 4),
        "logloss": round(float(log_loss(yb, np.clip(p_yes, 1e-9, 1 - 1e-9))), 4),
        "brier": round(float(np.mean((p_yes - yb) ** 2)), 4),
        "ece": round(ece(conf, ok.astype(float)), 4),
        "acc@30%": round(float(acc_cov[int(0.3 * len(y)) - 1]), 4),
        "acc@50%": round(float(acc_cov[int(0.5 * len(y)) - 1]), 4),
    }
    for name, code in (("None", 0.0), ("Negative", 1.0), ("Positive", 3.0)):
        m = bx == code
        out[f"acc_{name}"] = round(float(ok[m].mean()), 3) if m.sum() else None
    return out


def protocol_verdict(X: np.ndarray, names: list[str], bx: np.ndarray) -> np.ndarray:
    """Criterio EAU por cubo; ``nan`` cuando el panel no determina el caso."""
    pir = X[:, names.index("pirads")] if "pirads" in names else np.full(len(bx), np.nan)
    out = np.full(len(bx), np.nan)
    naive = bx == 0.0
    out[naive] = np.where(np.nan_to_num(pir[naive], nan=0.0) >= 3, 1.0, 0.0)
    neg = bx == 1.0
    out[neg] = np.where(np.nan_to_num(pir[neg], nan=0.0) >= 4, 1.0, 0.0)
    return out


# ---------------------------------------------------------------------------
# Bucle principal
# ---------------------------------------------------------------------------


def _one_config(set_name, Xtab, names, Xemb, model_name, factory, y, bx,
                n_splits, n_repeats, prf_trees):
    """Una celda de la tabla: (conjunto de variables x modelo), out-of-fold."""
    Xfull = Xtab if Xemb is None else np.hstack([Xtab, Xemb])
    n_tab = None if Xemb is None else Xtab.shape[1]
    S = sigma_matrix(Xtab, names)
    oof = np.zeros(len(y))
    counts = np.zeros(len(y))
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=SEED)
    for tr, te in cv.split(Xfull, y):
        if model_name == "PRF":
            if Xemb is not None:
                return []
            prf = ProbabilisticRandomForest(n_estimators=prf_trees, max_depth=6, random_state=SEED)
            prf.fit(Xtab[tr], y[tr], S[tr])
            p = prf.predict_proba(Xtab[te], S[te])
            p_yes = p[:, list(prf.classes_).index("yes")]
        else:
            pipe = make_pipe(factory(), n_tab)
            pipe.fit(Xfull[tr], y[tr])
            p_yes = pipe.predict_proba(Xfull[te])[:, list(pipe.classes_).index("yes")]
        oof[te] += p_yes
        counts[te] += 1
    oof = oof / np.maximum(counts, 1)
    proto = protocol_verdict(Xtab, names, bx)
    blended = np.where(np.isnan(proto), oof, proto)
    return [
        {"conjunto": set_name, "modelo": model_name, **evaluate(oof, y, bx)},
        {"conjunto": set_name, "modelo": f"protocolo + {model_name}", **evaluate(blended, y, bx)},
    ]


def run(n_splits: int = 5, n_repeats: int = 5, prf_trees: int = 150, n_jobs: int = -1) -> pd.DataFrame:
    from joblib import Parallel, delayed  # noqa: PLC0415

    D = load()
    y, bx = D["y"], D["bx"]
    sets = feature_sets(D)
    models = {**catalogue(), "PRF": None}
    jobs = [(sn, Xt, nm, Xe, mn, fx)
            for sn, (Xt, nm, Xe) in sets.items()
            for mn, fx in models.items()]
    print(f"{len(jobs)} configuraciones x {n_splits * n_repeats} particiones...", flush=True)
    out = Parallel(n_jobs=n_jobs, verbose=5)(
        delayed(_one_config)(sn, Xt, nm, Xe, mn, fx, y, bx, n_splits, n_repeats, prf_trees)
        for sn, Xt, nm, Xe, mn, fx in jobs)
    return pd.DataFrame([r for group in out for r in group])


def _unused(n_splits, n_repeats, prf_trees):
    D = load()
    y, bx = D["y"], D["bx"]
    sets = feature_sets(D)
    models = catalogue()
    rows = []

    for set_name, (Xtab, names, Xemb) in sets.items():
        Xfull = Xtab if Xemb is None else np.hstack([Xtab, Xemb])
        n_tab = None if Xemb is None else Xtab.shape[1]
        S = sigma_matrix(Xtab, names)

        for model_name, factory in {**models, "PRF": None}.items():
            oof = np.zeros(len(y))
            counts = np.zeros(len(y))
            cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=SEED)
            for tr, te in cv.split(Xfull, y):
                if model_name == "PRF":
                    if Xemb is not None:      # el PRF sólo come la parte tabular
                        continue
                    med = np.nanmedian(Xtab[tr], axis=0)
                    prf = ProbabilisticRandomForest(n_estimators=prf_trees, max_depth=6,
                                                    random_state=SEED)
                    prf.fit(Xtab[tr], y[tr], S[tr])
                    p = prf.predict_proba(Xtab[te], S[te])
                    p_yes = p[:, list(prf.classes_).index("yes")]
                    del med
                else:
                    pipe = make_pipe(factory(), n_tab)
                    pipe.fit(Xfull[tr], y[tr])
                    p = pipe.predict_proba(Xfull[te])
                    p_yes = p[:, list(pipe.classes_).index("yes")]
                oof[te] += p_yes
                counts[te] += 1
            if counts.max() == 0:
                continue
            oof = oof / np.maximum(counts, 1)

            met = evaluate(oof, y, bx)
            rows.append({"conjunto": set_name, "modelo": model_name, **met})

            # variante: el criterio de protocolo manda donde se pronuncia
            proto = protocol_verdict(Xtab, names, bx)
            blended = np.where(np.isnan(proto), oof, proto)
            met2 = evaluate(blended, y, bx)
            rows.append({"conjunto": set_name, "modelo": f"protocolo + {model_name}", **met2})

    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="3x3 en vez de 5x5")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "ablation_task1.csv"))
    args = ap.parse_args()

    df = run(n_splits=3, n_repeats=3, prf_trees=80) if args.quick else run(prf_trees=120)
    df.to_csv(args.out, index=False)

    solo = df[~df["modelo"].str.startswith("protocolo")]
    con = df[df["modelo"].str.startswith("protocolo")]
    cols = ["conjunto", "modelo", "acc", "f1_yes", "ranking_proxy", "auc", "logloss", "ece",
            "acc_None", "acc_Negative", "acc_Positive"]
    print("\n=== Clasificador solo — top 12 por proxy de ranking ===")
    print(solo.sort_values("ranking_proxy", ascending=False)[cols].head(12).to_string(index=False))
    print("\n=== Criterio de protocolo + clasificador — top 12 ===")
    print(con.sort_values("ranking_proxy", ascending=False)[cols].head(12).to_string(index=False))
    print(f"\nescrito {args.out}  ({len(df)} filas)")


if __name__ == "__main__":
    main()
