"""E02 — ¿el panel de T2 evita las consultas rutinarias? (PLAN §6.1, §11)

La ruta de V1 abre **seis secciones en todos los casos** y declara
`reveal_sequence: []`. Corregir la declaración cuesta 0,00587 de ranking T2
(ver E00). La salida que propone el PLAN no es seguir ocultando consultas, sino
comprobar si el panel inicial —40 campos, con `bx_isup`, `bx_gl_prim`,
`bx_gl_sec`, `ipss`, `note_sections`— basta para decidir.

Se comparan tres políticas **cerradas**, todas bajo la misma validación anidada
por grupo de `splits.py`:

- **ancla ISUP**: la regla de grado sola, sin aprender nada.
- **panel**: bloques que salen de `structured-prompt.json` y de los embeddings,
  que llegan sin llamar a ninguna herramienta (A, G, J).
- **completo**: lo anterior más lo que exige abrir documentos (B, C, D, E, H, I).

Medición: exactitud, F1 ponderado y F1 macro fuera de muestra, más el resultado
por clase. El PLAN avisa: «Se admite una ruta más corta con las mismas
decisiones si ahorra recursos y conserva explicación fiel; no se la presenta
como mejora predictiva».
"""
from __future__ import annotations

import json
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent

BLOQUES_PANEL = "AGJ"        # llegan en el socket; cero herramientas
BLOQUES_COMPLETO = "ABCDEGHIJ"  # incluye las seis secciones del EHR

CLASES = ["active_surveillance", "active_treatment", "continued_surveillance", "watchful_waiting"]


def _modelos():
    return {
        "logistica_regularizada": make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(),
            LogisticRegression(max_iter=2000, C=0.3, class_weight="balanced")),
        "bosque_pequeno": make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(n_estimators=300, max_depth=4, min_samples_leaf=3,
                                   class_weight="balanced", random_state=0)),
    }


def ancla_isup_entrenada(prompts, y, tr, te):
    """Regla de grado, con el mapeo grado -> clase **aprendido en train**.

    Escribir el mapeo a mano fue un error medido: una regla inventada
    (ISUP>=2 -> tratar) da 0,306 de exactitud en este corpus. El PLAN ya lo
    advierte para T2: «Se documentarán los usos con datos de train antes de
    aprender el mapeo de estados a clases». Así que el ancla aprende, dentro
    del pliegue, qué clase es mayoritaria para cada grado, y los grados no
    vistos caen en la clase mayoritaria global de ese train.
    """
    def grado(p):
        try:
            return int(float(p.get("bx_isup")))
        except (TypeError, ValueError):
            return None

    por_grado = {}
    for i in tr:
        g = grado(prompts[i])
        por_grado.setdefault(g, Counter())[y[i]] += 1
    respaldo = Counter(y[i] for i in tr).most_common(1)[0][0]
    mapeo = {g: c.most_common(1)[0][0] for g, c in por_grado.items()}
    return [CLASES[mapeo.get(grado(prompts[i]), respaldo)] for i in te]


