#!/usr/bin/env python3
"""Entrenamiento del Experto 2 — proyector de PSA.

Compara los regresores candidatos sobre el conjunto de prefijos y guarda el
ganador junto con los residuos out-of-fold que calibran el intervalo conforme.

Protocolo: validación cruzada **agrupada por paciente** (``GroupKFold``, 5
particiones × 6 semillas). Agrupar es obligatorio: dos prefijos del mismo
paciente comparten casi toda la serie, y separarlos entre entrenamiento y test
inflaría la métrica sin que nada lo delate.

Además de MAE y RMSE se reporta la **cobertura empírica** del intervalo al
95 %: un intervalo que dice 95 % y cubre el 70 % es peor que no dar intervalo.

Salidas en ``model/``:

``expert_two_psa_projector.joblib``  modelo, residuos de calibración, metadatos
``../train/artifacts/psa_projector_bakeoff.csv``  comparación de regresores
``../train/artifacts/psa_projector_coverage.csv``  cobertura por método
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
# Los procesos hijo de joblib no heredan el filtro; sin esto el log se llena.
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from sklearn.base import clone  # noqa: E402
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor  # noqa: E402
from sklearn.experimental import enable_iterative_imputer  # noqa: F401,E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import BayesianRidge, HuberRegressor, RidgeCV  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from chimera_experts.evaluation import SEED  # noqa: E402
from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.psa_projector import AnchoredRegressor, build_training_set, jackknife_plus_interval  # noqa: E402

ART = Path(__file__).resolve().parents[1] / "train" / "artifacts"
MODEL_DIR = Path(__file__).resolve().parent / "model"


def _pipe(est):
    return Pipeline(
        [("impute", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler()), ("reg", est)]
    )


def catalog(seed: int = SEED, anchor_index: int | None = None) -> dict:
    cat = {
        # Suelos: lo que hay que batir para justificar cualquier aprendizaje.
        "naive_last_value": "LAST",
        "loglinear_extrapolation": "OLS",
        # Lineales sobre las variables de trayectoria.
        "ridge": _pipe(RidgeCV(alphas=np.logspace(-3, 3, 25))),
        "bayesian_ridge": _pipe(BayesianRidge()),
        "huber": _pipe(HuberRegressor(epsilon=1.35, max_iter=2000)),
        # No lineales.
        "random_forest": _pipe(RandomForestRegressor(n_estimators=600, min_samples_leaf=3, random_state=seed, n_jobs=-1)),
        "extra_trees": _pipe(ExtraTreesRegressor(n_estimators=600, min_samples_leaf=3, random_state=seed, n_jobs=-1)),
        "grad_boosting": _pipe(GradientBoostingRegressor(n_estimators=300, max_depth=2, learning_rate=0.05, random_state=seed)),
    }
    if anchor_index is not None:
        # Variantes ancladas: el regresor aprende el incremento sobre log(PSA)
        # de la última medida en lugar del nivel absoluto. Sin esto, un
        # ensemble de árboles arrastra los PSA extremos hacia el centro de la
        # cohorte y llega a proyectar descensos en pacientes cuyo PSA se
        # dispara. Véase AnchoredRegressor.
        for base in ("ridge", "huber", "random_forest", "extra_trees", "grad_boosting"):
            cat[f"{base}_anchored"] = AnchoredRegressor(cat[base], anchor_index)
    return cat


def grouped_oof(est, X, y, groups, names, n_splits=5, n_repeats=6, seed=SEED) -> np.ndarray:
    """Predicciones out-of-fold agrupadas por paciente, promediadas sobre semillas."""
    if isinstance(est, str):
        # Los suelos no se entrenan: se leen directamente de las variables.
        col = names.index("log_last" if est == "LAST" else "loglinear_forecast")
        return np.tile(X[:, col], (n_repeats, 1))
    out = np.full((n_repeats, len(y)), np.nan)
    uniq = np.unique(groups)
    for r in range(n_repeats):
        rng = np.random.default_rng(seed + r)
        perm = rng.permutation(uniq)
        order = {g: i for i, g in enumerate(perm)}
        shuffled = np.array([order[g] for g in groups])
        for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups=shuffled):
            m = clone(est).fit(X[tr], y[tr])
            out[r, te] = m.predict(X[te])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data_filtered" / "task1"))
    ap.add_argument("--repeats", type=int, default=6)
    args = ap.parse_args()

    ART.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Se usan los 195 casos: el proyector de PSA no necesita la etiqueta de
    # biopsia, así que los 104 casos sin ground truth también entrenan.
    cases = load_cases(args.data, task=1)
    X, y, groups, names = build_training_set(cases)
    print(f"Casos: {len(cases)}  ejemplos (prefijos): {len(y)}  pacientes distintos: {len(set(groups))}")
    print(f"Variables: {len(names)}  |  log(PSA) objetivo: media {y.mean():.2f} sd {y.std():.2f}\n")

    anchor_index = names.index("log_last")
    rows, oof_store = [], {}
    for name, est in catalog(anchor_index=anchor_index).items():
        oof = grouped_oof(est, X, y, groups, names, n_repeats=args.repeats)
        p = np.nanmean(oof, axis=0)
        resid = y - p
        mae_log = float(np.mean(np.abs(resid)))
        rmse_log = float(np.sqrt(np.mean(resid**2)))
        # Error relativo en escala natural: exp(|residuo log|) - 1.
        med_rel = float(np.median(np.expm1(np.abs(resid))))
        rows.append(
            {
                "model": name,
                "mae_log": mae_log,
                "rmse_log": rmse_log,
                "median_relative_error": med_rel,
                "r2_log": float(1 - np.sum(resid**2) / np.sum((y - y.mean()) ** 2)),
                "oof_sd_across_repeats": float(np.nanmean(np.nanstd(oof, axis=0))),
            }
        )
        hi = y > np.log(50.0)
        rows[-1]["mae_log_psa_gt50"] = float(np.mean(np.abs(resid[hi]))) if hi.any() else float("nan")
        rows[-1]["bias_log_psa_gt50"] = float(np.mean(resid[hi])) if hi.any() else float("nan")
        oof_store[name] = p
        print(f"  {name:26s} MAE(log)={mae_log:.3f}  RMSE(log)={rmse_log:.3f}  err.rel.mediano={med_rel:6.1%}  R2={rows[-1]['r2_log']:.3f}")

    df = pd.DataFrame(rows).sort_values("mae_log").reset_index(drop=True)
    df.to_csv(ART / "psa_projector_bakeoff.csv", index=False)
    champion = df.iloc[0]["model"]
    print(f"\nCampeón: {champion}")

    # --- Cobertura del intervalo: conforme frente al de Student ---------------
    cov_rows = []
    for name in df["model"]:
        resid = y - oof_store[name]
        # Jackknife+ : el cuantil se calcula excluyendo el propio caso, de modo
        # que la cobertura medida no está contaminada por su propio residuo.
        hits, widths = [], []
        for i in range(len(y)):
            mask = np.ones(len(y), dtype=bool)
            mask[i] = False
            lo, hi = jackknife_plus_interval(resid[mask], oof_store[name][i], alpha=0.05)
            hits.append(lo <= y[i] <= hi)
            widths.append(hi - lo)
        cov_rows.append(
            {
                "model": name,
                "interval": "jackknife_plus_95",
                "empirical_coverage": float(np.mean(hits)),
                "median_width_log": float(np.median(widths)),
                "median_width_ratio": float(np.exp(np.median(widths) / 2)),
            }
        )
        print(f"  cobertura {name:26s} {cov_rows[-1]['empirical_coverage']:.3f}  (anchura x{cov_rows[-1]['median_width_ratio']:.2f})")
    pd.DataFrame(cov_rows).to_csv(ART / "psa_projector_coverage.csv", index=False)

    # --- Ajuste final sobre todos los ejemplos -------------------------------
    est = catalog(anchor_index=anchor_index)[champion]
    if isinstance(est, str):
        final = None
    else:
        final = clone(est).fit(X, y)
    resid_final = y - oof_store[champion]

    joblib.dump(
        {
            "model": final,
            "fallback": champion if isinstance(catalog(anchor_index=anchor_index)[champion], str) else None,
            "feature_names": names,
            "calibration_residuals_log": resid_final,
            "champion": champion,
            "n_examples": int(len(y)),
            "n_patients": int(len(set(groups))),
            "seed": SEED,
            "bakeoff": df.to_dict("records"),
            "coverage": cov_rows,
        },
        MODEL_DIR / "expert_two_psa_projector.joblib",
        compress=3,
    )
    print(f"\nGuardado en {MODEL_DIR / 'expert_two_psa_projector.joblib'}")


if __name__ == "__main__":
    main()
