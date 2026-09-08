#!/usr/bin/env python3
"""Experto 5 — el estratificador: la cascada de guía de tres nodos.

No mejora el acierto del Experto 1 —nada lo mejora en esta cohorte— pero
**descompone** el 0.8611 en las tres preguntas que la guía encadena, y cada una
con su propio rendimiento medido. Esa descomposición es lo que la junta puede
usar: un veredicto de cuatro salidas no se puede rebatir; tres respuestas con
sus AUC sí.

    1. ¿Hay cáncer confirmado?      GH    ->  no: continued_surveillance
    2. ¿Está indicado tratar?       AGH   ->  no: active_surveillance
    3. ¿El paciente se beneficia?   AGI   ->  no: watchful_waiting

El nodo 3 se entrena y se publica **aunque esté en el azar**. Con 2 casos de
``watchful_waiting`` frente a 31 de ``active_treatment``, un AUC de 0.500 no es
un fallo del modelo: es la medida de que la cohorte no contiene la evidencia
para contestar esa pregunta. Publicarlo es lo que impide que la junta trate
como informado un veredicto que no lo está.

Uso::

    python train_expert_five.py
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
from sklearn.base import clone
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import LeaveOneOut, RepeatedStratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

from chimera_experts import dataset_task2 as d2  # noqa: E402
from chimera_experts import evaluation_multiclass as ev  # noqa: E402
from chimera_experts import features_wsi, models_multiclass as mm  # noqa: E402
from chimera_experts.cascade_task2 import GuidelineCascade, node_targets  # noqa: E402
from chimera_experts.io import load_cases  # noqa: E402
from chimera_experts.train_expert_task2 import _thin  # noqa: E402
from chimera_experts.uncertainty_multiclass import ladder_table  # noqa: E402

HERE = Path(__file__).resolve().parent
ART = HERE.parent / "train" / "artifacts"
NAME = "expert_five"
ROLE = "estratificador de guía en cascada"

#: Qué bloque contesta cada pregunta. Cada nodo ve lo que la guía mira para
#: contestarlo y nada más: el nodo de aptitud no debe ver el grado del tumor.
NODE_BLOCKS = {"cancer": "GH", "treat": "AGH", "fit": "AGI"}
UNION = "ACDGHIJK"

NODE_QUESTION = {
    "cancer": "¿hay cáncer confirmado en la biopsia?",
    "treat": "¿está indicado un tratamiento con intención curativa?",
    "fit": "¿el paciente se beneficiaría de ese tratamiento?",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[3] / "data" / "task2"))
    ap.add_argument("--model", default="extra_trees")
    ap.add_argument("--members", type=int, default=25)
    ap.add_argument("--imputations", type=int, default=10)
    ap.add_argument("--ladder-splits", type=int, default=4)
    ap.add_argument("--ladder-repeats", type=int, default=2)
    args = ap.parse_args()

    (HERE / "model").mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)

    all_cases = load_cases(args.data, task=2)
    cases = [c for c in all_cases if c.has_label]
    projector = features_wsi.EmbeddingProjector(8).fit(all_cases)
    X, names = d2.build_matrix(cases, UNION, projector=projector)
    y = d2.build_labels(cases)
    print(f"{NAME} | {ROLE} | {len(cases)} casos | matriz {X.shape}\n")

    def cols(blocks: str) -> list[int]:
        _, sub = d2.build_matrix(cases, blocks, projector=projector)
        return [names.index(n) for n in sub if n in names]

    isup = names.index("bx_isup") if "bx_isup" in names else 0
    base = mm.build_catalog(isup_col=isup)[args.model]
    node_cols = {n: cols(b) for n, b in NODE_BLOCKS.items()}

    # --- cada nodo, medido por separado ---
    print("### los tres nodos, leave-one-out y por separado")
    node_report = []
    for node, blocks in NODE_BLOCKS.items():
        t, mask = node_targets(y)[node]
        Xi = X[mask][:, node_cols[node]]
        p = np.zeros(len(t))
        for tr, te in LeaveOneOut().split(Xi):
            if len(np.unique(t[tr])) < 2:
                p[te] = t[tr].mean()
                continue
            p[te] = clone(base).fit(Xi[tr], t[tr]).predict_proba(Xi[te])[:, 1]
        auc = float(roc_auc_score(t, p)) if len(np.unique(t)) > 1 else float("nan")
        acc = float((((p >= 0.5).astype(int)) == t).mean())
        majority = float(max(t.mean(), 1 - t.mean()))
        node_report.append({"nodo": node, "pregunta": NODE_QUESTION[node], "bloques": blocks,
                            "n": int(len(t)), "positivos": int(t.sum()),
                            "auc": round(auc, 4), "acierto": round(acc, 4),
                            "suelo_mayoritaria": round(majority, 4)})
        flag = "  <-- en el azar: sin evidencia en la cohorte" if not (auc == auc) or auc <= 0.55 else ""
        print(f"  {node:7s} ({blocks:4s}) n={len(t):3d} pos={int(t.sum()):3d}  "
              f"AUC={auc:.3f}  acierto={acc:.3f}  suelo={majority:.3f}{flag}")

    # --- la cascada compuesta ---
    casc = GuidelineCascade(heads={n: clone(base) for n in NODE_BLOCKS}, columns=node_cols)
    P = ev.loo_probabilities(casc, X, y)
    metrics = ev.metrics(y, P)
    lo, hi = ev.bootstrap_ci(y, P)
    P_rule = ev.loo_probabilities(mm.build_catalog(isup_col=isup)["grade_rule"], X, y)
    rule = ev.metrics(y, P_rule)
    vs_rule = ev.paired_bootstrap(y, P, P_rule)

    print(f"\n### la cascada compuesta")
    print(f"  acierto LOO = {metrics['accuracy']:.4f}  IC95 [{lo:.3f}, {hi:.3f}]")
    print(f"  F1 macro    = {metrics['f1_macro']:.4f}   Brier = {metrics['brier']:.4f}  ECE = {metrics['ece']:.4f}")
    print(f"  suelo regla = {rule['accuracy']:.4f}   delta = {vs_rule['delta']:+.4f}  p = {vs_rule['p_two_sided']:.3f}")
    print("\n" + ev.confusion(y, P, d2.CLASSES))

    # --- escalera fuera de muestra ---
    comp = d2.completeness_vector(cases)
    # Los miembros del envoltorio llevan el bosque adelgazado, igual que los de
    # los otros cuatro expertos: el bagging ya aporta la dispersión entre
    # modelos, y mantener 1000 árboles por cabeza dentro de una cascada de tres
    # nodos multiplica el coste por quince sin añadir desacuerdo. Sin esto la
    # escalera de este experto no sale en un tiempo razonable, y además no
    # sería comparable con la de los demás.
    casc_thin = GuidelineCascade(heads={n: _thin(base) for n in NODE_BLOCKS}, columns=node_cols)
    wrapper = mm.MulticlassUncertaintyExpert(base_estimator=casc_thin, n_members=args.members,
                                             n_imputations=args.imputations)
    # La escalera se mide con **validación cruzada estratificada repetida** y no
    # con leave-one-out, que es lo que usan los otros cuatro expertos. El motivo
    # es de coste y está medido: cada miembro del envoltorio es una cascada de
    # tres tuberías, así que un LOO de 25 miembros son 5400 ajustes con
    # imputación iterativa sobre 184 columnas —más de dos horas sin terminar—,
    # frente a los 600 de 4x2 pliegues. Las dos estimaciones son fuera de
    # muestra; ésta entrena con el 75 % de los casos en vez del 98.6 %, así que
    # si difiere será por ser algo más **pesimista**, no al revés. Se declara en
    # el informe para que nadie compare esta fila con las de los demás como si
    # fueran la misma medida.
    ladder_protocol = f"repeated_stratified_cv_{args.ladder_splits}x{args.ladder_repeats}"
    seen: dict[int, object] = {}
    splitter = RepeatedStratifiedKFold(n_splits=args.ladder_splits,
                                       n_repeats=args.ladder_repeats, random_state=0)
    for tr, te in splitter.split(X, y):
        w = clone(wrapper).fit(X[tr], y[tr])
        for i, v in zip(te, w.verdicts(X[te], d2.CLASSES, comp[te])):
            seen.setdefault(int(i), v)
    # Un caso aparece una vez por repetición; se conserva el primer veredicto
    # para que la tabla tenga exactamente 72 filas y no 144.
    verdicts = [seen[i] for i in range(len(y))]
    table = ladder_table(y, verdicts, {c: i for i, c in enumerate(d2.CLASSES)})
    print(f"\n  escalera de fiabilidad (fuera de muestra, {ladder_protocol})")
    for row in table:
        print(f"    {row['ladder']:9s} {row['confidence']:11s} n={row['n']:3d} "
              f"acierto={row['accuracy']}  margen medio={row.get('mean_margin')}")

    wrapper.fit(X, y)
    bundle = {"name": NAME, "role": ROLE, "blocks": UNION, "model_name": f"cascade[{args.model}]",
              "feature_names": names, "column_index": None, "model": wrapper,
              "classes": d2.CLASSES, "n_cases": len(cases),
              "loo_accuracy": round(metrics["accuracy"], 4),
              "nodes": node_report, "node_blocks": NODE_BLOCKS,
              "metrics": {"loo": {k: round(v, 4) for k, v in metrics.items()},
                          "loo_accuracy_ci": [round(lo, 4), round(hi, 4)],
                          "grade_rule_floor": {k: round(v, 4) for k, v in rule.items()},
                          "vs_rule": {k: round(v, 4) for k, v in vs_rule.items()}},
              "ladder": table, "ladder_protocol": ladder_protocol, "selection": [],
              "confusion": ev.confusion(y, P, d2.CLASSES)}
    joblib.dump(bundle, HERE / "model" / f"{NAME}.joblib")
    (ART / f"{NAME}_report.json").write_text(
        json.dumps({k: v for k, v in bundle.items() if k != "model"}, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"\n  -> {HERE / 'model' / (NAME + '.joblib')}")


if __name__ == "__main__":
    main()
