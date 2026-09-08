"""Junta clínica sobre pizarra — tarea 1 (decisión de biopsia), segunda corrección.

Reordena la sesión en siete estados de pizarra y nueve papeles, con la traza
escrita como el acta de una junta: intervenciones numeradas, cada una con quién
habla y en calidad de qué.

    from delete_solution_one.solution_task_one_correction_II import (
        Board, create_conference_graph,
    )
"""

from .board import Board, Intervention
from .graph import create_conference_graph
from .roster import Roster

__all__ = ["Board", "Intervention", "Roster", "create_conference_graph"]
