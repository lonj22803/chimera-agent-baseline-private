"""Audita los 75 artefactos de T3 y la invariancia global del orden."""
import hashlib
import json
from pathlib import Path

import numpy as np

from delete_final_versions_task_V1.common.guards import validate_output
from delete_final_versions_task_V1.task_3.agent.decide import DECISION, REASONING
from delete_final_versions_task_V1.task_3.agent.protocol import BASE


def main():
    root = BASE / 'runs/labeled'
    report_dir = BASE / 'experts_3/train/artifacts'
    order = json.loads((report_dir / 'expert_one_report.json').read_text())
    horizon = json.loads((report_dir / 'expert_five_report.json').read_text())
    summary = [json.loads(line) for line in (root / 'summary.jsonl').read_text().splitlines()]
    telemetry = [json.loads(line) for line in (root / 'telemetry.jsonl').read_text().splitlines()]
    errors, hashes = [], {}
    months, risk = [], []
    counts = dict(outputs=0, schema_valid=0, boards_complete=0, with_actual_documents=0,
                  no_nodal_sampling=0, fallback_notes=sum(bool(r['fallback']) for r in summary))
    expected = set(horizon['case_ids'])
    for name, rows in [('summary', summary), ('telemetry', telemetry)]:
        if len(rows) != 75 or {r['case_id'] for r in rows} != expected:
            errors.append(f'{name}: cohort mismatch')
    if {p.name for p in (root/'output/task3').iterdir() if p.is_dir()} != expected:
        errors.append('Output cohort mismatch')
    for i, cid in enumerate(horizon['case_ids']):
        folder = root/'output/task3'/cid
        try:
            for name in (DECISION, REASONING, 'acta.json', 'acta.md'):
                hashes[str((folder/name).relative_to(BASE))] = hashlib.sha256((folder/name).read_bytes()).hexdigest()
            dec = json.loads((folder/DECISION).read_text())
            note = json.loads((folder/REASONING).read_text())
            assert isinstance(note, str) and dec['event'] in (0, 1)
            assert np.isfinite(dec['months_to_recurrence'])
            assert validate_output(3, {'case_id': cid, 'task': 3, 'reasoning': note,
                                      'months_to_recurrence': dec['months_to_recurrence']})[0]
            counts['outputs'] += 1
            counts['schema_valid'] += 1
            assert dec['months_to_recurrence'] == horizon['months'][i]
            assert dec['event'] == horizon['event_oof'][i]
            board = json.loads((folder/'acta.json').read_text())
            assert len(board['interventions']) == 11
            counts['boards_complete'] += 1
            rows = {r['speaker']: r['data'] for r in board['interventions']}
            assert any(rows['REGISTRAR']['documents'].values())
            counts['with_actual_documents'] += 1
            counts['no_nodal_sampling'] += rows['EXPERT-CAPRA']['ln_unknown'] == 1
            months.append(dec['months_to_recurrence'])
            risk.append(order['score'][order['case_ids'].index(cid)])
        except (OSError, ValueError, KeyError, AssertionError) as exc:
            errors.append(f'{cid}: {type(exc).__name__}: {exc}')
    if len(months) == 75:
        r, m = np.array(risk), np.array(months)
        if not np.array_equal(np.sign(r[:, None]-r), -np.sign(m[:, None]-m)):
            errors.append('Order or ties changed')
    scores = json.loads((BASE/'runs/score_no_judge.json').read_text())['task3']
    if not (scores['ranking_score'] == order['metrics']['c_index'] == horizon['metrics']['c_index']):
        errors.append('c-index mismatch')
    judge_path = BASE/'runs/judge/entrega.json'
    judge_ok = False
    if judge_path.exists():
        judge = json.loads(judge_path.read_text())
        judged = judge.get('rows', [])
        judge_ok = (len(judged) == 75 and {r['case_id'] for r in judged} == expected
                    and all(isinstance(r.get('rationale_score'), (int, float))
                            and np.isfinite(r['rationale_score']) for r in judged)
                    and judge['aggregate']['ranking_score'] == scores['ranking_score'])
        if not judge_ok:
            errors.append('Judge artifact incomplete or inconsistent')
    result = {'counts': counts, 'c_index_before': order['metrics']['c_index'],
              'c_index_after': scores['ranking_score'], 'errors': errors,
              'artifacts_accepted': not errors, 'judge_accepted': judge_ok,
              'sha256': hashes}
    (BASE/'runs/acceptance_6_2.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'sha256'}, indent=2))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
