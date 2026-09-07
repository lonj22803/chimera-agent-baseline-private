"""Pizarra multi-experto con moderador — tarea 1 de CHIMERA-Agent.

Segunda generación de `../solution_task_one`. Cambios de fondo:

* un **moderador** que decide si la información es suficiente, primero para
  abrir la sesión y después antes del veredicto, y que puede **reabrir la
  pizarra** para una segunda ronda con todos los expertos hasta que haya
  consenso;
* un **experto de clasificación elegido por ablación** en vez de por
  suposición: se comparan kNN, regresión logística, Random Forest, Random
  Forest calibrado y Probabilistic Random Forest sobre cuatro bloques de
  información distintos (prompt, EHR, embeddings y sus combinaciones);
* uso explícito de los tres ficheros de entrada del reto, cada uno por la vía
  que le corresponde.

Autocontenido y borrable: importa de `chimera_agent_baseline` pero no lo
modifica. El único contrato intocable, `output/schema.py`, es el que valida la
salida.
"""

__all__ = ["blackboard", "features", "moderator", "prompts", "graph", "decide", "experts"]
