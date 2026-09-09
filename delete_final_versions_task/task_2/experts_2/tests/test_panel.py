import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from delete_final_versions_task.task_2.experts_2 import panel as p
from delete_final_versions_task.task_2.experts_2.verify import compare, isup_loo


class Model:
    def __init__(self):
        self.calls = []

    def probability_tensor(self, X):
        self.calls.append(X.copy())
        return np.tile([0.8, 0.1, 0.08, 0.02], (len(X), 1, 1, 1))


def live():
    model = Model()
    bundles = {name: dict(model=model, blocks='G', feature_names=['bx_isup', 'absent'],
                         loo_accuracy=0.8611) for name in p.EXPERTS}
    bundles['expert_five']['ladder_protocol'] = 'repeated_stratified_cv_4x2'
    reasoning = SimpleNamespace(weight_mode={v: 'important' for v in p.TASK2_VARIABLES},
                                confidence_mode='clear')
    return dict(bundles=bundles, reasoning=reasoning, projector=None), model


def test_alignment_preserves_missing_and_order():
    case = p.io.Case('new', 2, prompt={'bx_isup': 3})
    X = p.align(case, {'blocks': 'G', 'feature_names': ['missing', 'bx_isup']}, None)
    assert X.shape == (1, 2)
    assert np.isnan(X[0, 0]) and X[0, 1] == 3


def test_live_without_cache_and_no_rescoring(tmp_path, monkeypatch):
    models, model = live()
    monkeypatch.setattr(p, '_live_models', lambda: models)
    panel = p.Panel(tmp_path / 'absent.json')
    assert panel.ensure('unseen', {'prompt': {'bx_isup': 2}})
    assert len(model.calls) == 5
    assert not panel.ensure('unseen', {})
    assert len(model.calls) == 5
    row = panel.verdicts('unseen')
    assert row['spokesperson']['expert'] not in p.REPLICAS
    assert row['trace']['confidence'] == 'clear'
    for name, expert in row['experts'].items():
        assert expert['available']
        assert set(expert['variable_weights']) == set(p.TASK2_VARIABLES)
        assert 'VARIABLES I WEIGHED' in expert['turn']
        assert expert['turn'].splitlines()[-1].startswith('CONFIDENCE: clear')
        assert expert['replica_of'] == p.REPLICAS.get(name)
    assert row['experts']['expert_five']['ladder_protocol'] == 'repeated_stratified_cv_4x2'
    with pytest.raises(ValueError, match='deployed'):
        panel.verdicts('unseen', 'honest')


def test_batch_equivalent_to_live_and_grade_gate(tmp_path, monkeypatch):
    models, model = live()
    cases = [p.io.Case('graded', 2, prompt={'bx_isup': 2}), p.io.Case('missing', 2)]
    monkeypatch.setattr(p, '_live_models', lambda: models)
    monkeypatch.setattr(p.io, 'load_cases', lambda *a, **k: cases)
    out = tmp_path / 'cache.json'
    batch = p.build_cache(tmp_path, out)['cases']
    assert len(model.calls) == 5
    assert all(X.shape == (2, 2) for X in model.calls)
    for case in cases:
        assert p.run_case(case, **models)[0] == batch[case.case_id]
    assert not set(p.GATED_VARIABLES) & batch['missing']['trace']['variable_weights'].keys()
    assert p.Panel(out).has('graded')


def test_verification_does_not_accept_missing_or_changed_metrics():
    assert not compare(None, 0.8611)['passed']
    assert not compare(0.862, 0.8611)['passed']
    assert compare(62 / 72, 0.8611)['passed']
    cases = [p.io.Case(str(i), 2, prompt={'bx_isup': 1}) for i in range(3)]
    # Holding out either majority observation leaves a tie, won by class 0.
    assert isup_loo(cases, np.array([0, 1, 1])).tolist() == [1, 0, 0]
