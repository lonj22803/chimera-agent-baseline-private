"""El experto de clasificación de la pizarra, con el modelo que elija la ablación.

Qué aporta que un LLM no puede aportar
--------------------------------------
Una probabilidad **calibrada** y una **barra de error separada en sus dos
componentes**, que es lo que permite al presidente de la mesa ponderar el
número en vez de creérselo o ignorarlo:

* **epistémica** — con otra muestra de entrenamiento la respuesta habría sido
  otra. Es la **barra de error del número** (``dp``), y se reduce con más casos
  etiquetados. Se estima como la desviación típica de la probabilidad entre los
  miembros del bagging: la receta de los *deep ensembles* (Lakshminarayanan
  et al., 2017) aplicada a un estimador clásico, y la descomposición
  información-mutua de Depeweg et al. (2018) en su forma práctica.
* **aleatoria** — entre pacientes indistinguibles para el modelo, el urólogo
  decidió cosas distintas. Es irreducible con más datos del mismo tipo, y se
  reporta como la **entropía normalizada** de la predicción media, en [0, 1].

Se reportan por separado a propósito: son magnitudes distintas y sumarlas en
cuadratura —como si la varianza de Bernoulli fuera un error estándar— produce
una barra de error de ±0.45 en todos los casos, que no informa de nada.

Honestidad sobre los casos etiquetados
--------------------------------------
Los 91 casos con etiqueta son a la vez el entrenamiento y el conjunto sobre el
que se mide. Para que la respuesta que ve el agente no esté contaminada, el
experto guarda las probabilidades **out-of-fold** de esos 91 y las sirve tal
cual cuando le preguntan por uno de ellos. Un caso nuevo pasa por el modelo
completo. Es la misma cifra que se reporta en la validación: lo que se mide es
literalmente lo que se sirve.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .. import features as F

log = logging.getLogger(__name__)

DISCLAIMER = (
    "A basic classifier, whose sole purpose is to provide a suggestion, produces this "
    "result along with its associated uncertainty. The purpose of this decision is to "
    "use it as an initial reference point for discussing the results."
)

_TIER_TEXT = {
    "firm": ("TIER 'firm': p +/- 1.96*dp does not cross the 0.5 threshold. Treat it as a strong "
             "prior that should only be overturned by explicit contradicting evidence."),
    "supports": ("TIER 'supports': p +/- dp does not cross 0.5 but p +/- 1.96*dp does. A direction, "
                 "not a conclusion; a weighted vote."),
    "discuss": ("TIER 'discuss': p +/- dp straddles 0.5. The classifier genuinely CANNOT tell the "
                "two answers apart here. Its number is a starting point only."),
}

ROLE = ("statistical expert; bagged classifier over the structured panel, trained on the labelled "
        "cohort, out-of-fold honest")


@dataclass
class ExpertSpec:
    """Lo que la ablación decide: qué variables y qué modelo."""

    feature_set: str = "A-core"          # A-core | A-full | A-core+C | A-full+C
    model: str = "kNN-5"                 # nombre del catálogo de la ablación
    n_bags: int = 30
    seed: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------


def _columns(names: list[str], feature_set: str) -> list[str]:
    core = [c for c in F.CORE_A if c in names]
    ehr = [c for c in names if c.startswith("ehr_")]
    a_full = [c for c in names if not c.startswith("ehr_")]
    return {
        "A-core": core,
        "A-full": a_full,
        "A-core+C": core + ehr,
        "A-full+C": a_full + ehr,
    }[feature_set]


def build_estimator(name: str, seed: int = 0):
    """Los mismos modelos del catálogo de la ablación, sin depender de él."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    core = {
        "kNN-5": KNeighborsClassifier(n_neighbors=5),
        "kNN-10-dist": KNeighborsClassifier(n_neighbors=10, weights="distance"),
        "logreg": LogisticRegression(max_iter=2000, C=1.0),
        "logreg-balanceado": LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced"),
        "RF": RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=seed, n_jobs=1),
        "RF-balanceado": RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                                class_weight="balanced_subsample",
                                                random_state=seed, n_jobs=1),
        "ExtraTrees": ExtraTreesClassifier(n_estimators=300, min_samples_leaf=2,
                                           random_state=seed, n_jobs=1),
        "RF-calibrado": CalibratedClassifierCV(
            RandomForestClassifier(n_estimators=200, min_samples_leaf=2, random_state=seed, n_jobs=1),
            method="isotonic", cv=3),
    }[name]
    return Pipeline([("imp", SimpleImputer(strategy="median")),
                     ("sc", StandardScaler()), ("clf", core)])


