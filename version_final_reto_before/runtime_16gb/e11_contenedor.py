"""E11, segundo tramo: las tres interfaces en un contenedor con 16 GiB.

Docker no sabe limitar VRAM, así que el recorte se hace desde el anfitrión: un
proceso lastre ocupa la diferencia y la tarjeta ofrece al contenedor el espacio
de una de 16 GiB. El PLAN lo admite como **ensayo preliminar**; el cierre exige
una GPU física de 16 GB identificada.

Reutiliza ``gc_profile.py`` de la V1.1 en lugar de copiarlo: es quien ya sabe
poner los 4 núcleos de la A10G, inventar un ``case_id`` fuera de la caché de
expertos y correr la imagen sin montar código encima. Sólo se le añade el
lastre alrededor y se recoge su directorio de salida bajo V2.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PERFILADOR = RAIZ / "version_final_reto" / "verification" / "gc_profile.py"
INFORMES = Path(__file__).resolve().parent.parent / "evaluation" / "reports" / "resources_16gb"
GIB = 1024 ** 3


class Muestreador(threading.Thread):
    def __init__(self, intervalo=0.25):
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


def lanzar_lastre(objetivo_libre_gib: float):
    import pynvml
    pynvml.nvmlInit()
    h = pynvml.nvmlDeviceGetHandleByIndex(0)
    libre = pynvml.nvmlDeviceGetMemoryInfo(h).free / GIB
    sobra_mib = int((libre - objetivo_libre_gib) * 1024)
    if sobra_mib <= 256:
        raise SystemExit(f"La tarjeta ya ofrece {libre:.2f} GiB; libérala antes de medir.")
    codigo = ("import torch,time;"
              f"x=torch.empty(int({sobra_mib}*1024*1024//2),dtype=torch.float16,device='cuda');"
              "print('LASTRE_LISTO',flush=True);time.sleep(100000)")
    p = subprocess.Popen([sys.executable, "-c", codigo], stdout=subprocess.PIPE, text=True)
    for _ in range(900):
        if "LASTRE_LISTO" in (p.stdout.readline() or ""):
            libre = pynvml.nvmlDeviceGetMemoryInfo(h).free / GIB
            print(f"lastre listo: la tarjeta ofrece {libre:.2f} GiB", flush=True)
            return p, libre
        if p.poll() is not None:
            raise RuntimeError("el lastre murió al reservar VRAM")
        time.sleep(0.1)
    raise RuntimeError("el lastre no confirmó")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagen", default="chimera_agent_baseline_v2")
    ap.add_argument("--interfaces", default="0,1,2")
    ap.add_argument("--sim-total-gib", type=float, default=16.0)
    ap.add_argument("--cpuset", default="0-3")
    ap.add_argument("--tag", default="v2_e11")
    ap.add_argument("--sin-lastre", action="store_true")
    ap.add_argument("--montar", action="store_true",
                    help="monta el árbol en vez de usar la imagen tal cual; sólo para depurar")
    a = ap.parse_args()

    lastre, libre = None, None
    if not a.sin_lastre:
        lastre, libre = lanzar_lastre(a.sim_total_gib)
    m = Muestreador()
    m.start()
    try:
        cmd = [sys.executable, str(PERFILADOR), "--cpuset", a.cpuset,
               "--interfaces", a.interfaces, "--image", a.imagen, "--tag", a.tag]
        if not a.montar:
            cmd.append("--no-mount")
        else:
            cmd += ["--source", str(RAIZ / "version_final_reto.runtime_16gb"),
                    "--package", "version_final_reto.runtime_16gb",
                    "--entry", "verification/inference_v2.py"]
        print(" ".join(cmd), flush=True)
        proc = subprocess.run(cmd, text=True, capture_output=True)
        salida = proc.stdout + proc.stderr
        print(salida[-4000:], flush=True)
    finally:
        m.parar = True
        m.join(timeout=2)
        if lastre:
            lastre.kill()
            lastre.wait(timeout=10)

    hit = re.search(r"RUN_DIR=(\S+)", salida)
    INFORMES.mkdir(parents=True, exist_ok=True)
    destino = None
    if hit:
        origen = Path(hit.group(1))
        if origen.is_dir():
            destino = INFORMES / origen.name
            if destino.exists():
                shutil.rmtree(destino)
            shutil.move(str(origen), str(destino))

    resumen = {
        "imagen": a.imagen,
        "montado": a.montar,
        "sim_total_gib": a.sim_total_gib,
        "vram_libre_ofrecida_gib": round(libre, 2) if libre else None,
        "cpuset": a.cpuset,
        "pico_tarjeta_durante_la_corrida_mib": round(m.pico / 2**20),
        "muestras_nvml": m.n,
        "codigo_salida_perfilador": proc.returncode,
        "directorio": str(destino) if destino else None,
    }
    if destino and (destino / "summary.json").exists():
        resumen["perfilador"] = json.loads((destino / "summary.json").read_text())
    (INFORMES / f"e11_contenedor_{a.tag}.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False))
    print("\n===E11_CONTENEDOR===")
    print(json.dumps({k: v for k, v in resumen.items() if k != "perfilador"},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
