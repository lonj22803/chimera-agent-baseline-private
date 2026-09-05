"""Corre el agente en dos brazos (predictor OFF / ON) sobre los mismos casos.

No modifica `run.py`: reutiliza sus piezas (`load_cases`, `create_graph`,
`_write_task_outputs`) y anade lo que el experimento necesita y el runner
upstream no tiene:

* **el modelo se carga UNA vez** y se reutiliza en los dos brazos, para que la
  unica diferencia entre ellos sea la herramienta;
* **try/except por caso** — el runner upstream no lo tiene y un `form_fill` que
  lanza se lleva por delante el resto de la cola (pasa en T3);
* **traza por caso** — herramientas llamadas, avisos del form_fill, duracion y
  la salida estructurada, que es lo que luego compara el notebook;
* **reanudable** — un caso ya escrito no se repite.

    python delete_test/run_experiment.py --arms off on --tasks 1 2 3
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

from dotenv import load_dotenv
from hydra import compose, initialize_config_dir
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from chimera_agent_baseline.agent.graph import create_graph  # noqa: E402
from chimera_agent_baseline.agent.prompts import build_system_prompt  # noqa: E402
from chimera_agent_baseline.case_loader import load_cases  # noqa: E402
from chimera_agent_baseline.models import load_model  # noqa: E402
from chimera_agent_baseline.rag import start_embedding_service  # noqa: E402
from chimera_agent_baseline.run import _write_task_outputs  # noqa: E402
from chimera_agent_baseline.utils import setup_logging  # noqa: E402

load_dotenv()
log = logging.getLogger("experimento")

# Anadido al prompt de sistema SOLO en el brazo `on_prompt`. Se limita a
# presentar la herramienta en el mismo registro que las demas (coste + cuando
# usarla) y a decirle al agente que pese la salida por la fiabilidad que la
# propia herramienta reporta. NO le dice que responder.
ADENDA_PREDICTOR = """

## Image-embedding predictor

One further tool is available: `get_image_predictor`.

| Tool                    | Cost | What it covers |
|-------------------------|------|----------------|
| `get_image_predictor`   | ~\u20ac0  | a trained head over foundation-model embeddings of images already acquired |

It runs a trained head over this patient's frozen foundation-model \
embeddings (MRI / biopsy / prostatectomy, whichever exist) and returns a \
compact score or label — never the raw vectors. The images were already \
acquired, so the call adds no patient burden and no marginal cost.

