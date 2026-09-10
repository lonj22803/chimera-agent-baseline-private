"""Runner de la junta final — tarea 1 (decisión de biopsia).

Configuración de entrega, y por qué es ésa:

* **los cuatro expertos entrenados sobre los 91 casos etiquetados** (modo
  ``deployed``). Son un modelo entrenado con el material que el organizador
  entrega para entrenar, que es exactamente para lo que lo entrega;
* **la biblioteca de precedentes en *leave-one-out***: nunca devuelve el caso
  que se está decidiendo. Sobre el test eso no cambia nada —ningún caso de test
  está en la serie etiquetada— y sobre los 91 hace que la nota mida algo. Con
  ``--self-match`` se enciende el atajo y se ve el techo del mecanismo;
* **temperatura 0** en todos los papeles, con tope de tokens por papel;
* **validación contra ``Task1Output``** antes de escribir cada caso.

    python -m delete_final_versions_task_V1.task_1.agent.run_task1 \
        --out-root .../runs/final --all-cases

Escribe, por caso: los dos ficheros de Grand Challenge, el acta completa en
JSON y en Markdown, y una línea en ``summary.jsonl`` con la telemetría (tokens
por papel, tiempos, herramientas, memoria) que consume el cuaderno de análisis.
"""

from __future__ import annotations

from delete_final_versions_task_V1.task_1.agent.paths import EMBEDDING_MODEL, TEMPLATES, RESOURCES, CONFIGS, SPLITS, RUNS

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from delete_final_versions_task_V1.task_1.agent.paths import REPO, DATA, TASK_ROOT, EVAL_REPO
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

from delete_final_versions_task_V1.task_1.agent import protocol as P  # noqa: E402
from delete_final_versions_task_V1.common.board import Board  # noqa: E402
from delete_final_versions_task_V1.task_1.agent.decide import to_gc_outputs  # noqa: E402
from delete_final_versions_task_V1.task_1.experts_1.experience import ProfessionalExperience  # noqa: E402
from delete_final_versions_task_V1.task_1.experts_1.panel import (  # noqa: E402
    CACHE, Panel, build_cache,
)
from delete_final_versions_task_V1.task_1.agent.graph import (  # noqa: E402
    create_conference_graph,
)
from delete_final_versions_task_V1.common.telemetry import (  # noqa: E402
    ConferenceMeter, device_vram_mb, host_rss_mb,
)

load_dotenv()
log = logging.getLogger("junta-final")

TASK = 1
HERE = TASK_ROOT
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
        log.info("Muestreo de Monte Carlo: %d casos (semilla %d)", len(out), seed)
    return out[:limit] if limit else out


def mcp_args() -> list[str]:
    return ["-m", "chimera_agent_baseline.mcp_server", "--data-dir", str(INPUT_DIR), "--resource-dir",
            str(RESOURCES), "--tool-registry", f"task{TASK}", "--log-level", "ERROR"]


def write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, default=str))


def get_panel(rebuild: bool) -> Panel:
    if not CACHE.exists() or rebuild:
        log.info("Precalculando el panel de expertos (%s)", CACHE)
        build_cache(DATA, CACHE, with_oof=True)
    return Panel(CACHE)


