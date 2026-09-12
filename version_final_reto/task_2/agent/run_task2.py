"""Runner de la junta clínica — tarea 2 (decisión de tratamiento).

Configuración de entrega, y por qué es ésa:

* **los cinco expertos entrenados sobre los 72 casos etiquetados**. El Experto 1
  es el ancla de calibración (ECE 0,0425) y actúa de portavoz; los Expertos 2 y 4
  se sientan como réplicas confirmatorias —emiten las mismas 72 decisiones— y el
  acta lo dice en vez de disfrazarlas de voces independientes;
* **el LLM no vota**: la decisión sale de la cascada de guía y del portavoz por
  fiabilidad medida. El presidente redacta la nota y rellena el formulario;
* **``reveal_sequence`` entregado vacío**: los 72 patrones la traen vacía y
  ``compute_tool_score`` premia precisión, así que declarar cualquier sección la
  pone a 0. El registrador **sí** abre documentos internamente —sin el informe de
  patología el Experto 2 no puede hablar—, pero eso no se entrega;
* **temperatura 0** en todos los papeles;
* **``confidence`` constante ``clear``**: la compuerta del paso 1.2 mide que
  ninguna política por peldaño la bate en esta tarea (ver
  ``common/analysis/forms_report.json``). Se entrega la constante y se escribe.

    python -m version_final_reto.task_2.agent.run_task2 \
        --out-root .../runs/entrega --all-cases --split all

Escribe, por caso: los dos ficheros de Grand Challenge, el acta en JSON y en
Markdown, y una línea en ``summary.jsonl`` con la telemetría.
"""

from __future__ import annotations

from version_final_reto.task_2.agent.paths import (
    CONFIGS, DATA, EMBEDDING_MODEL, REPO, RESOURCES, RUNS, SPLITS, TEMPLATES,
)

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

for _p in (str(REPO / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from hydra import compose, initialize_config_dir  # noqa: E402
from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: E402

from chimera_agent_baseline.case_loader import render_baseline_prompt  # noqa: E402
from chimera_agent_baseline.models import load_model  # noqa: E402
from chimera_agent_baseline.rag import start_embedding_service  # noqa: E402
from chimera_agent_baseline.utils import setup_logging  # noqa: E402

from version_final_reto.common import warmup  # noqa: E402
from version_final_reto.common.board import Board  # noqa: E402
from version_final_reto.common.telemetry import (  # noqa: E402
    ConferenceMeter, device_vram_mb, host_rss_mb,
)
from version_final_reto.task_2.agent.decide import to_gc_outputs  # noqa: E402
from version_final_reto.task_2.agent.graph import create_conference_graph  # noqa: E402

load_dotenv()
log = logging.getLogger("junta-task2")

TASK = 2
INPUT_DIR = DATA / "agent_input"
GT_DIR = DATA / "ground_truth"
PROMPT_FILE = "structured-prompt.json"
CLINICAL_FILE = "prostate-treatment-decision-clinical-data.json"
FEATURES_FILE = "prostate-modality-level-neural-representations.json"
DECISION_FILE = "prostate-treatment-decision.json"
REASONING_FILE = "prostate-treatment-decision-reasoning.json"


def load_case_files(sub: Path) -> dict[str, dict]:
    out = {}
    for key, name in (("prompt", PROMPT_FILE), ("clinical", CLINICAL_FILE), ("features", FEATURES_FILE)):
        f = sub / name
        try:
            out[key] = json.loads(f.read_text()) if f.exists() else {}
        except json.JSONDecodeError:
            out[key] = {}
    return out


def load_queries(only_labelled: bool, split: str | None, pids: list[str] | None,
                 limit: int | None, sample: int | None, seed: int) -> list[dict]:
    wanted: set[str] | None = None
    labelled = {p.name for p in GT_DIR.iterdir() if p.is_dir()}
    if pids:
        wanted = set(pids)
    elif split in ("dev", "val"):
        f = SPLITS / f"task{TASK}_{split}.txt"
        wanted = {ln.strip() for ln in f.read_text().splitlines() if ln.strip()}
    elif only_labelled and split not in ("labeled", "unlabeled", "all"):
        wanted = labelled
    out: list[dict] = []
    for sub in sorted(p for p in INPUT_DIR.iterdir() if p.is_dir() and (p / PROMPT_FILE).exists()):
        files = load_case_files(sub)
        cid = files["prompt"].get("case_id") or sub.name
        if split == "labeled" and cid not in labelled:
            continue
        if split == "unlabeled" and cid in labelled:
            continue
        if wanted is not None and cid not in wanted:
            continue
        out.append({"case_id": cid, "files": files, "payload": files["prompt"],
                    "context": render_baseline_prompt(files["prompt"], TEMPLATES)})
    if sample and sample < len(out):
        rng = np.random.default_rng(seed)
        idx = sorted(rng.choice(len(out), size=sample, replace=False))
        out = [out[i] for i in idx]
        log.info("Muestreo: %d casos (semilla %d)", len(out), seed)
    return out[:limit] if limit else out


def mcp_args() -> list[str]:
    return ["-m", "chimera_agent_baseline.mcp_server", "--data-dir", str(INPUT_DIR),
            "--resource-dir", str(RESOURCES), "--tool-registry", f"task{TASK}",
            "--log-level", "ERROR"]


def write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, default=str))


