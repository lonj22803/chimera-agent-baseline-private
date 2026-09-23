"""Generate baseline evidence for PASO 0.1."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from version_final_reto.task_1.agent import protocol as P
from version_final_reto.task_1.analysis import simulate
from version_final_reto.task_1.experts_1.panel import CACHE, Panel

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "Ablation_study" / "results"
HASH_TARGETS = (
    ROOT / "version_final_reto_send_v4",
    ROOT / "src",
    ROOT / "inference.py",
    ROOT / "dev",
)


def _iter_hash_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".log":
            continue
        files.append(path)
    return sorted(files)


def write_fingerprint(path: Path) -> None:
    lines = []
    for target in HASH_TARGETS:
        if not target.exists():
            lines.append(f"MISSING  {target.relative_to(ROOT)}")
            continue
        for file_path in _iter_hash_files(target):
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {file_path.relative_to(ROOT)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _step_counts(rows: list[dict], scored: list[dict]) -> dict[str, str]:
    counts: dict[str, list[int]] = {}
    scored_by_case = {row["case_id"]: row for row in scored}
    for row in rows:
        case_id = row["case_id"]
        if case_id not in scored_by_case:
            continue
        key = str(row.get("who") or row.get("rule") or "unknown")
        counts.setdefault(key, [0, 0])
        counts[key][0] += int(scored_by_case[case_id]["decision_score"] == 1.0)
        counts[key][1] += 1
    return {key: f"{hit}/{total}" for key, (hit, total) in sorted(counts.items())}


def _run_anchor(mode: str) -> dict:
    panel = Panel(Path(CACHE))
    params = {
        **P.PARAMS,
        "confidence_policy": P.PARAMS["confidence_policy"],
        "threshold": P.PARAMS["threshold"],
        "library_weight": P.PARAMS["library_weight"],
        "grade_rule": P.PARAMS["grade_rule"],
    }
    rows = simulate.simulate(mode, True, 3, params, "model+mode", panel)
    score = simulate.score(rows)
    scored_rows = score.pop("rows")
    score["by_step"] = _step_counts(rows, scored_rows)
    score["n_rows"] = len(scored_rows)
    return score


def write_anchors(path: Path) -> None:
    data = {
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "modes": {mode: _run_anchor(mode) for mode in ("deployed", "honest")},
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    os.environ.setdefault("USE_RATIONALE_JUDGE", "0")
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_fingerprint(RESULTS / "huella_v4.txt")
    write_anchors(RESULTS / "anclas.json")


if __name__ == "__main__":
    main()
