"""Audita las notas Tier L con los detectores de la V4, sin invocar un juez."""

from __future__ import annotations

from datetime import date
import csv
import json
from pathlib import Path
from statistics import fmean
from typing import Any

from version_final_reto.common.guards import unsourced_grades, unsourced_values
from version_final_reto.task_1.agent.decide import process_language

from .paths import DATA, RESULTS, RUNS
from .run_arm import REASONING_FILE
from .run_tier_l import ARMS


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_summary(run_root: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in (run_root / "summary.jsonl").read_text().splitlines() if line]
    return {str(row["case_id"]): row for row in rows}


def _source_context(case_id: str, revealed: list[str], board: dict[str, Any]) -> tuple[str, str]:
    case_root = DATA / "agent_input" / case_id
    prompt = _json(case_root / "structured-prompt.json")
    clinical = _json(case_root / "prostate-biopsy-decision-clinical-data.json")
    documents = {section: clinical.get(section) for section in revealed if section in clinical}
    corpus = json.dumps(documents, ensure_ascii=False, sort_keys=True, default=str)
    prior_interventions = [
        item.get("body") or ""
        for item in board.get("interventions") or []
        if item.get("speaker") != "CHAIR"
    ]
    panel = json.dumps(prompt, ensure_ascii=False, sort_keys=True, default=str) + "\n" + "\n".join(prior_interventions)
    return corpus, panel


def _audit_arm(arm: str) -> dict[str, Any]:
    run_root = RUNS / arm
    summaries = _latest_summary(run_root)
    findings = []
    note_words = []
    fallback_cases = []
    chair_retry_cases = []
    chair_challenge_cases = []
    registrar_retry_cases = []
    registrar_calls = []
    for case_id in sorted(summaries):
        summary = summaries[case_id]
        reasoning = _json(run_root / "output" / "task1" / case_id / REASONING_FILE)
        note = str(reasoning.get("free_text") or "")
        board = _json(run_root / "boards" / f"{case_id}.json")
        corpus, panel = _source_context(case_id, list(reasoning.get("reveal_sequence") or []), board)
        process_hits = process_language(note)
        grade_hits = unsourced_grades(note, corpus)
        value_hits = unsourced_values(note, corpus, panel)
        if process_hits or grade_hits or value_hits:
            findings.append(
                {
                    "case_id": case_id,
                    "process": process_hits,
                    "unsourced_grades": grade_hits,
                    "unsourced_values": value_hits,
                }
            )
        note_words.append(len(note.split()))
        if summary.get("fallback_note"):
            fallback_cases.append(case_id)
        attempts = int(summary.get("chair_attempts") or 0)
        if attempts > 1:
            chair_retry_cases.append(case_id)
        if summary.get("prose_challenged"):
            chair_challenge_cases.append(case_id)
        role = (summary.get("tel_by_role") or {}).get("registrar") or {}
        calls = int(role.get("calls") or 0)
        registrar_calls.append(calls)
        warnings = summary.get("warnings") or []
        if calls > 2 or any("registrar" in str(item).lower() and "challenge" in str(item).lower() for item in warnings):
            registrar_retry_cases.append(case_id)

    process_cases = [row["case_id"] for row in findings if row["process"]]
    grade_cases = [row["case_id"] for row in findings if row["unsourced_grades"]]
    value_cases = [row["case_id"] for row in findings if row["unsourced_values"]]
    return {
        "arm": arm,
        "n": len(summaries),
        "process_language_cases": len(process_cases),
        "unsourced_grade_cases": len(grade_cases),
        "unsourced_value_cases": len(value_cases),
        "any_violation_cases": len({*process_cases, *grade_cases, *value_cases}),
        "fallback_note_cases": len(fallback_cases),
        "chair_retry_cases": len(chair_retry_cases),
        "chair_prose_challenge_cases": len(chair_challenge_cases),
        "registrar_retry_cases": len(registrar_retry_cases),
        "registrar_calls_mean": fmean(registrar_calls),
        "note_words_mean": fmean(note_words),
        "note_words_min": min(note_words),
        "note_words_max": max(note_words),
        "case_ids": {
            "process_language": process_cases,
            "unsourced_grades": grade_cases,
            "unsourced_values": value_cases,
            "fallback_note": fallback_cases,
            "chair_retry": chair_retry_cases,
            "chair_prose_challenge": chair_challenge_cases,
            "registrar_retry": registrar_retry_cases,
        },
        "findings": findings,
    }


def _flat(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"case_ids", "findings"}}


def run() -> list[dict[str, Any]]:
    rows = [_audit_arm(arm) for arm in ARMS]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "N_audit.json").write_text(
        json.dumps({"date": date.today().isoformat(), "rows": rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    flat = [_flat(row) for row in rows]
    with (RESULTS / "N_audit.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    baseline = next(row for row in rows if row["arm"] == "L0")
    if baseline["any_violation_cases"]:
        raise RuntimeError(f"L0 tiene {baseline['any_violation_cases']} notas con violaciones.")
    return rows


def main() -> int:
    rows = run()
    print(json.dumps({row["arm"]: row["any_violation_cases"] for row in rows}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
