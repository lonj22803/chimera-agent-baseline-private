"""Cobertura de los 423 casos con V2_2, salidas y pizarras en `result_v2/`.

Calcado del arnés de cobertura de V1 en lo que importa —un contenedor por tarea,
GPU en serie, código congelado por hash— con dos diferencias:

- **T3 entra por el runner de V2_2**, que aplica el exportador suave antes de
  arrancar. T1 y T2 entran por los de la V1.1 sin tocar: E04 concluyó que el
  corrector sobre conceptos no aporta, así que no hay nada que cambiarles.
- La salida va a `result_v2/`, con las pizarras que cada runner ya escribe.

Esto **no** es la compuerta de entrega: monta código sobre la imagen. La
compuerta sin montar ya está hecha en `../version_final_reto.runtime_16gb/`.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
V11 = RAIZ / "version_final_reto"
V2 = RAIZ / "version_final_reto.runtime_16gb"
V22 = RAIZ / "version_final_reto.investigacion"
SALIDA = RAIZ / "result_v2"
IMAGEN = "chimera_agent_baseline_v2"

TAREAS = {
    3: ["-m", "version_final_reto.investigacion.task_3.run_task3",
        "--out-root", "/output/task_3", "--split", "all", "--backend", "vllm",
        "--mode", "deployed"],
    1: ["-m", "version_final_reto.task_1.agent.run_task1",
        "--out-root", "/output/task_1", "--split", "all"],
    2: ["-m", "version_final_reto.task_2.agent.run_task2",
        "--out-root", "/output/task_2", "--split", "all"],
}


def hashes(raiz: Path) -> dict:
    return {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raiz.rglob("*.py")) if "__pycache__" not in str(p)}


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    SALIDA.chmod(0o777)
    marca = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    resumen = {
        "marca": marca, "imagen": IMAGEN,
        "imagen_id": subprocess.run(["docker", "image", "inspect", IMAGEN, "--format", "{{.Id}}"],
                                    text=True, capture_output=True).stdout.strip(),
        "alcance": ("V2_2 = V2 (perfil de 16 GB) + exportador suave de T3. T1 y T2 son los de "
                    "la V1.1 sin cambios. Cobertura es contrato, no calidad."),
        "hashes_v2_2": hashes(V22),
        "runs": [],
    }
    (SALIDA / "cobertura_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))

    for tarea, args in TAREAS.items():
        destino = SALIDA / f"task_{tarea}"
        if destino.exists() and any(destino.iterdir()):
            print(f"task{tarea}: ya existe {destino}, se salta", flush=True)
            continue
        nombre = f"chimera-v2-2-cobertura-{tarea}-{marca}"
        cmd = ["docker", "run", "--rm", "--name", nombre, "--gpus", "device=0",
               "--network", "none", "--platform=linux/amd64",
               "--memory=32g", "--memory-swap=32g",
               "-e", "CHIMERA_SLUG_STRICT=canonical",
               "-e", "CHIMERA_GPU_MEMORY_UTILIZATION=0.8",
               "-e", "CHIMERA_VLLM_MAX_GIB=19",
               "-v", f"{V11}:/opt/app/version_final_reto:ro",
               "-v", f"{V2}:/opt/app/version_final_reto.runtime_16gb:ro",
               "-v", f"{V22}:/opt/app/version_final_reto.investigacion:ro",
               "-v", f"{RAIZ}/data:/opt/app/data:ro",
               "-v", f"{RAIZ}/model:/opt/ml/model:ro",
               "-v", f"{SALIDA}:/output",
               "--mount", "type=volume,destination=/tmp",
               "--entrypoint", "python3", IMAGEN] + args
        (SALIDA / f"task{tarea}_command.json").write_text(json.dumps(cmd, indent=2))
        print(f"START task{tarea}  ({datetime.datetime.now():%H:%M:%S})", flush=True)
        t0 = time.monotonic()
        proc = subprocess.run(cmd, text=True, capture_output=True)
        seg = round(time.monotonic() - t0, 1)
        (SALIDA / f"task{tarea}.log").write_text(proc.stdout + proc.stderr)
        # T1 y T2 parten la corrida en `labeled/` y `unlabeled/`; T3 no. Contar
        # sólo en la raíz daba 0 y parecía que no había escrito nada.
        salidas = pizarras = 0
        for base in (destino, destino / "labeled", destino / "unlabeled"):
            d = base / f"output/task{tarea}"
            if d.is_dir():
                salidas += sum(1 for x in d.iterdir() if x.is_dir())
            b = base / "boards"
            if b.is_dir():
                pizarras += len(list(b.glob("*.json")))
            # T3 escribe el acta junto a la salida de cada caso, no en `boards/`.
            if d.is_dir():
                pizarras += sum(1 for x in d.iterdir() if (x / "acta.json").exists())
        fila = {"tarea": tarea, "exit_code": proc.returncode, "segundos": seg,
                "casos_con_salida": salidas, "pizarras": pizarras}
        resumen["runs"].append(fila)
        (SALIDA / "cobertura_resumen.json").write_text(
            json.dumps(resumen, indent=2, ensure_ascii=False))
        print(f"  task{tarea}: exit {proc.returncode}, {seg}s, {salidas} salidas, "
              f"{pizarras} pizarras", flush=True)

    print("FINISHED " + str(SALIDA), flush=True)


if __name__ == "__main__":
    main()


def normalizar_pizarras() -> dict:
    """Deja las pizarras de las tres tareas en el mismo sitio.

    T1 y T2 las escriben en `boards/<caso>.json`; T3 las escribe como
    `acta.json`/`acta.md` **dentro del directorio de cada caso**. Las tres
    existen y las tres tienen el mismo contenido —el acta de la junta—, pero
    buscar las de T3 en `boards/` da cero y parece que no hay.

    Se copian, no se mueven: el `acta.json` tiene que seguir junto a su salida,
    que es donde lo dejó el runner.
    """
    import shutil
    cuenta = {}
    for tarea in (1, 2, 3):
        base = SALIDA / f"task_{tarea}"
        destino = base / "boards"
        if tarea in (1, 2):
            # Ya las escribe el runner, repartidas en labeled/ y unlabeled/.
            n = 0
            for sub in ("labeled", "unlabeled"):
                d = base / sub / "boards"
                n += len(list(d.glob("*.json"))) if d.is_dir() else 0
            cuenta[f"task{tarea}"] = n
            continue
        salidas = base / "output" / f"task{tarea}"
        if not salidas.is_dir():
            cuenta[f"task{tarea}"] = 0
            continue
        destino.mkdir(parents=True, exist_ok=True)
        n = 0
        for caso in sorted(p for p in salidas.iterdir() if p.is_dir()):
            for ext in ("json", "md"):
                origen = caso / f"acta.{ext}"
                if origen.exists():
                    shutil.copy2(origen, destino / f"{caso.name}.{ext}")
            n += int((caso / "acta.json").exists())
        cuenta[f"task{tarea}"] = n
    return cuenta
