"""Simulación sin LLM de la junta de la tarea 2.

Réplica de ``task_1/analysis/simulate.py``: corre el protocolo —la cascada de
guía y el portavoz por fiabilidad— sobre los 72 casos etiquetados, **sin
levantar el modelo de lenguaje**, y puntúa con el evaluador oficial. Sirve para
medir el protocolo en segundos en vez de en una hora de GPU.

**ESTOS NÚMEROS SON DENTRO DE MUESTRA. No son la nota de entrega.**

Dos razones independientes, las dos importantes:

1. *Memorización.* Los cinco expertos están entrenados con los 72 etiquetados
   (``Panel.verdicts`` sólo admite ``mode='deployed'``; no hay veredictos LOO
   completos). Evaluarlos sobre esos mismos 72 mide cuánto recuerdan, no cuánto
   generalizan. Es el mismo patrón que en la tarea 1, donde el techo memorizado
   (0,9765) casi dobló la distancia al honesto (0,7807). La referencia honesta de
   esta tarea es la regla ISUP: **0,8611 de puerta**. Si la simulación sale por
   encima, la diferencia es memorización mientras no se mida fuera de muestra.
   El propio ``panel.elect`` lo declara: los 3 casos históricos en los que habla
   el Experto 3 son *in-sample*.
2. *Falta el juez.* El presidente no redacta (``free_text`` es un marcador), así
   que ``rationale_score`` no interviene y el reparto de pesos con el juez
   apagado no es el del leaderboard —el grounding pasa de 0,05 a 0,175—.

Sirve para **comparar protocolos entre sí** en segundos, que es para lo que se
escribió, no para anunciar un resultado.

    PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task_V1.task_2.analysis.simulate
"""
from __future__ import annotations

import argparse
import json
import sys

from delete_final_versions_task_V1.task_2.agent.paths import DATA, EVAL_REPO, REPO

for _p in (str(REPO / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from delete_final_versions_task_V1.task_2.agent import protocol as P  # noqa: E402
from delete_final_versions_task_V1.task_2.experts_2.panel import Panel  # noqa: E402

EVAL = EVAL_REPO / "evaluation"
PROMPT_FILE = "structured-prompt.json"
CLINICAL_FILE = "prostate-treatment-decision-clinical-data.json"


def _evaluator():
    sys.path.insert(0, str(EVAL))
    import evaluate  # noqa: PLC0415
    return evaluate


def simulate(panel: Panel, only: set[str] | None = None) -> list[dict]:
    """Un registro por caso etiquetado, con la decisión del protocolo."""
    rows = []
    for d in sorted(p for p in (DATA / "ground_truth").iterdir() if p.is_dir()):
        cid = d.name
        if only and cid not in only:
            continue
        payload = json.loads((DATA / "agent_input" / cid / PROMPT_FILE).read_text())
        if not panel.has(cid):
            continue
        # El caché guarda {case_id, mode, experts, spokesperson, trace,
        # available_sources}; consolidate espera el diccionario PLANO de expertos.
        experts = panel.verdicts(cid)["experts"]
        # El plan interno es lo que el registrador abre; la entrega declara vacío.
        opened = list(P.INTERNAL_PLAN)
        res = P.consolidate(payload, experts, opened)
        pred = {"action": res["decision"],
                # El evaluador oficial lee el envoltorio de tratamiento.
                "treatment_recommendation": {"primary": res["decision"]},
                "confidence": res["confidence"],
                "variable_weights": dict(res["variable_weights"]),
                "reveal_sequence": [],          # entregado vacío, a propósito
                "free_text": "simulated", "case_id": cid}
        rows.append({"case_id": cid, "pred": pred, "rule": res["rule"], "who": res["who"],
                     "isup": payload.get("bx_isup")})
    return rows


def score(rows: list[dict]) -> dict:
    ev = _evaluator()
    gts = {ev.get_case_id(g): g for g in ev.load_ground_truth_records(DATA / "ground_truth", "task2")}
    out_rows = [ev.evaluate_case(gts[r["case_id"]], r["pred"], None, None)
                for r in rows if r["case_id"] in gts]
    agg = ev.compute_aggregate_metrics(out_rows)
    comps = {}
    for key in ("confidence_score", "variable_weight_score", "important_decisive_factor_score",
                "tool_score", "section_grounding_score"):
        vals = [r[key] for r in out_rows if r.get(key) is not None]
        comps[key] = sum(vals) / len(vals) if vals else None
    who = {}
    for r in rows:
        who[r["who"]] = who.get(r["who"], 0) + 1
    return {"ranking": agg.get("ranking_score"), "mean_case": agg.get("mean_case_score"),
            "gate": agg.get("decision_accuracy"), "n": len(out_rows),
            "components": comps, "spokesperson": who, "rows": out_rows}


def main() -> None:
    ap = argparse.ArgumentParser(description="Simulación sin LLM — tarea 2")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    panel = Panel()
    if not panel.cases:
        print("El caché del panel está vacío. Constrúyelo antes:")
        print("  PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task_V1.task_2.experts_2.panel")
        raise SystemExit(2)

    rows = simulate(panel)
    res = score(rows)
    print(f"\n=== simulación sin LLM · tarea 2 · {res['n']} casos etiquetados ===")
    print(f"  ranking_score      {res['ranking']}")
    print(f"  mean_case_score    {res['mean_case']}")
    print(f"  puerta (decisión)  {res['gate']}")
    print("  componentes:")
    for k, v in res["components"].items():
        print(f"    {k:34s} {'n/d' if v is None else round(v, 4)}")
    print("  quién habló:")
    for k, v in sorted(res["spokesperson"].items(), key=lambda kv: -kv[1]):
        print(f"    {k:22s} {v:3d}")
    print()
    print("  DENTRO DE MUESTRA: los expertos se entrenaron con estos mismos 72 casos.")
    print("  Referencia honesta (regla ISUP): puerta 0.8611. Lo que exceda de ahí es,")
    print("  mientras no se mida fuera de muestra, memorización.")
    print("  Sin juez ni redacción del presidente: no comparable con la entrega.")
    if args.json_out:
        from pathlib import Path  # noqa: PLC0415
        Path(args.json_out).write_text(json.dumps(
            {k: v for k, v in res.items() if k != "rows"}, indent=2, default=str))


if __name__ == "__main__":
    main()
