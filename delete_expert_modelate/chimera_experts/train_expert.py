"""Rutina de entrenamiento compartida por los expertos clasificadores.

Los Expertos 1 y 3 se diferencian **sólo** en qué bloques de variables leen: el
1 se limita a ``structured-prompt.json`` (bloque A); el 3 añade todo lo
extraíble de ``*-clinical-data.json`` (bloques B-E) y, opcionalmente, la
proyección del Experto 2. El procedimiento de entrenamiento, selección y
calibración es idéntico, y vive aquí para que la comparación entre ambos sea
una comparación de *fuentes de evidencia* y no de metodología.

Pasos:

1. Se evalúa el catálogo completo sobre los bloques pedidos y se elige el
   modelo por AUC de validación cruzada repetida (desempate por Brier, que
   penaliza la mala calibración).
2. El ganador se envuelve en :class:`UncertaintyExpert` (bagging × imputación
   múltiple) y se ajusta sobre todos los casos etiquetados.
3. Se mide la **importancia de permutación out-of-fold**, que alimenta los
   ``variable_weights`` del formulario del reto.
4. Se evalúa la escalera de fiabilidad —cobertura y acierto por peldaño— con
   las probabilidades e incertidumbres out-of-fold del propio envoltorio, de
   modo que los tramos ``firm``/``supports``/``discuss`` que se publican son
   los medidos, no los supuestos.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from sklearn.base import clone
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedKFold

from .dataset import build_labels, build_matrix, completeness_vector
from .evaluation import SEED, bootstrap_ci, evaluate, metrics
from .models import UncertaintyExpert, build_catalog
from .uncertainty import ladder_table, reliability_table


def select_model(cases, blocks: str, n_repeats: int = 20, seed: int = SEED) -> tuple[str, object, dict]:
    """Elige el mejor candidato del catálogo para estos bloques."""
    X, names = build_matrix(cases, blocks)
    y = build_labels(cases)
    pirads_col = names.index("pirads") if "pirads" in names else 0
    psad_col = names.index("psad_calc") if "psad_calc" in names else 1
    catalog = build_catalog(seed=seed, pirads_col=pirads_col, psad_col=psad_col)

    table = []
    for name, est in catalog.items():
        res = evaluate(est, X, y, name, n_repeats=n_repeats, with_loo=False)
        table.append(
            {
                "model": name,
                "cv_auc": res["cv_auc"],
                "cv_brier": res["cv_brier"],
                "cv_ece": res["cv_ece"],
                "cv_balanced_accuracy": res["cv_balanced_accuracy"],
                "cv_auc_sd_across_repeats": res["cv_auc_sd_across_repeats"],
            }
        )
    # Orden: AUC descendente, Brier ascendente como desempate.
    table.sort(key=lambda r: (-r["cv_auc"], r["cv_brier"]))
    best = table[0]["model"]
    return best, catalog[best], {"selection_table": table, "feature_names": names, "n_features": X.shape[1]}


def oof_permutation_importance(
    estimator, X: np.ndarray, y: np.ndarray, names: list[str], n_repeats: int = 10, seed: int = SEED
) -> dict[str, float]:
    """Importancia de permutación medida fuera de la partición de ajuste.

    Medirla sobre los datos de entrenamiento premiaría a las variables que el
    modelo memorizó. Aquí se ajusta en cada partición y se permuta sobre la
    partición retenida, y se promedia; el resultado es la caída de AUC
    atribuible a cada variable en datos que el modelo no vio.
    """
    agg = defaultdict(list)
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    for tr, te in cv.split(X, y):
        est = clone(estimator).fit(X[tr], y[tr])
        r = permutation_importance(
            est, X[te], y[te], scoring="roc_auc", n_repeats=n_repeats, random_state=seed, n_jobs=-1
        )
        for j, n in enumerate(names):
            agg[n].append(float(r.importances_mean[j]))
    return {n: float(np.mean(v)) for n, v in agg.items()}


def fit_expert(
    cases,
    blocks: str,
    name: str,
    model_name: str | None = None,
    n_repeats: int = 20,
    n_members: int = 30,
    n_imputations: int = 10,
    seed: int = SEED,
) -> dict:
    """Entrena un experto completo y devuelve el paquete serializable."""
    X, names = build_matrix(cases, blocks)
    y = build_labels(cases)
    comp = completeness_vector(cases)

    if model_name is None:
        model_name, base, sel = select_model(cases, blocks, n_repeats, seed)
    else:
        pirads_col = names.index("pirads") if "pirads" in names else 0
        psad_col = names.index("psad_calc") if "psad_calc" in names else 1
        base = build_catalog(seed=seed, pirads_col=pirads_col, psad_col=psad_col)[model_name]
        sel = {"selection_table": [], "feature_names": names, "n_features": X.shape[1]}

    # --- métricas del clasificador desnudo, para el informe ------------------
    res = evaluate(base, X, y, model_name, n_repeats=n_repeats, with_loo=True)
    auc, auc_lo, auc_hi = bootstrap_ci(y, res["oof_mean"], "auc")
    ba, ba_lo, ba_hi = bootstrap_ci(y, res["oof_mean"], "balanced_accuracy")

    # --- el envoltorio de incertidumbre, evaluado out-of-fold ----------------
    # La escalera se mide con predicciones fuera de muestra: un tramo "firm"
    # calculado sobre los datos de entrenamiento sería trivialmente perfecto.
    p_oof = np.empty(len(y))
    s_oof = np.empty(len(y))
    sm_oof = np.empty(len(y))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(X, y):
        ue = UncertaintyExpert(
            base_estimator=_inner(base), n_members=n_members, n_imputations=n_imputations, seed=seed
        ).fit(X[tr], y[tr])
        for i, v in zip(te, ue.verdicts(X[te], comp[te])):
            p_oof[i] = v.probability
            s_oof[i] = v.epistemic_total
            sm_oof[i] = v.epistemic_missing

    # --- ajuste final sobre todos los casos ----------------------------------
    final = UncertaintyExpert(
        base_estimator=_inner(base), n_members=n_members, n_imputations=n_imputations, seed=seed
    ).fit(X, y)

    importance = oof_permutation_importance(base, X, y, names, seed=seed)

    return {
        "name": name,
        "blocks": blocks,
        "model": final,
        "model_name": model_name,
        "feature_names": names,
        "importance": importance,
        "threshold": 0.5,
        "n_cases": int(len(y)),
        "n_positive": int(y.sum()),
        "seed": seed,
        "selection_table": sel["selection_table"],
        "metrics": {
            "cv_auc": auc,
            "cv_auc_ci": [auc_lo, auc_hi],
            "cv_balanced_accuracy": ba,
            "cv_bal_acc_ci": [ba_lo, ba_hi],
            "cv_brier": res["cv_brier"],
            "cv_ece": res["cv_ece"],
            "cv_sensitivity": res["cv_sensitivity"],
            "cv_specificity": res["cv_specificity"],
            "loo_auc": res["loo_auc"],
            "loo_balanced_accuracy": res["loo_balanced_accuracy"],
            "loo_brier": res["loo_brier"],
            "ensemble_oof": metrics(y, p_oof),
        },
        "ladder": ladder_table(y, p_oof, s_oof),
        "reliability": reliability_table(y, p_oof),
        "oof": {
            "case_ids": [c.case_id for c in cases],
            "y": y.tolist(),
            "p_plain": res["oof_mean"].tolist(),
            "p_ensemble": p_oof.tolist(),
            "sigma_total": s_oof.tolist(),
            "sigma_missing": sm_oof.tolist(),
            "completeness": comp.tolist(),
        },
    }


#: Árboles por miembro del ensemble de incertidumbre. El catálogo del bakeoff usa
#: 1000 para que la comparación entre candidatos no dependa del tamaño del
#: bosque, pero dentro del envoltorio hay 30 miembros bootstrap promediándose ya,
#: de modo que 1000 árboles por miembro sólo multiplican por cuatro el tamaño del
#: modelo y el tiempo de inferencia sin mover la probabilidad. Se recorta.
MEMBER_N_ESTIMATORS = 250


def _inner(estimator):
    """Extrae el clasificador de una tubería, para reenvolverlo sin duplicar imputación."""
    est = estimator.named_steps["clf"] if (hasattr(estimator, "named_steps") and "clf" in estimator.named_steps) else estimator
    est = clone(est)
    if hasattr(est, "n_estimators") and isinstance(getattr(est, "n_estimators", None), int):
        est.set_params(n_estimators=min(est.n_estimators, MEMBER_N_ESTIMATORS))
    return est
