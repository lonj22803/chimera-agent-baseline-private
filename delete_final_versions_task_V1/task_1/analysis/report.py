"""Lectura y puntuación de una corrida. Es lo que consume el cuaderno.

Todo lo que puntúa pasa por el **evaluador oficial** de los organizadores
(``DIAGNijmegen/CHIMERA-agent/evaluation/evaluate.py``), importado y no
reimplementado: si cambian los pesos, estos números cambian con ellos.
Reimplementar la métrica es la forma más rápida de optimizar contra un número
que no existe.

El cuaderno llama a estas funciones en vez de traer la lógica dentro, para que
lo que se publica se pueda probar por separado y para que la celda se lea.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from delete_final_versions_task_V1.task_1.agent.paths import REPO, DATA, TASK_ROOT, EVAL_REPO
os.environ.setdefault("USE_RATIONALE_JUDGE", "0")

SECTIONS = ["radiology_report", "psa_trend", "previous_notes", "laboratory_results", "family_history"]
VARIABLES = ["bx", "fh", "age", "dre", "psa", "vol", "psad", "cspca", "pirads", "comorbidity"]
COMPONENTS = ("confidence_score", "variable_weight_score", "important_decisive_factor_score",
              "tool_score", "section_grounding_score")
#: Pesos del evaluador oficial con el juez de razonamiento DESACTIVADO. Con el
#: juez activo se redistribuyen (grounding 0.175 -> 0.05), así que un número de
#: aquí no es comparable con uno de leaderboard.
WEIGHTS_NO_JUDGE = {"confidence_score": 0.225, "variable_weight_score": 0.275,
                    "important_decisive_factor_score": 0.175, "tool_score": 0.150,
                    "section_grounding_score": 0.175}

#: Corridas de las generaciones anteriores, para la comparación pareada.
from delete_final_versions_task_V1.task_1.agent.paths import PREVIOUS


def evaluator():
    """El ``evaluate.py`` oficial, importado una vez."""
    d = EVAL_REPO / "evaluation"
    if not (d / "evaluate.py").exists():
        raise SystemExit(f"No encuentro el evaluador oficial en {d}. Clónalo con:\n"
                         f"  git clone https://github.com/DIAGNijmegen/CHIMERA-agent.git {EVAL_REPO}")
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    import evaluate  # noqa: PLC0415
    return evaluate


# ---------------------------------------------------------------------------
# lectura
# ---------------------------------------------------------------------------


def labelled_ids() -> set[str]:
    return {p.name for p in (DATA / "ground_truth").iterdir() if p.is_dir()}


def ground_truth() -> dict[str, dict]:
    out = {}
    for d in sorted(p for p in (DATA / "ground_truth").iterdir() if p.is_dir()):
        rec = json.loads((d / "prostate-biopsy-decision-reasoning.json").read_text())
        rec["biopsy_decision"] = json.loads((d / "prostate-biopsy-decision.json").read_text())
        rec["case_id"] = d.name
        out[d.name] = rec
    return out


def payloads() -> dict[str, dict]:
    out = {}
    for d in sorted(p for p in (DATA / "agent_input").iterdir() if p.is_dir()):
        f = d / "structured-prompt.json"
        if f.exists():
            out[d.name] = json.loads(f.read_text())
    return out


def load_predictions(output_root: Path) -> dict[str, dict]:
    """Lee ``output/task1/<caso>/`` al shape plano que espera el evaluador."""
    preds: dict[str, dict] = {}
    task_dir = Path(output_root) / "task1"
    if not task_dir.is_dir():
        return preds
    for case in sorted(p for p in task_dir.iterdir() if p.is_dir()):
        d, r = case / "prostate-biopsy-decision.json", case / "prostate-biopsy-decision-reasoning.json"
        if not (d.exists() and r.exists()):
            continue
        rec = json.loads(r.read_text())
        rec["biopsy_decision"] = json.loads(d.read_text())
        rec["case_id"] = case.name
        preds[case.name] = rec
    return preds


def load_run(root: Path) -> dict[str, Any]:
    """Todo lo de una corrida: config, resumen, telemetría, salidas y actas."""
    root = Path(root)
    # Una corrida reanudada vuelve a escribir la línea de un caso que falló y se
    # repitió, así que se deduplica por caso quedándose con la última: es la que
    # corresponde a los ficheros que hay en disco.
    rows = [json.loads(l) for l in (root / "summary.jsonl").read_text().splitlines() if l.strip()]
    by_case = {r["case_id"]: r for r in rows}
    summary = [by_case[c] for c in dict.fromkeys(r["case_id"] for r in rows)]
    tele_file = root / "telemetry.jsonl"
    telemetry = ([json.loads(l) for l in tele_file.read_text().splitlines() if l.strip()]
                 if tele_file.exists() else [])
    cfg_file = root / "run_config.json"
    return {"root": root, "config": json.loads(cfg_file.read_text()) if cfg_file.exists() else {},
            "summary": summary, "telemetry": telemetry,
            "preds": load_predictions(root / "output")}


def load_boards(root: Path) -> dict[str, dict]:
    out = {}
    for f in sorted((Path(root) / "boards").glob("*.json")):
        out[f.stem] = json.loads(f.read_text())
    return out


# ---------------------------------------------------------------------------
# puntuación con el evaluador oficial
# ---------------------------------------------------------------------------


def score(preds: dict[str, dict], only: set[str] | None = None, count_missing: bool = True) -> dict[str, Any]:
    """Puntúa contra el ground truth con el evaluador oficial.

    ``count_missing`` puntúa como fallo (``pred=None``) el caso etiquetado sin
    predicción, que es lo que hace Grand Challenge cuando un contenedor aborta.
    Excluirlos da un número optimista si el agente abandona casos.
    """
    ev = evaluator()
    gts = ev.load_ground_truth_records(DATA / "ground_truth", "task1")
    rows = []
    for gt in gts:
        cid = ev.get_case_id(gt)
        if only is not None and cid not in only:
            continue
        pred = preds.get(cid)
        if pred is None and not count_missing:
            continue
        rows.append(ev.evaluate_case(gt, pred, None, None))
    if not rows:
        return {"n": 0}
    agg = ev.compute_aggregate_metrics(rows)
    out = {"n": len(rows), "ranking": agg["ranking_score"], "mean_case": agg["mean_case_score"],
           "f1_yes": agg["decision_f1_yes"], "accuracy": agg["decision_accuracy"],
           "gate": agg["decision_gate_pass_rate"],
           "missing": sum(1 for r in rows if r["gate"] == "missing_candidate"),
           "schema_failed": sum(1 for r in rows if r["gate"] == "schema_failed")}
    for k in COMPONENTS:
        vals = [r[k] for r in rows if r.get(k) is not None]
        out[k] = mean(vals) if vals else None
    out["_rows"] = {r["case_id"]: r for r in rows}
    return out


def score_table(runs: dict[str, dict[str, dict]], only: set[str] | None = None) -> "Any":
    """Una fila por corrida, con las columnas que importan. Devuelve un DataFrame."""
    import pandas as pd  # noqa: PLC0415
    rows = []
    for name, preds in runs.items():
        s = score(preds, only=only)
        if not s.get("n"):
            continue
        rows.append({"corrida": name, "ranking_score": s["ranking"], "mean_case": s["mean_case"],
                     "F1(yes)": s["f1_yes"], "puerta": s["gate"], "confianza": s["confidence_score"],
                     "pesos": s["variable_weight_score"], "factores": s["important_decisive_factor_score"],
                     "herramientas": s["tool_score"], "aterrizaje": s["section_grounding_score"],
                     "sin salida": s["missing"]})
    return pd.DataFrame(rows).set_index("corrida").round(4)


def paired(a: dict, b: dict) -> dict[str, int]:
    """Comparación caso a caso del ``case_score`` entre dos puntuaciones."""
    up = down = tie = 0
    for cid, ra in a["_rows"].items():
        rb = b["_rows"].get(cid)
        if rb is None:
            continue
        d = ra["case_score"] - rb["case_score"]
        up += d > 1e-9
        down += d < -1e-9
        tie += abs(d) <= 1e-9
    return {"suben": up, "bajan": down, "empatan": tie}


def sign_test(a: dict, b: dict) -> float:
    """p bilateral de la prueba de signos sobre los casos que cambian."""
    from math import comb  # noqa: PLC0415
    r = paired(a, b)
    n, k = r["suben"] + r["bajan"], r["suben"]
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(k, n - k) + 1)) / 2**n
    return min(1.0, 2 * tail)


def by_bucket(scored: dict, pay: dict[str, dict]) -> "Any":
    """Acierto de la puerta de decisión por cubo de biopsia previa."""
    import pandas as pd  # noqa: PLC0415
    acc: dict[str, list[int]] = {}
    for cid, r in scored["_rows"].items():
        b = str(pay.get(cid, {}).get("bx") or "?")
        acc.setdefault(b, []).append(int(r["decision_score"] == 1.0))
    rows = [{"cubo": b, "n": len(v), "aciertos": sum(v), "exactitud": sum(v) / len(v)}
            for b, v in sorted(acc.items())]
    rows.append({"cubo": "TOTAL", "n": sum(r["n"] for r in rows), "aciertos": sum(r["aciertos"] for r in rows),
                 "exactitud": sum(r["aciertos"] for r in rows) / sum(r["n"] for r in rows)})
    return pd.DataFrame(rows).set_index("cubo").round(4)


def component_contribution(scored: dict) -> "Any":
    """Cuánto aporta cada componente al ``case_score``, con sus pesos oficiales."""
    import pandas as pd  # noqa: PLC0415
    rows = []
    for k, w in WEIGHTS_NO_JUDGE.items():
        v = scored.get(k)
        rows.append({"componente": k, "valor": v, "peso": w, "aporta": (v or 0) * w,
                     "margen que queda": (1 - (v or 0)) * w})
    df = pd.DataFrame(rows).set_index("componente")
    return df.round(4).sort_values("margen que queda", ascending=False)


# ---------------------------------------------------------------------------
# comprobaciones que no necesitan etiqueta
# ---------------------------------------------------------------------------


def unlabelled_checks(summary: list[dict], pay: dict[str, dict], gt: dict[str, dict]) -> list[dict]:
    """Lo que se puede verificar sin ground truth, con su criterio de aprobado.

    Sobre los 104 casos sin etiqueta no hay nota que calcular, pero sí hay
    invariantes que deben cumplirse y distribuciones que deben parecerse a las
    de la serie etiquetada. Una desviación grande aquí es un fallo aunque no
    haya con qué compararla.
    """
    lab = set(gt)
    unl = [r for r in summary if r["case_id"] not in lab and r.get("ok")]
    n = len(unl)
    if not n:
        return []

    def rate(pred) -> float:
        return sum(1 for r in unl if pred(r)) / n

    gt_rev = {s: sum(1 for g in gt.values() if s in g["reveal_sequence"]) / len(gt) for s in SECTIONS}
    got_rev = {s: rate(lambda r, s=s: s in (r["reveal_sequence"] or [])) for s in SECTIONS}
    gt_yes = sum(1 for g in gt.values() if g["biopsy_decision"] == "yes") / len(gt)

    checks = [
        {"comprobación": "todos los casos entregan salida", "valor": rate(lambda r: True),
         "referencia": 1.0, "pasa": rate(lambda r: True) == 1.0},
        {"comprobación": "la salida valida contra Task1Output", "valor": rate(lambda r: r.get("schema_ok")),
         "referencia": 1.0, "pasa": rate(lambda r: r.get("schema_ok")) == 1.0},
        {"comprobación": "la nota no describe el procedimiento",
         "valor": rate(lambda r: not r.get("note_violations")), "referencia": 1.0,
         "pasa": rate(lambda r: not r.get("note_violations")) == 1.0},
        {"comprobación": "ningún precedente idéntico (no puede haberlo)",
         "valor": rate(lambda r: bool(r.get("library_self_match"))), "referencia": 0.0,
         "pasa": rate(lambda r: bool(r.get("library_self_match"))) == 0.0},
        {"comprobación": "lo abierto coincide con el plan",
         "valor": rate(lambda r: set(r.get("reveal_sequence") or []) == set(r.get("planned") or [])),
         "referencia": 1.0,
         "pasa": rate(lambda r: set(r.get("reveal_sequence") or []) == set(r.get("planned") or [])) == 1.0},
        {"comprobación": "nunca se abre family_history (el urólogo: 0/91)",
         "valor": rate(lambda r: "family_history" in (r["reveal_sequence"] or [])), "referencia": 0.0,
         "pasa": rate(lambda r: "family_history" in (r["reveal_sequence"] or [])) == 0.0},
        {"comprobación": "la nota llega a 40 caracteres (mínimo del esquema)",
         "valor": rate(lambda r: len(r.get("free_text") or "") >= 40), "referencia": 1.0,
         "pasa": rate(lambda r: len(r.get("free_text") or "") >= 40) == 1.0},
        {"comprobación": "respaldo determinista del formulario",
         "valor": rate(lambda r: r.get("fallback_form")), "referencia": "bajo",
         "pasa": rate(lambda r: r.get("fallback_form")) <= 0.05},
    ]
    for s in SECTIONS[:4]:
        checks.append({"comprobación": f"frecuencia de apertura · {s}", "valor": got_rev[s],
                       "referencia": round(gt_rev[s], 3), "pasa": abs(got_rev[s] - gt_rev[s]) <= 0.15})
    yes = rate(lambda r: r["decision"] == "yes")
    checks.append({"comprobación": "proporción de «biopsia»", "valor": yes, "referencia": round(gt_yes, 3),
                   "pasa": abs(yes - gt_yes) <= 0.20})
    return checks


def distribution_table(summary: list[dict], pay: dict[str, dict], gt: dict[str, dict]) -> "Any":
    """Decisión, confianza y revelaciones: sin etiqueta frente a la serie."""
    import pandas as pd  # noqa: PLC0415
    lab = set(gt)
    unl = [r for r in summary if r["case_id"] not in lab and r.get("ok")]
    labr = [r for r in summary if r["case_id"] in lab and r.get("ok")]
    rows = []

    def block(title: str, key, values):
        c_u = Counter(key(r) for r in unl)
        c_l = Counter(key(r) for r in labr)
        c_g = Counter(values(g) for g in gt.values())
        for v in sorted(set(c_u) | set(c_l) | set(c_g), key=str):
            rows.append({"qué": title, "valor": v,
                         "sin etiqueta": round(c_u[v] / max(len(unl), 1), 3),
                         "etiquetados": round(c_l[v] / max(len(labr), 1), 3),
                         "urólogo": round(c_g[v] / len(gt), 3)})

    block("decisión", lambda r: r["decision"], lambda g: g["biopsy_decision"])
    block("confianza", lambda r: r["confidence"], lambda g: g["confidence"])
    for s in SECTIONS:
        rows.append({"qué": "abre", "valor": s,
                     "sin etiqueta": round(sum(1 for r in unl if s in (r["reveal_sequence"] or [])) / max(len(unl), 1), 3),
                     "etiquetados": round(sum(1 for r in labr if s in (r["reveal_sequence"] or [])) / max(len(labr), 1), 3),
                     "urólogo": round(sum(1 for g in gt.values() if s in g["reveal_sequence"]) / len(gt), 3)})
    for v in VARIABLES:
        for lvl in ("decisive", "important"):
            rows.append({"qué": f"pesa {lvl}", "valor": v,
                         "sin etiqueta": round(sum(1 for r in unl if (r["variable_weights"] or {}).get(v) == lvl) / max(len(unl), 1), 3),
                         "etiquetados": round(sum(1 for r in labr if (r["variable_weights"] or {}).get(v) == lvl) / max(len(labr), 1), 3),
                         "urólogo": round(sum(1 for g in gt.values() if (g["variable_weights"] or {}).get(v) == lvl) / len(gt), 3)})
    return pd.DataFrame(rows)


def rule_table(summary: list[dict], gt: dict[str, dict], pay: dict[str, dict]) -> "Any":
    """Qué peldaño del protocolo decidió cada caso, y con qué acierto."""
    import pandas as pd  # noqa: PLC0415
    agg: dict[str, dict[str, Any]] = {}
    for r in summary:
        if not r.get("ok"):
            continue
        rule = str(r.get("protocol_rule") or "?")
        key = ("documented prior grade" if rule.startswith("documented") else
               "weighted vote" if rule.startswith("weighted") else rule.split(";")[0])
        a = agg.setdefault(key, {"n": 0, "etiquetados": 0, "aciertos": 0})
        a["n"] += 1
        if r["case_id"] in gt:
            a["etiquetados"] += 1
            a["aciertos"] += int(gt[r["case_id"]]["biopsy_decision"] == r["decision"])
    rows = [{"peldaño": k, "casos": v["n"], "de ellos etiquetados": v["etiquetados"],
             "aciertos": v["aciertos"],
             "exactitud": round(v["aciertos"] / v["etiquetados"], 3) if v["etiquetados"] else None}
            for k, v in sorted(agg.items(), key=lambda kv: -kv[1]["n"])]
    return pd.DataFrame(rows).set_index("peldaño")


def telemetry_tables(telemetry: list[dict]) -> tuple["Any", "Any"]:
    """(por papel, por herramienta) — tokens, llamadas y tiempo."""
    import pandas as pd  # noqa: PLC0415
    llm = pd.DataFrame([r for r in telemetry if r.get("kind") == "llm"])
    tools = pd.DataFrame([r for r in telemetry if r.get("kind") == "tool"])
    n_cases = llm["case_id"].nunique() if len(llm) else 1
    by_role = (llm.groupby("role").agg(llamadas=("role", "size"),
                                       tokens_entrada=("prompt_tokens", "sum"),
                                       tokens_salida=("completion_tokens", "sum"),
                                       segundos=("seconds", "sum")).sort_values("tokens_entrada", ascending=False))
    by_role["llamadas/caso"] = (by_role["llamadas"] / n_cases).round(2)
    by_role["tokens_entrada/caso"] = (by_role["tokens_entrada"] / n_cases).round(0)
    by_role["tokens_salida/caso"] = (by_role["tokens_salida"] / n_cases).round(0)
    by_role["s/caso"] = (by_role["segundos"] / n_cases).round(2)
    by_tool = pd.DataFrame()
    if len(tools):
        by_tool = (tools.groupby("tool").agg(llamadas=("tool", "size"), segundos=("seconds", "sum"),
                                             tokens_devueltos=("tokens", "sum")))
        by_tool["llamadas/caso"] = (by_tool["llamadas"] / n_cases).round(2)
        by_tool["s/llamada"] = (by_tool["segundos"] / by_tool["llamadas"]).round(3)
        by_tool = by_tool.sort_values("llamadas", ascending=False)
    return by_role.round(1), by_tool.round(1)