async def run(args) -> None:
    with initialize_config_dir(config_dir=str(CONFIGS), version_base=None):
        cfg = compose(config_name="config", overrides=["+experiment=local_paths",
                                                       f"generation.temperature={args.temperature}",
                                                       f"generation.gpu_memory_utilization={args.gpu_util}"])
    panel = get_panel(args.rebuild_panel)
    library = ProfessionalExperience(DATA, exclude_self=not args.self_match, k=args.k)
    params = {**P.PARAMS, "confidence_policy": args.confidence_policy, "threshold": args.threshold,
              "grade_rule": not args.no_grade_rule, "library_weight": args.library_weight,
              "form_weights": args.form_weights}

    t_model = time.time()
    from delete_final_versions_task_V1.common.runtime import configure
    configure(cfg, args.gpu_util)
    model = load_model(cfg)
    log.info("Modelo cargado en %.1f s", time.time() - t_model)
    meter = ConferenceMeter(getattr(model, "tokenizer", None))
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
            "token_scale": float(args.token_scale), "mode": args.mode,
            "library_exclude_self": library.exclude_self, "k": args.k, "protocol_params": params,
            "weights_policy": args.weights_policy, "max_passes": args.max_passes, "n_cases": len(queries),
            "sample": args.sample, "seed": seed,
            "split": args.split or ("labelled" if not args.all_cases else "all"),
            "mcp_tools": [t.name for t in tools], "panel_experts": panel.experts,
            "model_load_seconds": round(time.time() - t_model, 1),
            "vram_after_load_mb": round(device_vram_mb()[0], 1),
            "design": "final conference: intake -> E1 -> cohort -> library -> E4 trace -> EAU -> moderator -> "
                      "[image] -> registrar -> E2 psa -> E3 fusion -> protocol -> verifier -> [reopen] -> chair "
                      "(clinical digest, no minute, prose guard, schema-validated)",
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
                {"case_id": cid, "task": TASK, "prompt_payload": q["payload"], "case_files": q["files"],
                 "case_prompt": q["context"]},
                {"recursion_limit": args.recursion_limit, "callbacks": [meter]})
            from chimera_agent_baseline.output.schema import normalise_to_full_shape
            structured = normalise_to_full_shape(1, state["structured_response"])
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
                "confidence": structured["confidence"], "reveal_sequence": structured["reveal_sequence"],
                "variable_weights": structured["variable_weights"], "free_text": structured["reasoning"],
                "free_text_chars": len(structured["reasoning"]), "note_words": audit.get("note_words"),
                "schema_ok": audit.get("schema_ok"), "note_violations": audit.get("note_violations"),
                "prose_challenged": audit.get("prose_challenged"),
                "fallback_note": audit.get("fallback_note"), "fallback_form": audit.get("fallback_form"),
                "chair_attempts": audit.get("attempts"), "digest_chars": audit.get("digest_chars"),
                "n_interventions": len(state.get("interventions", [])), "passes": verdict.get("passes", 1),
                "verifier_ready": verdict.get("ready"), "verifier_suggest": verdict.get("suggest"),
                "registrar_lean": (next((it.get("data", {}).get("lean") for it in reversed(state.get("interventions", []))
                                         if it["speaker"] == "REGISTRAR"), None)),
                "planned": state.get("planned"), "protocol_rule": proto.get("rule"),
                "protocol_who": proto.get("who"), "protocol_p": proto.get("p"),
                "protocol_votes": proto.get("votes"), "dissenting": proto.get("dissenting"),
                "variable_view": [{k: r[k] for k in ("variable", "value", "levels", "n_strong", "trace", "record")}
                                  for r in (proto.get("variable_view") or [])],
                "expert_confidence": {sp: (next((it.get("data", {}).get("confidence") for it in reversed(state.get("interventions", []))
                                                 if it["speaker"] == sp), None))
                                      for sp in ("EXPERT-STRUCTURED", "EXPERT-FUSION", "EXPERT-COHORT",
                                                 "EXPERT-EXPERIENCE", "EXPERT-PSA", "EXPERT-TRACE")},
                "grade": (state.get("grade") or {}).get("gg"),
                "grade_quote": (state.get("grade") or {}).get("quote"),
                "on_surveillance": (state.get("grade") or {}).get("on_surveillance"),
                "library_self_match": (state.get("library") or {}).get("self_match"),
                "questions": state.get("questions"), "need_image": state.get("need_image"),
                "warnings": state.get("warnings") or [], **{f"tel_{k}": v for k, v in tele.items()},
            }
            with telemetry.open("a") as fh:
                for row in meter.rows:
                    fh.write(json.dumps({"kind": "llm", **row}) + "\n")
                for row in meter.tools:
                    fh.write(json.dumps({"kind": "tool", **row}) + "\n")
        except Exception as exc:  # noqa: BLE001
            record |= {"ok": False, "seconds": round(time.time() - t0, 1), "error": f"{type(exc).__name__}: {exc}"}
            log.exception("Caso %s falló", cid)
        with summary.open("a") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        if i % 5 == 0 or i == len(queries):
            log.info("%d/%d casos · RSS %.0f MiB · VRAM %.0f MiB", i, len(queries), host_rss_mb(),
                     device_vram_mb()[0])
    log.info("Muestra terminada. Salidas en %s", out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description="Junta clínica con expertos entrenados — tarea 1, versión final")
    ap.add_argument("--out-root", default=str(RUNS / "final"))
    ap.add_argument("--mode", default="deployed", choices=["deployed", "honest"],
                    help="deployed: expertos entrenados con los 91 (entrega). honest: out-of-fold, para medir")
    ap.add_argument("--self-match", action="store_true",
                    help="deja que la biblioteca devuelva el propio caso (techo del mecanismo, no entrega)")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--confidence-policy", default=P.PARAMS["confidence_policy"], choices=["trace", "agreement"])
    ap.add_argument("--weights-policy", default="model+mode", choices=["model+mode", "model", "mode"])
    ap.add_argument("--threshold", type=float, default=P.PARAMS["threshold"])
    ap.add_argument("--library-weight", type=float, default=P.PARAMS["library_weight"])
    ap.add_argument("--no-grade-rule", action="store_true")
    ap.add_argument("--form-weights", default=P.PARAMS["form_weights"], choices=["trace", "board"],
                    help="qué pesos van al formulario: los del Experto 4 (trace) o subidos por acuerdo del panel (board)")
    ap.add_argument("--rebuild-panel", action="store_true")
    ap.add_argument("--split", default=None, choices=["labeled", "unlabeled", "all", "dev", "val"],
                    help="all escribe labeled/ y unlabeled/ separados bajo --out-root")
    ap.add_argument("--pids", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, nargs="+", default=None)
    ap.add_argument("--all-cases", action="store_true", help="los 195, no sólo los 91 etiquetados")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--token-scale", type=float, default=1.0)
    ap.add_argument("--max-passes", type=int, default=2)
    ap.add_argument("--eau-calls", type=int, default=2)
    ap.add_argument("--registrar-calls", type=int, default=6)
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


