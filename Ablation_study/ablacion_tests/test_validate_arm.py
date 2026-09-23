from __future__ import annotations

from Ablation_study.harness.run_arm import main as run_arm_main
from Ablation_study.harness.validate_arm import validate_arm


def test_simulated_arm_passes_integrity_and_contract_validation(tmp_path) -> None:
    run_root = tmp_path / "L1"
    assert run_arm_main(["--arm", "L1", "--out-root", str(run_root), "--simulate"]) == 0
    report = validate_arm(
        "L1",
        run_root=run_root,
        expected_count=2,
        require_l0_identity=False,
        run_official_score=False,
        result_path=tmp_path / "L_L1.json",
    )

    assert report["accepted"] is True
    assert report["outputs"]["found"] == 2
    assert report["contract"]["valid"] == 2
    assert report["audit"]["missing_boards"] == []


def test_missing_gpu_run_writes_a_readable_blocker(tmp_path) -> None:
    report = validate_arm(
        "L0",
        run_root=tmp_path / "missing",
        expected_count=91,
        run_official_score=False,
        result_path=tmp_path / "L_L0.json",
    )

    assert report["accepted"] is False
    assert "salidas 0/91" in report["blocker"]
