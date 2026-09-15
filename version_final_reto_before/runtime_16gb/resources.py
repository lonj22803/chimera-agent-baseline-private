"""Perfil obligatorio de 16 GB (PLAN.md §13.1): presupuesto y residencia.

Sustituye a ``version_final_reto/common/runtime.py``, que capa el
motor en 19 GiB y deja que vLLM se quede con todo lo libre. Ese reparto es el
que llevó el smoke de la V1 a 21 502 MiB en una A10G y el que impide arrancar
en una tarjeta de 16 GiB.

La corrección no quita nada de la arquitectura: mismo modelo, misma precisión
bf16, mismo contexto de 32 768 y los mismos expertos. Lo que cambia es que el
KV deja de dimensionarse por «lo que sobre en la tarjeta» y pasa a
dimensionarse por lo que un paciente necesita, que es lo único que atiende un
contenedor. Un contexto completo de 32 768 tokens de este modelo ocupa
0,29 GiB de KV: 1 KV head, head_dim 256, y 28 de sus 35 capas con ventana
deslizante de 512.

Efecto secundario buscado: el pico deja de depender del tamaño de la tarjeta.
Medido en contenedor son 13 332 MiB, y en una A10G de 24 GiB serían los mismos
en vez de los 21 502 MiB del smoke de la V1.
"""
from __future__ import annotations

import os

GIB = 1024 ** 3

# Techo y presupuesto del PLAN §13.1.
TECHO_ABSOLUTO_GIB = 14.0
MARGEN_TARJETA_GIB = 1.0      # la tarjeta nunca ofrece sus 16 GB nominales
MOTOR_ABSOLUTO_GIB = 12.0
MARGEN_AUXILIARES_GIB = 2.0   # transitorios, contexto CUDA y procesos hijos

# Suelo medido en RTX 5090 / vLLM 0.25.0 con este modelo: por debajo de
# 10,7 GiB de motor vLLM anuncia «Available KV cache memory: -0.05 GiB» y no
# arranca. Se guarda como guardia, no como objetivo.
MOTOR_MINIMO_GIB = 10.7

# KV fijado en lugar de «lo que sobre». 1 GiB son 3,4 contextos completos.
KV_FIJO_GIB = 1.0

# Troceado del prefill. Se deja en el 8192 por omisión de vLLM **a propósito**:
# bajarlo a 4096 ahorra ~0,73 GiB de activaciones, pero mueve las fronteras del
# troceado y con ellas el orden de reducción en coma flotante. A temperatura 0
# eso basta para cambiar un token, y se midió: con 4096 la prosa de T1 cambia,
# con 8192 la salida es **byte a byte idéntica** a la referencia V1.1 en las
# tres interfaces. Para un cambio que sólo debe tocar memoria, esa igualdad vale
# más que 0,73 GiB de margen que no hacen falta: el pico queda en 13 332 MiB,
# aún 1 GiB bajo el techo.
#
# `CHIMERA_PREFILL_TOKENS=4096` lo recupera si algún día el margen manda; la
# decisión y los pesos no cambian en ninguno de los dos casos.
PREFILL_TOKENS = 8192

# Un paciente por arranque de contenedor (PLAN §13). Reservar concurrencia
# para secuencias que nunca llegan es de donde salía el desperdicio.
SECUENCIAS = 1


def inventario() -> dict:
    """Datos reales de la tarjeta. NVML si está; si no, torch."""
    datos = {"fuente": None, "nombre": None, "driver": None,
             "total_bytes": 0, "libre_bytes": 0, "usada_bytes": 0}
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(h)
        datos.update(fuente="nvml", nombre=_texto(pynvml.nvmlDeviceGetName(h)),
                     driver=_texto(pynvml.nvmlSystemGetDriverVersion()),
                     total_bytes=int(info.total), libre_bytes=int(info.free),
                     usada_bytes=int(info.used))
        return datos
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            libre, total = torch.cuda.mem_get_info()
            datos.update(fuente="torch", nombre=torch.cuda.get_device_name(0),
                         total_bytes=int(total), libre_bytes=int(libre),
                         usada_bytes=int(total - libre))
    except Exception:
        pass
    return datos


def _texto(v):
    return v.decode() if isinstance(v, bytes) else v


