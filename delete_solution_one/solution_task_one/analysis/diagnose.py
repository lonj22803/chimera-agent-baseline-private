"""Diagnóstico de una corrida de la pizarra: qué decidió, qué reveló y qué falló.

Se usa desde la línea de órdenes y desde el cuaderno. No reimplementa la
métrica del reto (para eso está ``dev/score_local.py``, que importa el
evaluador oficial): mide el **comportamiento** del agente, que es lo que se
corrige tocando prompts.

    python delete_solution_one/solution_task_one/analysis/diagnose.py \
        delete_solution_one/solution_task_one/runs/run1
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
GT = REPO / "data" / "task1" / "ground_truth"
IN = REPO / "data" / "task1" / "agent_input"

#: Frecuencia con la que el urólogo reveló cada sección en los 91 casos
#: etiquetados. ``tool_score`` es precisión, así que ésta es la probabilidad
#: de que una revelación concreta cuente como "aprobada".
GT_REVEAL_RATE = {
    "radiology_report": 0.967,
    "psa_trend": 0.868,
    "previous_notes": 0.846,
    "laboratory_results": 0.451,
    "family_history": 0.0,
}

#: Marcas de que el modelo copió el enunciado del prompt en su respuesta.
ECHO_MARKERS = (
    "One block per document you opened",
    "<document>",
    "Two short lists",
    "One line naming what you deliberately",
)


def load_run(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    rows = [json.loads(ln) for ln in (run_dir / "summary.jsonl").read_text().splitlines() if ln.strip()]
    # una corrida reanudada puede repetir un caso: nos quedamos con la última
    by_id = {r["case_id"]: r for r in rows}
    boards = {}
    bdir = run_dir / "blackboards"
    if bdir.is_dir():
        for f in sorted(bdir.glob("*.json")):
            boards[f.stem] = json.loads(f.read_text())
    cfg_path = run_dir / "run_config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    return {"dir": run_dir, "rows": by_id, "boards": boards, "config": cfg}


def ground_truth() -> dict[str, dict]:
    out = {}
    for d in sorted(GT.iterdir()):
        if not d.is_dir():
            continue
        out[d.name] = {
            "decision": json.loads((d / "prostate-biopsy-decision.json").read_text()),
            "reasoning": json.loads((d / "prostate-biopsy-decision-reasoning.json").read_text()),
            "prompt": json.loads((IN / d.name / "structured-prompt.json").read_text()),
        }
    return out


def analyse(run: dict[str, Any]) -> dict[str, Any]:
    gt = ground_truth()
    rows = run["rows"]
    boards = run["boards"]

    ok = [r for r in rows.values() if r.get("ok")]
    failed = [r for r in rows.values() if not r.get("ok")]
    labelled = [r for r in ok if r["case_id"] in gt]

    # --- decisión -----------------------------------------------------------
    correct = [r for r in labelled if r["decision"] == gt[r["case_id"]]["decision"]]
    by_bucket: dict[str, list[bool]] = defaultdict(list)
    confusion: Counter = Counter()
    for r in labelled:
        g = gt[r["case_id"]]
        by_bucket[str(g["prompt"].get("bx"))].append(r["decision"] == g["decision"])
        confusion[(g["decision"], r["decision"])] += 1

    # --- revelaciones -------------------------------------------------------
    reveal_counts: Counter = Counter()
    n_reveals: Counter = Counter()
    precisions = []
    for r in labelled:
        seq = r.get("reveal_sequence") or []
        n_reveals[len(seq)] += 1
        for s in seq:
            reveal_counts[s] += 1
        expected = set(gt[r["case_id"]]["reasoning"].get("reveal_sequence") or [])
        precisions.append(len(set(seq) & expected) / len(seq) if seq else 1.0)

    # --- confianza y pesos --------------------------------------------------
    conf_pred: Counter = Counter(r["confidence"] for r in labelled)
    conf_pairs: Counter = Counter((gt[r["case_id"]]["reasoning"]["confidence"], r["confidence"]) for r in labelled)
    weight_dist: dict[str, Counter] = defaultdict(Counter)
    for r in labelled:
        for k, v in (r.get("variable_weights") or {}).items():
            weight_dist[k][v] += 1

    # --- comportamiento de los sub-bucles -----------------------------------
    l1_used_rag = sum(1 for r in ok if r.get("l1_rounds", 0) > 0)
    l2_rounds = Counter(r.get("l2_rounds", 0) for r in ok)
    fallbacks = [r["case_id"] for r in ok if any("fallback" in w for w in (r.get("warnings") or []))]
    retries = [r["case_id"] for r in ok if r.get("warnings")]

    # --- calidad textual de las intervenciones ------------------------------
    echoes: Counter = Counter()
    body_chars: dict[str, list[int]] = defaultdict(list)
    raw_json_dumps = 0
    for cid, b in boards.items():
        for e in b["entries"]:
            body_chars[e["speaker"]].append(len(e["body"]))
            if e["speaker"] in ("LLM-1-GAP-ANALYST", "LLM-2-EVIDENCE"):
                for m in ECHO_MARKERS:
                    if m in e["body"]:
                        echoes[m] += 1
            if e["speaker"] == "LLM-2-EVIDENCE" and '{"case_id"' in e["body"]:
                raw_json_dumps += 1

    # --- trazabilidad numérica del texto libre --------------------------------
    # Todo número que aparezca en el `free_text` del presidente debería poder
    # encontrarse en algún sitio de la pizarra. Si no, es un número inventado,
    # que es exactamente lo que el juez de razonamiento del reto penaliza.
    # Y al revés: un razonamiento que sólo repite los números del panel visible es
    # una explicación *sobre* el caso, no una síntesis *de* la conferencia. Se mide
    # exigiendo al menos un valor que aparezca en el informe de L2 y NO en el panel.
    untraceable: dict[str, list[str]] = {}
    uses_evidence = 0
    mentions_conflict = 0
    n_boards = 0
    for cid, b in boards.items():
        chair = next((e for e in b["entries"] if e["speaker"] == "LLM-3-CHAIR"), None)
        if not chair:
            continue
        n_boards += 1
        text = chair["data"].get("reasoning", "")
        bodies = {e["speaker"]: e["body"] for e in b["entries"]}
        context = " ".join(v for k, v in bodies.items() if k != "LLM-3-CHAIR")
        nums = [n for n in set(re.findall(r"\d+\.?\d*", text)) if len(n) > 1]
        missing = [n for n in nums if n not in context]
        if missing:
            untraceable[cid] = sorted(missing)
        panel = bodies.get("INTAKE", "")
        evidence = bodies.get("LLM-2-EVIDENCE", "")
        if any(n in evidence and n not in panel for n in nums) or re.search(
            r"added no finding|added nothing|report added|notes? record|trajectory|compared with",
            text,
            re.I,
        ):
            uses_evidence += 1
        if re.search(r"prior|criterion|classifier|recommender|conference|disagree|overturn", text, re.I):
            mentions_conflict += 1

    return {
        "n_rows": len(rows),
        "n_ok": len(ok),
        "n_failed": len(failed),
        "failed": [(r["case_id"], r.get("error")) for r in failed],
        "n_labelled": len(labelled),
        "accuracy": round(len(correct) / len(labelled), 4) if labelled else None,
        "confusion_gt_pred": {f"{a}->{b}": c for (a, b), c in sorted(confusion.items())},
        "accuracy_by_prior_biopsy": {
            k: {"n": len(v), "acc": round(sum(v) / len(v), 3)} for k, v in sorted(by_bucket.items())
        },
        "pred_decision_dist": dict(Counter(r["decision"] for r in labelled)),
        "reveal_rate": {k: round(v / len(labelled), 3) for k, v in reveal_counts.most_common()} if labelled else {},
        "n_reveals_dist": dict(sorted(n_reveals.items())),
        "mean_tool_precision": round(sum(precisions) / len(precisions), 4) if precisions else None,
        "expected_precision_from_gt_rates": round(
            sum(GT_REVEAL_RATE.get(k, 0.0) * v for k, v in reveal_counts.items()) / sum(reveal_counts.values()), 4
        )
        if reveal_counts
        else None,
        "confidence_pred_dist": dict(conf_pred),
        "confidence_gt_vs_pred": {f"{a}->{b}": c for (a, b), c in sorted(conf_pairs.items())},
        "weight_dist": {k: dict(v.most_common()) for k, v in sorted(weight_dist.items())},
        "l1_rag_calls": l1_used_rag,
        "l2_rounds_dist": dict(sorted(l2_rounds.items())),
        "l3_fallbacks": fallbacks,
        "l3_retry_cases": retries,
        "prompt_echo_hits": dict(echoes),
        "l2_raw_json_dumps": raw_json_dumps,
        "mean_body_chars": {k: int(sum(v) / len(v)) for k, v in sorted(body_chars.items())},
        "free_text_untraceable_numbers": untraceable,
        "free_text_uses_retrieved_evidence_rate": round(uses_evidence / n_boards, 4) if n_boards else None,
        "free_text_names_the_conference_rate": round(mentions_conflict / n_boards, 4) if n_boards else None,
        "free_text_untraceable_rate": round(len(untraceable) / len(boards), 4) if boards else None,
        "mean_free_text_chars": int(sum(r["free_text_chars"] for r in ok) / len(ok)) if ok else None,
        "mean_seconds": round(sum(r["seconds"] for r in rows.values()) / len(rows), 1) if rows else None,
    }


def main() -> None:
    run_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "delete_solution_one/solution_task_one/runs/run1")
    print(json.dumps(analyse(load_run(run_dir)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