async def run(args) -> None:
    with initialize_config_dir(config_dir=str(CONFIGS), version_base=None):
        cfg = compose(config_name="config", overrides=["+experiment=local_paths",
                                                       f"generation.temperature={args.temperature}",
                                                       f"generation.gpu_memory_utilization={args.gpu_util}"])
    t_model = time.time()
    from version_final_reto.common.runtime import configure
    configure(cfg, args.gpu_util)
    model = load_model(cfg)
    log.info("Modelo cargado en %.1f s", time.time() - t_model)
    meter = ConferenceMeter(getattr(model, "tokenizer", None))
    client = MultiServerMCPClient({"chimera": {"command": sys.executable, "args": mcp_args(),
                                               "transport": "stdio"}})
    tools = await client.get_tools()
    log.info("Herramientas MCP servidas: %s", ", ".join(t.name for t in tools))

    graph = create_conference_graph(
        tools, model, max_passes=args.max_passes, chair_max_retries=args.chair_retries,
        step_timeout=cfg.agent.step_timeout, temperature=args.temperature,
        token_scale=args.token_scale)

    root = Path(args.out_root)
    queries = load_queries(not args.all_cases, args.split, args.pids, args.limit, args.sample, args.seed)
    log.info("casos a correr: %d -> %s", len(queries), root)
    write_json(root / "run_config.json", {
        "model_id": cfg.model.model_id, "temperature": float(args.temperature),
        "token_scale": float(args.token_scale), "max_passes": args.max_passes,
        "n_cases": len(queries), "seed": args.seed,
        "split": args.split or ("labelled" if not args.all_cases else "all"),
        "mcp_tools": [t.name for t in tools],
        "model_load_seconds": round(time.time() - t_model, 1),
        "vram_after_load_mb": round(device_vram_mb()[0], 1),
        "confidence_policy": "constant_clear",
        "confidence_rationale": "La compuerta 1.2 mide que ninguna politica por peldano bate a la "
                                "constante en task2 (forms_report.json). Se entrega la constante.",
        "reveal_sequence_policy": "empty_on_delivery",
        "design": "task2 conference: intake -> E1 grade -> E2 pathology -> E5 cascade -> E4 trace "
                  "(fixes the plan) -> EAU -> moderator -> registrar -> E4 fusion -> [E3 fitness] -> "
                  "protocol (guideline cascade + reliability spokesperson) -> verifier -> [reopen] -> chair",
    })
    if args.split == "all":
        labelled = {p.name for p in GT_DIR.iterdir() if p.is_dir()}
        for name in ("labeled", "unlabeled"):
            selected = [q for q in queries if (q["case_id"] in labelled) == (name == "labeled")]
            split_root = root / name
            config = json.loads((root / "run_config.json").read_text())
            write_json(split_root / "run_config.json", {**config, "split": name, "n_cases": len(selected)})
            await _run_queries(graph, selected, split_root, args, meter)
    else:
        await _run_queries(graph, queries, root, args, meter)
    log.info("Terminado.")


