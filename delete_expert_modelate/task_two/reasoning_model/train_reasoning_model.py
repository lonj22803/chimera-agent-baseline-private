#!/usr/bin/env python3
"""Experto 5 — la traza de razonamiento: ``confidence`` y ``variable_weights``.

Pasada la puerta de la decisión, el 82.5 % restante del ``case_score`` se juega
en el formulario. Este experto lo rellena, y lo hace midiendo cada casilla
contra su propia constante con la métrica que el reto usa —distancia ordinal,
no acierto exacto— y adoptando el modelo aprendido sólo donde la bate.

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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.reasoning_task2 import (  # noqa: E402
    CONFIDENCE_LEVELS, TASK2_VARIABLES, WEIGHT_VALUE, ReasoningTraceModel,
)

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "train" / "artifacts"


def composite(cases, model) -> dict:
    """Los cuatro componentes del ``case_score`` que dependen del formulario.

    Se calculan tal y como los calcula ``evaluation/evaluate.py``: la distancia
    ordinal para los pesos y la confianza, el F1 de conjuntos para los factores
    *important*/*decisive*, y el *grounding* de secciones con la lista de
    revelaciones vacía que esta tarea exige.
    """
    always = {"psa", "age"}
    gradable = {"pirads", "psad", "cspca", "ct", "bx_isup", "bx_gl_prim", "bx_gl_sec", "fh"}
    conf_val = {"clear": 0, "borderline": 1, "uncertain": 2}
    vw, f1, sg, cf = [], [], [], []
    for c in cases:
        gt = c.reasoning or {}
        pr = model.predict_trace(c)
        gw, pw = gt.get("variable_weights") or {}, pr["variable_weights"]
        if gw:
            vw.append(1 - np.mean([abs(WEIGHT_VALUE[v] - WEIGHT_VALUE[pw.get(k, "not_used")]) / 3
                                   for k, v in gw.items() if v in WEIGHT_VALUE]))
        gs = {k for k, v in gw.items() if WEIGHT_VALUE.get(v, 0) >= 2}
        ps = {k for k, v in pw.items() if WEIGHT_VALUE.get(v, 0) >= 2}
        tp = len(gs & ps)
        f1.append(1.0 if not gs and not ps else (0.0 if tp == 0 else 2 * tp / (len(gs) + len(ps))))
        act = {k for k, v in pw.items() if WEIGHT_VALUE.get(v, 0) > 0}
        g, u = len(act & always), len(act & gradable)
        if g + u:
            sg.append(g / (g + u))
        if gt.get("confidence") in conf_val:
            cf.append(1 - abs(conf_val[gt["confidence"]] - conf_val[pr["confidence"]]) / 2)
    return {"variable_weight_score": float(np.mean(vw)), "important_decisive_f1": float(np.mean(f1)),
            "section_grounding": float(np.mean(sg)), "confidence_score": float(np.mean(cf)),
            "tool_score": 1.0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data" / "task2"))
    args = ap.parse_args()
    (HERE / "model").mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)

    cases = [c for c in load_cases(args.data, task=2) if c.has_label and c.reasoning]
    print(f"Experto 5 | traza de razonamiento | {len(cases)} trazas\n")

    model = ReasoningTraceModel().fit(cases)

    print(f'{"casilla":14s}{"LOO":>9s}{"constante":>11s}   {"valor":12s} adoptado')
    for r in model.report():
        print(f'{r["campo"]:14s}{r["loo"]:>9.4f}{r["moda"]:>11.4f}   {str(r["moda_valor"]):12s} {r["aprendido"]}')

    comp = composite(cases, model)
    print("\ncomponentes del case_score que dependen del formulario (dentro de muestra)")
    for k, v in comp.items():
        print(f"  {k:26s} {v:.4f}")
    no_judge = (0.225 * comp["confidence_score"] + 0.275 * comp["variable_weight_score"]
                + 0.175 * comp["important_decisive_f1"] + 0.150 * comp["tool_score"]
                + 0.175 * comp["section_grounding"])
    print(f"\n  suma ponderada sin juez de razonamiento: {no_judge:.4f}")
    print("  (el ``case_score`` real la multiplica por la puerta de la decisión:")
    print("   un caso con la conducta equivocada puntúa 0 aunque el formulario sea perfecto)")

    joblib.dump(model, HERE / "model" / "reasoning_task2.joblib")
    (ART / "reasoning_task2_report.json").write_text(
        json.dumps({"cells": model.report(), "composite": comp}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"\n  -> {HERE / 'model' / 'reasoning_task2.joblib'}")


if __name__ == "__main__":
    main()
