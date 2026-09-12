"""Entrada de V2_2: la V2 (perfil de 16 GB) más el exportador suave de T3.

V2_2 no trae un agente nuevo: E04 concluyó que el corrector sobre conceptos
verificados no aporta señal, así que T1 y T2 son bit a bit los de la V1.1. Lo
único que cambia es el último paso de T3.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import inference  # noqa: F401
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from delete_final_versions_task_V2.verification import inference_v2 as base  # noqa: E402
from delete_final_versions_task_V2_2.task_3 import policy  # noqa: E402

policy.aplicar()

run_merged_solution = base.run_merged_solution
run = base.run

if __name__ == "__main__":
    raise SystemExit(run())
