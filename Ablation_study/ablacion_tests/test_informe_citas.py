from __future__ import annotations

import json
from pathlib import Path

from Ablation_study.harness.report import REPORTS


ROOT = Path(__file__).resolve().parents[1]


def test_summary_table_matches_master_when_report_exists() -> None:
    report_path = REPORTS / "INFORME_ABLACION_T1.md"
    master_path = ROOT / "results" / "tabla_maestra.json"
    if not report_path.is_file() or not master_path.is_file():
        return
    report = report_path.read_text(encoding="utf-8")
    master = json.loads(master_path.read_text(encoding="utf-8"))
    for row in master["rows"]:
        assert f"| {row['id']} | {row['name']} | **{row['verdict']}** |" in report
        if row["d"]["delta"] is not None:
            assert f"{row['d']['delta']:.6f}" in report
        if row["n"] is not None:
            assert f"{row['n']['delta']:.6f}" in report

    anchors = json.loads((ROOT / "results" / "anclas.json").read_text(encoding="utf-8"))
    judge = json.loads((ROOT / "results" / "J_efectos.json").read_text(encoding="utf-8"))
    assert f"{anchors['modes']['honest']['ranking']:.6f}" in report
    assert f"delta_N={judge['delta_n']:.6f}" in report