async def _run_queries(graph, queries, out_root: Path, args, meter: ConferenceMeter) -> None:
    out_dir = out_root / "output" / f"task{TASK}"
    board_dir = out_root / "boards"
    summary = out_root / "summary.jsonl"
    telemetry = out_root / "telemetry.jsonl"
    for i, q in enumerate(queries, 1):
        cid = q["case_id"]
        case_out = out_dir / cid
        if (case_out / DECISION_FILE).exists() and (board_dir / f"{cid}.json").exists():
            continue
        meter.start_case(cid)
        t0 = time.time()
        record: dict[str, Any] = {"case_id": cid, "task": TASK}
        try:
            state = await graph.ainvoke(
                {"case_id": cid, "task": TASK, "prompt_payload": q["payload"],
                 "case_files": q["files"], "case_prompt": q["context"]},
                {"recursion_limit": args.recursion_limit, "callbacks": [meter]})
            from chimera_agent_baseline.output.schema import normalise_to_full_shape
            structured = normalise_to_full_shape(2, state["structured_response"])
            decision, reasoning = to_gc_outputs(structured)
            write_json(case_out / DECISION_FILE, decision)
            write_json(case_out / REASONING_FILE, reasoning)
            board = Board.from_dicts(cid, TASK, state.get("interventions", []))
            write_json(board_dir / f"{cid}.json", board.to_dict())
            (board_dir / f"{cid}.md").write_text(board.to_markdown())
            verdict = state.get("verdict") or {}
            proto = state.get("protocol") or {}
            audit = state.get("chair_audit") or {}
            tele = meter.summary()
            record |= {
                "ok": True, "seconds": round(time.time() - t0, 1), "decision": decision,
                "confidence": structured.get("confidence"),
                "reveal_sequence": structured.get("reveal_sequence"),
                "variable_weights": structured.get("variable_weights"),
                "free_text": structured.get("reasoning"),
                "free_text_chars": len(structured.get("reasoning") or ""),
                "note_words": audit.get("note_words"), "schema_ok": audit.get("schema_ok"),
                "note_violations": audit.get("note_violations"),
                "fallback_note": audit.get("fallback_note"), "fallback_form": audit.get("fallback_form"),
                "chair_attempts": audit.get("attempts"),
                "n_interventions": len(state.get("interventions", [])),
                "passes": verdict.get("passes", 1), "verifier_ready": verdict.get("ready"),
                "verifier_suggest": verdict.get("suggest"),
                # El protocolo de la tarea 2: quien hablo y por que, mas lo que la
                # junta esta obligada a declarar (nodo de aptitud y techo de consistencia).
                "protocol_rule": proto.get("rule"), "protocol_who": proto.get("who"),
                "protocol_nodes": proto.get("nodes"),
                "protocol_replicas": proto.get("replicas"),
                "fitness_auc": proto.get("fitness_auc"),
                "consistency_ceiling": proto.get("consistency_ceiling"),
                "confidence_diagnostic": proto.get("confidence_diagnostic"),
                "planned": state.get("planned"), "revealed": state.get("revealed"),
                "tools_called": state.get("tools_called"),
                "documents_opened": sorted((state.get("documents") or {}).keys()),
                "expert_ladder": {k: (v or {}).get("ladder")
                                  for k, v in (state.get("experts") or {}).items()},
                "questions": state.get("questions"),
                "warnings": state.get("warnings") or [],
                **{f"tel_{k}": v for k, v in tele.items()},
            }
            with telemetry.open("a") as fh:
                for row in meter.rows:
                    fh.write(json.dumps({"kind": "llm", **row}) + "\n")
                for row in meter.tools:
                    fh.write(json.dumps({"kind": "tool", **row}) + "\n")
        except Exception as exc:  # noqa: BLE001
            record |= {"ok": False, "seconds": round(time.time() - t0, 1),
                       "error": f"{type(exc).__name__}: {exc}"}
            log.exception("Caso %s falló", cid)
        with summary.open("a") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        if i % 5 == 0 or i == len(queries):
            log.info("%d/%d casos · RSS %.0f MiB · VRAM %.0f MiB", i, len(queries),
                     host_rss_mb(), device_vram_mb()[0])
    log.info("Muestra terminada. Salidas en %s", out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description="Junta clínica con expertos entrenados — tarea 2")
    ap.add_argument("--out-root", default=str(RUNS / "entrega"))
    ap.add_argument("--split", default=None, choices=["labeled", "unlabeled", "all", "dev", "val"],
                    help="all escribe labeled/ y unlabeled/ separados bajo --out-root")
    ap.add_argument("--pids", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--all-cases", action="store_true",
                    help="los 153, no sólo los 72 etiquetados")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--token-scale", type=float, default=1.0)
    ap.add_argument("--max-passes", type=int, default=2)
    ap.add_argument("--chair-retries", type=int, default=3)
    ap.add_argument("--recursion-limit", type=int, default=160)
    ap.add_argument("--gpu-util", type=float, default=0.8)
    args = ap.parse_args()

    setup_logging("INFO")
    svc = start_embedding_service(str(EMBEDDING_MODEL))
    try:
        asyncio.run(run(args))
    finally:
        if svc:
            svc.stop()


def prewarm(case, input_dir):
    """Los 329 MB de expertos de T2, cargados mientras carga vLLM.

    ``ExpertReader`` no usa ``panel_cache.json``: puntúa siempre en vivo sobre
    la vista visible, así que estos artefactos se desunpicklan en **todos** los
    casos, también en los del dev. 16,5 s medidos aquí, y es el tramo que en GC
    se dispara. El lector que sale de aquí es el mismo que el grafo construiría.
    """
    from version_final_reto.task_2.agent import protocol as proto
    from version_final_reto.task_2.experts_2 import panel as trained
    reader = proto.ExpertReader()
    reader.live = trained._live_models()
    return {"reader": reader}


async def run_case(case, input_dir, model, tools, step_timeout, meter=None):
    """Adaptador de un caso; las decisiones siguen viviendo en el grafo existente."""
    warm = warmup.result(f"prewarm:{case.case_id}", lambda: prewarm(case, input_dir))
    graph = create_conference_graph(tools, model, warm["reader"],
                                    step_timeout=step_timeout, temperature=0.0)
    state = await graph.ainvoke(
        {"case_id": case.case_id, "task": 2, "prompt_payload": case.prompt,
         "case_files": {"prompt": case.prompt, "clinical": case.clinical,
                        "features": case.embeddings},
         "case_prompt": render_baseline_prompt(case.prompt, TEMPLATES)},
        {"recursion_limit": 160, "callbacks": [meter] if meter else []})
    return state["structured_response"], None


def fallback_case(case):
    from .protocol import consolidate
    from .decide import build_output
    payload, _ = build_output(case.case_id, case.prompt, consolidate(case.prompt, {}, []), [])
    return payload, None


if __name__ == "__main__":
    main()
