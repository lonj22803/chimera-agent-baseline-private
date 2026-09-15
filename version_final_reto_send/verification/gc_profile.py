"""Perfilado bajo las condiciones reales de Grand Challenge.

Lo que nunca medimos y por eso no vimos el fallo:

1. **La máquina.** La A10G de GC trae 4 vCPU. Todo lo medido hasta ahora salió
   de una caja de 28 núcleos, y el grueso del reloj de un caso es trabajo de
   CPU —desunpicklar bosques, arrancar dos subprocesos de Python, renderizar
   plantillas—, que no escala por un factor: se hunde. ``--cpus`` lo replica.
2. **El caso.** ``panel_cache.json`` trae los 195/153 casos del dev, así que
   todo smoke local entró por la rama cacheada. En GC ningún caso de test está
   en la caché: se cargan los 329 MB de expertos y se calcula en vivo. Aquí se
   renombra el ``case_id`` para forzar esa rama, que es la única que corre allí.

Uso::

    python3 verification/gc_profile.py --cpus 4 --interfaces 0,1,2

Escribe un directorio por corrida con el log del contenedor, la telemetría
``gc_resources``/``gc_delivery`` y el reloj de pared por interfaz.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
V11 = ROOT / "version_final_reto"
LIMIT_SECONDS = 900  # el tope de GC por caso

CLINICAL = {0: "prostate-biopsy-decision-clinical-data.json",
            1: "prostate-treatment-decision-clinical-data.json",
            2: "prostate-time-to-recurrence-or-last-follow-up-clinical-data.json"}


def run(args, **kw):
    return subprocess.run(args, text=True, capture_output=True, **kw)


def stage_unseen(interface: int, dest: Path, case_id: str) -> None:
    """Copia /test/input/interfN cambiando el case_id por uno que no esté en caché."""
    src = ROOT / "test" / "input" / f"interf{interface}"
    dest.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.suffix != ".json":
            continue
        payload = json.loads(f.read_text())
        if isinstance(payload, dict) and "case_id" in payload:
            payload["case_id"] = case_id
        (dest / f.name).write_text(json.dumps(payload, indent=2))
    dest.chmod(0o755)


def telemetry(log: str) -> dict:
    out = {}
    for kind in ("gc_resources", "gc_delivery"):
        hit = re.search(r'\{"kind": "%s".*?\}\s*$' % kind, log, re.M)
        if hit:
            try:
                out[kind] = json.loads(hit.group(0))
            except json.JSONDecodeError:
                pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpus", default="", help="cuota de CPU; deja ver todos los núcleos")
    ap.add_argument("--cpuset", default="0-3",
                    help="núcleos REALES visibles. La cuota de --cpus no basta: deja nproc en 28 "
                         "y joblib/OMP siguen abriendo 28 hilos sobre 4 núcleos de cuota, que no es "
                         "lo que hace la A10G de 4 vCPU. cpuset sí cambia sched_getaffinity.")
    ap.add_argument("--memory", default="32g")
    ap.add_argument("--interfaces", default="0,1,2")
    ap.add_argument("--image", default="chimera_agent_baseline_v1")
    ap.add_argument("--source", default=str(V11), help="árbol montado como el paquete")
    ap.add_argument("--package", default="version_final_reto")
    ap.add_argument("--entry", default="verification/inference_v1_1.py")
    ap.add_argument("--cached-case", action="store_true",
                    help="conserva el case_id original (rama con caché de expertos)")
    ap.add_argument("--case-id", default="UNSEEN",
                    help="prefijo del case_id inventado. Estable a propósito: comparar "
                         "V1 contra V1.1 exige el MISMO case_id en los dos brazos, porque "
                         "viaja dentro del prompt renderizado.")
    ap.add_argument("--no-mount", action="store_true",
                    help="no montar el árbol ni la entrada: la imagen tal cual, con su "
                         "propio ENTRYPOINT. Es la única forma de comprobar lo que se "
                         "sube, porque todo lo demás monta el código de fuera.")
    ap.add_argument("--tag", default="")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = V11 / "verification" / f"gc_profile_{stamp}{('_' + args.tag) if args.tag else ''}"
    out.mkdir(parents=True)
    print(f"RUN_DIR={out}", flush=True)

    summary = {"cpus": args.cpus, "cpuset": args.cpuset, "memory": args.memory, "image": args.image,
               "montado": not args.no_mount,
               "source": None if args.no_mount else args.source,
               "package": None if args.no_mount else args.package,
               "unseen_case": not args.cached_case, "limit_seconds": LIMIT_SECONDS,
               "runs": []}

    for interface in [int(x) for x in args.interfaces.split(",")]:
        folder = out / f"interf{interface}"
        inputs = folder / "input"
        output = folder / "output"
        output.mkdir(parents=True)
        output.chmod(0o777)
        case_id = None
        if args.cached_case:
            shutil.copytree(ROOT / "test" / "input" / f"interf{interface}", inputs)
        else:
            case_id = f"{args.case_id}-{interface}"
            stage_unseen(interface, inputs, case_id)

        name = f"chimera-profile-{stamp}-{interface}"
        cmd = ["docker", "run", "--rm", "--name", name, "--gpus", "device=0",
               "--network", "none", "--platform=linux/amd64",
               f"--memory={args.memory}",
               f"--memory-swap={args.memory}",
               "-e", "CHIMERA_SLUG_STRICT=canonical",
               "-e", "CHIMERA_GPU_MEMORY_UTILIZATION=0.8"]
        if not args.no_mount:
            cmd += ["-v", f"{args.source}:/opt/app/{args.package}:ro",
                    "-v", f"{args.source}/{args.entry}:/opt/app/entry.py:ro"]
        cmd += ["-v", f"{inputs}:/input:ro", "-v", f"{output}:/output",
                "-v", f"{ROOT}/model:/opt/ml/model:ro",
                "--mount", "type=volume,destination=/tmp"]
        # Sin montar nada, manda el ENTRYPOINT de la imagen: es lo que se sube.
        cmd += [args.image] if args.no_mount else ["--entrypoint", "python3", args.image, "entry.py"]
        # Variables extra para el contenedor, delante de la imagen para no partir
        # ningún par bandera/valor.
        at = cmd.index("--entrypoint") if "--entrypoint" in cmd else cmd.index(args.image)
        for pair in filter(None, os.environ.get("CHIMERA_PROFILE_ENV", "").split(",")):
            cmd[at:at] = ["-e", pair]
        extra = ([f"--cpus={args.cpus}"] if args.cpus else []) + \
                ([f"--cpuset-cpus={args.cpuset}"] if args.cpuset else [])
        cmd[2:2] = extra  # justo tras "run": no partir "--gpus device=0"
        (folder / "command.json").write_text(json.dumps(cmd, indent=2))

        print(f"START interf{interface} (case_id={case_id or 'cacheado'})", flush=True)
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=args.timeout)
            code, log = proc.returncode, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as exc:
            code, log = None, (exc.stdout or "") + (exc.stderr or "")
            run(["docker", "kill", name])
        seconds = round(time.monotonic() - start, 1)
        (folder / "container.log").write_text(log)

        row = {"interface": interface, "case_id": case_id, "seconds": seconds,
               "exit_code": code, "over_gc_limit": seconds > LIMIT_SECONDS,
               "files": sorted(p.name for p in output.iterdir()),
               **telemetry(log)}
        summary["runs"].append(row)
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
        verdict = "SOBREPASA EL LÍMITE" if row["over_gc_limit"] else "dentro del límite"
        print(f"  interf{interface}: {seconds}s de 900s — {verdict}", flush=True)
        phases = (row.get("gc_resources") or {}).get("phases_seconds")
        if phases:
            # Un hilo que nadie esperó (caso cortado) sale como None.
            print("    fases:", {k: (None if v is None else round(v, 1)) for k, v in phases.items()}, flush=True)

    print(f"FINISHED {out}", flush=True)


if __name__ == "__main__":
    main()
