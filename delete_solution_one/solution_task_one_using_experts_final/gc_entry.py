"""Punto de entrada para Grand Challenge: un caso, un contenedor.

En el reto cada caso llega solo. ``inference.py`` recibe en ``/input`` los tres
ficheros de un paciente, tiene que arrancar el modelo, decidir y escribir dos
ficheros en ``/output``. Esta solución se desarrolló con un runner por lotes,
así que la adaptación vive aquí y **no en el upstream**: integrarla es un cambio
de dos líneas en ``inference.py``.

```python
from delete_solution_one.solution_task_one_using_experts_final.gc_entry import run_task1_case

def interf0_handler():
    return run_task1_case(
        structured_prompt=load_json_file(location=INPUT_PATH / "structured-prompt.json"),
        clinical_data=load_json_file(location=INPUT_PATH / "prostate-biopsy-decision-clinical-data.json"),
        neural_representations=load_json_file(
            location=INPUT_PATH / "prostate-modality-level-neural-representations.json"),
        output_path=OUTPUT_PATH,
    )
```

Lo que hace, en orden: escribe el caso en un directorio temporal con el layout
que el servidor MCP espera, arranca el servidor sobre ese directorio, construye
el grafo, lo invoca, valida la salida contra ``Task1Output`` y escribe los dos
ficheros. Si algo falla, escribe igualmente una salida válida construida desde
los expertos: en Grand Challenge un caso sin salida no es un cero, es un caso
perdido que además cuesta recall en el F1 de su clase.

Tres cosas que hay que empaquetar en la imagen, y que el README documenta:
los artefactos ``.joblib`` de los cuatro expertos, los 91 casos etiquetados —la
biblioteca de precedentes y la moda por cubo los leen en tiempo de ejecución— y
``scikit-learn==1.9.0``, que es con la que se serializaron.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DECISION_FILE = "prostate-biopsy-decision.json"
REASONING_FILE = "prostate-biopsy-decision-reasoning.json"
CLINICAL_FILE = "prostate-biopsy-decision-clinical-data.json"
FEATURES_FILE = "prostate-modality-level-neural-representations.json"


def _write(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False))


def _stage(case_id: str, prompt: dict, clinical: dict, features: dict, root: Path) -> Path:
    """El layout ``agent_input/<case>/`` que el servidor MCP indexa."""
    case_dir = root / "agent_input" / case_id
    _write(case_dir / "structured-prompt.json", prompt)
    _write(case_dir / CLINICAL_FILE, clinical or {})
    _write(case_dir / FEATURES_FILE, features or {})
    return root / "agent_input"


def run_task1_case(
    structured_prompt: dict,
    clinical_data: dict,
    neural_representations: dict,
    output_path: Path,
    *,
    config_path: Path | None = None,
    labelled_root: Path | None = None,
    panel_cache: Path | None = None,
    templates_dir: Path | None = None,
    resource_dir: Path | None = None,
    embedding_model_dir: Path | None = None,
) -> int:
    """Decide un caso y escribe los dos ficheros del reto. Devuelve 0 siempre."""
    from hydra import compose, initialize_config_dir
    from langchain_mcp_adapters.client import MultiServerMCPClient

    from chimera_agent_baseline.case_loader import render_baseline_prompt
    from chimera_agent_baseline.features import FeatureStore
    from chimera_agent_baseline.models import load_model
    from chimera_agent_baseline.rag import start_embedding_service

    from .decide import to_gc_outputs, validate_output
    from .experts.library import Library
    from .experts.panel import CACHE, Panel
    from .graph import create_conference_graph

    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    config_path = Path(config_path or repo / "configs")
    templates_dir = Path(templates_dir or repo / "templates" / "prompts")
    resource_dir = Path(resource_dir or repo / "resources")
    labelled_root = Path(labelled_root or repo / "data" / "task1")
    panel_cache = Path(panel_cache or CACHE)
    output_path = Path(output_path)

    case_id = str(structured_prompt.get("case_id") or structured_prompt.get("pid") or "case")
    payload = dict(structured_prompt)

    svc = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = _stage(case_id, payload, clinical_data, neural_representations, Path(tmp))
            if embedding_model_dir is not None:
                svc = start_embedding_service(str(embedding_model_dir))
            with initialize_config_dir(config_dir=str(config_path), version_base=None):
                cfg = compose(config_name="config", overrides=["generation.temperature=0.0"])
            model = load_model(cfg)
            panel = Panel(panel_cache) if panel_cache.exists() else None
            # En el test el caso nunca está en el caché: se puntúa en vivo.
            if panel is not None:
                try:
                    panel.ensure(case_id, {"prompt": payload, "clinical": clinical_data,
                                           "features": neural_representations})
                except Exception as exc:  # noqa: BLE001
                    log.exception("No se pudo puntuar en vivo: %s", exc)
            library = Library(labelled_root, exclude_self=True) if (labelled_root / "ground_truth").is_dir() else None

            async def _go() -> dict:
                client = MultiServerMCPClient({"chimera": {
                    "command": sys.executable,
                    "args": ["-m", "chimera_agent_baseline.mcp_server", "--data-dir", str(input_dir),
                             "--resource-dir", str(resource_dir), "--tool-registry", "task1",
                             "--log-level", "ERROR"],
                    "transport": "stdio"}})
                tools = await client.get_tools()
                graph = create_conference_graph(tools, model, FeatureStore(input_dir), panel, library,
                                                step_timeout=cfg.agent.step_timeout)
                state = await graph.ainvoke(
                    {"case_id": case_id, "task": 1, "prompt_payload": payload,
                     "case_files": {"prompt": payload, "clinical": clinical_data,
                                    "features": neural_representations},
                     "case_prompt": render_baseline_prompt(payload, templates_dir)},
                    {"recursion_limit": 160})
                return state["structured_response"]

            structured = asyncio.run(_go())
            ok, why = validate_output(structured)
            if not ok:
                raise ValueError(f"la salida no valida contra Task1Output: {why}")
            decision, reasoning = to_gc_outputs(structured)
    except Exception as exc:  # noqa: BLE001 — un caso sin salida es un caso perdido
        log.exception("La junta falló en %s; se escribe la salida de respaldo: %s", case_id, exc)
        decision, reasoning = _fallback(payload)

    _write(output_path / DECISION_FILE, decision)
    _write(output_path / REASONING_FILE, reasoning)
    return 0


def _fallback(payload: dict) -> tuple[str, dict]:
    """Salida válida sin la junta: el criterio de cohorte y la nota determinista.

    No usa el LLM ni los expertos: es el último recurso, y aun así respeta el
    esquema y no afirma nada que no esté en el panel.
    """
    from .decide import clinical_note
    from .experts.cohort import criterion
    from .protocol import clinical_reason

    c = criterion(payload)
    decision = c["verdict"] or "yes"
    because, against, alternative = clinical_reason(payload, None, [], decision)
    return decision, {
        "confidence": "uncertain",
        "variable_weights": {"bx": "important", "fh": "not_used", "age": "noted", "dre": "not_used",
                             "psa": "important", "vol": "not_used", "psad": "not_used",
                             "cspca": "not_used", "pirads": "not_used", "comorbidity": "noted"},
        "reveal_sequence": [],
        "free_text": clinical_note(payload, None, [], because, decision, against, alternative),
    }
