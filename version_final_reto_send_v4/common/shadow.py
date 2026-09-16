"""La sombra: la salida de los expertos, escrita sin esperar al LLM.

Por qué existe
--------------
La fase Test de Grand Challenge rechazó la V2 porque muchos casos pasaron de
15 minutos (uno llegó a ~1291 s). El reloj de ``deadline`` corta dentro del
mismo proceso y cae al respaldo de ``runner.fallback_case``, que en T1 decide
sólo por la cohorte: **71/91** frente a los **83/91** de la entrega.

Pero la parte de la salida que puntúa el evaluador sin juez no la decide el LLM.
Medido el 15-sep-2026 contra ``result_v2/``:

* T1: la cascada de expertos y protocolo da la misma decisión, confianza, pesos
  y revelaciones que la junta en **91/91** casos;
* T2: la misma decisión, confianza y pesos en **72/72**;
* T3: ``fallback_case`` ya da el mismo evento y los mismos meses en **75/75**.

El LLM sólo redacta el texto libre. Así que este módulo calcula esa salida por
el camino determinista —las mismas funciones, en el mismo orden que el grafo, y
la nota de ``clinical_note`` que el propio presidente usa cuando no redacta— y
la deja lista en disco para que ``supervisor`` la publique si la junta no
termina a tiempo.

Qué NO cambia
-------------
Corre en **su propio proceso**. No toca el proceso de la junta: ni sus
expertos, ni el ``RandomState`` de sus imputadores, ni sus prompts. Cada
proceso desunpickla sus propios artefactos, así que los sorteos de la sombra
parten del mismo estado que los de la junta. Un caso que termina a tiempo
entrega exactamente lo que entregaba la V2.

Dos etapas, cada una publicada con un ``rename`` de directorio atómico:

``0-respaldo``  el ``fallback_case`` del runner, en milisegundos;
``1-expertos``  la decisión de los expertos con la nota determinista.

    python -m version_final_reto.common.shadow --input /input --out /tmp/x
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

log = logging.getLogger(__name__)

STAGE_FALLBACK = "0-respaldo"
STAGE_EXPERTS = "1-expertos"
STAGES = (STAGE_EXPERTS, STAGE_FALLBACK)  # de mejor a peor


def detect_task(input_dir: Path) -> int:
    """La tarea por el fichero clínico presente, como ``inference.get_interface_key``."""
    from .chimera_experts.io import CLINICAL_FILENAME
    found = [t for t, name in CLINICAL_FILENAME.items() if (input_dir / name).is_file()]
    if len(found) != 1:
        raise ValueError(f"No se reconoce la interfaz en {input_dir}: {found}")
    return found[0]


def read_case(task: int, input_dir: Path):
    """El mismo ``Case`` que construye ``gc_entry.dispatch``."""
    from .chimera_experts.io import Case, CLINICAL_FILENAME, FEATURES_FILENAME
    from .gc_entry import _read
    case = Case("case", task)
    case.prompt = _read(input_dir / "structured-prompt.json")
    case.case_id = str(case.prompt.get("case_id") or case.prompt.get("pid") or "case")
    case.clinical = _read(input_dir / CLINICAL_FILENAME[task])
    case.embeddings = _read(input_dir / FEATURES_FILENAME)
    return case


def stage_inputs(task: int, case, root: Path) -> Path:
    """Replica el ``agent_input`` que ``dispatch`` prepara para MCP."""
    from .chimera_experts.io import CLINICAL_FILENAME, FEATURES_FILENAME
    from .gc_entry import _write
    input_dir = root / f"task{task}" / "agent_input"
    if Path(case.case_id).name != case.case_id or case.case_id in (".", ".."):
        raise ValueError("case_id must be a single safe path component")
    staged = input_dir / case.case_id
    _write(staged / "structured-prompt.json", {**case.prompt, "case_id": case.case_id})
    _write(staged / CLINICAL_FILENAME[task], case.clinical)
    _write(staged / FEATURES_FILENAME, case.embeddings)
    return input_dir


# -- T1: el grafo sin la sala -------------------------------------------------

def _tool_text(store, case_id: str, fields) -> str:
    """Lo que devuelve la herramienta MCP (``mcp_server._register_precomputed_tool``)."""
    result = store.extract(case_id, fields)
    if set(result.keys()) == {"case_id"}:
        return json.dumps({"case_id": case_id, "note": "No data available for this tool and case."})
    return json.dumps(result)


def experts_task1(case, input_dir: Path):
    """Los nodos de ``task_1/agent/graph.py`` que no llaman al LLM, en su orden.

    Registrador ideal: abre exactamente lo que planifica el experto de traza,
    que es lo que hizo la sala en los 91 casos etiquetados. El presidente toma
    su rama determinista: misma decisión, confianza y pesos, nota de
    ``clinical_note``.
    """
    from chimera_agent_baseline.output.schema import normalise_to_full_shape
    from chimera_agent_baseline.tools.base import CaseDataStore
    from chimera_agent_baseline.tools.definitions import TASK1_TOOLS
    from version_final_reto.common import roster as R
    from version_final_reto.task_1.agent import protocol as P
    from version_final_reto.task_1.agent import run_task1
    from version_final_reto.task_1.agent.decide import (
        clinical_note, documented_grade, enforce_grounding, validate_output)
    from version_final_reto.task_1.experts_1 import cohort as cohort_expert
    from version_final_reto.task_1.experts_1 import experience as library_expert
    from version_final_reto.task_1.experts_1 import fusion as fusion_expert
    from version_final_reto.task_1.experts_1 import psa as psa_expert
    from version_final_reto.task_1.experts_1 import structured as structured_expert
    from version_final_reto.task_1.experts_1 import trace as trace_expert

    warm = run_task1.prewarm(case, input_dir)
    panel, library = warm["panel"], warm["library"]
    cid, payload, mode = case.case_id, case.prompt, "deployed"

    _, structured = structured_expert.render(panel, cid, mode, payload)
    _, cohort = cohort_expert.render(payload)
    recalled = library.recall(cid, payload)
    _, experience = library_expert.render(recalled, payload)
    bx = str(payload.get("bx") or "None")
    bucket_mode = library.bucket_mode(bx, exclude=cid if library.exclude_self else None)
    trace = trace_expert.predict(panel, cid, mode, recalled, bucket_mode, weights_policy="model+mode")

    roster = R.Roster([SimpleNamespace(name=t.name) for t in TASK1_TOOLS])
    revealed = [s for s in trace["reveal_sequence"] if roster.tool_for(s) and s not in R.NEVER]
    specs = {t.name: t for t in TASK1_TOOLS}
    store = CaseDataStore(input_dir)
    corpus = "\n".join(_tool_text(store, cid, specs[R.TOOL_BY_SECTION[s]].fields) for s in revealed)

    _, psa = psa_expert.render(panel, cid, revealed, payload)
    _, fusion = fusion_expert.render(panel, cid, mode, revealed, payload)
    grade = documented_grade(corpus)
    proto = P.consolidate(payload, cohort, structured, fusion, experience or None, trace, grade, revealed,
                          params=dict(P.PARAMS), psa=psa)

    decision = proto.get("decision") or "yes"
    because, against, alternative = P.clinical_reason(payload, grade, revealed, decision)
    grounded, _ = enforce_grounding({"variable_weights": dict(proto.get("variable_weights") or {})}, revealed)
    final = {"case_id": cid, "task": 1, "biopsy_decision": decision == "yes",
             "confidence": proto.get("confidence") or "clear",
             "variable_weights": dict(grounded["variable_weights"]),
             "reasoning": clinical_note(payload, grade, revealed, because, decision, against, alternative)}
    full = normalise_to_full_shape(1, final)
    full["reveal_sequence"] = revealed
    full, _ = enforce_grounding(full, revealed)
    ok, why = validate_output(full)
    if not ok:
        raise ValueError(why)
    return full, None


# -- T2: el grafo sin la sala -------------------------------------------------

def experts_task2(case, input_dir: Path):
    """Los nodos de ``task_2/agent/graph.py`` que no llaman al LLM, en su orden.

    Registrador ideal: abre todo el plan interno fijo. El presidente toma su
    rama determinista (``build_output`` con ``note=None``).
    """
    from chimera_agent_baseline.tools.base import CaseDataStore
    from chimera_agent_baseline.tools.definitions import TASK2_TOOLS
    from version_final_reto.task_2.agent import decide
    from version_final_reto.task_2.agent import protocol as P
    from version_final_reto.task_2.agent import run_task2

    reader = run_task2.prewarm(case, input_dir)["reader"]
    cid, payload, features_all = case.case_id, case.prompt, case.embeddings

    def reading(name, documents=None):
        clinical = documents or {}
        features = {k: v for k, v in features_all.items()
                    if ('radiology_report' in clinical and 'mri' in k.lower()) or
                       ('pathology_report' in clinical and 'biopsy' in k.lower())}
        try:
            return reader.predict(name, cid, payload, clinical, features)
        except Exception as exc:  # noqa: BLE001 — igual que ``graph.reading``
            return {'available': False, 'error': f'{type(exc).__name__}: {exc}'}

    experts = {'expert_one': reading('expert_one')}
    experts['expert_five'] = reading('expert_five')

    by_name = {t.name: t for t in TASK2_TOOLS}
    section_tools = {section: by_name[name] for name, section in P.SECTION_BY_TOOL.items() if name in by_name}
    store = CaseDataStore(input_dir)
    documents = {}
    for section in P.trace(payload)['internal_plan']:
        if section in documents or section not in section_tools:
            continue
        tool = section_tools[section]
        value = json.loads(_tool_text(store, cid, tool.fields))
        got = P.SECTION_BY_TOOL[tool.name]
        if isinstance(value, dict) and got in value and value[got] is not None:
            documents[got] = value[got]
    revealed = list(documents)

    if 'pathology_report' in documents:
        experts['expert_two'] = reading('expert_two', documents)
    else:
        experts['expert_two'] = {'available': False, 'pending': 'pathology_report'}
    experts['expert_four'] = reading('expert_four', documents)
    experts['expert_five'] = reading('expert_five', documents)
    if P.fitness_needed(experts):
        experts['expert_three'] = reading('expert_three', documents)

    proto = P.consolidate(payload, experts, revealed)
    out, _ = decide.build_output(cid, payload, proto, revealed, None)
    return out, None


def experts_task3(case, input_dir: Path):
    """T3 ya lo tenía: ``fallback_case`` coincide con la entrega en 75/75."""
    from version_final_reto.task_3.agent import run_task3
    return run_task3.fallback_case(case)


BUILDERS = {1: experts_task1, 2: experts_task2, 3: experts_task3}


# -- ficheros de Grand Challenge ---------------------------------------------

def gc_files(task: int, runner, payload: dict, event) -> dict[str, object]:
    """Los mismos pasos que ``dispatch`` entre el registro y los dos ficheros."""
    from chimera_agent_baseline.output.schema import normalise_to_full_shape
    from .guards import validate_output
    from .slugs import output_files
    payload = normalise_to_full_shape(task, payload)
    ok, why = validate_output(task, payload)
    if not ok:
        raise ValueError(why)
    if task == 3:
        decision, reasoning = list(runner.to_gc_outputs(payload, event).values())
    else:
        decision, reasoning = runner.to_gc_outputs(payload)
    return output_files(task, decision, reasoning)


def publish(out_root: Path, stage: str, files: dict[str, object], meta: dict) -> None:
    """Escribe una etapa entera y la hace visible con un único ``rename``.

    Quien lee nunca ve una etapa a medias: o existe el directorio con los dos
    ficheros y su ``meta.json``, o no existe.
    """
    from .gc_entry import _write
    tmp = out_root / f".{stage}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    for name, value in files.items():
        _write(tmp / name, value)
    _write(tmp / "meta.json", meta)
    os.replace(tmp, out_root / stage)


def best_stage(out_root: Path) -> Path | None:
    for stage in STAGES:
        if (out_root / stage / "meta.json").is_file():
            return out_root / stage
    return None


def run_fallback_only(input_dir: Path, out_root: Path):
    """Etapa 0: el respaldo del runner. Devuelve lo que ``run`` necesita después."""
    started = time.monotonic()
    out_root.mkdir(parents=True, exist_ok=True)
    task = detect_task(input_dir)
    runner = importlib.import_module(f"version_final_reto.task_{task}.agent.run_task{task}")
    case = read_case(task, input_dir)
    payload, event = runner.fallback_case(case)
    publish(out_root, STAGE_FALLBACK, gc_files(task, runner, payload, event),
            {"stage": STAGE_FALLBACK, "seconds": round(time.monotonic() - started, 2)})
    return task, runner, case


def run(input_dir: Path, out_root: Path) -> int:
    started = time.monotonic()
    task, runner, case = run_fallback_only(input_dir, out_root)
    record = {"kind": "gc_shadow", "task": task, "case_id": case.case_id,
              "fallback_seconds": round(time.monotonic() - started, 2)}

    try:
        with tempfile.TemporaryDirectory(prefix="chimera-shadow-", dir=os.environ.get("CHIMERA_TMP", "/tmp")) as tmp:
            staged = stage_inputs(task, case, Path(tmp))
            payload, event = BUILDERS[task](case, staged)
        publish(out_root, STAGE_EXPERTS, gc_files(task, runner, payload, event),
                {"stage": STAGE_EXPERTS, "seconds": round(time.monotonic() - started, 2)})
        record["experts_seconds"] = round(time.monotonic() - started, 2)
    except Exception as exc:  # noqa: BLE001 — la etapa 0 ya está en disco
        log.exception("La sombra no pudo calcular la decisión de los expertos")
        record["experts_error"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(record), file=sys.stderr, flush=True)
    return 0 if "experts_seconds" in record else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", default=os.environ.get("CHIMERA_INPUT_PATH", "/input"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    return run(Path(args.input), Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
