"""Entrada de V2_2: la V2 (perfil de 16 GB) más el exportador suave de T3.

V2_2 no trae un agente nuevo: E04 concluyó que el corrector sobre conceptos
verificados no aporta señal, así que T1 y T2 son bit a bit los de la V1.1. Lo
único que cambia es el último paso de T3.

Desde la fase Test (15-sep-2026) el contenedor arranca en
``common/supervisor.py``, que pone el límite de 15 minutos fuera del proceso
que trabaja y lanza este mismo fichero como trabajador (``CHIMERA_WORKER=1``).
El trabajador es la V2 sin cambios: sólo escribe en el directorio que le da el
supervisor en vez de en ``/output``. ``CHIMERA_SUPERVISOR=0`` vuelve al
arranque directo de la V2.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if (__name__ == "__main__" and os.environ.get("CHIMERA_WORKER") != "1"
        and os.environ.get("CHIMERA_SUPERVISOR", "1") != "0"):
    # Antes de importar nada pesado: el supervisor no carga torch ni vLLM.
    _here = Path(__file__).resolve()
    for _root in (_here.parent, _here.parents[1]):
        if (_root / "version_final_reto").is_dir() and str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
    from version_final_reto.common import supervisor
    raise SystemExit(supervisor.main(_here))

try:
    import inference  # noqa: F401
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import inference  # noqa: F401

from version_final_reto.investigacion import inference_solo_perfil as base  # noqa: E402
from version_final_reto.investigacion.task_3 import policy  # noqa: E402

policy.aplicar()

if os.environ.get("CHIMERA_WORKER_OUTPUT"):
    # ``inference_solo_perfil`` lee ``inference.OUTPUT_PATH`` al despachar.
    inference.OUTPUT_PATH = Path(os.environ["CHIMERA_WORKER_OUTPUT"])

run_merged_solution = base.run_merged_solution
run = base.run

if __name__ == "__main__":
    raise SystemExit(run())
