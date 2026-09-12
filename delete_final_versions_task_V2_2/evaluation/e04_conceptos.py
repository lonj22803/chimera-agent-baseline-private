"""E04 — ¿aportan señal los conceptos verificados sobre el ancla? (PLAN §4.5, §11)

Ésta es la pregunta central de V2. Si la respuesta es no, el PLAN es explícito:
«Ancla sin corrector», y las correcciones de extracción se conservan sólo por
fidelidad, sin reclamar mejora de ranking.

Se ensayan exactamente las dos familias que el PLAN cierra (§4.5), ni una más:

1. **Modelo pequeño sobre conceptos**, con regularización fuerte.
2. **Corrección residual**, que conserva la predicción del ancla y sólo aprende
   el aporte de los conceptos nuevos. Como el ancla de T1 es una cascada de
   reglas sin probabilidad, se usa la variante con **ancla categórica**: su
   decisión entra como rasgo y la regularización decide cuánto puede moverla.

Anclas:
- **T1**: la decisión histórica de V1 (cascada de reglas). Es fija, así que no
  se reajusta por pliegue; su exposición histórica al corpus queda declarada.
- **T2**: la regla de grado con el mapeo aprendido en train (E02: 0,86111), que
  es el listón real, no el 0,847 del modelo completo.

Todo se mide con las particiones anidadas por grupo de `splits.py`, tres
semillas, y el corrector se entrena **sólo** dentro del train de cada pliegue.
"""
from __future__ import annotations

import json
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
HIST_T1 = RAIZ / "delete_final_versions_task" / "resultados" / "task_1" / "output" / "task1"

CLASES_T2 = ["active_surveillance", "active_treatment", "continued_surveillance", "watchful_waiting"]


def conceptos_de(caso, extraer) -> dict[str, float]:
    """Los hechos de V2 como rasgos numéricos, conservando 'desconocido'.

    Un concepto desconocido entra como NaN, **no como 0**: ésa es justo la
    distinción que V1 no podía representar y que E01 cuantificó en 468
    negativas documentadas frente a 3717 ausencias.
    """
    reg = extraer(caso.clinical, caso.case_id)
    f: dict[str, float] = {}
    for concepto in {h.concept for h in reg}:
        hechos = [h for h in reg.de(concepto) if h.status == "observed"]
        if not hechos:
            f[f"c_{concepto}"] = np.nan
            f[f"c_{concepto}_desconocido"] = 1.0
            continue
        f[f"c_{concepto}_desconocido"] = 0.0
        v = reg.valor(concepto)
        if v is None:
            f[f"c_{concepto}"] = np.nan
            f[f"c_{concepto}_conflicto"] = 1.0
        elif isinstance(v, bool):
            f[f"c_{concepto}"] = float(v)
        elif isinstance(v, (int, float)):
            f[f"c_{concepto}"] = float(v)
        elif isinstance(v, tuple):
            f[f"c_{concepto}_a"] = float(v[0]); f[f"c_{concepto}_b"] = float(v[1])
    f["n_conflictos"] = float(len(reg.conflictos()))
    f["n_hechos_observados"] = float(sum(1 for h in reg if h.status == "observed"))
    return f


def _matriz(dicts: list[dict]) -> tuple[np.ndarray, list[str]]:
    nombres = sorted({k for d in dicts for k in d})
    X = np.array([[d.get(n, np.nan) for n in nombres] for d in dicts], dtype=float)
    return X, nombres


def _familias():
    return {
        "logistica_fuerte": make_pipeline(
            SimpleImputer(strategy="median", add_indicator=False), StandardScaler(),
            LogisticRegression(max_iter=3000, C=0.1, class_weight="balanced")),
        "arbol_minusculo": make_pipeline(
            SimpleImputer(strategy="median"),
            DecisionTreeClassifier(max_depth=3, min_samples_leaf=8, class_weight="balanced",
                                   random_state=0)),
    }


def _puntuar(tarea, y_txt, pred):
    if tarea == 1:
        f1 = f1_score(y_txt, pred, pos_label="yes", zero_division=0)
        return {"exactitud": accuracy_score(y_txt, pred), "f1_yes": f1,
                "ranking_parcial": f1}
    f1 = f1_score(y_txt, pred, average="weighted", zero_division=0)
    return {"exactitud": accuracy_score(y_txt, pred), "f1_ponderado": f1,
            "f1_macro": f1_score(y_txt, pred, average="macro", zero_division=0),
            "ranking_parcial": f1}


def ancla_t1(ids) -> list[str]:
    salida = []
    for c in ids:
        f = HIST_T1 / c / "prostate-biopsy-decision.json"
        salida.append(json.loads(f.read_text()) if f.exists() else "no")
    return salida


def ancla_t2(prompts, y, tr, te) -> list[str]:
    def grado(p):
        try:
            return int(float(p.get("bx_isup")))
        except (TypeError, ValueError):
            return None
    por_grado: dict = {}
    for i in tr:
        por_grado.setdefault(grado(prompts[i]), Counter())[y[i]] += 1
    respaldo = Counter(y[i] for i in tr).most_common(1)[0][0]
    mapeo = {g: c.most_common(1)[0][0] for g, c in por_grado.items()}
    return [CLASES_T2[mapeo.get(grado(prompts[i]), respaldo)] for i in te]


