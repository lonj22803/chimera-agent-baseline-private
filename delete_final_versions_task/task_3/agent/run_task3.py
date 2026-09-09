"""Corrida T3 con predicciones OOF ya medidas; no reentrena ni consulta etiquetas."""
from __future__ import annotations
import argparse
import json
import resource
import time
from pathlib import Path
from delete_final_versions_task.common.chimera_experts.io import (
    Case, CLINICAL_FILENAME, FEATURES_FILENAME,
)
from .decide import to_gc_outputs
from .graph import create_conference_graph, OllamaChair, dump
from .protocol import BASE, Panel

ROOT = BASE.parents[1]

def load_inputs(data):
    def read(path):
        return json.loads(path.read_text()) if path.exists() else {}
    for path in sorted((data / 'agent_input').iterdir()):
        if path.is_dir():
            yield Case(path.name, 3, prompt=read(path/'structured-prompt.json'),
                       clinical=read(path/CLINICAL_FILENAME[3]), embeddings=read(path/FEATURES_FILENAME))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=ROOT/'data/task3')
    parser.add_argument('--out-root', type=Path, default=BASE/'runs/labeled')
    parser.add_argument('--mode', choices=['oof', 'deployed'], default='oof')
    parser.add_argument('--model', default='gemma4:e4b')
    parser.add_argument('--ollama-url', default='http://localhost:11434')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if (args.out_root/'summary.jsonl').exists():
        parser.error('output already contains a run; choose a fresh --out-root')
    panel = Panel(args.mode)
    graph = create_conference_graph(panel, OllamaChair(args.ollama_url, args.model))
    args.out_root.mkdir(parents=True, exist_ok=True)
    (args.out_root/'manifest.json').write_text(dump({'mode': args.mode, 'temperature': 0,
        'model': args.model, 'expert_sha256': panel.hashes, 'labels_read': False,
        'limitation': 'OOF cache replay for measured cohort, not an independent external validation'}))
    cases = list(load_inputs(args.data_root))
    if args.limit:
        cases = cases[:args.limit]
    for i, case in enumerate(cases, 1):
        start = time.monotonic()
        result = graph.invoke(case)
        destination = args.out_root/'output/task3'/case.case_id
        destination.mkdir(parents=True, exist_ok=True)
        for name, value in to_gc_outputs(result['payload'], result['event']).items():
            (destination/name).write_text(dump(value)+'\n')
        (destination/'acta.json').write_text(dump(result['board'].to_dict())+'\n')
        (destination/'acta.md').write_text(result['board'].to_markdown())
        summary = {k: result[k] for k in ('risk', 'event', 'fallback', 'opened', 'mode', 'uncertainty')}
        summary.update(result['payload'])
        with (args.out_root/'summary.jsonl').open('a') as stream:
            stream.write(dump(summary)+'\n')
        telemetry = {'case_id': case.case_id, 'calls': result['calls'], 'seconds': time.monotonic()-start,
                     'host_peak_rss_mb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                     'vram_mb': None, 'fallback': result['fallback']}
        with (args.out_root/'telemetry.jsonl').open('a') as stream:
            stream.write(dump(telemetry)+'\n')
        print(f'{i}/{len(cases)} {case.case_id}: {summary["months_to_recurrence"]:.6f} months '
              f'event={result["event"]} fallback={result["fallback"]}', flush=True)

async def run_case(case, input_dir, model, tools, step_timeout):
    """Mismo panel desplegado y grafo; presidente local sin depender de Ollama."""
    from langchain_core.messages import HumanMessage

    def chair(prompt):
        response = model.invoke([HumanMessage(content=prompt)])
        content = response.content
        if not isinstance(content, str):
            content = " ".join(block.get("text", "") for block in content if isinstance(block, dict))
        return content, {"role": "CHAIR", "temperature": 0, "backend": "local"}

    result = create_conference_graph(Panel("deployed"), chair).invoke(case)
    return result["payload"], result["event"]


def fallback_case(case):
    from . import decide, protocol
    from delete_final_versions_task.common.chimera_experts import dataset_task3 as ds
    try:
        findings = ds._surgical(case)
        horizon = Panel("deployed").horizon(case, findings["capra_s"])
        band = protocol.uncertainty(horizon["months_to_recurrence"],
                                    findings.get("ln_unknown") == 1, 4)
        payload = decide.finish(case.case_id, horizon, decide.fallback_note(case, findings), band)
        return payload, horizon["event"]
    except Exception:
        # Último recurso técnico si faltan incluso los artefactos del experto.
        # No se presenta como una predicción de EXPERT-HORIZON.
        return {"case_id": case.case_id, "task": 3, "months_to_recurrence": 60.0,
                "reasoning": "The prognostic estimate is unavailable. This default follow-up horizon "
                             "without an event is not a known recurrence date or an individualized prediction."}, 0


if __name__ == '__main__':
    main()
