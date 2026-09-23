"""Deriva T2-Ldet de T2-Lmin sustituyendo solo la nota del presidente."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone

from version_final_reto.common.board import Board
from version_final_reto.task_2.agent.decide import clinical_note

from .paths import DATA2, RUNS, ensure_dirs

DECISION = "prostate-treatment-decision.json"
REASONING = "prostate-treatment-decision-reasoning.json"


def main() -> None:
    ensure_dirs()
    source = RUNS / "T2-Lmin"
    target = RUNS / "T2-Ldet"
    expected = sorted(path.name for path in (DATA2 / "ground_truth").iterdir() if path.is_dir())
    summaries = []
    for case_id in expected:
        source_case = source / "output" / "task2" / case_id
        if not (source_case / DECISION).is_file() or not (source_case / REASONING).is_file():
            raise FileNotFoundError(f"T2-Lmin incompleto: {case_id}")
        decision = json.loads((source_case / DECISION).read_text())
        reasoning = json.loads((source_case / REASONING).read_text())
        payload = json.loads(
            (DATA2 / "agent_input" / case_id / "structured-prompt.json").read_text()
        )
        reasoning["free_text"] = clinical_note(payload, decision)
        case_out = target / "output" / "task2" / case_id
        case_out.mkdir(parents=True, exist_ok=True)
        (case_out / DECISION).write_text(json.dumps(decision, indent=2) + "\n")
        (case_out / REASONING).write_text(
            json.dumps(reasoning, indent=2, ensure_ascii=False) + "\n"
        )
        board = Board(case_id, 2)
        board.say("PANEL-PROTOCOL", json.dumps({"decision": decision, "source": "T2-Lmin"}))
        board.say("CHAIR", reasoning["free_text"], {"deterministic": True})
        board_dir = target / "boards"
        board_dir.mkdir(parents=True, exist_ok=True)
        (board_dir / f"{case_id}.json").write_text(
            json.dumps(board.to_dict(), indent=2, ensure_ascii=False) + "\n"
        )
        (board_dir / f"{case_id}.md").write_text(board.to_markdown())
        summaries.append(
            {"case_id": case_id, "ok": True, "decision": decision, "deterministic": True}
        )
    (target / "summary.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in summaries)
    )
    (target / "telemetry.jsonl").write_text("")
    source_manifest = json.loads((source / "arm.json").read_text())
    manifest = {
        **source_manifest,
        "arm": "T2-Ldet",
        "description": "D/F de T2-Lmin con nota clinica determinista",
        "derived_from": "T2-Lmin",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "llm_calls": 0,
    }
    (target / "arm.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if (source / "run_config.json").is_file():
        shutil.copy2(source / "run_config.json", target / "source_run_config.json")
    print(f"T2-Ldet: {len(expected)} casos")


if __name__ == "__main__":
    main()
