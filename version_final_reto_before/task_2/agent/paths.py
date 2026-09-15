"""Single source for task 2 data, models and analysis artifact locations.

Mirrors task_1/agent/paths.py: the repo-level entries (templates, configs,
embedding model) are shared; DATA, CACHE, MODEL and RUNS are task-specific.
"""
from pathlib import Path
import os

REPO = Path(__file__).resolve().parents[3]
TASK_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "task2"  # 72 labelled of 153; the rest have no ground truth.
CACHE = TASK_ROOT / "experts_2" / "artifacts" / "panel_cache.json"
MODEL = TASK_ROOT / "experts_2" / "model"
ARTIFACT = {
    "expert_one": MODEL / "expert_one.joblib",
    "expert_two": MODEL / "expert_two.joblib",
    "expert_three": MODEL / "expert_three.joblib",
    "expert_four": MODEL / "expert_four.joblib",
    "expert_five": MODEL / "expert_five.joblib",
    "reasoning": MODEL / "reasoning_task2.joblib",
    "projector": MODEL / "embedding_projector.joblib",
}
EVAL_REPO = Path(os.getenv("CHIMERA_EVAL_REPO", Path.home() / "PycharmProjects" / "CHIMERA-agent-eval"))

RUNS = TASK_ROOT / "runs"
ANALYSIS = TASK_ROOT / "analysis"
EMBEDDING_MODEL = REPO / "model" / "embedding_model"
TEMPLATES = REPO / "templates" / "prompts"
RESOURCES = REPO / "resources"
CONFIGS = REPO / "configs"
SPLITS = REPO / "dev" / "splits"
