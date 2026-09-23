"""Valida integridad, contrato y compuertas de un brazo Tier L."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
from typing import Any

from version_final_reto.common.contract import validate_case

from .paths import DATA, EVAL_REPO, REPO, RESULTS, RUNS
from .run_arm import DECISION_FILE, REASONING_FILE, load_arms
from .sim import A0, score_rows, simulate_variant


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _outputs(run_root: Path) -> dict[str, Path]:
    root = run_root / "output" / "task1"
    if not root.is_dir():
        return {}
    return {path.name: path for path in root.iterdir() if path.is_dir()}


def _expected_labelled() -> set[str]:
    return {path.name for path in (DATA / "ground_truth").iterdir() if path.is_dir()}


def _prediction_row(case_id: str, folder: Path) -> dict[str, Any]:
    decision = _json(folder / DECISION_FILE)
    reasoning = _json(folder / REASONING_FILE)
    payload = _json(DATA / "agent_input" / case_id / "structured-prompt.json")
    return {
        "case_id": case_id,
        "pred": {
            "case_id": case_id,
            "biopsy_decision": decision,
            **reasoning,
        },
        "rule": "LLM arm",
        "who": "LLM arm",
        "bx": payload.get("bx"),
    }


def _board_audit(run_root: Path, case_ids: set[str]) -> dict[str, Any]:
    summary_rows = {row.get("case_id"): row for row in _jsonl(run_root / "summary.jsonl")}
    image_cases = []
    reopened_cases = []
    eau_nudge_cases = []
    registrar_nudge_cases = []
    empty_plan_cases = []
    exact_plan_cases = []
    missing_boards = []
    for case_id in sorted(case_ids):
        board_path = run_root / "boards" / f"{case_id}.json"
        if not board_path.is_file():
            missing_boards.append(case_id)
            continue
        interventions = _json(board_path).get("interventions") or []
        speakers = [item.get("speaker") for item in interventions]
        if "EXPERT-IMAGE" in speakers:
            image_cases.append(case_id)
        if any(
            item.get("speaker") == "VERIFIER" and (item.get("data") or {}).get("reopened")
            for item in interventions
        ):
            reopened_cases.append(case_id)
        eau = next((item for item in interventions if item.get("speaker") == "EXPERT-EAU"), None)
        if eau and not (eau.get("data") or {}).get("searched"):
            eau_nudge_cases.append(case_id)
        registrar = next((item for item in interventions if item.get("speaker") == "REGISTRAR"), None)
        summary = summary_rows.get(case_id) or {}
        planned = list(summary.get("planned") or [])
        revealed = list(summary.get("reveal_sequence") or [])
        if not planned:
            empty_plan_cases.append(case_id)
        if sorted(planned) == sorted(revealed):
            exact_plan_cases.append(case_id)
        if registrar and planned and not (registrar.get("data") or {}).get("tools_called"):
            registrar_nudge_cases.append(case_id)
    return {
        "missing_boards": missing_boards,
        "image_activations": len(image_cases),
        "image_cases": image_cases,
        "reopenings": len(reopened_cases),
        "reopened_cases": reopened_cases,
        "eau_nudges_inferred": len(eau_nudge_cases),
        "registrar_nudges_inferred": len(registrar_nudge_cases),
        "empty_plans": len(empty_plan_cases),
        "empty_plan_cases": empty_plan_cases,
        "registrar_exact_plan": len(exact_plan_cases),
        "registrar_exact_plan_cases": exact_plan_cases,
        "summary_rows": len(summary_rows),
    }


def _l0_identity(actual_rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = {row["case_id"]: row for row in simulate_variant(A0, "honest")}
    mismatches = []
    fields = ("biopsy_decision", "confidence", "variable_weights", "reveal_sequence")
    for row in actual_rows:
        case_id = row["case_id"]
        expected = baseline[case_id]["pred"]
        actual = row["pred"]
        changed = []
        for field in fields:
            left = expected[field]
            right = actual[field]
            if field == "biopsy_decision":
                left = str(left).lower() in {"yes", "true"}
                right = str(right).lower() in {"yes", "true"}
            if left != right:
                changed.append(field)
        if changed:
            mismatches.append({"case_id": case_id, "fields": changed})
    expected_score = score_rows(list(baseline.values()))
    actual_score = score_rows(actual_rows)
    return {
        "identical": not mismatches,
        "mismatches": mismatches,
        "expected_ranking": expected_score["ranking"],
        "actual_ranking": actual_score["ranking"],
        "ranking_matches_4dp": round(expected_score["ranking"], 4) == round(actual_score["ranking"], 4),
    }


def _score_local(run_root: Path) -> dict[str, Any]:
    out = run_root / "score_local.json"
    command = [
        str(REPO / ".venv" / "bin" / "python"),
        str(REPO / "dev" / "score_local.py"),
        "--tasks",
        "1",
        "--count-missing",
        "--output-root",
        str(run_root / "output"),
        "--eval-repo",
        str(EVAL_REPO),
        "--json-out",
        str(out),
    ]
    completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True, check=False)
    if completed.returncode != 0 or not out.is_file():
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "score_local fallo")
    return _json(out)["task1"]


def validate_arm(
    arm_id: str,
    *,
    run_root: Path | None = None,
    expected_count: int = 91,
    require_l0_identity: bool | None = None,
    run_official_score: bool = True,
    result_path: Path | None = None,
) -> dict[str, Any]:
    arms = load_arms()
    if arm_id not in arms:
        raise ValueError(f"Brazo desconocido: {arm_id}.")
    run_root = run_root or RUNS / arm_id
    result_path = result_path or RESULTS / f"L_{arm_id}.json"
    require_l0_identity = arm_id == "L0" if require_l0_identity is None else require_l0_identity
    report: dict[str, Any] = {
        "date": date.today().isoformat(),
        "arm": arm_id,
        "run_root": str(run_root),
        "expected": expected_count,
        "accepted": False,
        "blocker": None,
    }
    blockers = []
    outputs = _outputs(run_root)
    expected_ids = _expected_labelled()
    if expected_count == 91:
        missing = sorted(expected_ids - set(outputs))
        extra = sorted(set(outputs) - expected_ids)
    else:
        missing = []
        extra = []
    if len(outputs) != expected_count:
        blockers.append(f"salidas {len(outputs)}/{expected_count}")
    if missing or extra:
        blockers.append(f"missing={len(missing)}, extra={len(extra)}")
    report["outputs"] = {"found": len(outputs), "missing": missing, "extra": extra}

    contract_errors = []
    rows = []
    for case_id, folder in sorted(outputs.items()):
        try:
            validate_case(1, folder, "canonical")
            rows.append(_prediction_row(case_id, folder))
        except Exception as exc:  # noqa: BLE001
            contract_errors.append({"case_id": case_id, "error": str(exc)})
    report["contract"] = {"valid": len(rows), "errors": contract_errors}
    if contract_errors:
        blockers.append(f"contrato invalido en {len(contract_errors)} casos")

    audit = _board_audit(run_root, set(outputs))
    report["audit"] = audit
    if audit["missing_boards"]:
        blockers.append(f"faltan {len(audit['missing_boards'])} actas")
    if expected_count == 91 and audit["summary_rows"] != 91:
        blockers.append(f"summary.jsonl tiene {audit['summary_rows']}/91")

    if len(rows) == expected_count and not contract_errors:
        report["score"] = {key: value for key, value in score_rows(rows).items() if key != "rows"}
        if run_official_score:
            try:
                report["score_local"] = _score_local(run_root)
            except Exception as exc:  # noqa: BLE001
                blockers.append(f"score_local: {exc}")
        if require_l0_identity:
            identity = _l0_identity(rows)
            report["tier_s_identity"] = identity
            if not identity["identical"]:
                blockers.append(f"L0 difiere de S-A0 en {len(identity['mismatches'])} casos")
            if not identity["ranking_matches_4dp"]:
                blockers.append("ranking L0 no coincide con S-A0 a 4 decimales")

    report["accepted"] = not blockers
    report["blocker"] = "; ".join(blockers) if blockers else None
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True)
    args = parser.parse_args(argv)
    report = validate_arm(args.arm)
    print(json.dumps({"arm": args.arm, "accepted": report["accepted"], "blocker": report["blocker"]}))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
