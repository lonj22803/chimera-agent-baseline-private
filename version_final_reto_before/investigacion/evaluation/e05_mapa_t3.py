"""E05 — ¿el mapa continuo evita pérdida en la exportación de T3? (PLAN §7.2, §11)

V1 exporta meses así: percentil del riesgo contra la CDF empírica de 75 valores
de entrenamiento, y luego `90·exp(−0,1·12·(1−percentil))`. La CDF empírica es
monótona **no estricta**: con 75 valores de referencia hay como mucho 76
intervalos de salida, así que **dos riesgos distintos pueden acabar con los
mismos meses**, y el c-index oficial se calcula sobre los meses exportados, no
sobre el riesgo latente.

Se compara, **con el mismo riesgo** y bajo la misma validación anidada por
grupo, el mapa escalonado contra uno continuo y estrictamente monótono:

    z     = (riesgo − centro_train) / escala_train
    meses = t_min + (t_max − t_min) · sigmoid(a − b·z),  con b > 0

`centro`, `escala`, `a`, `b` y los límites se congelan **sólo con train**.

Medición: empates, c-index de los meses exportados y `time_score` oficial. El
PLAN avisa de que este mapa «por sí solo no demuestra calibración clínica»: es
un comparador de exportación.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[3]
AQUI = Path(__file__).resolve().parent
PORTAVOZ = RAIZ / "version_final_reto/task_3/experts_3/train/artifacts/spokesperson_candidate.json"


def mapa_cdf(train_raw, riesgos, a=90.0, b=0.1, escala_riesgo=12.0):
    """El de V1: percentil contra la CDF empírica del train, luego exponencial."""
    ref = np.asarray(sorted(train_raw), dtype=float)
    n = len(ref)
    pct = np.array([((ref < x).sum() + 0.5 * (ref == x).sum()) / n for x in riesgos])
    return a * np.exp(-b * escala_riesgo * (1.0 - pct))


def mapa_continuo(train_raw, riesgos, t_min=1.0, t_max=120.0, a=0.0, b=2.0):
    """Estrictamente monótono y acotado; parámetros congelados desde train."""
    tr = np.asarray(train_raw, dtype=float)
    centro = float(np.median(tr))
    escala = float(np.std(tr)) or 1.0
    z = (np.asarray(riesgos, dtype=float) - centro) / escala
    # Orientación tomada del mapa de V1, no supuesta: allí un `train_raw` MAYOR
    # da percentil mayor y por tanto MÁS meses, así que la puntuación del
    # portavoz no es un riesgo creciente sino lo contrario. Suponer el signo al
    # revés da c-index 0,122, que es 1 − 0,878: el orden exactamente invertido.
    return t_min + (t_max - t_min) / (1.0 + np.exp(-(a + b * z)))


def main() -> None:
    sys.path.insert(0, str(RAIZ))
    from version_final_reto.investigacion.evaluation.referencias import cargar_evaluador, EVAL_POR_DEFECTO
    from version_final_reto.investigacion.evaluation import splits as sp
    ev = cargar_evaluador(EVAL_POR_DEFECTO)

    port = json.loads(PORTAVOZ.read_text())
    ids = port["case_ids"]
    riesgo = {c: r for c, r in zip(ids, port["train_raw"])}

    gt = {}
    for c in ids:
        f = RAIZ / f"data/task3/ground_truth/{c}/prostate-time-to-recurrence-or-last-follow-up.json"
        gt[c] = json.loads(f.read_text())

    part = sp.cargar(3)
    r = {"alcance": "E05: mismo riesgo, dos mapas de exportación, validación anidada por grupo",
         "aviso": ("Los riesgos (`train_raw`) vienen del portavoz ajustado con los 75 casos, "
                   "así que las cifras absolutas de c-index están infladas por dentro de "
                   "muestra. Lo que este experimento aísla y sí es comparable es la "
                   "DIFERENCIA entre mapas, porque ambos reciben exactamente los mismos "
                   "riesgos y sólo sus parámetros se ajustan por pliegue."),
         "mapas": {}, "referencia_desplegada": {}}

    # Referencia desplegada: el mapa de V1 ajustado con los 75 (dentro de muestra).
    meses_desp = np.array(port["months"])
    t_all = [gt[c]["months_to_recurrence"] for c in ids]
    e_all = [int(gt[c]["event"]) for c in ids]
    r["referencia_desplegada"] = {
        "c_index_meses_exportados": round(ev.concordance_index(t_all, list(meses_desp), e_all), 5),
        "meses_distintos": int(len(set(np.round(meses_desp, 6)))),
        "nota": "dentro de muestra; la CDF se ajustó con los mismos 75 casos",
    }

    for nombre, fn in (("cdf_escalonada_v1", mapa_cdf), ("continuo_sigmoide_v2", mapa_continuo)):
        c_idx, t_sc, empates, distintos = [], [], [], []
        for semilla, pliegues in part["reparticiones"].items():
            meses = {}
            for p in pliegues:
                tr = [riesgo[c] for c in p["train"]]
                te = p["test"]
                for c, m in zip(te, fn(tr, [riesgo[c] for c in te])):
                    meses[c] = float(m)
            orden = [c for c in ids if c in meses]
            mm = [meses[c] for c in orden]
            tt = [gt[c]["months_to_recurrence"] for c in orden]
            ee = [int(gt[c]["event"]) for c in orden]
            ci = ev.concordance_index(tt, mm, ee)
            c_idx.append(ci)
            ts = [ev.recurrence_time_score(gt[c], {"months_to_recurrence": meses[c]}) for c in orden]
            t_sc.append(float(np.mean([x for x in ts if x is not None])))
            redondeados = np.round(mm, 6)
            distintos.append(len(set(redondeados)))
            empates.append(len(redondeados) - len(set(redondeados)))
        r["mapas"][nombre] = {
            "c_index_medio": round(float(np.mean(c_idx)), 5),
            "c_index_por_semilla": [round(x, 5) for x in c_idx],
            "time_score_medio": round(float(np.mean(t_sc)), 5),
            "time_score_por_semilla": [round(x, 5) for x in t_sc],
            "meses_distintos_medio": round(float(np.mean(distintos)), 2),
            "empates_medio": round(float(np.mean(empates)), 2),
        }

    a, b = r["mapas"]["cdf_escalonada_v1"], r["mapas"]["continuo_sigmoide_v2"]
    r["delta_continuo_menos_cdf"] = {
        "c_index": round(b["c_index_medio"] - a["c_index_medio"], 5),
        "time_score": round(b["time_score_medio"] - a["time_score_medio"], 5),
    }
    destino = AQUI / "reports" / "e05_mapa_t3.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False))

    print(f"referencia desplegada (dentro de muestra): c-index "
          f"{r['referencia_desplegada']['c_index_meses_exportados']}, "
          f"{r['referencia_desplegada']['meses_distintos']} valores distintos de 75")
    print(f"\n{'mapa':24} {'c-index':>9} {'time_score':>11} {'valores':>8} {'empates':>8}")
    for k, v in r["mapas"].items():
        print(f"{k:24} {v['c_index_medio']:9.5f} {v['time_score_medio']:11.5f} "
              f"{v['meses_distintos_medio']:8.2f} {v['empates_medio']:8.2f}")
    d = r["delta_continuo_menos_cdf"]
    print(f"\ndelta continuo − CDF:  c-index {d['c_index']:+.5f}   time_score {d['time_score']:+.5f}")
    print(f"escrito {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
