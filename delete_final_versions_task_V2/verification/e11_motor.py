"""E11, primer tramo: el perfil de §13.1 por la ruta real de carga del modelo.

No simula el constructor: compone la misma configuración de Hydra que usa
``gc_entry``, le aplica ``runtime.resources.configure`` y llama a
``chimera_agent_baseline.models.load_model``. Si el perfil no llegara al
constructor, aquí se vería.

El lastre ocupa VRAM en otro proceso para que la tarjeta ofrezca de verdad el
espacio de una de 16 GiB. El PLAN lo admite como ensayo preliminar; el cierre
exige una GPU física de 16 GB identificada.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))

GIB = 1024 ** 3


class Muestreador(threading.Thread):
    """NVML cada 50 ms: a 0,5 s se pierden los transitorios de la carga."""

    def __init__(self, intervalo=0.05):
        super().__init__(daemon=True)
        self.intervalo, self.parar, self.pico, self.n = intervalo, False, 0, 0

    def run(self):
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        while not self.parar:
            try:
                self.pico = max(self.pico, pynvml.nvmlDeviceGetMemoryInfo(h).used)
                self.n += 1
            except Exception:
                pass
            time.sleep(self.intervalo)


def lanzar_lastre(objetivo_libre_gib: float) -> subprocess.Popen | None:
    """Deja libres ~objetivo GiB ocupando el resto en otro proceso."""
    import pynvml
    pynvml.nvmlInit()
    h = pynvml.nvmlDeviceGetHandleByIndex(0)
    libre = pynvml.nvmlDeviceGetMemoryInfo(h).free / GIB
    sobra_mib = int((libre - objetivo_libre_gib) * 1024)
    if sobra_mib <= 256:
        return None
    codigo = (
        "import torch,time,sys;"
        f"x=torch.empty(int({sobra_mib}*1024*1024//2),dtype=torch.float16,device='cuda');"
        "print('LASTRE_LISTO',flush=True);"
        "time.sleep(100000)")
    p = subprocess.Popen([sys.executable, "-c", codigo], stdout=subprocess.PIPE, text=True)
    for _ in range(600):
        linea = p.stdout.readline()
        if "LASTRE_LISTO" in linea:
            return p
        if p.poll() is not None:
            raise RuntimeError("el lastre murió al reservar VRAM")
        time.sleep(0.1)
    raise RuntimeError("el lastre no confirmó")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-total-gib", type=float, default=16.0)
    ap.add_argument("--sin-lastre", action="store_true")
    ap.add_argument("--perfil", choices=["v2", "v1_1"], default="v2")
    ap.add_argument("--prompt-tokens", type=int, default=7000)
    ap.add_argument("--salida", default="")
    a = ap.parse_args()

    lastre = None
    if not a.sin_lastre:
        lastre = lanzar_lastre(a.sim_total_gib)
        if lastre is None:
            raise SystemExit(
                "La tarjeta ya ofrece menos de lo pedido: hay otro proceso "
                "ocupando VRAM. Libérala antes de medir o usa --sin-lastre.")
    try:
        _medir(a, lastre)
    finally:
        if lastre:
            lastre.kill()
            lastre.wait(timeout=10)


def _medir(a, lastre) -> None:

    import pynvml
    pynvml.nvmlInit()
    h = pynvml.nvmlDeviceGetHandleByIndex(0)
    antes = pynvml.nvmlDeviceGetMemoryInfo(h)
    libre_ofrecida = antes.free / GIB

    from hydra import compose, initialize_config_dir
    from chimera_agent_baseline.models import load_model

    os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    modelo = Path(os.environ.get("CHIMERA_MODEL_DIR", RAIZ / "model/gemma-4-E2B-it"))

    with initialize_config_dir(config_dir=str(RAIZ / "configs"), version_base=None):
        cfg = compose(config_name="config", overrides=["generation.temperature=0.0"])
    cfg.paths.model_dir = str(modelo)
    cfg.model.model_id = str(modelo)

    if a.perfil == "v2":
        from delete_final_versions_task_V2.runtime import resources
        os.environ["CHIMERA_SIM_VRAM_GIB"] = str(a.sim_total_gib)
        resources.configure(cfg)
        manifiesto = resources.manifiesto(cfg)
    else:
        from delete_final_versions_task_V1_1.common.runtime import configure as v11
        v11(cfg)
        manifiesto = {"perfil": "v1_1", "gpu_memory_utilization": cfg.generation.gpu_memory_utilization}

    m = Muestreador()
    m.start()
    t0 = time.time()
    modelo_cargado = load_model(cfg)
    segundos_carga = time.time() - t0

    tok = getattr(modelo_cargado, "tokenizer", None) or modelo_cargado.llm.get_tokenizer()
    unidad = " paciente con adenocarcinoma de prostata ISUP 2 y PSA 8.4 ng/ml,"
    n = max(1, a.prompt_tokens // max(1, len(tok.encode(unidad))))
    from langchain_core.messages import HumanMessage
    t1 = time.time()
    resp = modelo_cargado.invoke([HumanMessage(content="Informe clinico:" + unidad * n
                                               + "\n\nResume en una frase.")])
    segundos_gen = time.time() - t1

    time.sleep(0.4)
    m.parar = True
    m.join(timeout=2)

    pico_neto = m.pico - antes.used
    r = {"perfil": a.perfil,
         "sim_total_gib": a.sim_total_gib,
         "lastre_activo": lastre is not None,
         "vram_libre_ofrecida_gib": round(libre_ofrecida, 2),
         "vram_total_real_mib": round(antes.total / 2**20),
         "pico_absoluto_mib": round(m.pico / 2**20),
         "pico_neto_mib": round(pico_neto / 2**20),
         "techo_global_gib": (manifiesto.get("presupuesto") or {}).get("techo_global_gib"),
         "cabe_en_techo": pico_neto <= ((manifiesto.get("presupuesto") or {})
                                        .get("techo_global_gib", 99) * GIB),
         "segundos_carga_modelo": round(segundos_carga, 2),
         "segundos_generacion": round(segundos_gen, 2),
         "caracteres_respuesta": len(getattr(resp, "content", "") or ""),
         "muestras_nvml": m.n,
         "manifiesto": manifiesto}
    print("\n===E11_MOTOR===")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    if a.salida:
        Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(a.salida).write_text(json.dumps(r, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
