"""¿Cambian los números de los expertos al poner los bosques en un hilo?

Un proceso por caso y por brazo, porque los imputadores de la tarea 1 llevan
``sample_posterior=True`` y su ``RandomState`` avanza con cada pasada: dos casos
en el mismo intérprete no son comparables. El brazo de control apaga
``serial_predict`` antes de importar nada, así que los estimadores se quedan
exactamente como los dejó el entrenamiento.

Uso::

    python3 verification/compare_experts.py --task 1 --cases 6 --cpuset 4-27
"""
import argparse
import json
import math
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).resolve().parent / "expert_worker.py"


def run_worker(task: int, case_dir: Path, arm: str, cpuset: str | None) -> dict:
    cmd = (["taskset", "-c", cpuset] if cpuset else []) + \
          [sys.executable, str(WORKER), str(task), str(case_dir), arm]
    proc = subprocess.run(cmd, text=True, capture_output=True, cwd=str(ROOT))
    line = next((l for l in proc.stdout.splitlines() if l.startswith("{")), None)
    if line is None:
        return {"error": (proc.stderr or proc.stdout)[-800:], "case": case_dir.name, "arm": arm}
    return json.loads(line)


def deltas(a, b, path="", out=None):
    """Diferencias hoja a hoja entre dos payloads, con su ruta."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            deltas(a.get(key), b.get(key), f"{path}.{key}", out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            deltas(x, y, f"{path}[{i}]", out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if a != b:
            out.append((path, float(a), float(b), abs(float(a) - float(b))))
    elif a != b:
        out.append((path, a, b, math.inf))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=int, default=1)
    ap.add_argument("--cases", type=int, default=6)
    ap.add_argument("--cpuset", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = ROOT / "data" / f"task{args.task}" / "agent_input"
    dirs = sorted(d for d in root.iterdir() if d.is_dir())[: args.cases]
    jobs = [(d, arm) for d in dirs for arm in ("base", "njobs1")]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        results = list(pool.map(
            lambda job: run_worker(args.task, job[0], job[1], args.cpuset or None), jobs))

    by_case: dict[str, dict] = {}
    for row in results:
        by_case.setdefault(row.get("case_id") or row.get("case"), {})[row.get("arm", "?")] = row

    report = {"task": args.task, "cases": len(dirs), "seconds": round(time.monotonic() - started, 1),
              "per_case": {}, "worst_delta": 0.0, "identical": True, "errors": []}
    for case_id, arms in sorted(by_case.items()):
        base, fast = arms.get("base"), arms.get("njobs1")
        if base is None or fast is None or "error" in base or "error" in fast:
            report["errors"].append({"case_id": case_id, "arms": {k: v.get("error") for k, v in arms.items()}})
            report["identical"] = False
            continue
        diff = deltas(base["payload"], fast["payload"])
        worst = max((d[3] for d in diff), default=0.0)
        report["worst_delta"] = max(report["worst_delta"], worst)
        if diff:
            report["identical"] = False
        report["per_case"][case_id] = {
            "seconds_base": base["seconds"], "seconds_njobs1": fast["seconds"],
            "speedup": round(base["seconds"] / max(fast["seconds"], 1e-9), 2),
            "n_differing_leaves": len(diff),
            "worst_delta": worst,
            "worst_field": (max(diff, key=lambda d: d[3])[0] if diff else None),
            "decision_changed": base["payload"] != fast["payload"] and _decisions(base) != _decisions(fast),
            "decisions_base": _decisions(base), "decisions_njobs1": _decisions(fast),
        }
    text = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)


def _decisions(row) -> dict:
    """Las decisiones publicadas, que son lo que entra en la métrica."""
    payload = row["payload"]
    found = {}

    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("decision", "tier", "ladder", "verdict", "confidence"):
                    found[f"{path}.{k}"] = v
                walk(v, f"{path}.{k}")
    walk(payload)
    return found


if __name__ == "__main__":
    main()
