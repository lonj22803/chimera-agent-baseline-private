"""T2 reducida: protocolo congelado y una unica llamada LLM del presidente."""

from __future__ import annotations

import json
import time
from pathlib import Path

from hydra import compose, initialize_config_dir
from langchain_core.messages import HumanMessage, SystemMessage

from chimera_agent_baseline.models import load_model
from chimera_agent_baseline.output.schema import normalise_to_full_shape

from version_final_reto.common import guards, sampling
from version_final_reto.common.board import Board
from version_final_reto.common.telemetry import ConferenceMeter, device_vram_mb, host_rss_mb
from version_final_reto.task_2.agent import decide, prompts, protocol as P
from version_final_reto.task_2.agent.decide import to_gc_outputs
from version_final_reto.task_2.agent.run_task2 import load_case_files
from version_final_reto.task_2.experts_2.panel import Panel

from .paths import DATA2, ROOT

DECISION_FILE = "prostate-treatment-decision.json"
REASONING_FILE = "prostate-treatment-decision-reasoning.json"


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n")


def _content(response) -> str:
    value = response.content
    if isinstance(value, str):
        return value
    return " ".join(block.get("text", "") for block in value if isinstance(block, dict))


def _documents(files: dict) -> dict:
    clinical = files.get("clinical") or {}
    return {
        section: clinical[section]
        for section in P.INTERNAL_PLAN
        if section in clinical and clinical[section] is not None
    }


def _board(case_id: str, payload: dict, experts: dict, documents: dict, proto: dict) -> Board:
    board = Board(case_id, 2)
    board.say("INTAKE", json.dumps(payload, ensure_ascii=False), payload)
    board.say("EXPERT-GRADE", P.render_expert("expert_one", experts["expert_one"]), experts["expert_one"])
    board.say("EXPERT-CASCADE", P.render_expert("expert_five", experts["expert_five"]), experts["expert_five"])
    trace = P.trace(payload)
    board.say("EXPERT-TRACE", json.dumps(trace), trace)
    questions = {section: f"What documented findings in {section} affect management?" for section in P.INTERNAL_PLAN}
    board.say("MODERATOR", json.dumps(questions), {"deterministic": True, "questions": questions})
    board.say("REGISTRAR", "Opened the fixed internal document plan.",
              {"deterministic": True, "opened": list(documents), "documents": documents})
    fusion = {name: experts[name] for name in ("expert_two", "expert_four", "expert_five")}
    board.say("EXPERT-FUSION", json.dumps(fusion, ensure_ascii=False), fusion)
    if proto["who"] == "expert_three":
        board.say("EXPERT-FITNESS", P.render_expert("expert_three", experts["expert_three"]), experts["expert_three"])
    board.say("PANEL-PROTOCOL", json.dumps(proto, ensure_ascii=False), proto)
    missing = [section for section in P.INTERNAL_PLAN if section not in documents]
    board.say("VERIFIER", "Actual missing: " + json.dumps(missing),
              {"ready": not missing, "missing": missing, "deterministic": True})
    return board


def run(out_root: Path, gpu_util: float = 0.9) -> None:
    with initialize_config_dir(config_dir=str(ROOT / "configs"), version_base=None):
        cfg = compose(
            config_name="config",
            overrides=[
                "+experiment=local_paths",
                "generation.temperature=0",
                f"generation.gpu_memory_utilization={gpu_util}",
            ],
        )
    from version_final_reto.common.runtime import configure

    configure(cfg, gpu_util)
    loaded = time.time()
    model = load_model(cfg)
    meter = ConferenceMeter(getattr(model, "tokenizer", None))
    chair = sampling.speak_as(model, sampling.voices(0.0, 1.0)["chair"])
    panel = Panel()
    case_ids = sorted(path.name for path in (DATA2 / "ground_truth").iterdir() if path.is_dir())
    _write(
        out_root / "run_config.json",
        {
            "model_id": cfg.model.model_id,
            "temperature": 0.0,
            "gpu_util": gpu_util,
            "n_cases": len(case_ids),
            "split": "labeled",
            "model_load_seconds": round(time.time() - loaded, 1),
            "vram_after_load_mb": round(device_vram_mb()[0], 1),
            "design": "frozen five-expert protocol -> deterministic controls -> chair",
            "llm_roles": ["chair"],
        },
    )
    for index, case_id in enumerate(case_ids, 1):
        destination = out_root / "output" / "task2" / case_id
        board_path = out_root / "boards" / f"{case_id}.json"
        if (destination / DECISION_FILE).is_file() and (destination / REASONING_FILE).is_file() and board_path.is_file():
            print(f"{index}/{len(case_ids)} {case_id}: already complete", flush=True)
            continue
        started = time.time()
        meter.start_case(case_id)
        files = load_case_files(DATA2 / "agent_input" / case_id)
        payload = files["prompt"]
        documents = _documents(files)
        experts = panel.verdicts(case_id)["experts"]
        proto = P.consolidate(payload, experts, list(documents))
        board = _board(case_id, payload, experts, documents, proto)
        digest = prompts.clinical_digest(payload, documents, proto["decision"])
        errors, note, attempts = [], None, 0
        for attempts in range(1, 4):
            user = digest + ("\nPrevious attempt invalid: " + "; ".join(errors[-4:]) if errors else "")
            try:
                response = chair.invoke(
                    [SystemMessage(content=prompts.CHAIR_SYSTEM), HumanMessage(content=user)],
                    config={"callbacks": [meter]},
                )
                candidate = guards.parse_json(_content(response)).get("reasoning")
                if not isinstance(candidate, str) or len(candidate.strip()) < 40:
                    errors.append("chair: missing or too short reasoning JSON")
                    continue
                faults = decide.note_faults(candidate, payload, documents)
                if faults:
                    errors.append("chair: unsupported/process prose: " + ", ".join(faults))
                    continue
                note = candidate
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"chair: {type(exc).__name__}: {exc}")
        structured, downgraded = decide.build_output(
            case_id, payload, proto, list(documents), note
        )
        structured = normalise_to_full_shape(2, structured)
        decision, reasoning = to_gc_outputs(structured)
        _write(destination / DECISION_FILE, decision)
        _write(destination / REASONING_FILE, reasoning)
        board.say("CHAIR", structured["reasoning"], {
            "fallback": note is None,
            "attempts": attempts,
            "errors": errors,
            "grounding_downgraded": downgraded,
        })
        _write(board_path, board.to_dict())
        (out_root / "boards" / f"{case_id}.md").write_text(board.to_markdown())
        summary = {
            "case_id": case_id,
            "ok": True,
            "seconds": round(time.time() - started, 1),
            "decision": decision,
            "protocol_who": proto["who"],
            "fallback_note": note is None,
            "chair_attempts": attempts,
            "n_interventions": len(board.items),
            "documents_opened": sorted(documents),
            "llm_roles": ["chair"],
            **{f"tel_{key}": value for key, value in meter.summary().items()},
        }
        with (out_root / "summary.jsonl").open("a") as stream:
            stream.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")
        with (out_root / "telemetry.jsonl").open("a") as stream:
            for row in meter.rows:
                stream.write(json.dumps({"kind": "llm", **row}) + "\n")
        print(
            f"{index}/{len(case_ids)} {case_id}: {decision} "
            f"fallback={note is None} {time.time() - started:.1f}s",
            flush=True,
        )
    print(f"T2-Lmin completo; RSS {host_rss_mb():.0f} MiB", flush=True)
