"""E03 — ¿las consultas por duda aportan más que un plan fijo? (PLAN §4.4, §11)

Versión fuera de línea, que es la que el PLAN autoriza para estudiar la utilidad
sin un agente en marcha: «Para estudiar su utilidad fuera de línea se reproducen
prefijos reales de lectura y se enmascaran también las features derivadas de lo
no leído».

Pregunta concreta: de los 72 casos de T2 en los que V1 abre **seis** secciones,
¿en cuántos cambia la decisión al abrirlas? Ésa es la cota superior del valor de
consultar. Lo que no cambia una decisión sólo puede justificarse por fidelidad
de la explicación, nunca por ranking.

Se mide además la utilidad **marginal por sección**: qué aporta cada documento
por separado sobre el panel, para saber si un plan fijo pequeño bastaría.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import make_pipeline

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
CLASES = ["active_surveillance", "active_treatment", "continued_surveillance", "watchful_waiting"]

# Bloque -> sección del EHR que hay que abrir para calcularlo.
SECCIONES = {"B": "laboratory_results", "C": "psa_trend", "D": "radiology_report",
             "E": "previous_notes", "H": "pathology_report", "I": "family_history"}


def main() -> None:
    warnings.filterwarnings("ignore")
    sys.path.insert(0, str(RAIZ))
    from delete_final_versions_task_V1_1.common.chimera_experts.io import load_cases
    from delete_final_versions_task_V1_1.common.chimera_experts import dataset_task2 as dt2
    from delete_final_versions_task_V2_2.evaluation import splits as sp

    casos = load_cases(RAIZ / "data/task2", task=2, labelled_only=True)
    por_id = {c.case_id: c for c in casos}
    ids = sorted(por_id); orden = {c: i for i, c in enumerate(ids)}
    y = np.array([dt2.label_index(por_id[c]) for c in ids])
    y_txt = [CLASES[i] for i in y]
    part = sp.cargar(2)
    plantilla = make_pipeline(SimpleImputer(strategy="median"),
                              RandomForestClassifier(n_estimators=300, max_depth=4,
                                                     min_samples_leaf=3,
                                                     class_weight="balanced", random_state=0))

    def oof(bloques):
        pred = np.empty(len(ids), dtype=object)
        X, _ = dt2.build_matrix([por_id[c] for c in ids], blocks=bloques)
        semilla = list(part["reparticiones"])[0]
        for p in part["reparticiones"][semilla]:
            tr = [orden[c] for c in p["train"]]; te = [orden[c] for c in p["test"]]
            m = clone(plantilla); m.fit(X[tr], y[tr])
            for i, yi in zip(te, m.predict(X[te])):
                pred[i] = CLASES[yi]
        return list(pred)

    panel = oof("AGJ")
    completo = oof("ABCDEGHIJ")

    cambian = [ids[i] for i in range(len(ids)) if panel[i] != completo[i]]
    aciertos_panel = sum(panel[i] == y_txt[i] for i in range(len(ids)))
    aciertos_comp = sum(completo[i] == y_txt[i] for i in range(len(ids)))
    arreglados = [c for c in cambian
                  if completo[orden[c]] == y_txt[orden[c]] and panel[orden[c]] != y_txt[orden[c]]]
    rotos = [c for c in cambian
             if panel[orden[c]] == y_txt[orden[c]] and completo[orden[c]] != y_txt[orden[c]]]

    r = {"alcance": "E03 fuera de línea: valor de consultar, medido como cambios de decisión",
         "casos": len(ids),
         "consultas_de_v1_por_caso": 6,
         "decisiones_que_cambian_al_abrir_los_6": len(cambian),
         "pct_casos_sin_cambio": round(100 * (len(ids) - len(cambian)) / len(ids), 2),
         "casos_arreglados": len(arreglados), "casos_rotos": len(rotos),
         "balance_neto": len(arreglados) - len(rotos),
         "aciertos_panel": aciertos_panel, "aciertos_completo": aciertos_comp,
         "utilidad_marginal_por_seccion": {}}

    base_f1 = f1_score(y_txt, panel, average="weighted", zero_division=0)
    for bloque, seccion in SECCIONES.items():
        p = oof("AGJ" + bloque)
        r["utilidad_marginal_por_seccion"][seccion] = {
            "bloque": bloque,
            "delta_f1_ponderado": round(
                f1_score(y_txt, p, average="weighted", zero_division=0) - base_f1, 5),
            "decisiones_cambiadas": sum(1 for i in range(len(ids)) if p[i] != panel[i]),
        }

    destino = AQUI / "reports" / "e03_consultas.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False))

    print(f"T2: {r['casos']} casos. V1 abre {r['consultas_de_v1_por_caso']} secciones en TODOS.")
    print(f"decisiones que cambian al abrirlas : {r['decisiones_que_cambian_al_abrir_los_6']}"
          f"  ({r['pct_casos_sin_cambio']}% de los casos no cambian)")
    print(f"  arregladas {r['casos_arreglados']}  ·  rotas {r['casos_rotos']}"
          f"  ·  balance {r['balance_neto']:+d}")
    print(f"\nutilidad marginal de cada sección sobre el panel:")
    print(f"{'sección':22} {'bloque':>7} {'Δ F1 pond.':>11} {'decisiones':>11}")
    for k, v in sorted(r["utilidad_marginal_por_seccion"].items(),
                       key=lambda kv: -kv[1]["delta_f1_ponderado"]):
        print(f"{k:22} {v['bloque']:>7} {v['delta_f1_ponderado']:+11.5f} {v['decisiones_cambiadas']:11}")
    print(f"\nescrito {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
