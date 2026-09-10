"""Contrato Grand Challenge de un caso; delega en los tres runners existentes.

No modifica inference.py. Pesos y embeddings locales, /input de sólo lectura,
y staging bajo /tmp. Un proceso/contenedor por paciente.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile

from .chimera_experts.io import Case, CLINICAL_FILENAME, DECISION_FILENAME, FEATURES_FILENAME
from .guards import validate_output

log = logging.getLogger(__name__)
REPO = Path(__file__).resolve().parents[2]


def _read(value):
    if isinstance(value, (str, Path)):
        value = json.loads(Path(value).read_text())
    if not isinstance(value, dict):
        raise ValueError("Input must be a JSON object or a path to one")
    return dict(value)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


async def _run(task, runner, case, input_dir, embedding_model_dir):
    from hydra import compose, initialize_config_dir
    from chimera_agent_baseline.models import load_model
    from chimera_agent_baseline.rag import start_embedding_service
    from langchain_mcp_adapters.client import MultiServerMCPClient

    model_dir = Path(os.environ.get("CHIMERA_MODEL_DIR", REPO / "model/gemma-4-E2B-it"))
    embeddings = Path(embedding_model_dir or REPO / "model/embedding_model")
    for path in (model_dir, embeddings):
        if not path.is_absolute() or not path.is_dir() or not any(path.iterdir()):
            raise ValueError(f"Local absolute populated model directory required: {path}")
    # Prevent library download fallbacks in the network-free challenge runtime.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    svc = None
    try:
        with initialize_config_dir(config_dir=str(REPO / "configs"), version_base=None):
            cfg = compose(config_name="config", overrides=["generation.temperature=0.0"])
        cfg.paths.model_dir = str(model_dir)
        cfg.model.model_id = str(model_dir)
        model = load_model(cfg)
        # T3 reads the supplied clinical documents directly, as its runner does.
        tools = []
        if task in (1, 2):
            svc = start_embedding_service(str(embeddings))
            client = MultiServerMCPClient({"chimera": {
                "command": sys.executable,
                "args": ["-m", "chimera_agent_baseline.mcp_server", "--data-dir", str(input_dir),
                         "--resource-dir", str(REPO / "resources"), "--tool-registry", f"task{task}",
                         "--log-level", "ERROR"], "transport": "stdio"}})
            tools = await client.get_tools()
        return await runner.run_case(case, input_dir, model, tools, cfg.agent.step_timeout)
    finally:
        if svc is not None:
            svc.stop()


def dispatch(task: int, *, structured_prompt, clinical_data, neural_representations,
             output_path, embedding_model_dir=None) -> int:
    """Escribe los dos JSON validados. Errores del grafo activan el respaldo del runner.

    Una tarea desconocida o un destino no escribible son errores del llamador.
    El respaldo se registra en stderr; devolver 0 indica salida escrita, no éxito del LLM.
    """
    if type(task) is not int or task not in (1, 2, 3):
        raise ValueError("task must be 1, 2 or 3")
    runner = importlib.import_module(f"delete_final_versions_task.task_{task}.agent.run_task{task}")
    case = Case("case", task)
    try:
        case.prompt = _read(structured_prompt)
        case.case_id = str(case.prompt.get("case_id") or case.prompt.get("pid") or "case")
        case.clinical = _read(clinical_data)
        case.embeddings = _read(neural_representations)
        with tempfile.TemporaryDirectory(prefix="chimera-", dir="/tmp") as tmp:
            # Case IDs are directory names in both the feature store and MCP.
            input_dir = Path(tmp) / f"task{task}" / "agent_input"
            if Path(case.case_id).name != case.case_id or case.case_id in (".", ".."):
                raise ValueError("case_id must be a single safe path component")
            staged = input_dir / case.case_id
            _write(staged / "structured-prompt.json", {**case.prompt, "case_id": case.case_id})
            _write(staged / CLINICAL_FILENAME[task], case.clinical)
            _write(staged / FEATURES_FILENAME, case.embeddings)
            payload, event = asyncio.run(_run(task, runner, case, input_dir, embedding_model_dir))
            valid, why = validate_output(task, payload)
            if not valid:
                raise ValueError(why)
    except Exception:
        log.exception("Task %s case %s failed; writing fallback", task, case.case_id)
        payload, event = runner.fallback_case(case)
    valid, why = validate_output(task, payload)
    if not valid:
        raise ValueError(f"Invalid fallback: {why}")
    if task == 3:
        files = runner.to_gc_outputs(payload, event)
    else:
        decision, reasoning = runner.to_gc_outputs(payload)
        # The GC output-socket schema requires the full per-task variable set
        # in variable_weights; pad any omitted key with "not_used".
        if isinstance(reasoning, dict) and "variable_weights" in reasoning:
            from chimera_agent_baseline.output.schema import normalise_to_full_shape

            reasoning["variable_weights"] = normalise_to_full_shape(
                task, {"variable_weights": reasoning["variable_weights"]}
            )["variable_weights"]
        name = DECISION_FILENAME[task]
        files = {name: decision, name.replace(".json", "-reasoning.json"): reasoning}
    for name, value in files.items():
        _write(Path(output_path) / name, value)
    return 0


def run_task1_case(**kwargs):
    return dispatch(1, **kwargs)


def run_task2_case(**kwargs):
    return dispatch(2, **kwargs)


def run_task3_case(**kwargs):
    return dispatch(3, **kwargs)
