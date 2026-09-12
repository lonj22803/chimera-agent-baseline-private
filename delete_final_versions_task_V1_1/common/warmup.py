"""Lo que no depende del LLM se calcula mientras vLLM carga.

Por qué existe este módulo
--------------------------
El reloj de un caso en Grand Challenge no se lo come el LLM. Medido sobre los
195 + 153 casos de la corrida de cobertura, las llamadas al modelo son 24 s de
media en la tarea 1 y 23 s en la tarea 2. El resto —la mayoría— es CPU que no
necesita el modelo para nada:

* desunpicklar los expertos entrenados (329 MB en la tarea 2, 77 MB en la 1),
* puntuar el caso con ellos, que en la tarea 1 son ~30 s de imputación
  múltiple según su propio ``Panel.ensure``,
* arrancar el servidor MCP y el servicio de embeddings, dos subprocesos de
  Python que vuelven a importar medio entorno.

Hasta la V1 eso corría **después** de cargar vLLM, en serie. En la A10G del
reto, que trae 4 vCPU, esa serie es lo que agota los 15 minutos por caso.

Y hay un detalle que escondía el problema: ``panel_cache.json`` trae los 195 y
153 casos del dev, así que todo smoke y toda corrida local entraron por la rama
cacheada. En el test real ningún caso está en la caché y **cada** caso paga la
puntuación en vivo. Nunca lo habíamos cronometrado.

Lo que este módulo cambia, y lo que no
--------------------------------------
No cambia ni un cálculo: cambia *cuándo* ocurre. Un hilo arranca el trabajo de
CPU en cuanto el caso está leído, el hilo principal carga vLLM, y la junta
espera a los dos. Los objetos que entrega el hilo son los mismos que la junta
habría construido ella misma, con los mismos ficheros de entrada, así que la
salida es idéntica por construcción.

Si el precalentamiento falla, el fallo **no** se propaga: se registra y
``result`` reconstruye el objeto en el momento, igual que antes. Perder el
solape es más lento, no incorrecto.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable

log = logging.getLogger(__name__)


class _Slot:
    """Un hilo demonio y su resultado.

    Demonio a propósito, y no ``ThreadPoolExecutor``: sus hilos no son demonios
    y el intérprete los espera al salir. Si el reloj del caso corta mientras un
    precalentamiento sigue dentro de sklearn, un hilo no-demonio dejaría el
    proceso colgado **después** de haber escrito la salida, que para GC es
    exactamente el fallo que estamos arreglando.
    """

    def __init__(self, build: Callable[[], Any]) -> None:
        self.done = threading.Event()
        self.value: Any = None
        self.error: BaseException | None = None
        self.seconds = 0.0
        self.thread = threading.Thread(target=self._run, args=(build,), daemon=True,
                                       name="chimera-warm")
        self.thread.start()

    def _run(self, build: Callable[[], Any]) -> None:
        start = time.monotonic()
        try:
            self.value = build()
        except BaseException as exc:  # noqa: BLE001  — se reintenta en línea
            self.error = exc
        finally:
            self.seconds = time.monotonic() - start
            self.done.set()


_LOCK = threading.Lock()
_SLOTS: dict[str, _Slot] = {}


def submit(key: str, build: Callable[[], Any]) -> None:
    """Arranca ``build`` en un hilo demonio y guarda el resultado bajo ``key``.

    Llamarlo dos veces con la misma clave no relanza el trabajo: el primero
    manda. Nunca lanza — si no se puede ni crear el hilo, ``result`` construye
    en el camino crítico.
    """
    with _LOCK:
        if key in _SLOTS:
            return
        try:
            _SLOTS[key] = _Slot(build)
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo precalentar %s (%s); se calculará en línea", key, exc)


def result(key: str, build: Callable[[], Any]) -> Any:
    """El objeto precalentado, esperando al hilo si aún corre.

    Si no se lanzó, o el hilo murió, construye aquí y ahora con ``build``: el
    mismo objeto que se habría construido sin este módulo.
    """
    with _LOCK:
        slot = _SLOTS.get(key)
    if slot is None:
        return build()
    slot.done.wait()
    if slot.error is not None:
        log.warning("El precalentamiento de %s falló (%r); se reconstruye en línea",
                    key, slot.error)
        with _LOCK:
            _SLOTS.pop(key, None)
        return build()
    if slot.value is None:
        return build()
    return slot.value


async def aresult(key: str, build: Callable[[], Any]) -> Any:
    """Como ``result``, sin bloquear el bucle de eventos.

    Importa para lo que se espera dentro de ``asyncio``: si el bucle se queda
    bloqueado en un ``join``, el reloj del caso no puede disparar y volvemos al
    fallo que arreglamos. Sondear un ``Event`` cada 50 ms cuesta eso, 50 ms.
    """
    with _LOCK:
        slot = _SLOTS.get(key)
    if slot is None:
        submit(key, build)
        with _LOCK:
            slot = _SLOTS.get(key)
        if slot is None:
            return build()
    while not slot.done.is_set():
        await asyncio.sleep(0.05)
    return result(key, build)


def phases() -> dict[str, float]:
    """Segundos que costó cada precalentamiento, para la telemetría.

    Un hilo que aún corre sale como ``None``: significa que nadie lo esperó.
    """
    with _LOCK:
        return {f"warm_{k}": (round(v.seconds, 2) if v.done.is_set() else None)
                for k, v in _SLOTS.items()}


def reset() -> None:
    """Sólo para las pruebas: olvida los hilos ya terminados."""
    with _LOCK:
        _SLOTS.clear()
