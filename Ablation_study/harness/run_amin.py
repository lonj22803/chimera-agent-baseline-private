"""Ejecuta el brazo L9 derivado mecanicamente de A_min_config.json."""

from __future__ import annotations

import argparse
import json

from version_final_reto.task_1.agent import run_task1

from .graph_variants import GraphVariantSpec, apply_graph_variant
from .paths import REPO, RESULTS, RUNS
from .run_arm import _argv, runner_arguments, valid_output_count, validate_manifest, write_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu-util", type=float, default=0.9)
    parser.add_argument("--check-complete", action="store_true")
    args = parser.parse_args(argv)
    out_root = RUNS / "L9"
    if args.check_complete:
        return 0 if valid_output_count(out_root) == 91 else 1
    config_path = RESULTS / "A_min_config.json"
    if not config_path.is_file():
        raise RuntimeError("Falta A_min_config.json; ejecuta primero harness.synthesize.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    enabled = {name: bool(value) for name, value in config["flags"].items()}
    if not any(enabled.values()):
        raise RuntimeError("A_min no requiere un brazo L9.")
    spec = GraphVariantSpec("A-min", **enabled)
    arguments = runner_arguments(out_root, gpu_util=args.gpu_util, k=3)
    arm = {
        "id": "L9",
        "variante_grafo": "A-min",
        "descripcion": "Ablacion conjunta derivada de los veredictos SOBRA.",
        "hipotesis": ["H16"],
    }
    write_manifest(arm, out_root, arguments, simulated=False)
    with apply_graph_variant(spec), _argv(arguments):
        run_task1.main()
    validate_manifest(out_root, expected_arm="L9", expected_outputs=91)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
