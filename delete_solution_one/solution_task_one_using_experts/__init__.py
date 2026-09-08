"""Junta clínica sobre pizarra con los expertos entrenados — tarea 1 (decisión de biopsia).

Cuarta generación de la pizarra: la junta de ``solution_task_one_correction_II``
con los cuatro expertos de ``delete_expert_modelate/task_one`` sentados en la
sala, una biblioteca de precedentes, y un protocolo escrito que consolida lo
que dicen. Ver ``README.md``.
"""

from .board import Board, Intervention
from .graph import create_conference_graph

__all__ = ["Board", "Intervention", "create_conference_graph"]
