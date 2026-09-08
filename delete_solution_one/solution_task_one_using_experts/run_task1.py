"""Runner de la junta con expertos — tarea 1.

Igual que el de la junta anterior en lo que funcionaba (modelo cargado una
vez, try/except por caso, actas persistidas, corrida reanudable, muestreo de
Monte Carlo) con lo que esta generación añade:

* ``--mode deployed | honest``: el panel tal como se entrenó, o su versión
  out-of-fold; la biblioteca con o sin el propio caso. ``deployed`` es lo que
  se empaqueta; ``honest`` es la cifra de generalización. Ver ``experts/panel.py``.
* el panel se lee de ``artifacts/panel_cache.json`` (precalculado con
  ``python -m ...experts.panel``); si no existe, se construye.

    python -m delete_solution_one.solution_task_one_using_experts.run_task1 \
        --mode deployed --out-root .../runs/deployed
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
for p in (str(REPO / "src"), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from hydra import compose, initialize_config_dir  # noqa: E402
from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: E402

from chimera_agent_baseline.case_loader import render_baseline_prompt  # noqa: E402
from chimera_agent_baseline.features import FeatureStore  # noqa: E402
from chimera_agent_baseline.models import load_model  # noqa: E402
from chimera_agent_baseline.rag import start_embedding_service  # noqa: E402
from chimera_agent_baseline.utils import setup_logging  # noqa: E402

from delete_solution_one.solution_task_one_using_experts import protocol as P  # noqa: E402
from delete_solution_one.solution_task_one_using_experts import roster as R  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.board import Board  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.decide import to_gc_outputs  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.experts.library import Library  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.experts.panel import CACHE, Panel, build_cache  # noqa: E402
from delete_solution_one.solution_task_one_using_experts.graph import create_conference_graph  # noqa: E402

load_dotenv()
log = logging.getLogger("junta-expertos")

TASK = 1
HERE = Path(__file__).resolve().parent
DATA = REPO / "data" / f"task{TASK}"
INPUT_DIR = DATA / "agent_input"
GT_DIR = DATA / "ground_truth"
PROMPT_FILE = "structured-prompt.json"
CLINICAL_FILE = "prostate-biopsy-decision-clinical-data.json"
FEATURES_FILE = "prostate-modality-level-neural-representations.json"
DECISION_FILE = "prostate-biopsy-decision.json"
REASONING_FILE = "prostate-biopsy-decision-reasoning.json"


def load_case_files(sub: Path) -> dict[str, dict]:
    out = {}
    for key, name in (("prompt", PROMPT_FILE), ("clinical", CLINICAL_FILE), ("features", FEATURES_FILE)):
        f = sub / name
        try:
            out[key] = json.loads(f.read_text()) if f.exists() else {}
        except json.JSONDecodeError:
            out[key] = {}
    return out


def load_queries(only_labelled: bool, split: str | None, pids: list[str] | None, limit: int | None,
                 sample: int | None, seed: int) -> list[dict]:
    wanted: set[str] | None = None
    if pids:
        wanted = set(pids)
    elif split in ("dev", "val"):
        f = REPO / "dev" / "splits" / f"task{TASK}_{split}.txt"
        wanted = {ln.strip() for ln in f.read_text().splitlines() if ln.strip()}
    elif only_labelled:
        wanted = {p.name for p in GT_DIR.iterdir() if p.is_dir()} if GT_DIR.is_dir() else None
    out: list[dict] = []
    for sub in sorted(p for p in INPUT_DIR.iterdir() if p.is_dir() and (p / PROMPT_FILE).exists()):
        files = load_case_files(sub)
        cid = files["prompt"].get("case_id") or sub.name
        if wanted is not None and cid not in wanted:
            continue
        out.append({"case_id": cid, "files": files, "payload": files["prompt"],
                    "context": render_baseline_prompt(files["prompt"], REPO / "templates" / "prompts")})
    if sample and sample < len(out):
        rng = np.random.default_rng(seed)
        idx = sorted(rng.choice(len(out), size=sample, replace=False))
        out = [out[i] for i in idx]
        log.info("Muestreo de Monte Carlo: %d casos (semilla %d)", len(out), seed)
    return out[:limit] if limit else out


def mcp_args() -> list[str]:
    return ["-m", "chimera_agent_baseline.mcp_server", "--data-dir", str(INPUT_DIR), "--resource-dir",
            str(REPO / "resources"), "--tool-registry", f"task{TASK}", "--log-level", "ERROR"]


def write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, default=str))


def get_panel(retrain: bool) -> Panel:
    if not CACHE.exists() or retrain:
        log.info("Precalculando el panel de expertos (%s)", CACHE)
        build_cache(DATA, CACHE, with_oof=True)
    return Panel(CACHE)


async def run(args) -> None:
    with initialize_config_dir(config_dir=str(REPO / "configs"), version_base=None):
        cfg = compose(config_name="config", overrides=["+experiment=local_paths",
                                                       f"generation.temperature={args.temperature}",
                                                       f"generation.gpu_memory_utilization={args.gpu_util}"])
    panel = get_panel(args.rebuild_panel)
    exclude_self = (args.library == "loo") if args.library != "auto" else (args.mode == "honest")
    library = Library(DATA, exclude_self=exclude_self, k=args.k)
    params = {**P.PARAMS, "confidence_policy": args.confidence_policy, "threshold": args.threshold,
              "grade_rule": not args.no_grade_rule, "library_weight": args.library_weight}

    model = load_model(cfg)
    feature_store = FeatureStore(INPUT_DIR)
    client = MultiServerMCPClient({"chimera": {"command": sys.executable, "args": mcp_args(), "transport": "stdio"}})
    tools = await client.get_tools()
    log.info("Herramientas MCP servidas: %s", ", ".join(t.name for t in tools))

    graph = create_conference_graph(
        tools, model, feature_store, panel, library, mode=args.mode, protocol_params=params,
        weights_policy=args.weights_policy, max_passes=args.max_passes, eau_max_calls=args.eau_calls,
        reg_max_calls=args.registrar_calls, chair_max_retries=args.chair_retries,
        step_timeout=cfg.agent.step_timeout, temperature=args.temperature, token_scale=args.token_scale)

    seeds = args.seeds if args.seeds is not None else [args.seed]
    for seed in seeds:
        root = Path(args.out_root) if len(seeds) == 1 else Path(args.out_root) / f"mc_s{seed}"
        queries = load_queries(not args.all_cases, args.split, args.pids, args.limit, args.sample, seed)
        log.info("[semilla %s] casos a correr: %d -> %s", seed, len(queries), root)
        write_json(root / "run_config.json", {
            "model_id": cfg.model.model_id, "temperature": float(args.temperature),
            "token_scale": float(args.token_scale), "mode": args.mode, "library_exclude_self": exclude_self,
            "k": args.k, "protocol_params": params, "weights_policy": args.weights_policy,
            "max_passes": args.max_passes, "n_cases": len(queries), "sample": args.sample, "seed": seed,
            "split": args.split or ("labelled" if not args.all_cases else "all"),
            "mcp_tools": [t.name for t in tools], "panel_experts": panel.experts,
            "design": "conference with trained experts: intake -> E1 -> cohort -> library -> E4 trace -> EAU -> "
                      "moderator -> [image] -> registrar -> E2 psa -> E3 fusion -> protocol -> verifier -> [reopen] -> chair",
        })
        await _run_queries(graph, queries, root, args)
    log.info("Terminado.")


async def _run_queries(graph, queries, out_root: Path, args) -> None:
    out_dir = out_root / "output" / f"task{TASK}"
    board_dir = out_root / "boards"
    summary = out_root / "summary.jsonl"
    for i, q in enumerate(queries, 1):
        cid = q["case_id"]
        case_out = out_dir / cid
        if (case_out / DECISION_FILE).exists() and (board_dir / f"{cid}.json").exists():
            continue
        t0 = time.time()
        record: dict[str, Any] = {"case_id": cid, "task": TASK}
        try:
            state = await graph.ainvoke(
                {"case_id": cid, "task": TASK, "prompt_payload": q["payload"], "case_files": q["files"],
                 "case_prompt": q["context"]}, {"recursion_limit": args.recursion_limit})
            structured = state["structured_response"]
            decision, reasoning = to_gc_outputs(structured)
            write_json(case_out / DECISION_FILE, decision)
            write_json(case_out / REASONING_FILE, reasoning)
            board = Board.from_dicts(cid, TASK, state.get("interventions", []))
            write_json(board_dir / f"{cid}.json", board.to_dict())
            (board_dir / f"{cid}.md").write_text(board.to_markdown())
            verdict = state.get("verdict") or {}
            proto = state.get("protocol") or {}
            chair_data = next((it.get("data") or {} for it in reversed(state.get("interventions", []))
                               if it["speaker"] == "CHAIR"), {})
            record |= {
                "ok": True, "seconds": round(time.time() - t0, 1), "decision": decision,
                "confidence": structured["confidence"], "reveal_sequence": structured["reveal_sequence"],
                "variable_weights": structured["variable_weights"], "free_text_chars": len(structured["reasoning"]),
                "n_interventions": len(state.get("interventions", [])), "passes": verdict.get("passes", 1),
                "verifier_ready": verdict.get("ready"), "verifier_suggest": verdict.get("suggest"),
                "planned": state.get("planned"), "protocol_rule": proto.get("rule"), "protocol_who": proto.get("who"),
                "protocol_p": proto.get("p"), "grade": (state.get("grade") or {}).get("gg"),
                "library_self_match": (state.get("library") or {}).get("self_match"),
                "chair_form": chair_data.get("chair_form"), "questions": state.get("questions"),
                "need_image": state.get("need_image"), "warnings": state.get("warnings") or [],
            }
        except Exception as exc:  # noqa: BLE001
            record |= {"ok": False, "seconds": round(time.time() - t0, 1), "error": f"{type(exc).__name__}: {exc}"}
            log.exception("Caso %s falló", cid)
        with summary.open("a") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        if i % 5 == 0 or i == len(queries):
            log.info("%d/%d casos", i, len(queries))
    log.info("Muestra terminada. Salidas en %s", out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description="Junta clínica con expertos entrenados — tarea 1")
    ap.add_argument("--out-root", default=str(HERE / "runs" / "run1"))
    ap.add_argument("--mode", default="deployed", choices=["deployed", "honest"])
    ap.add_argument("--library", default="auto", choices=["auto", "self", "loo"],
                    help="auto: self en deployed, loo en honest")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--confidence-policy", default=P.PARAMS["confidence_policy"], choices=["trace", "agreement"])
    ap.add_argument("--weights-policy", default="model+mode", choices=["model+mode", "model", "mode"])
    ap.add_argument("--threshold", type=float, default=P.PARAMS["threshold"])
    ap.add_argument("--library-weight", type=float, default=P.PARAMS["library_weight"])
    ap.add_argument("--no-grade-rule", action="store_true")
    ap.add_argument("--rebuild-panel", action="store_true")
    ap.add_argument("--split", default=None, choices=["dev", "val"])
    ap.add_argument("--pids", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, nargs="+", default=None)
    ap.add_argument("--all-cases", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--token-scale", type=float, default=1.0)
    ap.add_argument("--max-passes", type=int, default=2)
    ap.add_argument("--eau-calls", type=int, default=2)
    ap.add_argument("--registrar-calls", type=int, default=6)
    ap.add_argument("--chair-retries", type=int, default=3)
    ap.add_argument("--recursion-limit", type=int, default=160)
    ap.add_argument("--gpu-util", type=float, default=0.9,
                    help="fracción de VRAM para vLLM; 0.45 permite correr los dos modos a la vez en una 5090")
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
