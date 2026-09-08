"""Runner de la junta — tarea 1.

Igual que el de la generación anterior en lo que funcionaba (el modelo se carga
una sola vez, try/except por caso, actas persistidas, corrida reanudable,
muestreo de Monte Carlo) con tres cosas nuevas:

* **reutiliza el clasificador ya elegido**: carga el artefacto
  ``classifier_A-core_RF.joblib`` del paquete anterior en lugar de reentrenarlo,
  porque el modelo lo fijó su estudio de ablación y aquí no se toca. Si el
  artefacto no está, lo entrena y lo guarda en ``artifacts/`` de este paquete;
* **registra por caso cuántos pases hizo el verificador**, si cerró en `ready` y
  qué documentos quedaron sin abrir;
* **expone el muestreo por papel**: ``--temperature`` y ``--token-scale`` para
  poder medir de verdad el efecto del muestreo en vez de suponerlo. Ojo con
  ``--temperature``: la corrida anterior YA iba a 0.0, así que bajarla no es una
  opción — véase :mod:`sampling`.

    python -m delete_solution_one.solution_task_one_correction_II.run_task1 \
        --out-root .../runs/mc_s0 --sample 30 --seed 0
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

# El clasificador y el bloque de características se reutilizan tal cual del
# paquete anterior: son la pieza que su estudio de ablación dejó decidida
# (Random Forest sobre A-core, ganador en 10 de 10 semillas) y no se reabre aquí.
from delete_solution_one.solution_task_one_correction_claude import features as F  # noqa: E402
from delete_solution_one.solution_task_one_correction_claude.experts.classifier_expert import (  # noqa: E402
    ClassifierExpert,
    ExpertSpec,
)
from delete_solution_one.solution_task_one_correction_II import roster as R  # noqa: E402
from delete_solution_one.solution_task_one_correction_II.board import Board  # noqa: E402
from delete_solution_one.solution_task_one_correction_II.decide import to_gc_outputs  # noqa: E402
from delete_solution_one.solution_task_one_correction_II.graph import (  # noqa: E402
    create_conference_graph,
)

load_dotenv()
log = logging.getLogger("junta")

TASK = 1
HERE = Path(__file__).resolve().parent
PREV = HERE.parent / "solution_task_one_correction_claude"
DATA = REPO / "data" / f"task{TASK}"
INPUT_DIR = DATA / "agent_input"
GT_DIR = DATA / "ground_truth"
ARTIFACTS = HERE / "artifacts"
DECISION_FILE = "prostate-biopsy-decision.json"
REASONING_FILE = "prostate-biopsy-decision-reasoning.json"

#: El mismo experto que la generación anterior, y a propósito: su ablación
#: (15 familias × 6 conjuntos, 5×5 CV, y después 10 semillas de estabilidad) lo
#: dejó fijado. Aquí no se reabre esa decisión.
DEFAULT_SPEC = ExpertSpec(feature_set="A-core", model="RF", n_bags=30, seed=0)


def get_classifier(spec: ExpertSpec, retrain: bool = False) -> ClassifierExpert | None:
    """Carga el artefacto ya entrenado; si no está, lo entrena una vez."""
    name = f"classifier_{spec.feature_set}_{spec.model}.joblib"
    for path in (ARTIFACTS / name, PREV / "artifacts" / name):
        if path.exists() and not retrain:
            try:
                expert = ClassifierExpert.load(path)
                log.info("Clasificador cargado de %s — %s", path, expert.s["metrics"])
                return expert
            except Exception as exc:  # noqa: BLE001
                log.warning("No se pudo cargar %s (%s)", path, exc)
    try:
        expert = ClassifierExpert.train(DATA, spec)
        expert.save(ARTIFACTS / name)
        log.info("Clasificador entrenado y guardado en %s — %s", ARTIFACTS / name, expert.s["metrics"])
        return expert
    except Exception as exc:  # noqa: BLE001 — la junta corre igual sin él
        log.exception("No se pudo entrenar el clasificador: %s", exc)
        return None


def load_queries(only_labelled: bool, split: str | None, pids: list[str] | None,
                 limit: int | None, sample: int | None, seed: int) -> list[dict]:
    wanted: set[str] | None = None
    if pids:
        wanted = set(pids)
    elif split in ("dev", "val"):
        f = REPO / "dev" / "splits" / f"task{TASK}_{split}.txt"
        wanted = {ln.strip() for ln in f.read_text().splitlines() if ln.strip()}
    elif only_labelled:
        wanted = {p.name for p in GT_DIR.iterdir() if p.is_dir()} if GT_DIR.is_dir() else None

    out: list[dict] = []
    for sub in sorted(p for p in INPUT_DIR.iterdir() if p.is_dir() and (p / F.PROMPT_FILE).exists()):
        files = F.load_case(sub)
        cid = files["prompt"].get("case_id")
        if wanted is not None and cid not in wanted:
            continue
        out.append({
            "case_id": cid,
            "files": files,
            "payload": files["prompt"],
            "context": render_baseline_prompt(files["prompt"], REPO / "templates" / "prompts"),
        })
    if sample and sample < len(out):
        rng = np.random.default_rng(seed)
        idx = sorted(rng.choice(len(out), size=sample, replace=False))
        out = [out[i] for i in idx]
        log.info("Muestreo de Monte Carlo: %d casos (semilla %d)", len(out), seed)
    return out[:limit] if limit else out


def mcp_args() -> list[str]:
    return ["-m", "chimera_agent_baseline.mcp_server", "--data-dir", str(INPUT_DIR),
            "--resource-dir", str(REPO / "resources"), "--tool-registry", f"task{TASK}",
            "--log-level", "ERROR"]


def write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False))


async def run(args) -> None:
    with initialize_config_dir(config_dir=str(REPO / "configs"), version_base=None):
        cfg = compose(config_name="config",
                      overrides=["+experiment=local_paths",
                                 f"generation.temperature={args.temperature}"])

    spec = ExpertSpec(feature_set=args.feature_set, model=args.model, n_bags=args.n_bags, seed=0)
    classifier = get_classifier(spec, retrain=args.retrain)

    model = load_model(cfg)
    feature_store = FeatureStore(INPUT_DIR)
    client = MultiServerMCPClient({"chimera": {"command": sys.executable, "args": mcp_args(),
                                               "transport": "stdio"}})
    tools = await client.get_tools()
    log.info("Herramientas MCP servidas: %s", ", ".join(t.name for t in tools))

    graph = create_conference_graph(
        tools, model, feature_store, classifier,
        max_passes=args.max_passes, max_reveals=args.max_reveals,
        eau_max_calls=args.eau_calls, reg_max_calls=args.registrar_calls,
        chair_max_retries=args.chair_retries, step_timeout=cfg.agent.step_timeout,
        temperature=args.temperature, token_scale=args.token_scale,
    )

    seeds = args.seeds if args.seeds is not None else [args.seed]
    for seed in seeds:
        root = Path(args.out_root) if len(seeds) == 1 else Path(args.out_root) / f"mc_s{seed}"
        queries = load_queries(not args.all_cases, args.split, args.pids, args.limit,
                               args.sample, seed)
        log.info("[semilla %s] casos a correr: %d -> %s", seed, len(queries), root)
        write_json(root / "run_config.json", {
            "model_id": cfg.model.model_id,
            "temperature": float(args.temperature),
            "token_scale": float(args.token_scale),
            "classifier": spec.__dict__,
            "classifier_metrics": classifier.s["metrics"] if classifier else None,
            "max_passes": args.max_passes, "max_reveals": args.max_reveals,
            "n_cases": len(queries), "sample": args.sample, "seed": seed,
            "split": args.split or ("labelled" if not args.all_cases else "all"),
            "mcp_tools": [t.name for t in tools],
            "design": "conference: intake -> classifier -> cohort -> EAU -> moderator -> "
                      "[image] -> registrar -> verifier -> [reopen] -> chair",
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
                {"case_id": cid, "task": TASK, "prompt_payload": q["payload"],
                 "case_files": q["files"], "case_prompt": q["context"]},
                {"recursion_limit": args.recursion_limit})
            structured = state["structured_response"]
            decision, reasoning = to_gc_outputs(structured)
            write_json(case_out / DECISION_FILE, decision)
            write_json(case_out / REASONING_FILE, reasoning)

            board = Board.from_dicts(cid, TASK, state.get("interventions", []))
            write_json(board_dir / f"{cid}.json", board.to_dict())
            (board_dir / f"{cid}.md").write_text(board.to_markdown())

            verdict = state.get("verdict") or {}
            revealed = structured["reveal_sequence"]
            record |= {
                "ok": True, "seconds": round(time.time() - t0, 1),
                "decision": decision, "confidence": structured["confidence"],
                "reveal_sequence": revealed,
                "variable_weights": structured["variable_weights"],
                "free_text_chars": len(structured["reasoning"]),
                "n_interventions": len(state.get("interventions", [])),
                "passes": verdict.get("passes", 1),
                "verifier_ready": verdict.get("ready"),
                "verifier_suggest": verdict.get("suggest"),
                "verifier_parsed": verdict.get("parsed"),
                "left_closed": [s for s in R.SECTION_BY_TOOL.values()
                                if s not in R.NEVER and s not in revealed],
                "questions": state.get("questions"),
                "plan": state.get("plan"),
                "need_image": state.get("need_image"),
                "warnings": state.get("warnings") or [],
            }
        except Exception as exc:  # noqa: BLE001
            record |= {"ok": False, "seconds": round(time.time() - t0, 1),
                       "error": f"{type(exc).__name__}: {exc}"}
            log.exception("Caso %s falló", cid)
        with summary.open("a") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        if i % 5 == 0 or i == len(queries):
            log.info("%d/%d casos", i, len(queries))
    log.info("Muestra terminada. Salidas en %s", out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description="Junta clínica sobre pizarra — tarea 1")
    ap.add_argument("--out-root", default=str(HERE / "runs" / "run1"))
    ap.add_argument("--split", default=None, choices=["dev", "val"])
    ap.add_argument("--pids", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None,
                    help="muestrea N casos al azar (experimentos de Monte Carlo)")
    ap.add_argument("--seed", type=int, default=0, help="semilla del muestreo")
    ap.add_argument("--seeds", type=int, nargs="+", default=None,
                    help="varias semillas en un solo proceso; escribe <out-root>/mc_s<semilla>")
    ap.add_argument("--all-cases", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="temperatura de TODOS los papeles. Ya estaba en 0.0 en la corrida "
                         "anterior: no se puede bajar más, sólo subir para medir")
    ap.add_argument("--token-scale", type=float, default=1.0,
                    help="multiplica los topes de tokens por papel (ver sampling.VOICES)")
    ap.add_argument("--max-passes", type=int, default=3,
                    help="pases máximos que puede abrir el verificador")
    ap.add_argument("--max-reveals", type=int, default=R.MAX_REVEALS,
                    help="techo de documentos abiertos por caso; tool_score es precisión")
    ap.add_argument("--eau-calls", type=int, default=2)
    ap.add_argument("--registrar-calls", type=int, default=6)
    ap.add_argument("--chair-retries", type=int, default=3)
    ap.add_argument("--recursion-limit", type=int, default=160)
    ap.add_argument("--feature-set", default=DEFAULT_SPEC.feature_set)
    ap.add_argument("--model", default=DEFAULT_SPEC.model)
    ap.add_argument("--n-bags", type=int, default=DEFAULT_SPEC.n_bags)
    ap.add_argument("--retrain", action="store_true")
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
