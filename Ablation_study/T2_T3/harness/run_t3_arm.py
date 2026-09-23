"""Runner reanudable para T3-L0, T3-Lmin y T3-Ldet."""

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from version_final_reto.common import prompt_kit
from version_final_reto.common.chimera_experts import dataset_task3 as ds
from version_final_reto.common.chimera_experts.io import Case
from version_final_reto.task_3.agent import decide, prompts, protocol
from version_final_reto.task_3.agent.graph import Conference, OllamaChair, Task3Board, clean, dump
from version_final_reto.task_3.agent.run_task3 import load_inputs

from .paths import DATA3, ROOT, RUNS, ensure_dirs

ARMS = {
    "T3-L0": "conferencia V4 completa con portavoz selected",
    "T3-Lmin": "motor selected, horizonte, digest determinista y presidente",
    "T3-Ldet": "motor selected, horizonte y nota determinista",
}


class CompactConference:
    def __init__(self, panel: protocol.Panel, chair: OllamaChair | None):
        self.panel = panel
        self.chair = chair

    def invoke(self, original: Case) -> dict:
        case = Case(
            original.case_id,
            3,
            prompt=dict(original.prompt),
            clinical=dict(original.clinical),
            embeddings=dict(original.embeddings),
        )
        board = Task3Board(case.case_id, 3)
        intake = {
            key: case.prompt.get(key)
            for key in ("age", "psa", "dre", "active_treatment_prior_to_surgery")
        }
        board.say("INTAKE", dump(intake), intake)
        surgical_case = Case(
            case.case_id,
            3,
            prompt=case.prompt,
            clinical={
                key: case.clinical[key]
                for key in ("surgical_pathology_report", "pathology_report")
                if key in case.clinical
            },
        )
        findings = ds._surgical(surgical_case)
        risk = findings["capra_s"]
        if not np.isfinite(risk):
            raise ValueError("CAPRA-S cannot be computed from the available record")
        opened = {key: case.clinical.get(key) for key in (
            "surgical_pathology_report", "pathology_report", "radiology_report", "previous_notes"
        )}
        board.say(
            "REGISTRAR",
            dump(opened),
            {"opened": list(opened), "documents": opened, "deterministic": True},
        )
        engine = {
            "spokesperson": "nested-selected fusion",
            "family": self.panel.selected["final_selection"]["family"],
            "blocks": "ASGDE",
            "capra_s": float(risk),
            "policy": "frozen OOF prediction; no advisory turns",
        }
        board.say("EXPERT-FUSION", dump(engine), engine)
        horizon = self.panel.horizon(case, risk)
        missing = [key for key, value in opened.items() if not value]
        band = protocol.uncertainty(
            horizon["months_to_recurrence"], findings["ln_unknown"] == 1, len(missing)
        )
        board.say(
            "EXPERT-HORIZON",
            dump({"horizon": horizon, "uncertainty": band}),
            {"horizon": horizon, "uncertainty": band},
        )
        verification = {
            "ready": True,
            "missing_documents": missing,
            "ln_unknown": findings["ln_unknown"] == 1,
            "deterministic": True,
            "limitations": "Postoperative PSA trajectory and follow-up may be absent; sensitivity is heuristic.",
            "nodal_status": (
                "No nodes were sampled; pNx is not pN0. Missing nodal sampling widens uncertainty."
                if findings["ln_unknown"] == 1
                else "Nodes were sampled; do not claim missing nodal sampling."
            ),
        }
        board.say("VERIFIER", dump(verification), verification)

        calls, attempts, note = [], [], ""
        if self.chair is not None:
            prompt = prompts.chair_prompt(board, case.prompt, case.case_id)
            corpus = dump({"intake": intake, "documents": opened})
            for _ in range(2):
                try:
                    candidate, telemetry = self.chair(prompt)
                    calls.append(telemetry)
                    issues = decide.note_issues(candidate, corpus, "", findings)
                    attempts.append({"text": candidate, "issues": issues})
                    if not issues:
                        note = candidate
                        break
                    prompt = prompts.chair_prompt(board, case.prompt, case.case_id)
                    prompt += "\n" + prompt_kit.chair_challenge(issues)
                except (OSError, ValueError, KeyError) as exc:
                    attempts.append({"error": f"{type(exc).__name__}: {exc}"})
                    break
        fallback = not bool(note)
        if fallback:
            note = decide.fallback_note(case, findings)
        payload = decide.finish(case.case_id, horizon, note, band)
        board.say(
            "CHAIR",
            payload["reasoning"],
            {"fallback": fallback, "attempts": attempts, "deterministic": self.chair is None},
        )
        return {
            "payload": payload,
            "event": horizon["event"],
            "board": board,
            "risk": risk,
            "uncertainty": band,
            "calls": calls,
            "fallback": fallback,
            "opened": list(opened),
            "mode": self.panel.mode,
        }


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(value) + "\n")


def _complete(root: Path, case_id: str) -> bool:
    case = root / "output" / "task3" / case_id
    return all((case / name).is_file() for name in (decide.DECISION, decide.REASONING, "acta.json"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=tuple(ARMS), required=True)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    ensure_dirs()
    root = RUNS / args.arm
    root.mkdir(parents=True, exist_ok=True)
    panel = protocol.Panel("oof", spokesperson="selected")
    chair = None if args.arm == "T3-Ldet" else OllamaChair(args.ollama_url, args.model)
    graph = Conference(panel, chair) if args.arm == "T3-L0" else CompactConference(panel, chair)
    manifest = {
        "arm": args.arm,
        "task": 3,
        "description": ARMS[args.arm],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "mode": "oof",
        "spokesperson": "selected",
        "model": None if chair is None else args.model,
        "temperature": 0,
        "labels_read": False,
        "limitation": "OOF measured cohort, not independent external validation",
        "expert_sha256": panel.hashes,
    }
    _write(root / "arm.json", manifest)
    cases = list(load_inputs(DATA3))
    if args.limit:
        cases = cases[: args.limit]
    for index, case in enumerate(cases, 1):
        if _complete(root, case.case_id):
            print(f"{index}/{len(cases)} {case.case_id}: already complete", flush=True)
            continue
        started = time.monotonic()
        result = graph.invoke(case)
        destination = root / "output" / "task3" / case.case_id
        for name, value in decide.to_gc_outputs(result["payload"], result["event"]).items():
            _write(destination / name, value)
        _write(destination / "acta.json", result["board"].to_dict())
        (destination / "acta.md").write_text(result["board"].to_markdown())
        summary = {
            key: result[key]
            for key in ("risk", "event", "fallback", "opened", "mode", "uncertainty")
        }
        summary.update(result["payload"])
        with (root / "summary.jsonl").open("a") as stream:
            stream.write(dump(summary) + "\n")
        telemetry = {
            "case_id": case.case_id,
            "calls": result["calls"],
            "seconds": time.monotonic() - started,
            "host_peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "backend": "deterministic" if chair is None else "ollama",
            "fallback": result["fallback"],
        }
        with (root / "telemetry.jsonl").open("a") as stream:
            stream.write(dump(telemetry) + "\n")
        print(
            f"{index}/{len(cases)} {case.case_id}: "
            f"{summary['months_to_recurrence']:.6f} months event={result['event']} "
            f"fallback={result['fallback']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