def main() -> None:
    import sys
    sys.path.insert(0, str(RAIZ))
    warnings.filterwarnings("ignore")
    from delete_final_versions_task_V1_1.common.chimera_experts.io import load_cases
    from delete_final_versions_task_V1_1.common.chimera_experts import dataset_task2 as dt2
    from delete_final_versions_task_V2_2.evaluation import splits as sp

    casos = load_cases(RAIZ / "data/task2", task=2, labelled_only=True)
    por_id = {c.case_id: c for c in casos}
    part = sp.cargar(2)
    ids = sorted(por_id)
    y = np.array([dt2.label_index(por_id[c]) for c in ids])
    orden = {c: i for i, c in enumerate(ids)}
    prompts = [por_id[c].prompt for c in ids]

    matrices = {}
    for etiqueta, bloques in (("panel", BLOQUES_PANEL), ("completo", BLOQUES_COMPLETO)):
        X, nombres = dt2.build_matrix([por_id[c] for c in ids], blocks=bloques)
        matrices[etiqueta] = (X, nombres)

    r = {"alcance": "E02: panel vs completo bajo la MISMA validación anidada por grupo",
         "bloques": {"panel": BLOQUES_PANEL, "completo": BLOQUES_COMPLETO},
         "columnas": {k: len(v[1]) for k, v in matrices.items()},
         "resultados": {}}

    y_txt = [CLASES[i] for i in y]

    # Ancla ISUP, con el mismo protocolo anidado que todo lo demás.
    acc, f1w, f1m = [], [], []
    for semilla, pliegues in part["reparticiones"].items():
        pred = np.empty(len(ids), dtype=object)
        for p in pliegues:
            tr = [orden[c] for c in p["train"]]
            te = [orden[c] for c in p["test"]]
            for i, v in zip(te, ancla_isup_entrenada(prompts, y, tr, te)):
                pred[i] = v
        acc.append(accuracy_score(y_txt, list(pred)))
        f1w.append(f1_score(y_txt, list(pred), average="weighted", zero_division=0))
        f1m.append(f1_score(y_txt, list(pred), average="macro", zero_division=0))
    r["resultados"]["ancla_isup"] = {
        "exactitud_media": round(float(np.mean(acc)), 5),
        "exactitud_por_semilla": [round(x, 5) for x in acc],
        "f1_ponderado_medio": round(float(np.mean(f1w)), 5),
        "f1_ponderado_por_semilla": [round(x, 5) for x in f1w],
        "f1_macro_medio": round(float(np.mean(f1m)), 5),
        "nota": "mapeo grado->clase aprendido dentro de cada pliegue de train",
    }

    for etiqueta, (X, nombres) in matrices.items():
        for nombre_modelo, plantilla in _modelos().items():
            acc, f1w, f1m = [], [], []
            preds_todas = np.empty(len(ids), dtype=object)
            for semilla, pliegues in part["reparticiones"].items():
                pred = np.empty(len(ids), dtype=object)
                for p in pliegues:
                    tr = [orden[c] for c in p["train"]]
                    te = [orden[c] for c in p["test"]]
                    from sklearn.base import clone
                    m = clone(plantilla)
                    m.fit(X[tr], y[tr])
                    for i, yi in zip(te, m.predict(X[te])):
                        pred[i] = CLASES[yi]
                acc.append(accuracy_score(y_txt, list(pred)))
                f1w.append(f1_score(y_txt, list(pred), average="weighted", zero_division=0))
                f1m.append(f1_score(y_txt, list(pred), average="macro", zero_division=0))
                preds_todas = pred  # la última semilla, para el informe por clase
            r["resultados"][f"{etiqueta}|{nombre_modelo}"] = {
                "exactitud_media": round(float(np.mean(acc)), 5),
                "exactitud_por_semilla": [round(x, 5) for x in acc],
                "f1_ponderado_medio": round(float(np.mean(f1w)), 5),
                "f1_ponderado_por_semilla": [round(x, 5) for x in f1w],
                "f1_macro_medio": round(float(np.mean(f1m)), 5),
                "informe_ultima_semilla": classification_report(
                    y_txt, list(preds_todas), zero_division=0, output_dict=True),
            }

    destino = AQUI / "reports" / "e02_panel_t2.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False))

    print(f"columnas: panel={r['columnas']['panel']}  completo={r['columnas']['completo']}")
    print(f"\n{'política':34} {'exactitud':>10} {'F1 pond.':>10} {'F1 macro':>10}")
    for k, v in r["resultados"].items():
        a = v.get("exactitud_media", v.get("exactitud"))
        w = v.get("f1_ponderado_medio", v.get("f1_ponderado"))
        m = v.get("f1_macro_medio", v.get("f1_macro"))
        print(f"{k:34} {a:10.5f} {w:10.5f} {m:10.5f}")
    print(f"\nescrito {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
