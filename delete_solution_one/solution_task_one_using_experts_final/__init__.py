"""Junta clínica con expertos entrenados — tarea 1, versión final de entrega.

Cuatro expertos entrenados, una biblioteca de precedentes, un protocolo escrito
que consolida por regla medida, y una sala de deliberación cuyo trabajo es
**recuperar y verificar**, no votar. El presidente redacta la nota clínica desde
un parte sin locutores y firma. Ver ``README.md`` y ``PROMPTS.md``.
"""

from .board import Board, Intervention
from .graph import create_conference_graph

__all__ = ["Board", "Intervention", "create_conference_graph"]
