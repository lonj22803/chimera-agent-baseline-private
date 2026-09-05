"""Entrena las cabezas del predictor sobre los embeddings congelados (out-of-fold).

Este script NO toca el repo: lee `data/`, entrena una cabeza por tarea sobre los
vectores de `prostate-modality-level-neural-representations.json` y escribe en
`delete_test/artifacts/predictor_oof.json` una prediccion compacta por caso.

Honestidad del experimento
--------------------------
Cada caso ETIQUETADO recibe su prediccion **out-of-fold**: el modelo que la
produce nunca vio la etiqueta de ese caso (StratifiedKFold, 5 pliegues). Sin
esto, encender el predictor seria contarle al agente la respuesta y el "mejora
el baseline" no significaria nada.

Los casos sin etiqueta reciben la prediccion del modelo ajustado sobre TODO lo
etiquetado (marcados `oof: false`). No se puntuan, solo existen para que la
herramienta no devuelva vacio si se corre sobre ellos.

    python delete_test/train_head.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
OUT = REPO / "delete_test" / "artifacts" / "predictor_oof.json"
METRICS = REPO / "delete_test" / "artifacts" / "head_metrics.json"

FICHERO_EMB = "prostate-modality-level-neural-representations.json"
ORIGENES = {1: ("MRI image",), 2: ("MRI image", "Biopsy slide"), 3: ("MRI image", "Prostatectomy slide")}
DIMS = {"MRI image": 1024, "Biopsy slide": 960, "Prostatectomy slide": 960}
SEMILLA = 0
N_PLIEGUES = 5

ACCIONES = ["active_surveillance", "active_treatment", "continued_surveillance", "watchful_waiting"]
# Para estratificar los pliegues: watchful_waiting tiene n=2 y rompe el KFold.
FUSION_ESTRATIFICACION = {"watchful_waiting": "continued_surveillance"}


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------


def casos(task: int, sub: str = "agent_input") -> list[str]:
    d = DATA / f"task{task}" / sub
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def embeddings(task: int, cid: str) -> dict:
    f = DATA / f"task{task}" / "agent_input" / cid / FICHERO_EMB
    return json.loads(f.read_text()) if f.exists() else {}


def gt(task: int, cid: str):
    d = DATA / f"task{task}" / "ground_truth" / cid
    nombre = {
        1: "prostate-biopsy-decision.json",
        2: "prostate-treatment-decision.json",
        3: "prostate-time-to-recurrence-or-last-follow-up.json",
    }[task]
    f = d / nombre
    return json.loads(f.read_text()) if f.exists() else None


def bloque(vectores, dim: int) -> tuple[np.ndarray, float]:
    """Media de los vectores de un origen + bandera de ausencia."""
    if not vectores:
        return np.zeros(dim), 1.0
    vs = vectores if isinstance(vectores[0], list) else [vectores]
    return np.mean(np.asarray(vs, dtype=float), axis=0), 0.0


def matriz(task: int, ids: list[str]) -> np.ndarray:
    """Concatena los origenes de la tarea; los ausentes van a cero + bandera."""
    filas = []
    for cid in ids:
        e = embeddings(task, cid)
        trozos, banderas = [], []
        for o in ORIGENES[task]:
            v, falta = bloque(e.get(o), DIMS[o])
            trozos.append(v)
            banderas.append(falta)
        filas.append(np.concatenate([*trozos, np.asarray(banderas)]))
    X = np.asarray(filas)
    # Los ausentes (ceros) se sustituyen por la media de la columna para no
    # meter un cero artificial en el centro del espacio estandarizado.
    for j, o in enumerate(ORIGENES[task]):
        ini = sum(DIMS[oo] for oo in ORIGENES[task][:j])
        fin = ini + DIMS[o]
        falta = X[:, -len(ORIGENES[task]) + j] == 1.0
        if falta.any() and (~falta).any():
            X[np.ix_(falta, np.arange(ini, fin))] = X[np.ix_(~falta, np.arange(ini, fin))].mean(axis=0)
    return X


def modelo(C: float, multi: bool = False):
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=5000, C=C, class_weight="balanced" if multi else None),
    )


def oof_proba(X, y, clases, C, estratos=None, multi=False):
    """Probabilidades out-of-fold + el modelo reajustado sobre todo."""
    estratos = y if estratos is None else estratos
    P = np.zeros((len(y), len(clases)))
    cv = StratifiedKFold(N_PLIEGUES, shuffle=True, random_state=SEMILLA)
    for tr, te in cv.split(X, estratos):
        m = modelo(C, multi).fit(X[tr], y[tr])
        cols = {c: i for i, c in enumerate(m.classes_)}
        for k, c in enumerate(clases):
            if c in cols:
                P[te, k] = m.predict_proba(X[te])[:, cols[c]]
    completo = modelo(C, multi).fit(X, y)
    return P, completo


def banda(p: float, cortes=(0.35, 0.65)) -> str:
    return "low" if p < cortes[0] else ("high" if p >= cortes[1] else "intermediate")


# --------------------------------------------------------------------------
# Tareas
# --------------------------------------------------------------------------


def tarea1(salida: dict, metricas: dict) -> None:
    ids = [c for c in casos(1) if gt(1, c) is not None and embeddings(1, c)]
    X = matriz(1, ids)
    y = np.array([1 if gt(1, c) == "yes" else 0 for c in ids])
    P, completo = oof_proba(X, y, [0, 1], C=0.1)
    p1 = P[:, 1]

    from sklearn.metrics import roc_auc_score

    metricas["task1"] = {
        "n": len(ids),
        "dim": int(X.shape[1]),
        "auc_oof": float(roc_auc_score(y, p1)),
        "tasa_base_yes": float(y.mean()),
        "acc_oof_umbral_0.5": float(((p1 >= 0.5).astype(int) == y).mean()),
    }
    salida["task1"] = {
        c: {"p_biopsy_beneficial": round(float(p), 4), "risk_band": banda(float(p)), "oof": True}
        for c, p in zip(ids, p1)
    }
    # Casos sin etiqueta: modelo completo (no puntuan, solo evitan huecos).
    resto = [c for c in casos(1) if c not in set(ids) and embeddings(1, c)]
    if resto:
        pr = completo.predict_proba(matriz(1, resto))[:, list(completo.classes_).index(1)]
        salida["task1"].update(
            {c: {"p_biopsy_beneficial": round(float(p), 4), "risk_band": banda(float(p)), "oof": False}
             for c, p in zip(resto, pr)}
        )


def tarea2(salida: dict, metricas: dict) -> None:
    ids = [c for c in casos(2) if gt(2, c) is not None and embeddings(2, c)]
    X = matriz(2, ids)
    y = np.array([gt(2, c) for c in ids])
    estr = np.array([FUSION_ESTRATIFICACION.get(v, v) for v in y])
    P, completo = oof_proba(X, y, ACCIONES, C=0.05, estratos=estr, multi=True)
    P = P / P.sum(axis=1, keepdims=True)

    from sklearn.metrics import f1_score, roc_auc_score

    pred = [ACCIONES[i] for i in P.argmax(axis=1)]
    y_at = (y == "active_treatment").astype(int)
    metricas["task2"] = {
        "n": len(ids),
        "dim": int(X.shape[1]),
        "auc_oof_active_treatment": float(roc_auc_score(y_at, P[:, ACCIONES.index("active_treatment")])),
        "acc_oof_4clases": float(np.mean(np.array(pred) == y)),
        "f1_ponderado_oof": float(f1_score(y, pred, average="weighted", zero_division=0)),
        "distribucion_predicha": {a: int((np.array(pred) == a).sum()) for a in ACCIONES},
        "distribucion_real": {a: int((y == a).sum()) for a in ACCIONES},
    }

    def registro(cid, fila, oof):
        probs = {a: round(float(v), 4) for a, v in zip(ACCIONES, fila)}
        orden = sorted(probs, key=probs.get, reverse=True)
        return {
            "suggested_action": orden[0],
            "action_probabilities": probs,
            "runner_up": orden[1],
            "margin": round(probs[orden[0]] - probs[orden[1]], 4),
            "oof": oof,
        }

    salida["task2"] = {c: registro(c, P[i], True) for i, c in enumerate(ids)}
    resto = [c for c in casos(2) if c not in set(ids) and embeddings(2, c)]
    if resto:
        Pr = completo.predict_proba(matriz(2, resto))
        cols = [list(completo.classes_).index(a) for a in ACCIONES]
        salida["task2"].update({c: registro(c, Pr[i][cols], False) for i, c in enumerate(resto)})


def tarea3(salida: dict, metricas: dict) -> None:
    ids = [c for c in casos(3) if gt(3, c) is not None and embeddings(3, c)]
    X = matriz(3, ids)
    etiquetas = [gt(3, c) for c in ids]
    y = np.array([int(g["event"]) for g in etiquetas])
    meses = np.array([float(g["months_to_recurrence"]) for g in etiquetas])

    P, completo = oof_proba(X, y, [0, 1], C=0.05)
    riesgo = P[:, 1]

    # Riesgo -> meses. El ranking de T3 es SOLO el c-index (orden), asi que lo
    # que importa es la monotonia: mas riesgo => menos meses. Mapeamos el
    # percentil de riesgo sobre los cuantiles de los meses observados para que
    # ademas el numero caiga en un rango plausible.
    def a_meses(r: np.ndarray, referencia: np.ndarray) -> np.ndarray:
        pct = r.argsort().argsort() / max(len(r) - 1, 1)
        return np.quantile(referencia, np.clip(1.0 - pct, 0, 1))

    sug = a_meses(riesgo, meses)

    from sklearn.metrics import roc_auc_score

    import sys

    sys.path.insert(0, str(Path.home() / "PycharmProjects" / "CHIMERA-agent-eval" / "evaluation"))
    import evaluate as EV  # noqa: PLC0415

    metricas["task3"] = {
        "n": len(ids),
        "dim": int(X.shape[1]),
        "auc_oof_event": float(roc_auc_score(y, riesgo)),
        "tasa_censura": float((y == 0).mean()),
        # Techo del oraculo: c-index si el agente copiase los meses sugeridos.
        "c_index_oraculo_meses_sugeridos": EV.concordance_index(
            list(meses), list(sug), list(y)
        ),
        "c_index_oraculo_riesgo_directo": EV.concordance_index(
            list(meses), list(-riesgo), list(y)
        ),
    }

    pct = riesgo.argsort().argsort() / max(len(riesgo) - 1, 1)
    salida["task3"] = {
        c: {
            "p_recurrence": round(float(riesgo[i]), 4),
            "risk_band": banda(float(riesgo[i])),
            "risk_percentile": round(float(pct[i]), 3),
            "suggested_months_to_event": round(float(sug[i]), 1),
            "oof": True,
        }
        for i, c in enumerate(ids)
    }


def main() -> None:
    salida: dict = {}
    metricas: dict = {}
    tarea1(salida, metricas)
    tarea2(salida, metricas)
    tarea3(salida, metricas)

    salida["_meta"] = {
        "semilla": SEMILLA,
        "pliegues": N_PLIEGUES,
        "modelo": "StandardScaler + LogisticRegression",
        "nota": "predicciones out-of-fold para los casos etiquetados (oof=true)",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(salida, indent=2))
    METRICS.write_text(json.dumps(metricas, indent=2))
    print(json.dumps(metricas, indent=2))
    print(f"\nEscrito {OUT}  ({sum(len(v) for k, v in salida.items() if not k.startswith('_'))} casos)")


if __name__ == "__main__":
    main()
