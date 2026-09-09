#!/usr/bin/env python3
"""Aceptación del paso 2.2, comprobada contra los artefactos reales.

El plan fija cinco criterios y dice: «Si alguno de estos cinco falla, PARA y
reporta cuál y en qué casos. No ajustes parámetros para que salga el número.»
Este script los comprueba uno a uno y escribe un veredicto legible por máquina.

Existe porque la verificación por `pytest -q` es engañosa aquí: una corrida que
genera 0/195 casos deja los 92 tests en verde. Hay que mirar el artefacto.

    PYTHONPATH=src:. .venv/bin/python delete/accept_2_2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from delete_final_versions_task.common import guards  # noqa: E402
from delete_final_versions_task.task_1.agent import decide  # noqa: E402

RUNS = REPO / "delete_final_versions_task" / "task_1" / "runs"
DATA = REPO / "data" / "task1"
DECISION = "prostate-biopsy-decision.json"
REASONING = "prostate-biopsy-decision-reasoning.json"

# Objetivos del plan, con su tolerancia. No se tocan para que salga el número.
TARGETS = {"ranking_no_judge": (0.8390, 0.01),
           "ranking_with_judge": (0.8368, 0.01),
           "rationale": (0.8012, 0.02)}


def _cases(split: str) -> dict[str, dict]:
    out = {}
    base = RUNS / split / "output" / "task1"
    if not base.is_dir():
        return out
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        dec, rea = d / DECISION, d / REASONING
        if dec.exists() and rea.exists():
            out[d.name] = {"decision": json.loads(dec.read_text()),
                           "reasoning": json.loads(rea.read_text())}
    return out


def _corpus(case_id: str) -> str:
    """Todo lo que el caso tenía disponible, para juzgar si un valor está sin fuente."""
    parts = []
    for name in ("structured-prompt.json", "prostate-biopsy-decision-clinical-data.json"):
        f = DATA / "agent_input" / case_id / name
        if f.exists():
            parts.append(f.read_text())
    return "\n".join(parts)


def main() -> int:
    report: dict = {"step": "2.2", "criteria": {}}
    labeled, unlabeled = _cases("labeled"), _cases("unlabeled")
    allc = {**labeled, **unlabeled}

    # 1. cobertura
    n = len(allc)
    report["criteria"]["cobertura"] = {"ok": n == 195, "esperados": 195, "obtenidos": n,
                                       "labeled": len(labeled), "unlabeled": len(unlabeled)}

    # 2. validacion de esquema
    invalid = []
    for cid, c in allc.items():
        rea = c["reasoning"] if isinstance(c["reasoning"], dict) else {}
        # El fichero de reto guarda la prosa en `free_text` y la decisión como
        # cadena "yes"/"no"; Task1Output pide `reasoning` y un booleano.
        payload = {"case_id": cid, "task": 1,
                   "biopsy_decision": str(c["decision"]).strip().lower() == "yes",
                   "confidence": rea.get("confidence"),
                   "variable_weights": rea.get("variable_weights") or {},
                   "reveal_sequence": rea.get("reveal_sequence") or [],
                   "reasoning": rea.get("free_text") or ""}
        ok, err = guards.validate_output(1, payload)
        if not ok:
            invalid.append({"case_id": cid, "error": err[:200]})
    report["criteria"]["esquema_Task1Output"] = {
        "ok": not invalid and n > 0, "validados": n - len(invalid), "de": n,
        "fallos": invalid[:10]}

    # 3. lenguaje de proceso: 0 notas que nombren a un participante
    offenders = {}
    for cid, c in allc.items():
        text = (c["reasoning"] or {}).get("free_text", "") if isinstance(c["reasoning"], dict) else str(c["reasoning"])
        hits = decide.process_language(text)
        if hits:
            offenders[cid] = hits
    report["criteria"]["process_language"] = {
        "ok": not offenders, "casos_con_lenguaje_de_proceso": len(offenders),
        "ejemplos": dict(list(offenders.items())[:5])}

    # 4. grados sin documento
    ungrounded = {}
    for cid, c in allc.items():
        text = (c["reasoning"] or {}).get("free_text", "") if isinstance(c["reasoning"], dict) else str(c["reasoning"])
        hits = guards.unsourced_grades(text, _corpus(cid))
        if hits:
            ungrounded[cid] = hits
    report["criteria"]["unsourced_grades"] = {
        "ok": not ungrounded, "casos_con_grado_sin_fuente": len(ungrounded),
        "ejemplos": dict(list(ungrounded.items())[:5])}

    # 5. puntuaciones: se leen de los JSON que produzcan los scorers, si existen
    for key, path in (("ranking_no_judge", RUNS / "score_no_judge.json"),
                      ("ranking_with_judge", RUNS / "judge" / "entrega.json")):
        target, tol = TARGETS[key]
        if not path.exists():
            report["criteria"][key] = {"ok": None, "estado": "sin medir", "fichero": str(path)}
            continue
        data = json.loads(path.read_text())
        # Dos formatos distintos: score_with_judge.py escribe {"aggregate": {...}},
        # score_local.py escribe {"task1": {...}}. Aceptar los dos.
        agg = data.get("aggregate") or data.get("task1") or data
        if not agg.get("n_cases"):
            # Un fichero de una corrida anterior fallida: 0 casos, no es una medida.
            report["criteria"][key] = {"ok": None, "estado": "fichero obsoleto (n_cases=0)",
                                       "fichero": str(path)}
            continue
        got = agg.get("ranking_score")
        report["criteria"][key] = {
            "ok": got is not None and abs(got - target) <= tol,
            "obtenido": got, "objetivo": target, "tolerancia": tol}
        if key == "ranking_with_judge":
            t, tl = TARGETS["rationale"]
            rat = agg.get("mean_rationale_score")
            report["criteria"]["rationale"] = {
                "ok": rat is not None and abs(rat - t) <= tl,
                "obtenido": rat, "objetivo": t, "tolerancia": tl}

    decided = [c for c in report["criteria"].values() if c.get("ok") is not None]
    report["accepted"] = bool(decided) and all(c["ok"] for c in decided)
    report["pendientes"] = [k for k, v in report["criteria"].items() if v.get("ok") is None]

    out = RUNS / "acceptance_2_2_claude.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"\n=== ACEPTACIÓN 2.2 ===")
    for k, v in report["criteria"].items():
        mark = {True: "OK  ", False: "FALLA", None: "-   "}[v.get("ok")]
        detail = {kk: vv for kk, vv in v.items() if kk not in ("ok", "ejemplos", "fallos")}
        print(f"  [{mark}] {k:24s} {detail}")
    print(f"\n  ACEPTADO: {report['accepted']}")
    if report["pendientes"]:
        print(f"  sin medir todavía: {', '.join(report['pendientes'])}")
    print(f"  escrito en {out}")
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
