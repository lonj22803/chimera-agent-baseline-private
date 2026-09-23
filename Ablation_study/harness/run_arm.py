"""Lanza un brazo Tier L con parches reversibles sobre la V4."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any, Iterator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
import yaml

from version_final_reto.common.board import Board
from version_final_reto.common.roster import GUIDELINE_TOOL, SECTION_BY_TOOL
from version_final_reto.task_1.agent import run_task1
from version_final_reto.task_1.agent.decide import to_gc_outputs
from version_final_reto.task_1.experts_1.experience import ProfessionalExperience
from version_final_reto.task_1.experts_1.panel import CACHE, Panel

from .graph_variants import apply_graph_variant, get_graph_variant
from .paths import CONFIGS, DATA, REPO, RUNS, V4_ROOT

ARMS_PATH = CONFIGS / "brazos_llm.yaml"
DECISION_FILE = "prostate-biopsy-decision.json"
REASONING_FILE = "prostate-biopsy-decision-reasoning.json"


class ArmError(ValueError):
    """Configuracion o salida invalida de un brazo."""


class _Mute(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "mute"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="{}"))])


def load_arms(path: Path = ARMS_PATH) -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("brazos"), list):
        raise ArmError("El registro de brazos debe tener version 1 y una lista brazos.")
    arms = {}
    for index, arm in enumerate(raw["brazos"]):
        if not isinstance(arm, dict):
            raise ArmError(f"brazos[{index}] debe ser un mapa.")
        arm_id = arm.get("id")
        if not isinstance(arm_id, str) or not arm_id or arm_id in arms:
            raise ArmError(f"ID de brazo invalido o duplicado: {arm_id!r}.")
        get_graph_variant(str(arm.get("variante_grafo")))
        arms[arm_id] = dict(arm)
    orders = [arm["orden"] for arm in arms.values()]
    if len(set(orders)) != len(orders):
        raise ArmError("El orden de los brazos debe ser unico.")
    return arms


def _tree_sha256(root: Path = V4_ROOT) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".log":
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()


def runner_arguments(out_root: Path, *, gpu_util: float, k: int) -> list[str]:
    if not 0 < gpu_util <= 1:
        raise ArmError("gpu-util debe estar en (0, 1].")
    if k < 1:
        raise ArmError("k debe ser positivo.")
    return [
        "--out-root",
        str(out_root),
        "--mode",
        "honest",
        "--split",
        "labeled",
        "--temperature",
        "0",
        "--k",
        str(k),
        "--gpu-util",
        str(gpu_util),
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_manifest(
    arm: dict[str, Any], out_root: Path, arguments: list[str], *, simulated: bool
) -> dict[str, Any]:
    manifest = {
        "arm": arm["id"],
        "graph_variant": arm["variante_grafo"],
        "description": arm["descripcion"],
        "hypotheses": arm.get("hipotesis") or [],
        "arguments": arguments,
        "v4_sha256": _tree_sha256(),
        "git_head": _git_head(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "simulated": simulated,
    }
    _write_json(out_root / "arm.json", manifest)
    return manifest


def _fake_tools() -> list[StructuredTool]:
    def noop(query: str = "") -> str:
        """Herramienta muda del brazo simulado."""
        return "{}"

    return [
        StructuredTool.from_function(
            noop,
            name=name,
            description=f"Fake {name} for simulated arm.",
        )
        for name in (*SECTION_BY_TOOL, GUIDELINE_TOOL)
    ]


def simulate_arm(arm: dict[str, Any], out_root: Path, *, limit: int = 2) -> None:
    spec = get_graph_variant(arm["variante_grafo"])
    panel = Panel(Path(CACHE))
    library = ProfessionalExperience(DATA, exclude_self=True, k=3)
    with apply_graph_variant(spec):
        graph = run_task1.create_conference_graph(
            _fake_tools(), _Mute(), None, panel, library, mode="honest"
        )
        case_dirs = sorted(path for path in (DATA / "ground_truth").iterdir() if path.is_dir())[:limit]
        summaries = []
        for directory in case_dirs:
            case_id = directory.name
            input_root = DATA / "agent_input" / case_id
            files = run_task1.load_case_files(input_root)
            state = graph.invoke(
                {
                    "case_id": case_id,
                    "task": 1,
                    "prompt_payload": files["prompt"],
                    "case_files": files,
                    "case_prompt": "Muted arm simulation.",
                },
                {"recursion_limit": 100},
            )
            decision, reasoning = to_gc_outputs(state["structured_response"])
            case_out = out_root / "output" / "task1" / case_id
            _write_json(case_out / DECISION_FILE, decision)
            _write_json(case_out / REASONING_FILE, reasoning)
            board = Board.from_dicts(case_id, 1, state.get("interventions") or [])
            _write_json(out_root / "boards" / f"{case_id}.json", board.to_dict())
            (out_root / "boards" / f"{case_id}.md").write_text(
                board.to_markdown(), encoding="utf-8"
            )
            summaries.append(
                {
                    "case_id": case_id,
                    "ok": True,
                    "decision": decision,
                    "confidence": reasoning["confidence"],
                    "reveal_sequence": reasoning["reveal_sequence"],
                    "variable_weights": reasoning["variable_weights"],
                    "simulated": True,
                }
            )
    (out_root / "summary.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in summaries),
        encoding="utf-8",
    )
    (out_root / "telemetry.jsonl").write_text("", encoding="utf-8")


def valid_output_count(out_root: Path) -> int:
    task_root = out_root / "output" / "task1"
    if not task_root.is_dir():
        return 0
    return sum(
        (path / DECISION_FILE).is_file() and (path / REASONING_FILE).is_file()
        for path in task_root.iterdir()
        if path.is_dir()
    )


def validate_manifest(out_root: Path, *, expected_arm: str, expected_outputs: int) -> dict[str, Any]:
    path = out_root / "arm.json"
    if not path.is_file():
        raise ArmError(f"Falta {path}.")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = {"arm", "graph_variant", "arguments", "v4_sha256", "git_head", "created_at"}
    missing = required - set(manifest)
    if missing:
        raise ArmError(f"arm.json incompleto: {sorted(missing)}.")
    if manifest["arm"] != expected_arm:
        raise ArmError(f"arm.json pertenece a {manifest['arm']}, no a {expected_arm}.")
    count = valid_output_count(out_root)
    if count != expected_outputs:
        raise ArmError(f"Salidas validas: {count}; se esperaban {expected_outputs}.")
    return manifest


@contextmanager
def _argv(arguments: list[str]) -> Iterator[None]:
    previous = sys.argv
    sys.argv = ["run_task1", *arguments]
    try:
        yield
    finally:
        sys.argv = previous


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True)
    parser.add_argument("--out-root", default=None)
    parser.add_argument("--gpu-util", type=float, default=0.9)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--check-complete", action="store_true")
    args = parser.parse_args(argv)

    arms = load_arms()
    if args.arm not in arms:
        raise ArmError(f"Brazo desconocido: {args.arm}.")
    arm = arms[args.arm]
    out_root = Path(args.out_root) if args.out_root else RUNS / args.arm
    arguments = runner_arguments(out_root, gpu_util=args.gpu_util, k=args.k)
    if args.check_complete:
        return 0 if valid_output_count(out_root) == 91 else 1

    command = [str(REPO / ".venv" / "bin" / "python"), "-m", "version_final_reto.task_1.agent.run_task1", *arguments]
    if args.dry_run:
        print(shlex.join(command))
        return 0

    write_manifest(arm, out_root, arguments, simulated=args.simulate)
    if args.simulate:
        simulate_arm(arm, out_root, limit=2)
        validate_manifest(out_root, expected_arm=args.arm, expected_outputs=2)
        return 0

    spec = get_graph_variant(arm["variante_grafo"])
    with apply_graph_variant(spec), _argv(arguments):
        run_task1.main()
    validate_manifest(out_root, expected_arm=args.arm, expected_outputs=91)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
