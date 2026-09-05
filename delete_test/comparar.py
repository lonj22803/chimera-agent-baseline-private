"""Puntua y compara los brazos del experimento con el evaluador OFICIAL.

Todo lo que el notebook necesita para responder "¿cambia algo encender el
predictor?" en tres planos: la puntuacion, el comportamiento del agente y el
techo de la propia cabeza.

Reglas heredadas de dev/score_local.py (no reinventar la metrica):

* se importa `evaluate.py` del repo de evaluacion, no se reimplementa;
* el juez de razonamiento queda DESACTIVADO (modo determinista);
* un caso etiquetado SIN prediccion se puntua como fallo (`pred=None`), que es
  lo que hace Grand Challenge cuando un contenedor no entrega.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("USE_RATIONALE_JUDGE", "0")

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
AQUI = REPO / "delete_test"
EVAL_REPO = Path.home() / "PycharmProjects" / "CHIMERA-agent-eval"

PESO_TAREA = {1: 2.0, 2: 2.0, 3: 1.0}
NOMBRE_TAREA = {1: "T1 · biopsia", 2: "T2 · tratamiento", 3: "T3 · recurrencia"}
NOMBRE_BRAZO = {
    "off": "control (predictor apagado)",
    "on": "sonda (predictor encendido, prompt intacto)",
    "on_prompt": "tratamiento (predictor + prompt)",
}
PESOS_SIN_JUEZ = {
    "variable_weight_score": 0.275,
    "confidence_score": 0.225,
    "important_decisive_factor_score": 0.175,
    "section_grounding_score": 0.175,
    "tool_score": 0.150,
}

sys.path.insert(0, str(EVAL_REPO / "evaluation"))
sys.path.insert(0, str(REPO / "dev"))
import evaluate as EV  # noqa: E402
from score_local import load_predictions  # noqa: E402


# --------------------------------------------------------------------------
# Puntuacion
# --------------------------------------------------------------------------


def verdad(task: int) -> dict:
    registros = EV.load_ground_truth_records(DATA / f"task{task}" / "ground_truth", f"task{task}")
    return {EV.get_case_id(g): g for g in registros}


def filas(brazo: str, task: int) -> pd.DataFrame:
    """Una fila por caso ETIQUETADO. Los que no tienen salida se puntuan como fallo."""
    preds = load_predictions(AQUI / f"output_{brazo}", task)
    gt = verdad(task)
    return pd.DataFrame([EV.evaluate_case(g, preds.get(cid), None, None) for cid, g in gt.items()])


def agregados(brazo: str, tasks=(1, 2, 3)) -> tuple[dict, dict, float]:
    F, A = {}, {}
    for t in tasks:
        F[t] = filas(brazo, t)
        rows = F[t].to_dict("records")
        A[t] = EV.aggregate_recurrence_metrics(rows) if t == 3 else EV.compute_aggregate_metrics(rows)
    presentes = [t for t in tasks if A[t].get("ranking_score") is not None]
    overall = (
        sum(A[t]["ranking_score"] * PESO_TAREA[t] for t in presentes) / sum(PESO_TAREA[t] for t in presentes)
        if presentes
        else float("nan")
    )
    return F, A, overall


# --------------------------------------------------------------------------
# Comportamiento del agente (trazas)
# --------------------------------------------------------------------------


def trazas(brazo: str) -> pd.DataFrame:
    raiz = AQUI / "traces" / brazo
    if not raiz.is_dir():
        return pd.DataFrame()
    reg = []
    for f in sorted(raiz.rglob("*.json")):
        d = json.loads(f.read_text())
        herramientas = [tc["tool"] for tc in d.get("tool_calls", []) or []]
        resultados = d.get("tool_results", []) or []
        # ToolNode responde con un ToolMessage de error cuando el modelo invoca
        # una herramienta que no existe en el registro de esa tarea (el prompt
        # de sistema nombra get_pathology_report tambien en T1/T3, donde no
        # esta). Esas llamadas no revelan nada y no deben contar como uso.
        fantasma = [t["tool"] for t in resultados if "is not a valid tool" in (t.get("salida") or "")]
        devueltas = [t["tool"] for t in resultados if "is not a valid tool" not in (t.get("salida") or "")]
        est = d.get("structured") or {}
        reg.append({
            "brazo": brazo,
            "task": d["task"],
            "case_id": d["case_id"],
            "ok": bool(d.get("ok")),
            "error": d.get("error"),
            "segundos": d.get("segundos"),
            "n_llamadas": len(herramientas),
            "n_distintas": len(set(herramientas)),
            "llamo_predictor": "get_image_predictor" in devueltas,
            "n_fantasma": len(fantasma),
            "fantasma": tuple(sorted(set(fantasma))),
            "herramientas": tuple(sorted(set(devueltas))),
            "secuencia": tuple(herramientas),
            "n_avisos_form_fill": len(d.get("form_fill_warnings") or []),
            "n_mensajes": d.get("n_mensajes"),
            "reveal_sequence": tuple(est.get("reveal_sequence") or []),
            "confidence": est.get("confidence"),
            "decision": (
                est.get("action")
                if d["task"] == 2
                else ("yes" if est.get("biopsy_decision") else "no") if d["task"] == 1
                else est.get("months_to_recurrence")
            ),
            "texto_final": d.get("texto_final", ""),
        })
    return pd.DataFrame(reg)


def menciona_predictor(texto: str) -> bool:
    """¿El razonamiento final cita la salida de la cabeza?"""
    t = (texto or "").lower()
    claves = ("image_predictor", "image predictor", "embedding", "predictor tool",
              "p_recurrence", "suggested_action", "p_biopsy", "risk_band", "auc")
    return any(k in t for k in claves)


# --------------------------------------------------------------------------
# Techo de la cabeza (oraculo): que pasaria si el agente la copiase
# --------------------------------------------------------------------------


def tabla_cabeza() -> dict:
    return json.loads((AQUI / "artifacts" / "predictor_oof.json").read_text())


def oraculo() -> dict:
    """Puntuacion de la cabeza SOLA, sin agente. Separa 'hay senal' de 'se usa'."""
    tabla = tabla_cabeza()
    out = {}

    gt1 = verdad(1)
    par = [(g, tabla["task1"].get(cid)) for cid, g in gt1.items() if cid in tabla["task1"]]
    y = [EV._norm_decision(g.get("biopsy_decision")) for g, _ in par]
    p = ["yes" if r["p_biopsy_beneficial"] >= 0.5 else "no" for _, r in par]
    out[1] = {"n": len(par), "acierto_decision": float(np.mean([a == b for a, b in zip(y, p)]))}

    gt2 = verdad(2)
    par = [(g, tabla["task2"].get(cid)) for cid, g in gt2.items() if cid in tabla["task2"]]
    y = [EV._norm_treatment_decision(g) for g, _ in par]
    p = [r["suggested_action"] for _, r in par]
    from sklearn.metrics import f1_score

    out[2] = {
        "n": len(par),
        "acierto_decision": float(np.mean([a == b for a, b in zip(y, p)])),
        "f1_ponderado": float(f1_score(y, p, average="weighted", zero_division=0)),
    }

    gt3 = verdad(3)
    par = [(g, tabla["task3"].get(cid)) for cid, g in gt3.items() if cid in tabla["task3"]]
    tiempos = [EV._norm_months(g.get("months_to_recurrence")) for g, _ in par]
    eventos = [EV._norm_event(g.get("event")) for g, _ in par]
    meses = [r["suggested_months_to_event"] for _, r in par]
    out[3] = {"n": len(par), "c_index": EV.concordance_index(tiempos, meses, eventos)}
    return out


# --------------------------------------------------------------------------
# Ensamblado
# --------------------------------------------------------------------------


def comparar(brazos=("off", "on_prompt"), tasks=(1, 2, 3)) -> dict:
    res = {}
    for b in brazos:
        F, A, o = agregados(b, tasks)
        res[b] = {"filas": F, "agregados": A, "overall": o, "trazas": trazas(b)}
    return res


def tabla_resumen(res: dict, tasks=(1, 2, 3)) -> pd.DataFrame:
    reg = []
    for b, r in res.items():
        for t in tasks:
            a = r["agregados"][t]
            f = r["filas"][t]
            reg.append({
                "brazo": b,
                "tarea": NOMBRE_TAREA[t],
                "n": a["n_cases"],
                "sin salida": int(f["gate"].eq("missing_candidate").sum()),
                "mean_case_score": a["mean_case_score"],
                "ranking_score": a["ranking_score"],
                "puerta": (f["decision_score"] == 1.0).mean() if t != 3 else np.nan,
            })
        reg.append({"brazo": b, "tarea": "OVERALL (2:2:1)", "n": np.nan, "sin salida": np.nan,
                    "mean_case_score": np.nan, "ranking_score": r["overall"], "puerta": np.nan})
    return pd.DataFrame(reg)


if __name__ == "__main__":
    brazos = sys.argv[1:] or ["off", "on_prompt"]
    res = comparar(tuple(brazos))
    print(tabla_resumen(res).to_string(index=False))
    print("\nOraculo (la cabeza sola):", json.dumps(oraculo(), indent=2))
