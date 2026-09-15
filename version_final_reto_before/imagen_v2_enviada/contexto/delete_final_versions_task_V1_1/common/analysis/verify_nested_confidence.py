"""Audit real 10x9 artifacts, including exact partitions and deliberate leakage."""
import copy
import json
import math
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold
from ..chimera_experts.io import load_cases
from .measure_forms import _check_evidence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL = 'nested_stratified_cv_10x9'


def main():
    evidence = json.loads((HERE / 'nested_confidence_input.json').read_text())
    report = json.loads((HERE / 'forms_report.json').read_text())
    summary = {'protocol': PROTOCOL, 'tasks': {}, 'wall_seconds': evidence['metadata']['wall_seconds'],
               'workers': evidence['metadata']['workers']}
    for task, expected in ((1, 91), (2, 72)):
        cases = [c for c in load_cases(ROOT / f'data/task{task}', task, labelled_only=True) if c.reasoning]
        ids = np.array([c.case_id for c in cases])
        y = np.array([c.label for c in cases])
        rows = evidence[f'task{task}']
        by_id = {r['case_id']: r for r in rows}
        assert len(rows) == len(by_id) == expected
        _check_evidence(rows, set(ids))
        for tr, te in StratifiedKFold(10, shuffle=True, random_state=0).split(ids, y):
            inner_trains = {}
            for itr, ite in StratifiedKFold(9).split(ids[tr], y[tr]):
                for j in tr[ite]:
                    inner_trains[ids[j]] = set(ids[tr[itr]])
            for j in te:
                row = by_id[ids[j]]
                assert set(row['training_case_ids']) == set(ids[tr])
                assert len(row['calibration']) == len(tr)
                assert {c['case_id'] for c in row['calibration']} == set(ids[tr])
                for c in row['calibration']:
                    assert set(c['training_case_ids']) == inner_trains[c['case_id']]
                for r in [row, *row['calibration']]:
                    assert r['protocol'] == PROTOCOL
                    assert not any(word in r['provenance'].lower() for word in ('loo', 'honest', 'leave_one_out'))
                    assert all(math.isfinite(v) and v >= 0 for v in r['budget'].values())
                    if task == 2 and r['rung'] == 'fit':
                        assert r['agreement'] != 'clear'
        leaked = copy.deepcopy(rows[0])
        leaked['calibration'][0]['training_case_ids'].append(leaked['case_id'])
        try:
            _check_evidence([leaked], set(ids))
        except ValueError as exc:
            assert 'fuga del caso exterior' in str(exc)
        else:
            raise AssertionError('Validator accepted external leakage')
        result = report['tareas'][f'task{task}']['A']
        assert result['estado'] == 'medido' and result['protocolo'] == PROTOCOL
        policies = result['confidence_score']['politicas']
        for name in ('agreement', 'confidence_from_rung'):
            assert math.isfinite(policies[name]['metrica'])
            assert policies[name]['protocolo'] == PROTOCOL
        rung = policies['confidence_from_rung']
        assert rung['adoptar'] == (rung['delta'] > 1e-12 and rung['contraste_politica_actual']['delta'] > 1e-12)
        fit = [a for a in result['calibracion'] if by_id[a['case_id']]['rung'] == 'fit']
        assert all(a['confidence'] == 'uncertain' for a in fit)
        summary['tasks'][f'task{task}'] = {'n': len(rows), 'exact_splits_verified': True,
            'injected_external_leak_raises_ValueError': True, 'fit_cases': len(fit),
            'fit_clear': sum(a['confidence'] == 'clear' for a in fit),
            'policies': {name: {k: v for k, v in p.items() if k != 'scores_por_caso'} for name, p in policies.items()}}
    assert report['aceptacion_completa']
    (HERE / 'nested_confidence_verification.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
