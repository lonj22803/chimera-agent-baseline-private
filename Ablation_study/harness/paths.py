"""Path constants for the Task 1 ablation study."""

from __future__ import annotations

from pathlib import Path

from version_final_reto.task_1.agent import paths as v4_paths

REPO: Path = v4_paths.REPO
DATA: Path = v4_paths.DATA
EVAL_REPO: Path = v4_paths.EVAL_REPO
V4_ROOT: Path = REPO / "version_final_reto_send_v4"
STUDY_ROOT: Path = REPO / "Ablation_study"

CACHE: Path = v4_paths.CACHE
TASK_ROOT: Path = v4_paths.TASK_ROOT
SPLITS: Path = v4_paths.SPLITS

CONFIGS: Path = STUDY_ROOT / "configs"
HARNESS: Path = STUDY_ROOT / "harness"
TESTS: Path = STUDY_ROOT / "ablacion_tests"
RESULTS: Path = STUDY_ROOT / "results"
RUNS: Path = STUDY_ROOT / "runs"
REPORTS: Path = STUDY_ROOT / "reports"
