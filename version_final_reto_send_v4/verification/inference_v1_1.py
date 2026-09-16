"""Entrada de la versión V1: el `inference.py` real, con una sola pieza sustituida.

Antes esto era una copia de las 504 líneas de `inference.py` que difería en una:
el paquete del que sale `dispatch`. Dos copias que difieren en una línea no se
mantienen solas — un arreglo en el staging del tmpdir o en un manejador de
interfaz se aplicaría a una y no a la otra, y cuál se entrega depende de qué monte
el Dockerfile. El fallo no sería ruidoso: sería «Missing or extra output files».

Aquí no se copia nada. Se importa el módulo de verdad y se le sustituye
`run_merged_solution`, que es la única función que elige el paquete. Los tres
manejadores de interfaz resuelven ese nombre en los globales de `inference` cuando
lo llaman, así que reciben esta versión sin tocar su código.

`inference.py` es modificable según las reglas del reto — el único fichero
bloqueado es `src/chimera_agent_baseline/output/schema.py`. No se toca igualmente:
es el contrato del contenedor y lo que acaba de hacer pasar Debug, y la forma de
volver a la solución anterior es no ejecutar este envoltorio.

En el contenedor va montado como `/opt/app/inference_v1.py`, **junto** a
`inference.py`, no encima: sustituirlo haría que este módulo se importase a sí mismo.
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


def run_merged_solution(*, task, structured_prompt, clinical_data, neural_representations) -> int:
    """Idéntica a la original salvo el paquete que entrega."""
    os.environ["CHIMERA_MODEL_DIR"] = str(base.MODEL_PATH)
    from version_final_reto.common.gc_entry import dispatch

    return dispatch(
        task=task,
        structured_prompt=structured_prompt,
        clinical_data=clinical_data,
        neural_representations=neural_representations,
        output_path=base.OUTPUT_PATH,
        embedding_model_dir=str(base.EMBEDDING_MODEL_PATH),
    )


#: Los manejadores leen este nombre de los globales de `inference` al llamarlo,
#: así que reasignarlo aquí basta para redirigir las tres interfaces.
base.run_merged_solution = run_merged_solution

#: `base` es el módulo donde viven los manejadores y las rutas. Quien necesite
#: sustituir `INPUT_PATH`, `OUTPUT_PATH` o `USE_MERGED_SOLUTION` tiene que hacerlo
#: ahí, no en este envoltorio: parchear una copia local no cambiaría sus globales.
run = base.run

if __name__ == "__main__":
    raise SystemExit(base.run())
