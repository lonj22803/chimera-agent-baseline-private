"""El contrato del agente, cargado desde las copias literales de ``contract/verbatim/``.

Todo lo que el modelo ve en inferencia sale de aquí, para que el entrenamiento use
exactamente los mismos textos que el agente del reto:

* el prompt del sistema y la plantilla del caso;
* la lista de herramientas por tarea (volcada del servidor MCP real);
* el contenido de cada respuesta de herramienta, con la misma forma que produce
  ``langchain-mcp-adapters`` (una lista de bloques ``{"type": "text", ...}``);
* los prompts del nodo form-fill y las variables elegibles.

No reimplementa nada del agente: importa las funciones copiadas tal cual.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
import uuid
from pathlib import Path
from typing import Any

KIT = Path(__file__).resolve().parent.parent
VERBATIM = KIT / "contract" / "verbatim"
TOOL_SCHEMAS = KIT / "contract" / "tool_schemas"

CLINICAL_DATA_FILE = {
    1: "prostate-biopsy-decision-clinical-data.json",
    2: "prostate-treatment-decision-clinical-data.json",
    3: "prostate-time-to-recurrence-or-last-follow-up-clinical-data.json",
}

# Ficheros de ground truth: mismo nombre que las salidas del agente.
GT_FILES = {
    1: ("prostate-biopsy-decision.json", "prostate-biopsy-decision-reasoning.json"),
    2: ("prostate-treatment-decision.json", "prostate-treatment-decision-reasoning.json"),
    3: (
        "prostate-time-to-recurrence-or-last-follow-up.json",
        "prostate-time-to-recurrence-or-last-follow-up-reasoning.json",
    ),
}


def _load(name: str, filename: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, VERBATIM / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _package(name: str) -> None:
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = []
        sys.modules[name] = pkg


# Las copias importan por su ruta de paquete original; se registran con ese nombre.
for _p in ("chimera_agent_baseline", "chimera_agent_baseline.output",
           "chimera_agent_baseline.tools", "chimera_agent_baseline.agent"):
    _package(_p)
schema = _load("chimera_agent_baseline.output.schema", "schema.py")
tools_base = _load("chimera_agent_baseline.tools.base", "base.py")
definitions = _load("chimera_agent_baseline.tools.definitions", "definitions.py")
prompts = _load("chimera_agent_baseline.agent.prompts", "prompts.py")
form_fill = _load("chimera_agent_baseline.agent.form_fill", "form_fill.py")

SYSTEM_PROMPT: str = prompts.build_system_prompt()
FORM_FILL_SYSTEM_PROMPT: str = form_fill._SYSTEM_PROMPT

TASK_TOOLS = {1: definitions.TASK1_TOOLS, 2: definitions.TASK2_TOOLS, 3: definitions.TASK3_TOOLS}
TOOL_FIELDS = {t: {s.name: s.fields for s in specs} for t, specs in TASK_TOOLS.items()}

# Sección del ``reveal_sequence`` -> herramienta. T3 no tiene ``reveal_sequence``
# en la salida, pero se usa el mismo nombre de sección para construir su política.
SECTION_TO_TOOL = {
    "radiology_report": "get_mri_report",
    "pathology_report": "get_pathology_report",
    "surgical_pathology_report": "get_surgical_pathology_report",
    "psa_trend": "get_psa_trend",
    "previous_notes": "get_previous_notes",
    "laboratory_results": "get_lab_results",
    "family_history": "get_family_history",
}

# Orden canónico de llamada (el que recomienda el prompt del sistema).
CANONICAL_TOOL_ORDER = [
    "get_mri_report",
    "get_pathology_report",
    "get_surgical_pathology_report",
    "get_psa_trend",
    "get_previous_notes",
    "get_lab_results",
    "get_family_history",
]


def tool_schemas(task: int) -> list[dict]:
    """La lista ``tools=`` exacta que el agente pasa a ``llm.chat`` en esa tarea."""
    return json.loads((TOOL_SCHEMAS / f"tools_task{task}.json").read_text())


def render_case_prompt(payload: dict[str, Any]) -> str:
    """Primer ``HumanMessage``: ``agent_prompt.j2`` renderizado como en ``case_loader``."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(VERBATIM)), keep_trailing_newline=True)
    return env.get_template("agent_prompt.j2").render(**payload)


def tool_result_text(task: int, tool: str, case_id: str, clinical: dict[str, Any]) -> str:
    """Texto que devuelve el servidor MCP (``mcp_server._register_precomputed_tool``)."""
    fields = TOOL_FIELDS[task][tool]
    out: dict[str, Any] = {"case_id": clinical.get("case_id", case_id)}
    for f in fields:
        if f in clinical:
            out[f] = clinical[f]
    if set(out) == {"case_id"}:
        return json.dumps({"case_id": case_id, "note": "No data available for this tool and case."})
    return json.dumps(out)


def tool_message_content(text: str) -> list[dict[str, str]]:
    """Forma del ``ToolMessage.content`` tras ``langchain-mcp-adapters`` 0.2.2.

    Medido con el servidor real: una lista con un bloque de texto y un ``id``
    aleatorio. ``ChatVLLM`` la pasa sin tocar a ``llm.chat``.
    """
    return [{"type": "text", "text": text, "id": f"lc_{uuid.uuid4()}"}]


def eligible_variables(task: int, called: set[str]) -> list[str]:
    if task not in schema.VARIABLES_BY_TASK:
        return []
    return schema.eligible_variables(task, called)


def form_fill_user_prompt(case_id: str, task: int, transcript: str, called: set[str]) -> str:
    """Mensaje de usuario del form-fill, idéntico al de ``make_form_fill_node``."""
    elig = eligible_variables(task, called)
    base = form_fill._user_prompt(case_id, task, transcript, sorted(called), elig)
    return base + "\n\n" + form_fill._build_skeleton_instructions(task, elig)


def validate_form_fill(task: int, called: set[str], obj: dict[str, Any]) -> dict[str, Any]:
    """Valida el JSON objetivo con el mismo modelo dinámico que usa el form-fill."""
    if task in schema.VARIABLES_BY_TASK:
        model = schema.build_dynamic_model(task, called)
    else:
        model = schema.TASK_OUTPUT_MODELS[task]
    return model.model_validate(obj).model_dump(mode="json")