Call it as part of the workup. Its payload includes a `reliability` field \
with the head's cross-validated discrimination on labelled cases: weigh the \
score accordingly. A head reported near AUC 0.5 carries no information and \
must not move your decision; a head with good discrimination is evidence \
like any other and should be reconciled with the clinical variables — not \
substituted for them. State in your reasoning trace how much weight you \
gave it and why.
"""

ARMAS = {
    #  brazo        -> (predictor MCP, adenda en el prompt)
    "off":        (False, False),
    "on":         (True, False),
    "on_prompt":  (True, True),
}

FICHERO_DECISION = {
    1: "prostate-biopsy-decision.json",
    2: "prostate-treatment-decision.json",
    3: "prostate-time-to-recurrence-or-last-follow-up.json",
}


def casos_etiquetados(task: int) -> set[str]:
    d = REPO / "data" / f"task{task}" / "ground_truth"
    return {p.name for p in d.iterdir() if p.is_dir()} if d.is_dir() else set()


def mcp_args(input_dir: Path, registry: str, predictor: bool) -> list[str]:
    args = [
        "-m", "chimera_agent_baseline.mcp_server",
        "--data-dir", str(input_dir),
        "--resource-dir", str(REPO / "resources"),
        "--tool-registry", registry,
        "--log-level", "ERROR",
    ]
    if predictor:
        args.append("--enable-predictor")
    return args


def traza(mensajes: list) -> dict:
    """Resume la conversacion: que pidio el agente y que le devolvieron."""
    llamadas, herramientas = [], []
    for m in mensajes:
        if isinstance(m, AIMessage):
            for tc in getattr(m, "tool_calls", None) or []:
                llamadas.append({"tool": tc.get("name"), "args": tc.get("args")})
        elif isinstance(m, ToolMessage) and m.name:
            contenido = m.content if isinstance(m.content, str) else json.dumps(m.content)
            herramientas.append({"tool": m.name, "n_chars": len(contenido), "salida": contenido[:1500]})
    final = ""
    for m in reversed(mensajes):
        if isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None):
            final = m.content if isinstance(m.content, str) else json.dumps(m.content)
            break
    return {
        "tool_calls": llamadas,
        "tool_results": herramientas,
        "n_mensajes": len(mensajes),
        "texto_final": final,
    }


async def correr_brazo(cfg, brazo: str, tasks: list[int], modelo, limite: int | None,
                       raiz: Path) -> None:
    predictor, adenda = ARMAS[brazo]
    sistema = build_system_prompt() + (ADENDA_PREDICTOR if adenda else "")
    salidas = raiz / f"output_{brazo}"
    trazas = raiz / "traces" / brazo
    resumen_path = raiz / f"resumen_{brazo}.jsonl"

    for task in tasks:
        input_dir = REPO / "data" / f"task{task}" / "agent_input"
        etiquetados = casos_etiquetados(task)
        consultas = [q for q in load_cases(input_dir, task=task) if q["case_id"] in etiquetados]
        if limite:
            consultas = consultas[:limite]

        cliente = MultiServerMCPClient({"chimera": {
            "command": sys.executable,
            "args": mcp_args(input_dir, f"task{task}", predictor),
            "transport": "stdio",
        }})
        tools = await cliente.get_tools()
        log.info("[%s] task%d: %d herramientas (%s) · %d casos · prompt %d chars",
                 brazo, task, len(tools), ", ".join(t.name for t in tools), len(consultas), len(sistema))

        grafo = create_graph(tools, modelo, sistema,
                             step_timeout=cfg.agent.step_timeout,
                             form_fill_max_retries=cfg.agent.form_fill.max_retries)

        for i, q in enumerate(consultas, 1):
            cid = q["case_id"]
            destino = salidas / f"task{task}" / cid
            traza_f = trazas / f"task{task}" / f"{cid}.json"
            if (destino / FICHERO_DECISION[task]).exists() and traza_f.exists():
                continue

            t0 = time.time()
            registro: dict[str, Any] = {"brazo": brazo, "task": task, "case_id": cid}
            try:
                estado = {"messages": [HumanMessage(content=q["context"])], "case_id": cid, "task": task}
                res = await grafo.ainvoke(estado, {"recursion_limit": cfg.agent.max_iterations})
                estructurado = res["structured_response"]
                _write_task_outputs(destino, task, estructurado)
                registro |= {
                    "ok": True,
                    "segundos": round(time.time() - t0, 1),
                    "structured": estructurado,
                    "form_fill_warnings": res.get("form_fill_warnings") or [],
                    **traza(res["messages"]),
                }
            except Exception as exc:  # noqa: BLE001 — el objetivo es que la cola no se caiga
                registro |= {"ok": False, "segundos": round(time.time() - t0, 1),
                             "error": f"{type(exc).__name__}: {exc}"}
                log.error("[%s] task%d %s FALLO: %s", brazo, task, cid, exc)

            traza_f.parent.mkdir(parents=True, exist_ok=True)
            traza_f.write_text(json.dumps(registro, indent=2, default=str))
            with resumen_path.open("a") as fh:
                fh.write(json.dumps({k: v for k, v in registro.items()
                                     if k in ("brazo", "task", "case_id", "ok", "segundos", "error")}) + "\n")
            if i % 10 == 0 or i == len(consultas):
                log.info("[%s] task%d: %d/%d", brazo, task, i, len(consultas))


async def principal(args) -> None:
    with initialize_config_dir(config_dir=str(REPO / "configs"), version_base=None):
        overrides = ["+experiment=local_paths"]
        if args.temperature is not None:
            overrides.append(f"generation.temperature={args.temperature}")
        cfg = compose(config_name="config", overrides=overrides)

    log.info("modelo=%s provider=%s temperature=%s",
             cfg.model.model_id, cfg.model.provider, cfg.generation.temperature)
    modelo = load_model(cfg)
    raiz = Path(args.out_root)
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / f"config_experimento_{'_'.join(args.arms)}.json").write_text(json.dumps({
        "model_id": cfg.model.model_id,
        "temperature": float(cfg.generation.temperature),
        "top_p": float(cfg.generation.top_p),
        "max_new_tokens": int(cfg.generation.max_new_tokens),
        "max_iterations": int(cfg.agent.max_iterations),
        "brazos": args.arms,
        "adenda_prompt": ADENDA_PREDICTOR,
        "tasks": args.tasks,
        "limite": args.limit,
    }, indent=2))

    for brazo in args.arms:
        await correr_brazo(cfg, brazo, args.tasks, modelo, args.limit, raiz)
    log.info("Experimento terminado.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=["off", "on_prompt"], choices=["off", "on", "on_prompt"])
    ap.add_argument("--tasks", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--out-root", default=str(REPO / "delete_test"))
    args = ap.parse_args()

    setup_logging("INFO")
    svc = start_embedding_service(str(REPO / "model" / "embedding_model"))
    try:
        asyncio.run(principal(args))
    finally:
        if svc:
            svc.stop()


if __name__ == "__main__":
    main()
