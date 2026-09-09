"""Audita los artefactos de 4.3, sin GPU ni juez.

Uso: PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.task_2.analysis.accept_run
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from delete_final_versions_task.common.guards import validate_output
from delete_final_versions_task.task_2.agent.paths import DATA, RUNS


def main():
    report = {'splits': {}, 'errors': [], 'sha256': {}}
    labeled = {p.name for p in (DATA / 'ground_truth').iterdir() if p.is_dir()}
    all_ids = {p.name for p in (DATA / 'agent_input').iterdir()
               if (p / 'structured-prompt.json').exists()}
    for split, expected in [('labeled', labeled), ('unlabeled', all_ids - labeled)]:
        root = RUNS / split
        stats = Counter(expected=len(expected))
        summary = [json.loads(s) for s in (root / 'summary.jsonl').read_text().splitlines()] if (root / 'summary.jsonl').exists() else []
        telemetry = [json.loads(s) for s in (root / 'telemetry.jsonl').read_text().splitlines()] if (root / 'telemetry.jsonl').exists() else []
        counts = Counter(r['case_id'] for r in summary)
        telemetry_ids = {r.get('case_id') for r in telemetry}
        stats['summary_rows'] = len(summary)
        stats['failed_summary_rows'] = sum(not r.get('ok') for r in summary)
        stats['verifier_not_ready'] = sum(r.get('verifier_ready') is not True for r in summary)
        stats['no_documents_opened'] = sum(not r.get('documents_opened') for r in summary)
        stats['telemetry_rows'] = len(telemetry)
        for cid in sorted(expected):
            try:
                out = root / 'output' / 'task2' / cid
                d = out / 'prostate-treatment-decision.json'
                r = out / 'prostate-treatment-decision-reasoning.json'
                action, reasoning = json.loads(d.read_text()), json.loads(r.read_text())
                stats['outputs'] += 1
                structured = dict(case_id=cid, task=2, action=action,
                                  reasoning=reasoning['free_text'],
                                  **{k: reasoning[k] for k in ('confidence', 'variable_weights', 'reveal_sequence')})
                valid, why = validate_output(2, structured)
                if not valid:
                    raise ValueError(why)
                stats['schema_valid'] += 1
                assert reasoning['confidence'] == 'clear', 'confidence'
                assert reasoning['reveal_sequence'] == [], 'reveal_sequence'
                stats['policy_valid'] += 1
                board = root / 'boards' / (cid + '.json')
                markdown = root / 'boards' / (cid + '.md')
                assert json.loads(board.read_text()), 'empty board'
                assert markdown.read_text().strip(), 'empty markdown'
                stats['boards_complete'] += 1
                assert counts[cid] == 1, f'summary count {counts[cid]}'
                assert cid in telemetry_ids, 'missing telemetry'
                stats['telemetry_cases'] += 1
                for path in (d, r, board, markdown):
                    report['sha256'][str(path.relative_to(RUNS))] = hashlib.sha256(path.read_bytes()).hexdigest()
            except Exception as exc:
                report['errors'].append({'case_id': cid, 'error': str(exc)})
        actual = {p.name for p in (root / 'output' / 'task2').iterdir()} if (root / 'output' / 'task2').exists() else set()
        if actual != expected:
            report['errors'].append({'split': split, 'missing': sorted(expected-actual), 'extra': sorted(actual-expected)})
        report['splits'][split] = dict(stats)
    report['artifacts_complete'] = not report['errors'] and all(not s['failed_summary_rows'] for s in report['splits'].values())
    report['accepted'] = report['artifacts_complete'] and all(not s['verifier_not_ready'] for s in report['splits'].values())
    (RUNS / 'acceptance_4_3.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k:v for k,v in report.items() if k != 'sha256'}, indent=2))
    raise SystemExit(0 if report['accepted'] else 1)


if __name__ == '__main__':
    main()