def correr(tarea: int) -> dict:
    import sys
    sys.path.insert(0, str(RAIZ))
    from delete_final_versions_task_V1_1.common.chimera_experts.io import load_cases
    from delete_final_versions_task_V2_2.common.extractors import extraer_patologia
    from delete_final_versions_task_V2_2.evaluation import splits as sp
    if tarea == 1:
        from delete_final_versions_task_V1_1.common.chimera_experts import dataset as ds
        bloques_panel = "A"
    else:
        from delete_final_versions_task_V1_1.common.chimera_experts import dataset_task2 as ds
        bloques_panel = "AG"

    casos = load_cases(RAIZ / f"data/task{tarea}", task=tarea, labelled_only=True)
    por_id = {c.case_id: c for c in casos}
    ids = sorted(por_id)
    orden = {c: i for i, c in enumerate(ids)}
    part = sp.cargar(tarea)
    prompts = [por_id[c].prompt for c in ids]

    if tarea == 1:
        etq = {c: json.loads((RAIZ / f"data/task1/ground_truth/{c}/prostate-biopsy-decision.json").read_text())
               for c in ids}
        y_txt = [etq[c] for c in ids]
        y = np.array([1 if v == "yes" else 0 for v in y_txt])
        clases = ["no", "yes"]
    else:
        y = np.array([ds.label_index(por_id[c]) for c in ids])
        clases = CLASES_T2
        y_txt = [clases[i] for i in y]

    X_panel, _ = ds.build_matrix([por_id[c] for c in ids], blocks=bloques_panel)
    X_con, nombres_con = _matriz([conceptos_de(por_id[c], extraer_patologia) for c in ids])

    con_informe = sum(1 for c in ids if (por_id[c].clinical or {}).get("pathology_report", "").strip())
    r = {"tarea": tarea, "casos": len(ids), "columnas_conceptos": len(nombres_con),
         "columnas_panel": X_panel.shape[1],
         "casos_con_informe_de_patologia": con_informe, "resultados": {}}

    # --- Ancla ---
    if tarea == 1:
        pred_ancla_global = ancla_t1(ids)
        m = _puntuar(tarea, y_txt, pred_ancla_global)
        r["resultados"]["ancla"] = {k: round(v, 5) for k, v in m.items()}
        r["resultados"]["ancla"]["nota"] = ("cascada de reglas de V1, fija; su exposición "
                                            "histórica al corpus queda declarada")
    else:
        acc = []
        for semilla, pliegues in part["reparticiones"].items():
            pred = np.empty(len(ids), dtype=object)
            for p in pliegues:
                tr = [orden[c] for c in p["train"]]; te = [orden[c] for c in p["test"]]
                for i, v in zip(te, ancla_t2(prompts, y, tr, te)):
                    pred[i] = v
            acc.append(_puntuar(tarea, y_txt, list(pred)))
        r["resultados"]["ancla"] = {k: round(float(np.mean([a[k] for a in acc])), 5)
                                    for k in acc[0]}
        pred_ancla_global = list(pred)

    # --- Candidatos ---
    # One-hot, no ordinal: la decisión del ancla es nominal. Codificarla como
    # 0..3 le impondría un orden inexistente y hundiría al corrector por un
    # fallo de codificación, no por falta de señal.
    ancla_num = np.zeros((len(ids), len(clases)))
    for i, p in enumerate(pred_ancla_global):
        ancla_num[i, clases.index(p)] = 1.0

    conjuntos = {
        "conceptos_solos": X_con,
        "panel_mas_conceptos": np.hstack([X_panel, X_con]),
        "residual_ancla_mas_conceptos": np.hstack([ancla_num, X_con]),
    }

    for nombre_conjunto, X in conjuntos.items():
        for nombre_familia, plantilla in _familias().items():
            metricas = []
            for semilla, pliegues in part["reparticiones"].items():
                pred = np.empty(len(ids), dtype=object)
                for p in pliegues:
                    tr = [orden[c] for c in p["train"]]; te = [orden[c] for c in p["test"]]
                    mdl = clone(plantilla)
                    mdl.fit(X[tr], y[tr])
                    for i, yi in zip(te, mdl.predict(X[te])):
                        pred[i] = clases[int(yi)]
                metricas.append(_puntuar(tarea, y_txt, list(pred)))
            r["resultados"][f"{nombre_conjunto}|{nombre_familia}"] = {
                k: round(float(np.mean([m[k] for m in metricas])), 5) for k in metricas[0]}
            r["resultados"][f"{nombre_conjunto}|{nombre_familia}"]["por_semilla"] = [
                round(m["ranking_parcial"], 5) for m in metricas]
    return r


def main() -> None:
    warnings.filterwarnings("ignore")
    salida = {"alcance": "E04: ancla vs conceptos verificados, validación anidada por grupo"}
    for tarea in (1, 2):
        r = correr(tarea)
        salida[f"task{tarea}"] = r
        base = r["resultados"]["ancla"]["ranking_parcial"]
        print(f"\n=== TAREA {tarea} — {r['casos']} casos, {r['columnas_conceptos']} columnas de conceptos, "
              f"{r['casos_con_informe_de_patologia']} con informe de patología")
        print(f"{'política':42} {'métrica':>9} {'Δ ancla':>9}")
        for k, v in r["resultados"].items():
            d = v["ranking_parcial"] - base
            marca = "" if k == "ancla" else ("  MEJORA" if d >= 0.005 else "")
            print(f"{k:42} {v['ranking_parcial']:9.5f} {d:+9.5f}{marca}")
    destino = AQUI / "reports" / "e04_conceptos.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, indent=2, ensure_ascii=False))
    print(f"\nescrito {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
