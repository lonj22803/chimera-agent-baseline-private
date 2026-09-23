"""Rutas unicas para la extension de ablacion T2/T3."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "Ablation_study" / "T2_T3"
RESULTS = STUDY / "results"
RUNS = STUDY / "runs"
REPORTS = STUDY / "reports"
LOGS = STUDY / "logs"
DATA = ROOT / "data"
DATA2 = DATA / "task2"
DATA3 = DATA / "task3"
SPLITS = ROOT / "dev" / "splits"
EVAL_REPO = Path(
    os.getenv("CHIMERA_EVAL_REPO", Path.home() / "PycharmProjects" / "CHIMERA-agent-eval")
)


def ensure_dirs() -> None:
    for path in (RESULTS, RUNS, REPORTS, LOGS):
        path.mkdir(parents=True, exist_ok=True)
