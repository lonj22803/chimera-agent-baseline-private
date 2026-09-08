"""Muestreo por papel: el sitio donde de verdad se puede tocar la temperatura.

Lo primero, porque cambia la pregunta
-------------------------------------
**La corrida anterior ya iba a temperatura 0.0.** ``run_task1.py`` de la
generación anterior tiene ``--temperature`` con valor por defecto ``0.0``, y el
``run_config.json`` de la corrida completa lo confirma: ``"temperature": 0.0``.
El ``1.0`` que aparece en ``configs/config.yaml`` es lo que trae el repositorio
de fábrica, y el runner lo pisa. Así que "bajar un poco la temperatura" no es
una palanca disponible: ya está en el suelo, y a 0 el modelo es *greedy* — no
muestrea, con lo que ``top_p`` deja de tener efecto.

Y la evidencia sobre esa palanca ya está tomada: el propio control del
baseline puntúa 0.6351 a T=1.0 y 0.6428 a T=0. La dirección es la correcta y el
recorrido está agotado.

Lo que sí queda por hacer
-------------------------
Dos cosas, y las dos están aquí:

1. **Muestreo distinto por papel.** Hasta ahora todos los participantes
   compartían un único ``SamplingParams``. No hay ninguna razón para que el
   presidente, que copia una forma JSON, y el registrador, que redacta, tengan
   el mismo presupuesto de tokens. Recortar el tope de tokens es la palanca que
   de verdad ataca lo que se observó —"explicaba de más"—, porque en un modelo
   pequeño la deriva crece con la longitud del turno.

2. **Una temperatura por papel, para poder medirlo.** Si alguien quiere
   comprobar si subirla un punto ayuda a la prosa del presidente sin estropear
   el JSON, aquí se puede, en vez de moverla para todos a la vez. Por defecto
   está en 0.0 en todos los papeles.

Funciona con los dos backends del repositorio: ``ChatVLLM`` guarda un
``SamplingParams``, y ``ChatOpenAICompat`` lleva ``temperature`` y
``max_tokens`` como campos. Si el modelo no es ninguno de los dos, se devuelve
tal cual y la junta corre igual.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Voice:
    """Cuánto y cómo puede hablar un papel."""

    temperature: float = 0.0
    max_tokens: int = 1024


#: Presupuesto por papel. Los topes salen de lo que cada intervención tiene que
#: caber: el prompt del especialista en guía pide 200 palabras, el del
#: registrador 300, el del verificador 260. Un tope de tokens algo por encima de
#: eso deja escribir la intervención completa y corta la deriva que viene
#: después. El presidente tiene más porque emite JSON con nueve claves.
VOICES: dict[str, Voice] = {
    "eau":       Voice(temperature=0.0, max_tokens=700),
    "moderator": Voice(temperature=0.0, max_tokens=600),
    "registrar": Voice(temperature=0.0, max_tokens=1100),
    "verifier":  Voice(temperature=0.0, max_tokens=900),
    "chair":     Voice(temperature=0.0, max_tokens=1200),
}


def voices(temperature: float | None = None, scale: float = 1.0) -> dict[str, Voice]:
    """Los presupuestos, opcionalmente con una temperatura común y un factor.

    ``scale`` multiplica todos los topes de tokens a la vez: sirve para
    comprobar si el recorte ayuda o estorba sin editar la tabla.
    """
    out = {}
    for name, voice in VOICES.items():
        out[name] = replace(
            voice,
            temperature=voice.temperature if temperature is None else float(temperature),
            max_tokens=max(128, int(voice.max_tokens * scale)),
        )
    return out


def speak_as(model: Any, voice: Voice) -> Any:
    """Una copia del modelo con el presupuesto de ese papel.

    Nunca lanza: si el backend no expone estos campos, devuelve el modelo
    original y se registra una vez. La junta no puede caerse por no poder
    ajustar un tope de tokens.
    """
    try:
        params = getattr(model, "sampling_params", None)
        if params is not None:  # backend vLLM
            new = _copy_sampling_params(params, voice)
            return model.model_copy(update={"sampling_params": new}) if new is not None else model
        if hasattr(model, "temperature"):  # backend OpenAI-compatible
            return model.model_copy(update={"temperature": voice.temperature,
                                            "max_tokens": voice.max_tokens})
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo ajustar el muestreo del papel (%s); se usa el del modelo", exc)
    return model


def _copy_sampling_params(params: Any, voice: Voice) -> Any:
    """``SamplingParams`` de vLLM con la temperatura y el tope de este papel."""
    try:
        from copy import deepcopy
        new = deepcopy(params)
        new.temperature = voice.temperature
        new.max_tokens = voice.max_tokens
        return new
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo copiar SamplingParams (%s)", exc)
        return None
