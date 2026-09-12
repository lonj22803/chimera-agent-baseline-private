"""Un hilo por predicción, no cuatro: los bosques llegan con ``n_jobs=-1``.

Los expertos se entrenaron con ``RandomForestClassifier(n_estimators=1000,
n_jobs=-1)`` y ese ajuste viaja dentro del pickle. En entrenamiento es lo
correcto. En inferencia, donde se puntúa **una fila**, cada ``predict_proba``
levanta y destruye un pool de joblib: un caso de la tarea 2 encadena 100
bosques, y el perfil dice que la mitad del tiempo se va en montar y desmontar
pools. Medido: 10,3 s por caso antes, 5,0 s después.

Por qué esto no cambia la decisión
----------------------------------
Un bosque promedia las probabilidades de sus árboles. Con ``n_jobs=-1`` esa
suma la acumulan varios hilos sobre el mismo array, así que el orden **ya** era
no determinista de una corrida a otra; con un hilo queda fijo. La diferencia
medida está en el bit 16 —``margin`` 0,8315283228871304 pasa a ...303—, cinco
órdenes de magnitud por debajo de los cuatro decimales con los que se escribe
el turno y de cualquier frontera de decisión. La verificación de la V1.1 lo
comprueba caso a caso contra la salida de la V1, no de palabra.

No se toca nada más del estimador: ni hiperparámetros, ni árboles, ni el orden
en que se recorren.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

#: Atributos por los que hay que bajar. ``steps`` son tuplas ``(nombre, est)``,
#: que es justo lo que un recorrido ingenuo de ``__dict__`` se salta.
_CHILDREN = ("members_", "estimators_", "estimators", "steps", "named_steps",
             "transformers_", "transformers", "base_estimator", "estimator",
             "estimator_", "best_estimator_", "final_estimator_", "calibrated_classifiers_")


def serialize(obj, *, _seen=None) -> int:
    """Pone ``n_jobs=1`` en cada estimador alcanzable. Devuelve cuántos cambió."""
    seen = _seen if _seen is not None else set()
    if obj is None or id(obj) in seen:
        return 0
    seen.add(id(obj))
    changed = 0
    try:
        if getattr(obj, "n_jobs", 1) not in (1, None):
            obj.n_jobs = 1
            changed += 1
    except Exception:  # noqa: BLE001  — un atributo de sólo lectura no es un fallo
        pass

    def descend(value):
        nonlocal changed
        if isinstance(value, (list, tuple)):
            for item in value:
                descend(item)
        elif isinstance(value, dict):
            for item in value.values():
                descend(item)
        elif hasattr(value, "__dict__") or hasattr(value, "n_jobs"):
            changed += serialize(value, _seen=seen)

    for name in _CHILDREN:
        descend(getattr(obj, name, None))
    for value in list(getattr(obj, "__dict__", {}).values()):
        if hasattr(value, "__dict__") and not hasattr(value, "dtype"):
            changed += serialize(value, _seen=seen)
    return changed


def serialize_bundles(bundles) -> int:
    """``serialize`` sobre lo que sea: un bundle, una lista, o un dict de ellos.

    ``CHIMERA_SERIAL_PREDICT=0`` lo desactiva. Existe para el brazo de control
    de la verificación: comparar contra la V1 exige no tocar los estimadores en
    absoluto, no devolverlos a mano a ``-1``, que no es lo mismo si alguno venía
    ya en un hilo de fábrica.
    """
    if os.environ.get("CHIMERA_SERIAL_PREDICT") == "0":
        return 0
    total = 0
    items = bundles.values() if isinstance(bundles, dict) else (
        bundles if isinstance(bundles, (list, tuple)) else [bundles])
    for item in items:
        if isinstance(item, dict):
            for value in item.values():
                if hasattr(value, "__dict__"):
                    total += serialize(value)
        elif item is not None:
            total += serialize(item)
    if total:
        log.info("Bosques puestos en un hilo: %d", total)
    return total