def presupuesto(total_bytes: int, sim_total_gib: float | None = None) -> dict:
    """Techo global y presupuesto del motor a partir de la memoria real.

    ``sim_total_gib`` finge una tarjeta menor para el ensayo preliminar en una
    mayor. El PLAN lo admite como ensayo, nunca como cierre: el cierre exige
    una GPU física de 16 GB identificada.
    """
    nominal_gib = sim_total_gib if sim_total_gib else total_bytes / GIB
    techo = min(TECHO_ABSOLUTO_GIB, nominal_gib - MARGEN_TARJETA_GIB)
    motor = min(MOTOR_ABSOLUTO_GIB, techo - MARGEN_AUXILIARES_GIB)
    if motor < MOTOR_MINIMO_GIB:
        raise ValueError(
            f"Presupuesto de motor {motor:.2f} GiB bajo el suelo medido "
            f"{MOTOR_MINIMO_GIB} GiB: el modelo no arranca. Declararlo, no "
            "rebajar la arquitectura en silencio.")
    return {"nominal_gib": round(nominal_gib, 3),
            "techo_global_gib": round(techo, 3),
            "presupuesto_motor_gib": round(motor, 3),
            "simulado": bool(sim_total_gib)}


def configure(cfg, gpu_util=None):
    """Aplica el perfil a la configuración que consume el constructor real.

    Firma compatible con ``common/runtime.py`` de la V1.1 para poder
    sustituirla sin tocar ``gc_entry``. Deja en ``cfg.generation`` las claves
    que ``models/_load_vllm`` pasa a ``vllm.LLM``; una variable de entorno que
    no acabe en ese constructor no cuenta como cumplimiento.

    ``gpu_util`` se acepta y **se ignora**: existe sólo por compatibilidad de
    firma. Aquí la fracción sale del presupuesto de §13.1, y dejar que quien
    llama la fije por encima sería reabrir justo el agujero que este perfil
    cierra.
    """
    sim = os.environ.get("CHIMERA_SIM_VRAM_GIB")
    inv = inventario()
    total = inv["total_bytes"]
    if not total:
        # Sin CUDA no hay VRAM que repartir, pero el muestreo determinista sí
        # aplica: la V1.1 lo fijaba siempre y no debe depender de la tarjeta.
        _escribir(cfg, {"temperature": 0.0})
        return cfg
    pres = presupuesto(total, float(sim) if sim else None)

    motor_bytes = pres["presupuesto_motor_gib"] * GIB
    kv_gib = float(os.environ.get("CHIMERA_KV_GIB", KV_FIJO_GIB))
    longitud = int(os.environ.get("CHIMERA_MAX_MODEL_LEN", cfg.generation.max_model_len))
    prefill = int(os.environ.get("CHIMERA_PREFILL_TOKENS", PREFILL_TOKENS))
    if longitud < 1024 or not 0.1 <= kv_gib <= 4.0 or prefill < 512:
        raise ValueError("Límites de recursos CHIMERA inválidos")

    nuevas = {
        "gpu_memory_utilization": min(0.95, motor_bytes / total),
        "max_model_len": longitud,
        "max_num_seqs": SECUENCIAS,
        "max_num_batched_tokens": prefill,
        "kv_cache_memory_bytes": int(kv_gib * GIB),
        # Nunca se manda una imagen al modelo; sin esto vLLM perfila el
        # codificador de visión y reserva activaciones que no se van a usar.
        "limit_mm_image": 0,
        "temperature": 0.0,
        "presupuesto": pres,
    }
    _escribir(cfg, nuevas)
    return cfg


def _escribir(cfg, valores: dict) -> None:
    """La configuración de Hydra viene en modo struct y rechaza claves nuevas.

    ``open_dict`` es la vía soportada para añadirlas sin desactivar el struct
    del resto de la configuración.
    """
    try:
        from omegaconf import open_dict
        with open_dict(cfg.generation):
            for k, v in valores.items():
                cfg.generation[k] = v
    except ImportError:
        for k, v in valores.items():
            cfg.generation[k] = v


def manifiesto(cfg=None) -> dict:
    """Lo que hay que registrar para que E11 sea comprobable, no declarativo."""
    inv = inventario()
    man = {"gpu": inv, "vllm": None, "torch": None, "dtype": "auto"}
    try:
        import vllm
        man["vllm"] = vllm.__version__
    except Exception:
        pass
    try:
        import torch
        man["torch"] = torch.__version__
        man["capacidad_cuda"] = list(torch.cuda.get_device_capability()) \
            if torch.cuda.is_available() else None
    except Exception:
        pass
    if cfg is not None:
        g = cfg.generation
        man["opciones_efectivas"] = {
            k: _plano(g.get(k, None)) for k in
            ("max_model_len", "gpu_memory_utilization", "max_num_seqs",
             "max_num_batched_tokens", "kv_cache_memory_bytes",
             "limit_mm_image", "temperature")}
        man["presupuesto"] = _plano(g.get("presupuesto", None))
    return man


def _plano(v):
    """Contenedores de OmegaConf a tipos nativos: el manifiesto se serializa."""
    try:
        from omegaconf import OmegaConf
        if OmegaConf.is_config(v):
            return OmegaConf.to_container(v, resolve=True)
    except ImportError:
        pass
    return v
