"""Single source for task 1 data, models and analysis artifact locations."""
from pathlib import Path
import os

REPO = Path(__file__).resolve().parents[3]
TASK_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "task1"  # The 91 labelled precedents are read at runtime.
CACHE = TASK_ROOT / "artifacts" / "panel_cache.json"
MODEL = TASK_ROOT / "experts_1" / "model"
ARTIFACT = {
    "structured": MODEL / "expert_one.joblib",
    "fusion": MODEL / "expert_three.joblib",
    "psa": MODEL / "expert_two_psa_projector.joblib",
    "trace": MODEL / "reasoning_trace_model.joblib",
}
EVAL_REPO = Path(os.getenv("CHIMERA_EVAL_REPO", Path.home() / "PycharmProjects" / "CHIMERA-agent-eval"))
# Optional historical comparisons; the agent and simulation do not need them.
PREVIOUS = {name: TASK_ROOT / "analysis" / "historical" / key / "output"
            for name, key in (("baseline T=0", "baseline"), ("pizarra v1", "v1"),
                              ("pizarra v2", "v2"), ("junta", "junta"),
                              ("junta+expertos", "experts"))}

RUNS = TASK_ROOT / "runs"
ANALYSIS = TASK_ROOT / "analysis"
NOTEBOOK = ANALYSIS / "analisis_final.ipynb"
ANATOMIA = ANALYSIS / "anatomia_del_agente.ipynb"
EMBEDDING_MODEL = REPO / "model" / "embedding_model"
LANGUAGE_MODEL = REPO / "model" / "gemma-4-E2B-it"
TEMPLATES = REPO / "templates" / "prompts"
RESOURCES = REPO / "resources"
CONFIGS = REPO / "configs"
SPLITS = REPO / "dev" / "splits"
