"""Reproduce las medidas de ``CRITERIO_DIAGNOSTICO.md``.

Los tres cubos clínicos, las AUC por variable dentro del cubo indeterminado y
la tabla de políticas con separación dev / val. Todo sale de
``data/task1/ground_truth`` y de los splits de ``dev/splits``; nada está
escrito a mano en el documento que este script no calcule aquí.

    python delete_solution_one/solution_task_one/analysis/criterio.py
    python delete_solution_one/solution_task_one/analysis/criterio.py --run runs/run1
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / "data" / "task1"
SOL = REPO / "delete_solution_one" / "solution_task_one"
if str(SOL.parent.parent) not in sys.path:
    sys.path.insert(0, str(SOL.parent.parent))

STRUCTURED_VARS = ("psa", "age", "pirads", "psad", "psav", "psap", "vol", "cspca", "months")


def _num(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def load(run: Path | None = None) -> list[dict]:
    dev = {ln.strip() for ln in (REPO / "dev" / "splits" / "task1_dev.txt").read_text().splitlines() if ln.strip()}
    out = []
    for d in sorted((ROOT / "ground_truth").iterdir()):
        if not d.is_dir():
            continue
        cid = d.name
        row = {
            "cid": cid,
            "p": json.loads((ROOT / "agent_input" / cid / "structured-prompt.json").read_text()),
            "y": json.loads((d / "prostate-biopsy-decision.json").read_text()),
            "r": json.loads((d / "prostate-biopsy-decision-reasoning.json").read_text()),
            "split": "dev" if cid in dev else "val",
        }
        row["bx"] = str(row["p"].get("bx"))
        if run is not None:
            f = run / "output" / "task1" / cid / "prostate-biopsy-decision.json"
            row["agent"] = json.loads(f.read_text()) if f.exists() else None
        out.append(row)
    return out


def protocol(row: dict) -> str | None:
    """El criterio de protocolo; ``None`` cuando el panel no determina el caso."""
    from delete_solution_one.solution_task_one.experts.protocol import criterion  # noqa: PLC0415

    return criterion(row["p"])["verdict"]


def f1_yes(rows: list[dict], fn) -> float:
    cm = Counter((r["y"], fn(r)) for r in rows)
    tp = cm[("yes", "yes")]
    fp = sum(v for (g, q), v in cm.items() if q == "yes" and g != "yes")
    fn_ = sum(v for (g, q), v in cm.items() if g == "yes" and q != "yes")
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn_)
    return 2 * prec * rec / max(1e-9, prec + rec)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="corrida cuyas decisiones usar como 'agente'")
    args = ap.parse_args()
    run = (SOL / args.run) if args.run else None
    rows = load(run)

    print(f"casos etiquetados: {len(rows)}   dev/val: "
          f"{Counter(r['split'] for r in rows)}\n")

    # --- 1. los tres cubos --------------------------------------------------
    print("=== 1. Los tres cubos clínicos ===")
    for bx in ("None", "Negative", "Positive"):
        sub = [r for r in rows if r["bx"] == bx]
        dec = Counter(r["y"] for r in sub)
        pir = defaultdict(Counter)
        for r in sub:
            pir[str(r["p"].get("pirads"))][r["y"]] += 1
        hits = sum(1 for r in sub if protocol(r) == r["y"]) if protocol(sub[0]) is not None else None
        print(f"  bx = {bx:9} n={len(sub):3d}  {dict(dec)}")
        print(f"      por PI-RADS: {{{', '.join(f'{k}: {dict(v)}' for k, v in sorted(pir.items()))}}}")
        print(f"      criterio de protocolo: {f'{hits}/{len(sub)}' if hits is not None else 'se abstiene'}")
        conf = Counter(r["r"]["confidence"] for r in sub)
        print(f"      confianza declarada por el urólogo: {dict(conf)}")
    print()

    # --- 2. AUC dentro del cubo indeterminado -------------------------------
    print("=== 2. ¿Separa alguna variable estructurada dentro de bx = Positive? ===")
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415

    sub = [r for r in rows if r["bx"] == "Positive"]
    yb = np.array([1 if r["y"] == "yes" else 0 for r in sub])
    for v in STRUCTURED_VARS:
        x = np.array([_num(r["p"].get(v)) for r in sub])
        m = np.isfinite(x)
        if m.sum() < 10 or len(set(yb[m])) < 2:
            continue
        print(f"  {v:8} AUC={roc_auc_score(yb[m], x[m]):.3f}  (n={m.sum()})")
    rising = sum(1 for r in sub if _num(r["p"].get("psav")) > 0)
    print(f"  PSA con velocidad positiva: {rising}/{len(sub)} casos -> no discrimina nada\n")

    # --- 3. políticas -------------------------------------------------------
    print("=== 3. Políticas de decisión ===")
    policies: dict[str, Any] = {
        "protocolo + \"siempre no\"": lambda r: protocol(r) or "no",
    }
    if run is not None and all(r.get("agent") for r in rows):
        policies = {
            "agente solo": lambda r: r["agent"],
            "protocolo + agente": lambda r: protocol(r) or r["agent"],
            **policies,
        }
    try:
        sys.path.insert(0, str(SOL.parent / "recomendador_inicial"))
        from entrenar_recomendador_inicial import RecomendadorInicial  # noqa: PLC0415

        rec = RecomendadorInicial.cargar()
        cache = {r["cid"]: rec.recomendar(prompt=r["p"])["prediccion"] for r in rows}
        policies["prior kNN solo"] = lambda r: cache[r["cid"]]
        policies["protocolo + prior"] = lambda r: protocol(r) or cache[r["cid"]]
    except Exception as exc:  # noqa: BLE001
        print(f"  (recomendador inicial no disponible: {exc})")

    print(f"  {'política':28} {'dev':>7} {'val':>7} {'total':>7} {'F1(yes)':>9}   por cubo")
    for name, fn in policies.items():
        accs = {}
        for sp in ("dev", "val", "all"):
            S = [r for r in rows if sp == "all" or r["split"] == sp]
            accs[sp] = float(np.mean([fn(r) == r["y"] for r in S]))
        byb = defaultdict(list)
        for r in rows:
            byb[r["bx"]].append(fn(r) == r["y"])
        cubes = {k: round(float(np.mean(v)), 3) for k, v in sorted(byb.items())}
        print(f"  {name:28} {accs['dev']:7.3f} {accs['val']:7.3f} {accs['all']:7.3f} "
              f"{f1_yes(rows, fn):9.3f}   {cubes}")


if __name__ == "__main__":
    main()
