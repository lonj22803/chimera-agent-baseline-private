"""Rutina de entrenamiento compartida por los expertos de la tarea 2.

Un experto entrenado es un ``dict`` con el modelo, las variables que lee, las
métricas con las que se le puede pedir cuentas y la escalera de fiabilidad
medida fuera de muestra. Se guarda entero con ``joblib`` para que la
inferencia no tenga que reconstruir nada ni volver a mirar las etiquetas.

Selección de modelo
-------------------
Si no se fuerza un candidato, se elige por acierto leave-one-out entre el
catálogo. Ese acierto **está optimistamente sesgado** —se elige y se evalúa
sobre la misma validación— en torno a +0.02–0.04 con 17 candidatos y 72 casos
(Varma y Simon 2006). Se publica igualmente, junto al suelo de la regla de
guía, porque el sesgo afecta a todos los candidatos por igual y lo que se pide
de esta cifra es **ordenar**, no estimar.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import clone

from . import dataset_task2 as d2
from . import evaluation_multiclass as ev
from . import models_multiclass as mm
from .io import Case
from .uncertainty_multiclass import ladder_table


def _thin(estimator, n_estimators: int = 200):
    """Adelgaza el bosque interno antes de meterlo en el envoltorio de bagging.

    El envoltorio ya entrena ``n_members`` copias sobre remuestras distintas:
    esa es la fuente de varianza que la incertidumbre epistémica mide. Mantener
    además 1000 árboles por copia multiplica el coste por cinco sin añadir
    dispersión —un bosque grande converge y deja de disentir consigo mismo— y
    hace inviable medir la escalera fuera de muestra, que exige reentrenar el
    ensemble entero 72 veces.
    """
    est = clone(estimator)
    params = est.get_params()
    for key in params:
        if key.endswith("n_estimators") and isinstance(params[key], int) and params[key] > n_estimators:
            est.set_params(**{key: n_estimators})
    return est


def fit_expert(
    cases: list[Case],
    blocks: str,
    name: str,
    role: str,
    model_name: str | None = None,
    projector=None,
    n_members: int = 25,
    n_imputations: int = 10,
    estimator=None,
    candidates: list[str] | None = None,
) -> dict:
    X, names = d2.build_matrix(cases, blocks, projector=projector)
    y = d2.build_labels(cases)
    isup_col = names.index("bx_isup") if "bx_isup" in names else 0
    catalog = mm.build_catalog(isup_col=isup_col)

    # El suelo de guía se mide **siempre** sobre el bloque de grado, tenga o no
    # el experto acceso a él. `GradeRule` lee una columna por índice, así que
    # sobre un conjunto que no contenga `bx_isup` acabaría estratificando por
    # una variable arbitraria y devolvería un suelo sin sentido — el Experto 3,
    # que lee A+I, llegó a publicar 0.3056 por esta vía. El suelo es una
    # propiedad de la tarea, no del experto: es el mismo número para todos.
    X_rule, names_rule = d2.build_matrix(cases, "G", projector=projector)
    rule_estimator = mm.build_catalog(isup_col=names_rule.index("bx_isup"))["grade_rule"]

    # --- selección ---
    selection = []
    if estimator is not None:
        chosen, model_name = estimator, model_name or "custom"
    else:
        pool = candidates or [k for k in catalog if k != "prior_only"]
        if model_name:
            chosen = catalog[model_name]
        else:
            for cand in pool:
                P = ev.loo_probabilities(catalog[cand], X, y)
                m = ev.metrics(y, P)
                selection.append({"model": cand, **{k: round(v, 4) for k, v in m.items()}})
            selection.sort(key=lambda r: (-r["accuracy"], r["brier"]))
            model_name = selection[0]["model"]
            chosen = catalog[model_name]

    # --- rendimiento fuera de muestra del modelo elegido ---
    P_loo = ev.loo_probabilities(chosen, X, y)
    metrics = ev.metrics(y, P_loo)
    acc_lo, acc_hi = ev.bootstrap_ci(y, P_loo)
    P_cv = ev.cv_probabilities(chosen, X, y)
    metrics_cv = ev.metrics(y, P_cv)

    # --- suelo de guía, con el mismo protocolo ---
    P_rule = ev.loo_probabilities(rule_estimator, X_rule, y)
    rule = ev.metrics(y, P_rule)
    vs_rule = ev.paired_bootstrap(y, P_loo, P_rule)

    # --- envoltorio de incertidumbre y escalera, fuera de muestra ---
    wrapper = mm.MulticlassUncertaintyExpert(
        base_estimator=_thin(chosen), n_members=n_members, n_imputations=n_imputations
    )
    comp = d2.completeness_vector(cases)
    verdicts = _loo_verdicts(wrapper, X, y, comp)
    table = ladder_table(y, verdicts, {c: i for i, c in enumerate(d2.CLASSES)})

    wrapper.fit(X, y)
    return {
        "name": name,
        "role": role,
        "blocks": blocks,
        "model_name": model_name,
        "feature_names": names,
        "column_index": None,
        "model": wrapper,
        "classes": d2.CLASSES,
        "n_cases": len(cases),
        "loo_accuracy": round(metrics["accuracy"], 4),
        "metrics": {
            "loo": {k: round(v, 4) for k, v in metrics.items()},
            "loo_accuracy_ci": [round(acc_lo, 4), round(acc_hi, 4)],
            "cv": {k: round(v, 4) for k, v in metrics_cv.items()},
            "grade_rule_floor": {k: round(v, 4) for k, v in rule.items()},
            "vs_rule": {k: round(v, 4) for k, v in vs_rule.items()},
        },
        "ladder": table,
        "selection": selection,
        "loo_probabilities": P_loo,
        "confusion": ev.confusion(y, P_loo, d2.CLASSES),
    }


def _loo_verdicts(wrapper, X, y, completeness):
    """Veredictos leave-one-out del envoltorio completo.

    Se paga el coste de reentrenar el ensemble 72 veces porque la escalera es
    una promesa sobre datos no vistos: medirla dentro de muestra la haría
    parecer perfecta y no serviría para decidir cuándo abstenerse.
    """
    from sklearn.base import clone
    from sklearn.model_selection import LeaveOneOut

    out = []
    for tr, te in LeaveOneOut().split(X):
        w = clone(wrapper).fit(X[tr], y[tr])
        out.extend(w.verdicts(X[te], d2.CLASSES, completeness[te]))
    return out