async def run_case(case, input_dir, model, tools, step_timeout, meter=None):
    """Adaptador de un caso: mismo grafo y política que el runner de entrega."""
    panel = Panel(CACHE)
    library = ProfessionalExperience(DATA, exclude_self=True)
    graph = create_conference_graph(tools, model, FeatureStore(input_dir), panel, library,
                                    mode="deployed", protocol_params=dict(P.PARAMS),
                                    step_timeout=step_timeout, temperature=0.0)
    state = await graph.ainvoke(
        {"case_id": case.case_id, "task": 1, "prompt_payload": case.prompt,
         "case_files": {"prompt": case.prompt, "clinical": case.clinical,
                        "features": case.embeddings},
         "case_prompt": render_baseline_prompt(case.prompt, TEMPLATES)},
        {"recursion_limit": 160, "callbacks": [meter] if meter else []})
    return state["structured_response"], None


def fallback_case(case):
    from .decide import clinical_note
    from ..experts_1.cohort import criterion
    c = criterion(case.prompt)
    action = c["verdict"] or "yes"
    because, against, alternative = P.clinical_reason(case.prompt, None, [], action)
    return {"case_id": case.case_id, "task": 1, "biopsy_decision": action == "yes",
            "confidence": "uncertain", "reveal_sequence": [],
            "variable_weights": {"bx": "important", "fh": "not_used", "age": "noted",
                "dre": "not_used", "psa": "important", "vol": "not_used", "psad": "not_used",
                "cspca": "not_used", "pirads": "not_used", "comorbidity": "noted"},
            "reasoning": clinical_note(case.prompt, None, [], because, action, against, alternative)}, None


if __name__ == "__main__":
    main()
