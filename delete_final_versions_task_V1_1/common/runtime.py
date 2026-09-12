"""Resource settings shared by the container and batch vLLM paths."""
import os
from .telemetry import device_vram_mb


def configure(cfg, gpu_util=None):
    requested = float(os.environ.get('CHIMERA_GPU_MEMORY_UTILIZATION', gpu_util or .80))
    cap_gib = float(os.environ.get('CHIMERA_VLLM_MAX_GIB', '19'))
    length = int(os.environ.get('CHIMERA_MAX_MODEL_LEN', cfg.generation.max_model_len))
    if not 0 < requested <= .95 or not 0 < cap_gib <= 22 or length < 1024:
        raise ValueError('Invalid CHIMERA resource limits')
    _, total = device_vram_mb()
    # A fraction alone would allocate 26 GiB on the 32 GiB validation GPU.
    cfg.generation.gpu_memory_utilization = min(requested, cap_gib * 1024 / total) if total else requested
    cfg.generation.max_model_len = length
    cfg.generation.temperature = 0.0
    return cfg
