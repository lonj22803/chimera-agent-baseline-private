"""Contrato Grand Challenge de un caso; delega en los tres runners existentes.

No modifica inference.py. Pesos y embeddings locales, /input de sólo lectura,
y staging bajo /tmp. Un proceso/contenedor por paciente.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
from contextlib import AsyncExitStack
from .telemetry import ConferenceMeter, ResourceMonitor
from .slugs import output_files, output_filenames
from .runtime import configure
from . import deadline
from . import warmup
from chimera_agent_baseline.output.schema import normalise_to_full_shape

from .chimera_experts.io import Case, CLINICAL_FILENAME, DECISION_FILENAME, FEATURES_FILENAME
from .guards import validate_output

log = logging.getLogger(__name__)
REPO = Path(__file__).resolve().parents[2]


def _read(value):
    if isinstance(value, (str, Path)):
        value = json.loads(Path(value).read_text())
    if not isinstance(value, dict):
        raise ValueError("Input must be a JSON object or a path to one")
    return dict(value)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


async def _run(task, runner, case, input_dir, embedding_model_dir):
    from hydra import compose, initialize_config_dir
    from chimera_agent_baseline.models import load_model

    model_dir = Path(os.environ.get("CHIMERA_MODEL_DIR", REPO / "model/gemma-4-E2B-it"))
    needs_tools = task in (1, 2) or os.environ.get("CHIMERA_T3_RAG") == "1"
    embeddings = Path(embedding_model_dir or REPO / "model/embedding_model")
    for path in ([model_dir, embeddings] if needs_tools else [model_dir]):
        if not path.is_absolute() or not path.is_dir() or not any(path.iterdir()):
            raise ValueError(f"Local absolute populated model directory required: {path}")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    meter = ConferenceMeter()
    meter.start_case(case.case_id)
    phases = {}
    with ResourceMonitor() as monitor:
        try:
            # Lo que no necesita el modelo arranca antes que el modelo. En la V1
            # esto corría detrás de vLLM, en serie, y es el tramo que agotó el
            # límite de GC: entre "init engine" y la primera llamada al modelo,
            # su log muestra 308 s donde aquí hay 38 s. Mismo cálculo, mismos
            # ficheros de entrada, sólo antes. Un fallo aquí no se propaga:
            # ``warmup.result`` reconstruye en el camino crítico.
            # La clave lleva el caso. El modelo y el servicio de embeddings se
            # comparten si alguna vez se despachan dos casos en un proceso; el
            # panel de expertos, no: es de este paciente.
            if hasattr(runner, "prewarm"):
                warmup.submit(f"prewarm:{case.case_id}", lambda: runner.prewarm(case, input_dir))
            if needs_tools:
                from chimera_agent_baseline.rag import start_embedding_service
                warmup.submit("embed", lambda: start_embedding_service(str(embeddings)))

            start = time.monotonic()
            with initialize_config_dir(config_dir=str(REPO / "configs"), version_base=None):
                cfg = compose(config_name="config", overrides=["generation.temperature=0.0"])
            cfg.paths.model_dir = str(model_dir)
            cfg.model.model_id = str(model_dir)
            configure(cfg)
            # El grueso de cargar vLLM es CPU y disco, no GPU: en un hilo deja
            # que el bucle entre en la sesión MCP —otro subproceso de Python que
            # vuelve a importar medio entorno— a la vez. Si el backend no
            # tolerase cargarse fuera del hilo principal, se vería aquí y no a
            # mitad de la junta.
            #
            # Hilo demonio y no ``run_in_executor``: los del ejecutor por
            # omisión no son demonios y ``asyncio.run`` los espera al cerrar,
            # así que un caso cortado por el reloj se quedaría esperando a que
            # termine de cargar el modelo que ya no va a usar.
            warmup.submit("model", lambda: load_model(cfg))
            # Sessions and embedding service close before dispatch serializes output.
            async with AsyncExitStack() as stack:
                tools = []
                start_tools = time.monotonic()
                if needs_tools:
                    from langchain_mcp_adapters.client import MultiServerMCPClient
                    from langchain_mcp_adapters.tools import load_mcp_tools
                    client = MultiServerMCPClient({"chimera": {
                        "command": sys.executable,
                        "args": ["-m", "chimera_agent_baseline.mcp_server", "--data-dir", str(input_dir),
                                 "--resource-dir", str(REPO / "resources"), "--tool-registry", f"task{task}",
                                 "--log-level", "ERROR"], "transport": "stdio"}})
                    session = await stack.enter_async_context(client.session("chimera"))
                    tools = await load_mcp_tools(session)
                    svc = warmup.result("embed", lambda: start_embedding_service(str(embeddings)))
                    if svc is not None:
                        stack.callback(svc.stop)
                phases["mcp"] = time.monotonic() - start_tools
                model = await warmup.aresult("model", lambda: load_model(cfg))
                meter.tokenizer = getattr(model, "tokenizer", None)
                meter.approx = meter.tokenizer is None
                phases["model_load"] = time.monotonic() - start
                start = time.monotonic()
                result = await runner.run_case(case, input_dir, model, tools, cfg.agent.step_timeout, meter=meter)
                phases["graph"] = time.monotonic() - start
                # ``mcp`` y ``model_load`` se solapan a propósito, así que las
                # fases ya no suman el total: ``warm_*`` da el coste real de cada
                # hilo y ``model_load`` el reloj hasta que el modelo está listo.
            return result
        finally:
            print(json.dumps({"kind": "gc_resources", "case_id": case.case_id, "task": task,
                              "phases_seconds": {**phases, **warmup.phases()},
                              **meter.summary(), **monitor.summary()}),
                  file=sys.stderr, flush=True)


async def _bounded(task, runner, case, input_dir, embedding_model_dir):
    """``_run`` con el reloj de GC encima.

    Al agotarse el presupuesto, ``wait_for`` cancela la junta y la excepción cae
    en el ``except`` de ``dispatch``, que escribe el respaldo determinista. Sin
    esto, GC mata el contenedor y no se escribe nada: el caso no puntúa bajo,
    puntúa cero.
    """
    left = deadline.remaining()
    if left == float("inf"):
        return await _run(task, runner, case, input_dir, embedding_model_dir)
    return await asyncio.wait_for(_run(task, runner, case, input_dir, embedding_model_dir),
                                  timeout=max(left, 1.0))


def dispatch(task: int, *, structured_prompt, clinical_data, neural_representations,
             output_path, embedding_model_dir=None) -> int:
    """Escribe los dos JSON validados. Errores del grafo activan el respaldo del runner.

    Una tarea desconocida o un destino no escribible son errores del llamador.
    El respaldo se registra en stderr; devolver 0 indica salida escrita, no éxito del LLM.
    """
    if type(task) is not int or task not in (1, 2, 3):
        raise ValueError("task must be 1, 2 or 3")
    runner = importlib.import_module(f"delete_final_versions_task_V1_1.task_{task}.agent.run_task{task}")
    output_filenames(task)  # Reject invalid slug configuration before running the model.
    deadline.start()
    started = time.monotonic()
    fallback = cut = False
    case = Case("case", task)
    try:
        case.prompt = _read(structured_prompt)
        case.case_id = str(case.prompt.get("case_id") or case.prompt.get("pid") or "case")
        case.clinical = _read(clinical_data)
        case.embeddings = _read(neural_representations)
        with tempfile.TemporaryDirectory(prefix="chimera-", dir="/tmp") as tmp:
            # Case IDs are directory names in both the feature store and MCP.
            input_dir = Path(tmp) / f"task{task}" / "agent_input"
            if Path(case.case_id).name != case.case_id or case.case_id in (".", ".."):
                raise ValueError("case_id must be a single safe path component")
            staged = input_dir / case.case_id
            _write(staged / "structured-prompt.json", {**case.prompt, "case_id": case.case_id})
            _write(staged / CLINICAL_FILENAME[task], case.clinical)
            _write(staged / FEATURES_FILENAME, case.embeddings)
            payload, event = asyncio.run(_bounded(task, runner, case, input_dir, embedding_model_dir))
            payload = normalise_to_full_shape(task, payload)
            valid, why = validate_output(task, payload)
            if not valid:
                raise ValueError(why)
    except TimeoutError:
        # El reloj del caso. La junta queda cancelada a medias y los hilos
        # demonio —el que carga vLLM, el que puntúa— siguen donde estaban.
        log.warning("Task %s case %s agotó el presupuesto; se escribe el respaldo", task, case.case_id)
        fallback = cut = True
        payload, event = runner.fallback_case(case)
    except Exception:
        log.exception("Task %s case %s failed; writing fallback", task, case.case_id)
        fallback = True
        payload, event = runner.fallback_case(case)
    payload = normalise_to_full_shape(task, payload)
    valid, why = validate_output(task, payload)
    if not valid:
        raise ValueError(f"Invalid fallback: {why}")
    write_start = time.monotonic()
    if task == 3:
        canonical = runner.to_gc_outputs(payload, event)
        values = list(canonical.values())
        decision, reasoning = values
    else:
        decision, reasoning = runner.to_gc_outputs(payload)
    for name, value in output_files(task, decision, reasoning).items():
        _write(Path(output_path) / name, value)
    print(json.dumps({"kind": "gc_delivery", "task": task, "case_id": case.case_id,
                      "fallback": fallback, "cut": cut,
                      "write_seconds": time.monotonic() - write_start,
                      "total_seconds": time.monotonic() - started, **deadline.summary()}),
          file=sys.stderr, flush=True)
    if cut:
        # La salida ya está en disco y los dos flujos, vaciados. Lo que queda por
        # hacer es desmontar un CUDA que un hilo abandonado puede estar tocando, y
        # eso puede acabar en un exit distinto de 0 con los ficheros ya escritos:
        # para Grand Challenge, un caso perdido igual que si no hubiéramos escrito
        # nada. Salir aquí es el final correcto de un vigía.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    return 0


def run_task1_case(**kwargs):
    return dispatch(1, **kwargs)


def run_task2_case(**kwargs):
    return dispatch(2, **kwargs)


def run_task3_case(**kwargs):
    return dispatch(3, **kwargs)