class ClassifierExpert:
    """Experto entrenado y listo para escribir en la pizarra."""

    def __init__(self, state: dict[str, Any]):
        self.s = state

    # -- entrenamiento -------------------------------------------------------

    @classmethod
    def train(cls, data_root: Path | str, spec: ExpertSpec) -> "ClassifierExpert":
        from sklearn.model_selection import RepeatedStratifiedKFold

        data_root = Path(data_root)
        ids, rows, ys = [], [], []
        for d in sorted((data_root / "ground_truth").iterdir()):
            if not d.is_dir():
                continue
            case = F.load_case(data_root / "agent_input" / d.name)
            ids.append(d.name)
            ys.append(json.loads((d / "prostate-biopsy-decision.json").read_text()))
            rows.append(F.featurise(case["prompt"], case["ehr"], with_c=True, with_b=False))

        names = sorted({k for r in rows for k in r})
        cols = _columns(names, spec.feature_set)
        X = np.array([[r.get(c, np.nan) for c in cols] for r in rows], float)
        y = np.array(ys)

        # --- probabilidades out-of-fold: lo que se sirve para los 91 --------
        oof = np.zeros(len(y))
        cnt = np.zeros(len(y))
        cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=spec.seed)
        for tr, te in cv.split(X, y):
            est = build_estimator(spec.model, spec.seed)
            est.fit(X[tr], y[tr])
            oof[te] += est.predict_proba(X[te])[:, list(est.classes_).index("yes")]
            cnt[te] += 1
        oof /= np.maximum(cnt, 1)

        # --- bagging para la descomposición de la incertidumbre -------------
        rng = np.random.default_rng(spec.seed)
        members, idxs = [], []
        n = len(y)
        pos, neg = np.where(y == "yes")[0], np.where(y == "no")[0]
        for _ in range(spec.n_bags):
            sel = np.concatenate([rng.choice(pos, len(pos), replace=True),
                                  rng.choice(neg, len(neg), replace=True)])
            est = build_estimator(spec.model, int(rng.integers(1 << 31)))
            est.fit(X[sel], y[sel])
            members.append(est)
            idxs.append(sel)

        # --- incertidumbre OOF y escalera operativa -------------------------
        # dp = desviación entre miembros del bagging: el error estándar de la
        # estimación. La parte aleatoria va aparte, como entropía.
        P = np.stack([m.predict_proba(X)[:, list(m.classes_).index("yes")] for m in members])
        delta = P.std(0)
        z = np.abs(oof - 0.5) / np.maximum(delta, 1e-9)
        ok = (np.where(oof >= 0.5, "yes", "no") == y)
        tiers = {"firm": z >= 1.96, "supports": (z >= 1.0) & (z < 1.96), "discuss": z < 1.0}
        tier_acc = {k: (round(float(ok[m].mean()), 3), int(m.sum())) for k, m in tiers.items() if m.sum()}

        from sklearn.metrics import f1_score, roc_auc_score
        metrics = {
            "n": int(n),
            "acc": round(float(ok.mean()), 3),
            "auc": round(float(roc_auc_score((y == "yes").astype(int), oof)), 3),
            "f1_yes": round(float(f1_score((y == "yes").astype(int),
                                           (oof >= 0.5).astype(int), zero_division=0)), 3),
            "majority": round(float(max((y == "yes").mean(), (y == "no").mean())), 3),
            "protocol": "5x5 StratifiedKFold, out-of-fold",
        }

        return cls({
            "spec": spec.__dict__, "columns": cols, "ids": np.array(ids), "y": y,
            "X": X, "oof": oof, "delta_oof": delta, "members": members,
            "tier_acc": tier_acc, "metrics": metrics,
        })

    # -- persistencia --------------------------------------------------------

    def save(self, path: Path | str) -> None:
        import joblib
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.s, path)

    @classmethod
    def load(cls, path: Path | str) -> "ClassifierExpert":
        import joblib
        return cls(joblib.load(path))

    # -- inferencia ----------------------------------------------------------

    def predict(self, case_files: dict[str, dict]) -> dict[str, Any]:
        s = self.s
        feats = F.featurise(case_files.get("prompt") or {}, case_files.get("ehr") or {},
                            with_c=True, with_b=False)
        x = np.array([[feats.get(c, np.nan) for c in s["columns"]]], float)
        cid = str((case_files.get("prompt") or {}).get("case_id") or "")

        P = np.array([m.predict_proba(x)[0, list(m.classes_).index("yes")] for m in s["members"]])
        delta = float(P.std())

        in_train = cid in set(map(str, s["ids"]))
        if in_train:
            i = int(np.where(s["ids"].astype(str) == cid)[0][0])
            p = float(s["oof"][i])          # honesto: la del fold que no lo vio
            delta = float(s["delta_oof"][i])
        else:
            p = float(P.mean())

        q = min(max(p, 1e-9), 1 - 1e-9)
        entropy = float(-(q * np.log2(q) + (1 - q) * np.log2(1 - q)))

        z = abs(p - 0.5) / max(delta, 1e-9)
        tier = "firm" if z >= 1.96 else ("supports" if z >= 1.0 else "discuss")
        missing = [c for c, v in zip(s["columns"], x[0]) if not np.isfinite(v)]
        return {
            "prediccion": "yes" if p >= 0.5 else "no",
            "A": round(p, 4), "delta_A": round(delta, 4),
            "delta_epistemica": round(delta, 4), "entropia_aleatoria": round(entropy, 4),
            "intervalo_95": [round(max(0.0, p - 1.96 * delta), 3), round(min(1.0, p + 1.96 * delta), 3)],
            "veredicto_operativo": tier, "margen_z": round(z, 3),
            "variables_faltantes": missing,
            "caso_en_entrenamiento": in_train,
            "modelo": s["spec"]["model"], "conjunto": s["spec"]["feature_set"],
            "rendimiento_validacion": s["metrics"],
            "acierto_tramo": s["tier_acc"].get(tier),
        }

    # -- pizarra -------------------------------------------------------------

    def render(self, case_files: dict[str, dict]) -> tuple[str, str, dict[str, Any]]:
        try:
            o = self.predict(case_files)
        except Exception as exc:  # noqa: BLE001 — la pizarra sigue aunque esto falle
            log.warning("Clasificador no disponible: %s", exc)
            return ROLE, (f"The statistical classifier is unavailable for this case ({exc}). "
                          "No prior probability is contributed."), {"error": str(exc)}

        m = o["rendimiento_validacion"]
        acc_tier, n_tier = (o["acierto_tramo"] or (None, 0))
        tier_line = _TIER_TEXT[o["veredicto_operativo"]]
        if acc_tier is not None:
            tier_line += f" Measured accuracy in this tier on the labelled cohort: {acc_tier} over {n_tier} cases."

        body = f"""{DISCLAIMER}

SUGGESTION: {"BIOPSY" if o["prediccion"] == "yes" else "NO BIOPSY"}
  p(biopsy = yes) = {o["A"]:.2f} +/- {o["delta_A"]:.2f}   (95% CI {o["intervalo_95"][0]:.2f}-{o["intervalo_95"][1]:.2f})

Two different uncertainties, reported separately because they mean different things:
  - epistemic  dp = {o["delta_epistemica"]:.2f}  — the error bar on this number. It is the spread
    across bootstrap members: how much the answer would move with a different training sample.
  - aleatoric  H  = {o["entropia_aleatoria"]:.2f} of 1.00 — how mixed the outcome was among
    patients this model cannot tell apart. High H means the disagreement is in the data, not in
    the model, and more labelled cases would not fix it.

{tier_line}

Model: {o["modelo"]} over the {o["conjunto"]} variable set, chosen by the ablation study, not assumed.
Out-of-fold performance on the {m["n"]} labelled cases ({m["protocol"]}):
  accuracy {m["acc"]} (majority-class baseline {m["majority"]}), AUC {m["auc"]}, F1(yes) {m["f1_yes"]}.
Variables it could not read for this patient: {", ".join(o["variables_faltantes"]) or "none"}.

It has read ONLY the structured panel and the parsed record. It has not reasoned about the
prose of the mpMRI report, and it does not know what this patient's management plan is."""
        return ROLE, body, o
