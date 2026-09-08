"""Diagnóstico por caso de una corrida: qué regla decidió, si acertó, y qué
componente del case score se perdió.

    python -m ...analysis.diagnose --run runs/deployed
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
os.environ.setdefault("USE_RATIONALE_JUDGE", "0")
sys.path.insert(0, str(Path.home() / "PycharmProjects" / "CHIMERA-agent-eval" / "evaluation"))
import evaluate as ev  # noqa: E402

DATA = REPO / "data" / "task1"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--show-wrong", action="store_true")
    args = ap.parse_args()
    root = Path(args.run)
    summary = {}
    for line in (root / "summary.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            summary[r["case_id"]] = r
    gts = {ev.get_case_id(g): g for g in ev.load_ground_truth_records(DATA / "ground_truth", "task1")}
    rows = []
    for cid, g in gts.items():
        case = root / "output" / "task1" / cid
        pred = None
        if (case / "prostate-biopsy-decision.json").exists():
            pred = json.loads((case / "prostate-biopsy-decision-reasoning.json").read_text())
            pred["biopsy_decision"] = json.loads((case / "prostate-biopsy-decision.json").read_text())
            pred["case_id"] = cid
        o = ev.evaluate_case(g, pred, None, None)
        payload = json.loads((DATA / "agent_input" / cid / "structured-prompt.json").read_text())
        s = summary.get(cid, {})
        rows.append({"cid": cid, "bx": str(payload.get("bx")), "gt": g["biopsy_decision"], "pred": o.get("pred_decision"),
                     "ok": o["decision_score"] == 1.0, "case": o["case_score"], "rule": s.get("protocol_rule"),
                     "who": s.get("protocol_who"), "grade": s.get("grade"), "conf": o.get("confidence_score"),
                     "w": o.get("variable_weight_score"), "f": o.get("important_decisive_factor_score"),
                     "tool": o.get("tool_score"), "gnd": o.get("section_grounding_score"),
                     "chair": (s.get("chair_form") or {}).get("decision"), "warn": len(s.get("warnings") or []),
                     "secs": s.get("seconds"), "passes": s.get("passes")})
    n = len(rows)
    print(f"{n} casos; entregados {sum(1 for r in rows if r['pred'])}; puerta {sum(r['ok'] for r in rows)}/{n}")
    print("\n== acierto por cubo")
    for b in ("None", "Negative", "Positive"):
        sub = [r for r in rows if r["bx"] == b]
        print(f"  {b:9} {sum(r['ok'] for r in sub)}/{len(sub)}")
    print("\n== acierto por regla del protocolo")
    by = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        by[str(r["rule"])[:60]][0] += r["ok"]; by[str(r["rule"])[:60]][1] += 1
    for k, (h, t) in sorted(by.items(), key=lambda kv: -kv[1][1]):
        print(f"  {h:2}/{t:<3} {k}")
    print("\n== el presidente frente al protocolo")
    agree = sum(1 for r in rows if r["chair"] and r["chair"] == r["pred"])
    dis = [r for r in rows if r["chair"] and r["chair"] != r["pred"]]
    print(f"  firmó lo mismo que el protocolo en {agree}; disintió en {len(dis)}"
          + (f", y en esos el protocolo acertó {sum(r['ok'] for r in dis)}/{len(dis)}" if dis else ""))
    print("\n== componentes (media sobre los que pasan la puerta)")
    ok = [r for r in rows if r["ok"]]
    for k in ("conf", "w", "f", "tool", "gnd"):
        vals = [r[k] for r in ok if r[k] is not None]
        print(f"  {k:5} {sum(vals) / len(vals):.4f}" if vals else f"  {k:5} -")
    secs = [r["secs"] for r in rows if r.get("secs")]
    if secs:
        print(f"\n== tiempo medio por caso {sum(secs) / len(secs):.1f} s; pases>1 en "
              f"{sum(1 for r in rows if (r.get('passes') or 1) > 1)} casos")
    if args.show_wrong:
        print("\n== casos fallados")
        for r in rows:
            if not r["ok"]:
                print(f"  {r['cid']} bx={r['bx']:8} gt={r['gt']:3} pred={str(r['pred']):4} grade={r['grade']} "
                      f"rule={str(r['rule'])[:50]} chair={r['chair']}")


if __name__ == "__main__":
    main()
