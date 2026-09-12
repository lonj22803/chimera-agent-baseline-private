"""E06 y E07 — ancla clínica, residuo por modalidad y curva de supervivencia.

E06 (PLAN §7.1): sólo las tres composiciones que el PLAN cierra —ancla sola;
ancla más conceptos clínicos; ancla más conceptos y residuo de modalidades—.
Presupuesto: 3–5 grados de libertad efectivos en total, no cinco por modalidad.

E07 (PLAN §7.3): derivar meses de una curva `S(t|x)` en vez de un mapa, y medir
si mejora la interpretación temporal **sobre los meses realmente exportados**.

Diferencia con la medición de V1: aquí se usa la validación anidada **por
grupo** de `splits.py`, con 5 pliegues exteriores y 3 semillas, en vez del
dev/val histórico. Con 19 eventos en 75 casos, cualquier cifra de aquí lleva una
incertidumbre grande y así se informa.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent


def km_basal(t, e):
    """Riesgo basal de entrenamiento por Kaplan–Meier. Sin dependencias externas."""
    orden = np.argsort(t)
    t, e = np.asarray(t)[orden], np.asarray(e)[orden]
    n = len(t)
    pasos, S = [], 1.0
    for i, ti in enumerate(t):
        if e[i] != 1:
            continue
        en_riesgo = n - i
        if en_riesgo > 0:
            S *= (1 - 1 / en_riesgo)
            pasos.append((float(ti), S))
    return pasos


def mediana_o_rmst(pasos, lp, horizonte):
    """Tiempo resumen de la curva: mediana si cruza 0,5; si no, RMST al horizonte.

    El PLAN lo pide así: «mediana si la curva cruza 0,5; si no lo hace, declarar
    internamente que no es estimable y usar una convención de exportación
    validada». RMST es tiempo medio restringido sin evento, **no** una fecha
    individual de recurrencia.
    """
    if not pasos:
        return horizonte
    hr = float(np.exp(lp))
    prev_t, prev_S, area = 0.0, 1.0, 0.0
    for ti, S0 in pasos:
        S = S0 ** hr
        if prev_S >= 0.5 > S:
            # interpolación lineal en el tramo donde cruza
            frac = (prev_S - 0.5) / (prev_S - S) if prev_S > S else 0.0
            return float(prev_t + frac * (ti - prev_t))
        area += prev_S * (min(ti, horizonte) - prev_t)
        prev_t, prev_S = ti, S
        if prev_t >= horizonte:
            break
    area += prev_S * max(0.0, horizonte - prev_t)
    return float(area)


def main() -> None:
    warnings.filterwarnings("ignore")
    sys.path.insert(0, str(RAIZ))
    from delete_final_versions_task_V1_1.common.chimera_experts.io import load_cases
    from delete_final_versions_task_V1_1.common.chimera_experts import dataset_task3 as ds
    from delete_final_versions_task_V1_1.task_3.experts_3.train import protocol as P
    from delete_final_versions_task_V2_2.evaluation.referencias import cargar_evaluador, EVAL_POR_DEFECTO
    from delete_final_versions_task_V2_2.evaluation import splits as sp
    from delete_final_versions_task_V2_2.evaluation.e05_mapa_t3 import mapa_cdf, mapa_continuo
    ev = cargar_evaluador(EVAL_POR_DEFECTO)

    casos = load_cases(RAIZ / "data/task3", 3, labelled_only=True)
    por_id = {c.case_id: c for c in casos}
    ids = sorted(por_id)
    orden = {c: i for i, c in enumerate(ids)}
    t = np.array([por_id[c].label["months_to_recurrence"] for c in ids], float)
    e = np.array([por_id[c].label["event"] for c in ids], int)
    capra = np.array([ds._surgical(por_id[c])["capra_s"] for c in ids], float)
    part = sp.cargar(3)
    horizonte = float(np.percentile(t, 90))

    COMPOSICIONES = {
        "ancla_capra_sola": None,
        "ancla_mas_conceptos_clinicos": "SG",
        "ancla_conceptos_y_residuo_modalidades": "ASGDE",
    }

    r = {"alcance": "E06/E07 con validación anidada por grupo, 5x3 pliegues, 3 semillas",
         "eventos": int(e.sum()), "casos": len(ids), "horizonte_rmst_meses": round(horizonte, 1),
         "e06_riesgo": {}, "e07_meses_exportados": {}}

    riesgos_por_comp = {}
    for nombre, bloques in COMPOSICIONES.items():
        c_idx, pares = [], []
        riesgo_medio = np.zeros(len(ids))
        for semilla, pliegues in part["reparticiones"].items():
            pred = np.empty(len(ids))
            for p in pliegues:
                tr = [orden[c] for c in p["train"]]; te = [orden[c] for c in p["test"]]
                if bloques is None:
                    pred[te] = -capra[te]
                else:
                    x, nombres = ds.build_matrix([por_id[c] for c in p["train"]], bloques,
                                                 drop_constant=False)
                    xt, _ = ds.build_matrix([por_id[c] for c in p["test"]], bloques,
                                            drop_constant=False)
                    try:
                        m = P.CoxPipeline().fit(x, t[tr], e[tr], nombres, 4, 10.0)
                        col = [nombres.index(n) for n in m.names]
                        pred[te] = -m.risk(xt[:, col])
                    except Exception:
                        pred[te] = -capra[te]
            ci = ev.concordance_index(list(t), list(pred), list(e))
            c_idx.append(ci)
            riesgo_medio += pred / len(part["reparticiones"])
        riesgos_por_comp[nombre] = riesgo_medio
        r["e06_riesgo"][nombre] = {
            "c_index_medio": round(float(np.mean(c_idx)), 5),
            "c_index_por_semilla": [round(x, 5) for x in c_idx],
            "grados_de_libertad": 1 if bloques is None else 4,
        }

    # --- E07: de riesgo a meses, sobre la mejor composición de E06 ---
    mejor = max(r["e06_riesgo"], key=lambda k: r["e06_riesgo"][k]["c_index_medio"])
    r["mejor_composicion_e06"] = mejor

    for nombre_export in ("cdf_escalonada", "mapa_continuo", "curva_supervivencia"):
        c_idx, t_sc, distintos = [], [], []
        for semilla, pliegues in part["reparticiones"].items():
            meses = {}
            for p in pliegues:
                tr = [orden[c] for c in p["train"]]; te = [orden[c] for c in p["test"]]
                # El riesgo se recalcula dentro del pliegue para no exportar
                # desde un riesgo que ya vio el test.
                if COMPOSICIONES[mejor] is None:
                    rr_tr, rr_te = -capra[tr], -capra[te]
                else:
                    x, nombres = ds.build_matrix([por_id[c] for c in p["train"]],
                                                 COMPOSICIONES[mejor], drop_constant=False)
                    xt, _ = ds.build_matrix([por_id[c] for c in p["test"]],
                                            COMPOSICIONES[mejor], drop_constant=False)
                    try:
                        m = P.CoxPipeline().fit(x, t[tr], e[tr], nombres, 4, 10.0)
                        col = [nombres.index(n) for n in m.names]
                        rr_tr, rr_te = -m.risk(x[:, col]), -m.risk(xt[:, col])
                    except Exception:
                        rr_tr, rr_te = -capra[tr], -capra[te]

                if nombre_export == "cdf_escalonada":
                    vals = mapa_cdf(rr_tr, rr_te)
                elif nombre_export == "mapa_continuo":
                    vals = mapa_continuo(rr_tr, rr_te)
                else:
                    pasos = km_basal(t[tr], e[tr])
                    centro, escala = float(np.median(rr_tr)), float(np.std(rr_tr)) or 1.0
                    vals = [mediana_o_rmst(pasos, -(v - centro) / escala, horizonte)
                            for v in rr_te]
                for c, v in zip(p["test"], vals):
                    meses[c] = float(v)
            ord_c = [c for c in ids if c in meses]
            mm = [meses[c] for c in ord_c]
            tt = [t[orden[c]] for c in ord_c]; ee = [int(e[orden[c]]) for c in ord_c]
            c_idx.append(ev.concordance_index(tt, mm, ee))
            ts = [ev.recurrence_time_score({"months_to_recurrence": tt[i], "event": ee[i]},
                                           {"months_to_recurrence": mm[i]}) for i in range(len(mm))]
            t_sc.append(float(np.mean([x for x in ts if x is not None])))
            distintos.append(len(set(np.round(mm, 6))))
        r["e07_meses_exportados"][nombre_export] = {
            "c_index_medio": round(float(np.mean(c_idx)), 5),
            "time_score_medio": round(float(np.mean(t_sc)), 5),
            "valores_distintos_medio": round(float(np.mean(distintos)), 2),
        }

    destino = AQUI / "reports" / "e06_e07_supervivencia.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False))

    print(f"T3: {r['casos']} casos, {r['eventos']} eventos. Horizonte RMST {r['horizonte_rmst_meses']} meses")
    print(f"\nE06 — riesgo (c-index sobre el orden latente)")
    print(f"{'composición':42} {'c-index':>9} {'gl':>4}")
    for k, v in r["e06_riesgo"].items():
        print(f"{k:42} {v['c_index_medio']:9.5f} {v['grados_de_libertad']:4}")
    print(f"\nmejor composición: {mejor}")
    print(f"\nE07 — meses exportados (lo que puntúa de verdad)")
    print(f"{'exportador':24} {'c-index':>9} {'time_score':>11} {'valores':>8}")
    for k, v in r["e07_meses_exportados"].items():
        print(f"{k:24} {v['c_index_medio']:9.5f} {v['time_score_medio']:11.5f} "
              f"{v['valores_distintos_medio']:8.2f}")
    print(f"\nescrito {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
