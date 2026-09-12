"""Corrida T3 con predicciones OOF ya medidas; no reentrena ni consulta etiquetas."""
from __future__ import annotations
import argparse
import json
import resource
import time
from pathlib import Path
from delete_final_versions_task_V1_1.common.chimera_experts.io import (
    Case, CLINICAL_FILENAME, FEATURES_FILENAME,
)
from .decide import to_gc_outputs
from .graph import create_conference_graph, OllamaChair, LocalChair, dump
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
    parser.add_argument('--backend', choices=['ollama', 'vllm'], default='ollama')
    parser.add_argument('--split', choices=['all', 'dev', 'val', 'labeled'], default='all')
    parser.add_argument('--pids', nargs='+')
    parser.add_argument('--mode', choices=['oof', 'deployed'], default='oof')
    parser.add_argument('--model', default='gemma4:e4b')
    parser.add_argument('--ollama-url', default='http://localhost:11434')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if (args.out_root/'summary.jsonl').exists():
        parser.error('output already contains a run; choose a fresh --out-root')
    panel = Panel(args.mode)
    from delete_final_versions_task_V1_1.common.telemetry import ConferenceMeter, device_vram_mb
    meter = ConferenceMeter()
    model_id = args.model
    if args.backend == 'vllm':
        from hydra import compose, initialize_config_dir
        from chimera_agent_baseline.models import load_model
        from delete_final_versions_task_V1_1.common.runtime import configure
        with initialize_config_dir(config_dir=str(ROOT/'configs'), version_base=None):
            cfg = compose(config_name='config', overrides=['+experiment=local_paths'])
        configure(cfg)
        model = load_model(cfg)
        meter.tokenizer = getattr(model, 'tokenizer', None)
        meter.approx = meter.tokenizer is None
        model_id = cfg.model.model_id
        chair = LocalChair(model, meter)
    else:
        chair = OllamaChair(args.ollama_url, args.model)
    graph = create_conference_graph(panel, chair)
    args.out_root.mkdir(parents=True, exist_ok=True)
    (args.out_root/'manifest.json').write_text(dump({'mode': args.mode, 'temperature': 0,
        'model': model_id, 'backend': args.backend, 'split': args.split, 'expert_sha256': panel.hashes, 'labels_read': False,
        'limitation': 'OOF cache replay for measured cohort, not an independent external validation'}))
    cases = list(load_inputs(args.data_root))
    if args.pids:
        cases = [c for c in cases if c.case_id in set(args.pids)]
    elif args.split in ('dev', 'val'):
        ids = set((ROOT/f'dev/splits/task3_{args.split}.txt').read_text().splitlines())
        cases = [c for c in cases if c.case_id in ids]
    if args.limit:
        cases = cases[:args.limit]
    for i, case in enumerate(cases, 1):
        start = time.monotonic()
        meter.start_case(case.case_id)
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
                     'vram_mb': device_vram_mb()[0], 'meter': meter.summary(), 'backend': args.backend, 'fallback': result['fallback']}
        with (args.out_root/'telemetry.jsonl').open('a') as stream:
            stream.write(dump(telemetry)+'\n')
        print(f'{i}/{len(cases)} {case.case_id}: {summary["months_to_recurrence"]:.6f} months '
              f'event={result["event"]} fallback={result["fallback"]}', flush=True)

async def run_case(case, input_dir, model, tools, step_timeout, meter=None):
    import os
    evidence = None
    if os.environ.get('CHIMERA_T3_RAG') == '1':
        from ..experts_3.guideline import retrieve
        evidence = await retrieve(tools, case.case_id)
    result = create_conference_graph(Panel("deployed"), LocalChair(model, meter), evidence).invoke(case)
    return result["payload"], result["event"]


def fallback_case(case):
    from . import decide, protocol
    from delete_final_versions_task_V1_1.common.chimera_experts import dataset_task3 as ds
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
