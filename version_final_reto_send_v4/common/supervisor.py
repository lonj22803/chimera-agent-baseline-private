"""El reloj duro: un proceso que no hace nada más que vigilar.

Por qué existe
--------------
La fase Test rechazó la V2 porque muchos casos pasaron de 15 minutos, y uno
llegó a ~1291 s. ``deadline`` ya cortaba a los 780 s, pero corta **dentro** del
proceso que trabaja: ``asyncio.wait_for`` sólo dispara si el bucle de eventos
está libre, y cancelar la junta no detiene una llamada síncrona al LLM que ya
está corriendo en un hilo. Además, al salir, Python 3.11 espera sin límite a
esos hilos. Un reloj que depende de que el trabajo coopere no garantiza nada.

Este módulo pone el reloj **fuera**. El contenedor arranca aquí, y este proceso:

1. lanza la junta de siempre (``inference_final.py`` en modo trabajador) en su
   propio grupo de procesos, escribiendo en un directorio privado;
2. lanza la sombra (``common/shadow.py``) en otro grupo, con prioridad
   ``SCHED_IDLE``, que deja en disco la salida de los expertos sin esperar al
   LLM;
3. espera. Si la junta entrega a tiempo, publica **sus** ficheros, byte a byte.
   Si no llega, o cae al respaldo, mata el grupo entero —vLLM, MCP y
   embeddings incluidos— y publica la mejor etapa de la sombra.

El reloj arranca con este proceso y corta a ``CHIMERA_HARD_SECONDS`` (720 s por
omisión, de los 900 del reto). Lo que queda después del corte son milisegundos:
copiar dos ficheros que ya existen.

Qué NO cambia
-------------
La junta, sus prompts, sus expertos y el perfil de memoria. El trabajador es el
mismo ``inference_final.py``; sólo cambia a qué directorio escribe.
``CHIMERA_SUPERVISOR=0`` lo ejecuta sin supervisor, como en la V2.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

#: 720 s de los 900. El margen cubre lo que este reloj no ve: el arranque del
#: contenedor antes de Python y su parada después. El log de Test no llegó, así
#: que no hay cifra de cuánto es eso en su máquina; 180 s es más del doble de
#: todo el arranque medido aquí (~70 s hasta cargar el modelo).
DEFAULT_HARD_SECONDS = 600.0
MIN_HARD_SECONDS = 240.0
GC_LIMIT_SECONDS = 840.0
MAX_STARTUP_PENALTY_SECONDS = 600.0

#: Margen con el que el trabajador intenta cerrar por su cuenta antes del corte
#: duro, para que su propio reloj (``deadline``) suelte los empujones y la
#: segunda vuelta a tiempo.
WORKER_MARGIN_SECONDS = 25.0

#: Si la junta ya escribió su salida pero el proceso no termina (un cierre de
#: vLLM que se cuelga), cuánto se le espera antes de matarlo.
EXIT_GRACE_SECONDS = 30.0

POLL_SECONDS = 0.25

INPUT_PATH = Path(os.environ.get("CHIMERA_INPUT_PATH", "/input"))
OUTPUT_PATH = Path(os.environ.get("CHIMERA_OUTPUT_PATH", "/output"))


def _log(**record) -> None:
    print(json.dumps({"kind": "gc_supervisor", **record}), file=sys.stderr, flush=True)


def _log_startup(record: dict) -> None:
    print(json.dumps({"kind": "gc_arranque", **record}), file=sys.stderr, flush=True)


def _proc_age_seconds() -> float | None:
    try:
        uptime = float(Path("/proc/uptime").read_text().split()[0])
        fields = Path("/proc/self/stat").read_text().split()
        start_ticks = int(fields[21])
        hz = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        return max(0.0, uptime - (start_ticks / hz))
    except (OSError, ValueError, IndexError, KeyError):
        return None


def _model_mtime_age_seconds(model_root: Path = Path("/opt/ml/model")) -> float | None:
    try:
        mtimes = [p.stat().st_mtime for p in model_root.iterdir() if p.is_file()]
    except OSError:
        return None
    return max(0.0, time.time() - max(mtimes)) if mtimes else None


def _ram_mb() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def _gpu_info() -> dict | None:
    try:
        import pynvml  # noqa: PLC0415
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        return {"name": name, "memory_mb": int(memory.total // (1024 * 1024))}
    except Exception:  # noqa: BLE001 - la telemetría no debe impedir arrancar
        return None


def _startup_record() -> dict:
    try:
        uptime = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        uptime = None
    affinity = None
    try:
        affinity = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        pass
    return {
        "ahora": time.time(),
        "uptime": uptime,
        "edad_proceso_s": _proc_age_seconds(),
        "modelo_mtime_s": _model_mtime_age_seconds(),
        "cpus": {"os_cpu_count": os.cpu_count(), "affinity": affinity},
        "ram_mb": _ram_mb(),
        "gpu": _gpu_info(),
    }


def _effective_hard_seconds(startup: dict) -> tuple[float, dict]:
    requested = float(os.environ.get("CHIMERA_HARD_SECONDS", DEFAULT_HARD_SECONDS))
    raw_penalty = os.environ.get("CHIMERA_SIM_ARRANQUE_S")
    if raw_penalty is not None:
        startup_s = float(raw_penalty)
        source = "CHIMERA_SIM_ARRANQUE_S"
        stale = False
    else:
        startup_s = float(startup.get("modelo_mtime_s") or 0.0)
        source = "modelo_mtime_s"
        stale = startup_s > MAX_STARTUP_PENALTY_SECONDS
    penalty = 0.0 if stale else min(max(0.0, startup_s), MAX_STARTUP_PENALTY_SECONDS)
    # El suelo protege al término adaptativo de un arranque enorme; no está
    # para pisar lo que se pide a mano. Aplicarlo a toda la expresión dejaba
    # `CHIMERA_HARD_SECONDS=130` convertido en 240 en silencio, y con él la
    # compuerta que comprueba que el corte duro mata de verdad una generación.
    adaptativo = max(MIN_HARD_SECONDS, GC_LIMIT_SECONDS - penalty)
    effective = min(requested, adaptativo)
    return effective, {"requested_hard_seconds": requested, "startup_seconds": round(startup_s, 3),
                       "startup_source": source, "startup_penalty_seconds": round(penalty, 3),
                       "startup_mtime_stale": stale,
                       "gc_limit_seconds": GC_LIMIT_SECONDS,
                       "min_hard_seconds": MIN_HARD_SECONDS}


def _kill_group(proc: subprocess.Popen | None) -> None:
    """Mata el grupo entero: el ``EngineCore`` de vLLM y los hijos de MCP incluidos."""
    if proc is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _background_priority() -> None:
    """La sombra sólo usa CPU que la junta no quiere.

    Con ``nice 10`` la carga del modelo de T1 pasó de 105 a 135 s en 4 núcleos.
    ``SCHED_IDLE`` no toca los números (los hilos de BLAS siguen como estaban),
    sólo cuándo corre. Si el sistema no lo admite, ``nice 19``.
    """
    try:
        os.sched_setscheduler(0, os.SCHED_IDLE, os.sched_param(0))
    except (AttributeError, OSError):
        try:
            os.nice(19)
        except OSError:
            pass


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _worker_delivered(delivery: Path, out_dir: Path) -> bool:
    """¿La junta escribió su salida propia, no el respaldo?"""
    record = _read_json(delivery)
    if not isinstance(record, dict) or record.get("fallback") is not False:
        return False
    names = record.get("files") or []
    return bool(names) and all((out_dir / n).is_file() for n in names)


def _publish(files: list[Path]) -> list[str]:
    """Copia los ficheros a ``/output`` sin tocar sus bytes."""
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    names = []
    for src in files:
        tmp = OUTPUT_PATH / f".{src.name}.tmp"
        shutil.copyfile(src, tmp)
        os.replace(tmp, OUTPUT_PATH / src.name)
        names.append(src.name)
    return names


def _publish_stage(stage: Path) -> list[str]:
    return _publish([p for p in sorted(stage.iterdir()) if p.name != "meta.json"])


def _last_resort(work: Path) -> list[str]:
    """Ni junta ni sombra: el respaldo del runner, calculado aquí.

    Sólo si la sombra murió antes de su etapa 0, que es cuestión de milisegundos.
    """
    from version_final_reto.common import shadow
    out = work / "last_resort"
    shadow.run_fallback_only(INPUT_PATH, out)
    stage = shadow.best_stage(out)
    return _publish([p for p in sorted(stage.iterdir()) if p.name != "meta.json"]) if stage else []


def main(entry: Path) -> int:
    t0 = time.monotonic()
    startup = _startup_record()
    _log_startup(startup)
    hard, hard_reason = _effective_hard_seconds(startup)
    work = Path(tempfile.mkdtemp(prefix="chimera-supervisor-", dir=os.environ.get("CHIMERA_TMP", "/tmp")))
    worker_out, shadow_out, delivery = work / "worker", work / "shadow", work / "delivery.json"
    worker_out.mkdir()

    base_env = dict(os.environ)
    worker_env = {**base_env, "CHIMERA_WORKER": "1", "CHIMERA_WORKER_OUTPUT": str(worker_out),
                  "CHIMERA_DELIVERY_RECORD": str(delivery),
                  # El reloj de ``deadline`` pasa a contar hacia el corte duro,
                  # medido desde el arranque de este proceso y no de ``dispatch``.
                  "CHIMERA_HARD_DEADLINE_EPOCH": str(time.time() + hard - WORKER_MARGIN_SECONDS)}
    worker = subprocess.Popen([sys.executable, str(entry)], env=worker_env, cwd=str(entry.parent),
                              start_new_session=True)
    shadow = None
    try:
        shadow = subprocess.Popen([sys.executable, "-m", "version_final_reto.common.shadow",
                                   "--input", str(INPUT_PATH), "--out", str(shadow_out)],
                                  env=base_env, cwd=str(entry.parent), start_new_session=True,
                                  preexec_fn=_background_priority)
    except OSError as exc:
        _log(event="shadow_not_started", error=repr(exc))

    delivered_at = None
    published_shadow_stage = None
    shadow_rank = {None: -1}
    reason = "worker_exited"
    while True:
        if worker.poll() is not None:
            break
        now = time.monotonic() - t0
        if delivered_at is None and _worker_delivered(delivery, worker_out):
            delivered_at = now
        if shadow_out.is_dir():
            from version_final_reto.common import shadow as shadow_mod
            shadow_rank.update({shadow_mod.STAGE_FALLBACK: 0, shadow_mod.STAGE_EXPERTS: 1})
            for stage_name in (shadow_mod.STAGE_EXPERTS, shadow_mod.STAGE_FALLBACK):
                stage_path = shadow_out / stage_name
                if (shadow_rank[stage_name] > shadow_rank[published_shadow_stage]
                        and (stage_path / "meta.json").is_file()):
                    _publish_stage(stage_path)
                    published_shadow_stage = stage_name
                    _log(event="early_publish", source=f"shadow:{stage_name}",
                         elapsed_seconds=round(now, 1))
                    break
        if delivered_at is not None and now - delivered_at > EXIT_GRACE_SECONDS:
            reason = "worker_hung_after_delivery"
            break
        if now >= hard:
            reason = "hard_deadline"
            break
        time.sleep(POLL_SECONDS)
    if worker.poll() is None:
        _kill_group(worker)

    from_worker = _worker_delivered(delivery, worker_out)
    stage = None
    if from_worker:
        record = _read_json(delivery)
        published = _publish([worker_out / n for n in record["files"]])
        source = "board"
    else:
        # La junta no entregó. La sombra tiene hasta el corte duro para
        # terminar la etapa de los expertos; pasado, se queda con la que tenga.
        from version_final_reto.common import shadow as shadow_mod
        while (shadow is not None and shadow.poll() is None
               and not (shadow_out / shadow_mod.STAGE_EXPERTS).is_dir()
               and time.monotonic() - t0 < hard):
            time.sleep(POLL_SECONDS)
        stage = shadow_mod.best_stage(shadow_out)
        if stage is not None:
            published = _publish_stage(stage)
            source = f"shadow:{stage.name}"
        else:
            published, source = _last_resort(work), "last_resort"
    _kill_group(shadow)

    _log(source=source, reason=reason, worker_exit=worker.returncode, files=published,
         elapsed_seconds=round(time.monotonic() - t0, 1), hard_seconds=hard,
         worker_delivered_at=delivered_at, early_shadow_stage=published_shadow_stage,
         **hard_reason)
    shutil.rmtree(work, ignore_errors=True)
    return 0 if published else 1
