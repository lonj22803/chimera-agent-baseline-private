"""Expertos clásicos de machine learning para CHIMERA-agent 2026.

Este paquete contiene la infraestructura compartida por los expertos de las tres
tareas: carga de casos, extracción de características desde los tres ficheros de
entrada, cuantificación de incertidumbre y arneses de evaluación.

El principio de diseño es que cada experto sea *auditable*: cada característica
que entra en un modelo procede de un campo identificable de un JSON de entrada, y
cada veredicto sale acompañado de una descomposición de la incertidumbre
(epistémica / aleatoria) que un deliberador posterior (p. ej. un LLM) pueda usar
para decidir cuánto peso darle.
"""

__version__ = "0.1.0"

# Bundles store classes under the historical top-level package name. Register
# this relocated package before joblib resolves those class references.
import sys
sys.modules["chimera_experts"] = sys.modules[__name__]
