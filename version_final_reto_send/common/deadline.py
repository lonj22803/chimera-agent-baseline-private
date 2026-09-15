"""El reloj de los quince minutos, y qué se suelta cuando no alcanza.

Grand Challenge da 15 minutos por caso y, cuando se agotan, mata el job sin
escribir nada: es literalmente lo que pasó en Development, con la inferencia
corriendo con normalidad cuando la pararon. Un caso que se pasa no puntúa menos
—puntúa cero— y como el respaldo tampoco llega a escribirse, se pierde entero.

Este módulo no acelera nada; es el seguro. Mide cuánto queda del presupuesto y,
cuando no alcanza, suelta trabajo **opcional** de menos a más valioso:

1. los empujones (``nudge``) a un papel que no llamó a su herramienta,
2. la segunda vuelta de la junta cuando el verificador la pide,
3. el caso entero: ``dispatch`` corta y escribe el respaldo determinista, que
   es salida válida y decidida por los expertos entrenados, no por el LLM.

En un caso que va a tiempo no cambia nada: el peor caso medido son 268 s de
900, así que ``allows`` devuelve ``True`` en todas las consultas y lo único que
queda del reloj es una línea de telemetría. El presupuesto por omisión deja
margen para el arranque del contenedor y para escribir los dos JSON, que es
trabajo que ocurre fuera de este reloj.

``CHIMERA_CASE_BUDGET_SECONDS`` lo cambia; ``0`` lo desactiva, que es lo que
usan las comparaciones de salida byte a byte para que el reloj no pueda influir
en el resultado.
"""
from __future__ import annotations

import logging
import os
import time

log = logging.getLogger(__name__)

#: 780 s de los 900: deja dos minutos para el arranque del contenedor, la
#: carga del modelo desde el disco de GC y la escritura de la salida.
DEFAULT_BUDGET = 780.0

#: Lo que cuesta cada cosa opcional, para no empezarla si no cabe. Salen de la
#: telemetría de los 195 + 153 casos, redondeados hacia arriba y multiplicados
#: por tres porque la A10G decodifica a 26 tok/s frente a los ~70 de aquí.
COST = {
    "nudge": 30.0,       # una llamada corta de un papel
    "pass": 150.0,       # moderador + registrador + verificador otra vez
    "chair": 90.0,       # la nota y el formulario: nunca es opcional
}

_START: float | None = None
_BUDGET: float = 0.0
_SKIPPED: dict[str, int] = {}


def start(budget: float | None = None) -> None:
    """Arranca el reloj del caso. Llamado una vez por ``dispatch``."""
    global _START, _BUDGET
    _SKIPPED.clear()
    raw = os.environ.get("CHIMERA_CASE_BUDGET_SECONDS")
    hard = os.environ.get("CHIMERA_HARD_DEADLINE_EPOCH")
    if raw is not None:
        _BUDGET = float(raw)
    elif hard is not None:
        # Bajo ``common/supervisor.py`` el reloj cuenta hacia su corte duro,
        # que arranca con el contenedor y no con este caso.
        _BUDGET = max(1.0, float(hard) - time.time())
    else:
        _BUDGET = DEFAULT_BUDGET if budget is None else float(budget)
    _START = time.monotonic() if _BUDGET > 0 else None
    if _START is not None:
        log.info("Presupuesto del caso: %.0f s", _BUDGET)


def spent() -> float:
    return 0.0 if _START is None else time.monotonic() - _START


def remaining() -> float:
    """Segundos que quedan. ``inf`` si el reloj está desactivado."""
    return float("inf") if _START is None else _BUDGET - spent()


def allows(stage: str) -> bool:
    """¿Cabe este trozo opcional, dejando sitio para que hable el presidente?

    Nunca lanza y nunca bloquea lo obligatorio: preguntar por ``chair``
    devuelve ``True`` siempre, porque sin presidente no hay nota que entregar
    y el corte de ese caso le toca a ``dispatch``.
    """
    if _START is None or stage == "chair":
        return True
    room = remaining() - COST["chair"] - COST.get(stage, 0.0)
    if room <= 0:
        _SKIPPED[stage] = _SKIPPED.get(stage, 0) + 1
        log.warning("Se suelta %s: quedan %.0f s de %.0f", stage, remaining(), _BUDGET)
        return False
    return True


def summary() -> dict:
    """Para la línea ``gc_resources``: qué se soltó y cuánto quedaba."""
    if _START is None:
        return {"budget_seconds": 0}
    return {"budget_seconds": round(_BUDGET, 1), "budget_spent": round(spent(), 1),
            "budget_left": round(remaining(), 1),
            "budget_skipped": dict(_SKIPPED) or None}
