"""Renderiza los tres prompts que ve el modelo para un caso, a partir de las copias literales.

    python lora_kit/contract/render_example.py <dir_del_caso> <salida>

El caso es un directorio con structured-prompt.json y *-clinical-data.json. Genera
system_prompt.txt, user_prompt.txt (primer HumanMessage) y un form_fill_user_prompt.txt
de muestra, calculado como si el agente hubiera llamado a get_mri_report y get_psa_trend.
"""
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

HERE = Path(__file__).resolve().parent / "verbatim"
sys.path.insert(0, str(HERE))

import prompts  # noqa: E402
import schema  # noqa: E402

# form_fill.py importa el esquema por su ruta de paquete; se le da un alias.
import types  # noqa: E402
pkg = types.ModuleType("chimera_agent_baseline"); pkg.__path__ = []
sub = types.ModuleType("chimera_agent_baseline.output"); sub.__path__ = []
sys.modules.update({"chimera_agent_baseline": pkg, "chimera_agent_baseline.output": sub,
                    "chimera_agent_baseline.output.schema": schema})
import form_fill  # noqa: E402

case_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
payload = json.loads((case_dir / "structured-prompt.json").read_text())
task = int(payload.get("task", 1))

env = Environment(loader=FileSystemLoader(str(HERE)), keep_trailing_newline=True)
(out / "system_prompt.txt").write_text(prompts.build_system_prompt())
(out / "user_prompt.txt").write_text(env.get_template("agent_prompt.j2").render(**payload))

called = ["get_mri_report", "get_psa_trend"]
elig = schema.eligible_variables(task, set(called)) if task in schema.VARIABLES_BY_TASK else []
transcript = "<AQUI VA EL TEXTO FINAL DEL BUCLE ReAct>"
user = form_fill._user_prompt(payload["case_id"], task, transcript, sorted(called), elig)
user += "\n\n" + form_fill._build_skeleton_instructions(task, elig)
(out / "form_fill_system_prompt.txt").write_text(form_fill._SYSTEM_PROMPT)
(out / "form_fill_user_prompt.txt").write_text(user)
print("escrito en", out)
