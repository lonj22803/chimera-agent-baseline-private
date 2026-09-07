"""Pizarra en blanco (blackboard) para la tarea 1 del reto CHIMERA-Agent.

Solución alternativa al bucle ReAct del baseline: en lugar de un único agente
que llama herramientas y rellena un formulario, aquí varios participantes
—un clasificador estadístico, tres LLM con contextos distintos y un experto
sobre embeddings— escriben por turnos en una **pizarra compartida**. La
decisión final la toma el último participante leyendo toda la pizarra.

El paquete es autocontenido y borrable: importa del repositorio upstream
(``chimera_agent_baseline``) pero no lo modifica. Borrar
``delete_solution_one/`` deja el repositorio exactamente como estaba.

Contrato respetado sin excepción:
``chimera_agent_baseline.output.schema`` (``Task1Output``) es lo único
bloqueado por el reglamento del reto, y es lo que valida la salida final.
"""

__all__ = ["blackboard", "prompts", "graph", "decide"]
