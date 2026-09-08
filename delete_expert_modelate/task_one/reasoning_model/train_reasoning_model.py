#!/usr/bin/env python3
"""Entrena el modelo de la traza de razonamiento (Experto 4).

Predice las tres casillas que el *case score* puntúa además de la decisión:
``confidence``, ``variable_weights`` y ``reveal_sequence``. Un clasificador
multinomial por casilla, y una puerta de LOOCV que sólo conserva el modelo de
las casillas que baten a "predecir siempre la moda".

Uso::

    python train_reasoning_model.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.reasoning_model import ReasoningTraceModel  # noqa: E402

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "train" / "artifacts"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data_filtered" / "task1"))
    ap.add_argument("--min-gain", type=float, default=0.03)
    args = ap.parse_args()

    (HERE / "model").mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)

    cases = [c for c in load_cases(args.data, task=1) if c.reasoning]
    print(f"Trazas del urólogo disponibles: {len(cases)}\n")

    model = ReasoningTraceModel(min_gain=args.min_gain).fit(cases)
    m = model.metrics_
    hybrid = model.hybrid_loo_accuracy(cases)

    rows = []
    for name, v in sorted(m.items(), key=lambda kv: -kv[1]["gain"]):
        rows.append(
            {
                "target": name,
                "n": v["n"],
                "loo_accuracy_model": round(v["loo_accuracy"], 4),
                "majority_baseline": round(v["majority_baseline"], 4),
                "gain": round(v["gain"], 4),
                "model_kept": name in model.kept_,
                "hybrid_accuracy": round(hybrid[name], 4),
            }
        )
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    print(f"\nCasillas con modelo aprendido ({len(model.kept_)} de {len(m)}): {', '.join(model.kept_)}")
    print(f"\nacierto medio  híbrido = {np.mean(list(hybrid.values())):.3f}")
    print(f"acierto medio  sólo-moda = {df['majority_baseline'].mean():.3f}")
    print(f"acierto medio  modelo puro = {df['loo_accuracy_model'].mean():.3f}")

    df.to_csv(ART / "reasoning_model_loo.csv", index=False)
    joblib.dump({"model": model, "metrics": m, "kept": model.kept_}, HERE / "model" / "reasoning_trace_model.joblib", compress=3)
    (ART / "reasoning_model_summary.json").write_text(
        json.dumps(
            {
                "n_traces": len(cases),
                "kept": model.kept_,
                "min_gain": args.min_gain,
                "mean_hybrid": float(np.mean(list(hybrid.values()))),
                "mean_majority": float(df["majority_baseline"].mean()),
                "mean_model_only": float(df["loo_accuracy_model"].mean()),
            },
            indent=2,
        )
    )
    print(f"\nGuardado en {HERE / 'model' / 'reasoning_trace_model.joblib'}")


if __name__ == "__main__":
    main()
