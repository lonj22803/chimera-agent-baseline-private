"""Ejecuta los brazos L0/Lmin de T2 sobre los 72 casos etiquetados."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .paths import ROOT, RUNS, ensure_dirs
from .run_t2_minimal import run as run_minimal

ARMS = {
    "T2-L0": "V4 completa",
    "T2-Lmin": "expertos y protocolo V4; EAU/moderador/registrador/verificador deterministas",
}


def _tree_hash() -> str:
    digest = hashlib.sha256()
    root = ROOT / "version_final_reto_send_v4"
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".log":
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=tuple(ARMS), required=True)
    parser.add_argument("--gpu-util", type=float, default=0.9)
    args = parser.parse_args()
    ensure_dirs()
    out_root = RUNS / args.arm
    out_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "arm": args.arm,
        "task": 2,
        "description": ARMS[args.arm],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "v4_sha256": _tree_hash(),
        "temperature": 0,
        "split": "labeled",
        "labels_read": False,
    }
    (out_root / "arm.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if args.arm == "T2-L0":
        source = ROOT / "result_v2" / "task_2" / "labeled"
        if not source.is_dir():
            raise FileNotFoundError(f"No existe el artefacto V4 T2: {source}")
        for name in ("output", "boards"):
            shutil.copytree(source / name, out_root / name, dirs_exist_ok=True)
        for name in ("run_config.json", "summary.jsonl", "telemetry.jsonl"):
            shutil.copy2(source / name, out_root / name)
        manifest["reused_artifact"] = str(source.relative_to(ROOT))
        manifest["reused_reason"] = "control V4 completo ya ejecutado; evita una segunda generacion identica"
        (out_root / "arm.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print("T2-L0 importado: 72 casos V4")
    else:
        complete = sum(
            (case / "prostate-treatment-decision.json").is_file()
            and (case / "prostate-treatment-decision-reasoning.json").is_file()
            and (out_root / "boards" / f"{case.name}.json").is_file()
            for case in (out_root / "output" / "task2").glob("*")
            if case.is_dir()
        )
        if complete == 72:
            print("T2-Lmin ya esta completo: 72 casos; se omite la carga de vLLM")
        else:
            run_minimal(out_root, args.gpu_util)


if __name__ == "__main__":
    main()
