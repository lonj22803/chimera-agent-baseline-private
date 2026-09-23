from __future__ import annotations

import subprocess
from pathlib import Path

from Ablation_study.harness.run_arm import (
    main,
    runner_arguments,
    valid_output_count,
    validate_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "Ablation_study" / "harness" / "launch_arms.sh"


def test_dry_run_has_the_fixed_honest_gpu_arguments(capsys, tmp_path) -> None:
    assert main(["--arm", "L0", "--out-root", str(tmp_path / "L0"), "--dry-run"]) == 0
    command = capsys.readouterr().out
    for expected in ("--mode honest", "--split labeled", "--temperature 0", "--k 3", "--gpu-util 0.9"):
        assert expected in command


def test_simulated_arm_writes_and_validates_two_cases(tmp_path) -> None:
    out_root = tmp_path / "L1"
    assert main(["--arm", "L1", "--out-root", str(out_root), "--simulate"]) == 0
    manifest = validate_manifest(out_root, expected_arm="L1", expected_outputs=2)

    assert manifest["graph_variant"] == "N07-off"
    assert manifest["simulated"] is True
    assert valid_output_count(out_root) == 2


def test_launcher_rejects_every_unknown_arm_before_starting() -> None:
    result = subprocess.run(
        ["bash", str(LAUNCHER), "L0", "source"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Brazo desconocido: source" in result.stderr
    assert "[L0] inicio" not in result.stdout
