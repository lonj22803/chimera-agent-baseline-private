"""Entrada de la V2: la tubería de la V1.1 con el perfil de memoria sustituido.

En esta fase V2 **no** cambia decisiones, prompts ni expertos. El PLAN lo pide
así en E11: «Comparar la misma V2 congelada, casos y prompts, variando primero
sólo gestión de memoria». Lo único que se sustituye es quién reparte la VRAM.

Misma técnica que ``inference_v1_1.py`` y por la misma razón: no se copia
código, se importa el módulo real y se reasigna el nombre que hay que cambiar.
``gc_entry._run`` resuelve ``configure`` en los globales de su módulo cuando lo
llama, así que reasignarlo aquí basta y no hay una segunda copia que mantener.

Lo que queda intacto: los tres runners, la pizarra, los expertos, MCP, el
servicio de embeddings, el reloj de ``deadline`` y los dos JSON por interfaz.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import inference as base
except ModuleNotFoundError:  # ejecución local, fuera de /opt/app
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import inference as base

from delete_final_versions_task_V1_1.common import gc_entry
from delete_final_versions_task_V2.runtime import resources

#: La sustitución. ``common/runtime.py`` de la V1.1 capa el motor en 19 GiB y
#: deja que vLLM se quede con lo libre de la tarjeta; ``resources.configure``
#: aplica el techo de §13.1 y dimensiona el KV por paciente.
gc_entry.configure = resources.configure


def run_merged_solution(*, task, structured_prompt, clinical_data, neural_representations) -> int:
    """Idéntica a la de la V1.1 salvo el perfil ya sustituido arriba."""
    os.environ["CHIMERA_MODEL_DIR"] = str(base.MODEL_PATH)

    return gc_entry.dispatch(
        task=task,
        structured_prompt=structured_prompt,
        clinical_data=clinical_data,
        neural_representations=neural_representations,
        output_path=base.OUTPUT_PATH,
        embedding_model_dir=str(base.EMBEDDING_MODEL_PATH),
    )


base.run_merged_solution = run_merged_solution

run = base.run

if __name__ == "__main__":
    raise SystemExit(base.run())
