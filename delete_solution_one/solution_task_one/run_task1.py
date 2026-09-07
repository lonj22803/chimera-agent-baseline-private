"""Runner de la solución de pizarra para la tarea 1.

No toca nada del upstream: reutiliza el cargador de casos, la plantilla Jinja,
el cargador de modelo, el servicio de embeddings y el servidor MCP tal y como
están, y añade lo que este diseño necesita:

* **modelo cargado una sola vez** para toda la cola;
* **try/except por caso** — un caso que revienta no puede llevarse por delante
  la cola (y con el respaldo determinista de ``decide.py`` casi nunca revienta);
* **la pizarra persistida** en JSON y en Markdown, por caso, que es lo que
  permite ver *por qué* se comportó como se comportó;
* **reanudable** — un caso ya escrito no se repite.

    python -m delete_solution_one.solution_task_one.run_task1 \
        --out-root delete_solution_one/solution_task_one/runs/run1

Puntuar después con el evaluador oficial:

    python dev/score_local.py --tasks 1 --count-missing \
        --output-root delete_solution_one/solution_task_one/runs/run1/output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from dotenv import load_dotenv  # noqa: E402
from hydra import compose, initialize_config_dir  # noqa: E402
from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: E402

from chimera_agent_baseline.case_loader import render_baseline_prompt  # noqa: E402
from chimera_agent_baseline.features import FeatureStore  # noqa: E402
from chimera_agent_baseline.models import load_model  # noqa: E402
from chimera_agent_baseline.rag import start_embedding_service  # noqa: E402
from chimera_agent_baseline.utils import setup_logging  # noqa: E402
from delete_solution_one.solution_task_one import prompts as prompts_v2  # noqa: E402
from delete_solution_one.solution_task_one import prompts_v1  # noqa: E402
from delete_solution_one.solution_task_one.blackboard import Blackboard  # noqa: E402
from delete_solution_one.solution_task_one.decide import to_gc_outputs  # noqa: E402
from delete_solution_one.solution_task_one.graph import create_board_graph  # noqa: E402

PROMPT_VERSIONS = {"v1": prompts_v1, "v2": prompts_v2}

load_dotenv()
log = logging.getLogger("pizarra")

TASK = 1
INPUT_DIR = REPO / "data" / f"task{TASK}" / "agent_input"
GT_DIR = REPO / "data" / f"task{TASK}" / "ground_truth"
DECISION_FILE = "prostate-biopsy-decision.json"
REASONING_FILE = "prostate-biopsy-decision-reasoning.json"


def load_queries(only_labelled: bool, split: str | None, pids: list[str] | None, limit: int | None) -> list[dict]:
    """Casos a correr: payload crudo + prompt renderizado con la plantilla upstream."""
    wanted: set[str] | None = None
    if pids:
        wanted = set(pids)
    elif split in ("dev", "val"):
        f = REPO / "dev" / "splits" / f"task{TASK}_{split}.txt"
        wanted = {ln.strip() for ln in f.read_text().splitlines() if ln.strip()}
    elif only_labelled:
        wanted = {p.name for p in GT_DIR.iterdir() if p.is_dir()} if GT_DIR.is_dir() else None

    out: list[dict] = []
    for sub in sorted(p for p in INPUT_DIR.iterdir() if p.is_dir() and (p / "structured-prompt.json").exists()):
        payload = json.loads((sub / "structured-prompt.json").read_text())
        case_id = payload["case_id"]
        if wanted is not None and case_id not in wanted:
            continue
        out.append(
            {
                "case_id": case_id,
                "payload": payload,
                "context": render_baseline_prompt(payload, REPO / "templates" / "prompts"),
            }
        )
    return out[:limit] if limit else out


def mcp_args(input_dir: Path) -> list[str]:
    return [
        "-m",
        "chimera_agent_baseline.mcp_server",
        "--data-dir",
        str(input_dir),
        "--resource-dir",
        str(REPO / "resources"),
        "--tool-registry",
        f"task{TASK}",
        "--log-level",
        "ERROR",
    ]


def write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False))


async def run(args) -> None:
    out_root = Path(args.out_root)
    out_dir = out_root / "output" / f"task{TASK}"
    board_dir = out_root / "blackboards"
    summary = out_root / "summary.jsonl"
    out_root.mkdir(parents=True, exist_ok=True)

    with initialize_config_dir(config_dir=str(REPO / "configs"), version_base=None):
        overrides = ["+experiment=local_paths", f"generation.temperature={args.temperature}"]
        cfg = compose(config_name="config", overrides=overrides)

    queries = load_queries(not args.all_cases, args.split, args.pids, args.limit)
    log.info("Casos a correr: %d", len(queries))

    write_json(
        out_root / "run_config.json",
        {
            "model_id": cfg.model.model_id,
            "provider": cfg.model.provider,
            "temperature": float(cfg.generation.temperature),
            "top_p": float(cfg.generation.top_p),
            "max_new_tokens": int(cfg.generation.max_new_tokens),
            "l1_max_rounds": args.l1_rounds,
            "l2_max_rounds": args.l2_rounds,
            "l3_max_retries": args.l3_retries,
            "n_cases": len(queries),
            "split": args.split or ("labelled" if not args.all_cases else "all"),
            "prompts": args.prompts,
            "design": "blackboard: intake -> prior -> L1 gaps -> L2 evidence -> image expert -> L3 chair",
        },
    )

    model = load_model(cfg)
    feature_store = FeatureStore(INPUT_DIR)

    client = MultiServerMCPClient(
        {"chimera": {"command": sys.executable, "args": mcp_args(INPUT_DIR), "transport": "stdio"}}
    )
    tools = await client.get_tools()
    log.info("Herramientas MCP: %s", ", ".join(t.name for t in tools))

    graph = create_board_graph(
        tools,
        model,
        feature_store,
        l1_max_rounds=args.l1_rounds,
        l2_max_rounds=args.l2_rounds,
        l3_max_retries=args.l3_retries,
        step_timeout=cfg.agent.step_timeout,
        prompts=PROMPT_VERSIONS[args.prompts],
    )

    for i, q in enumerate(queries, 1):
        cid = q["case_id"]
        case_out = out_dir / cid
        if (case_out / DECISION_FILE).exists() and (board_dir / f"{cid}.json").exists():
            continue

        t0 = time.time()
        record: dict[str, Any] = {"case_id": cid, "task": TASK}
        try:
            state = await graph.ainvoke(
                {
                    "case_id": cid,
                    "task": TASK,
                    "prompt_payload": q["payload"],
                    "case_prompt": q["context"],
                },
                {"recursion_limit": args.recursion_limit},
            )
            structured = state["structured_response"]
            decision, reasoning = to_gc_outputs(structured)
            write_json(case_out / DECISION_FILE, decision)
            write_json(case_out / REASONING_FILE, reasoning)

            board = Blackboard.from_dict(
                {"case_id": cid, "task": TASK, "entries": state.get("entries", [])}
            )
            write_json(board_dir / f"{cid}.json", board.to_dict())
            (board_dir / f"{cid}.md").write_text(board.to_markdown())

            record |= {
                "ok": True,
                "seconds": round(time.time() - t0, 1),
                "decision": decision,
                "confidence": structured["confidence"],
                "reveal_sequence": structured["reveal_sequence"],
                "variable_weights": structured["variable_weights"],
                "free_text_chars": len(structured["reasoning"]),
                "warnings": state.get("warnings") or [],
                "l1_rounds": state.get("l1_rounds", 0),
                "l2_rounds": state.get("l2_rounds", 0),
            }
        except Exception as exc:  # noqa: BLE001 — la cola no se cae por un caso
            record |= {"ok": False, "seconds": round(time.time() - t0, 1), "error": f"{type(exc).__name__}: {exc}"}
            log.exception("Caso %s falló", cid)

        with summary.open("a") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        if i % 5 == 0 or i == len(queries):
            log.info("%d/%d casos", i, len(queries))

    log.info("Terminado. Salidas en %s", out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description="Pizarra multi-experto — tarea 1")
    ap.add_argument("--out-root", default=str(Path(__file__).resolve().parent / "runs" / "run1"))
    ap.add_argument("--split", default=None, choices=["dev", "val"], help="subconjunto de dev/splits/")
    ap.add_argument("--pids", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--all-cases", action="store_true", help="incluye los casos sin etiqueta")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--l1-rounds", type=int, default=2)
    ap.add_argument("--l2-rounds", type=int, default=6)
    ap.add_argument("--l3-retries", type=int, default=3)
    ap.add_argument("--recursion-limit", type=int, default=60)
    ap.add_argument("--prompts", default="v2", choices=sorted(PROMPT_VERSIONS),
                    help="v1 reproduce la corrida 1; v2 son los prompts corregidos")
    args = ap.parse_args()

    setup_logging("INFO")
    svc = start_embedding_service(str(REPO / "model" / "embedding_model"))
    try:
        asyncio.run(run(args))
    finally:
        if svc:
            svc.stop()


if __name__ == "__main__":
    main()
