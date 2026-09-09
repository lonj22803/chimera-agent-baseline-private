"""Aceptación ejecutable del protocolo y artefactos exigidos por 5.3."""
import importlib.util
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pytest

TRAIN = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('protocol', TRAIN/'protocol.py')
protocol = importlib.util.module_from_spec(spec)
sys.modules['protocol'] = protocol
spec.loader.exec_module(protocol)


@pytest.fixture(scope='module')
def cohort():
    cases = protocol.load_cases(protocol.ROOT/'data/task3', task=3, labelled_only=True)
    return cases, *protocol.ds.build_labels(cases)


def report(name):
    return json.loads((TRAIN/'artifacts'/f'expert_{name}_report.json').read_text())


@pytest.mark.parametrize('name', ['one', 'two', 'three', 'four', 'five'])
def test_reports_and_models(name, cohort):
    cases, t, e = cohort
    r = report(name)
    assert len(t) == 75 and e.sum() == 19
    assert r['case_ids'] == [c.case_id for c in cases]
    assert r['protocol']['floors'] == protocol.FLOORS
    p = np.asarray(r['months'] if name == 'five' else r['oof_months_order'])
    assert np.isfinite(p).all()
    assert protocol.measure(t, p, e) == r['metrics']
    assert sum(row['n'] for row in r['ladder']['rows']) == 75
    model = pickle.loads((TRAIN.parent/f'expert_{name}'/'model'/f'expert_{name}.joblib').read_bytes())
    if name in ('two', 'three', 'four'):
        assert len(model.beta) <= 5
        assert np.isfinite(model.beta).all()
        for seed in protocol.SEEDS:
            tests = []
            for fold in [f for f in r['folds'] if f['seed'] == seed]:
                assert not set(fold['train']) & set(fold['test'])
                assert len(fold['train']) + len(fold['test']) == 75
                assert fold['coefficients'] <= 5
                assert fold['k'] in (1, 2, 4) and fold['alpha'] in (1., 10.)
                tests.extend(fold['test'])
            assert sorted(tests) == list(range(75))
        if name == 'three':
            assert all(n.startswith('emb_rp_') for n in model.names)


def test_calibrator_preserves_global_order_and_event_fallback(cohort):
    _, t, e = cohort
    a, h = report('one'), report('five')
    risk, months = np.array(a['score']), np.array(h['months'])
    assert np.array_equal(np.sign(risk[:, None]-risk), -np.sign(months[:, None]-months))
    assert h['delta_c_index_pooled'] == 0.0
    assert h['global_order_acceptance']
    assert h['time_score'] == protocol.time_score(t, months, e)
    assert h['event_oof_accuracy'] == np.mean(np.array(h['event_oof']) == e)
    for fold in h['folds']:
        assert not set(fold['train']) & set(fold['test'])
        assert set(risk[fold['train']]).isdisjoint(risk[fold['test']])
    if h['event_oof_accuracy'] <= h['constant_zero_accuracy']:
        assert h['deployed_event'] == 'constant 0'


def test_ablation_has_paired_bootstrap():
    rows = report('four')['ablations']
    assert {r['removed'] for r in rows} == set('ASGDE')
    for row in rows:
        assert len(row['paired_bootstrap_95']) == 2
        assert row['metrics_without']['bootstrap_n'] == 1000


def test_projection_does_not_learn_from_validation():
    train = np.array([[i, 2*i, np.nan] for i in range(12)], float)
    p = protocol.Projection().fit(train, 1)
    before = p.transform(train).copy()
    p.transform(np.array([[1e9, -1e9, 3.]]))
    np.testing.assert_array_equal(p.transform(train), before)
    assert not p.keep[-1]


def test_numpy_cox_matches_existing_breslow_implementation():
    # Reference solver is an existing dependency; production protocol is numpy-only.
    from delete_final_versions_task.common.chimera_experts.survival import CoxPH
    rng = np.random.default_rng(6)
    x = rng.normal(size=(30, 5))
    t = np.arange(1, 31, dtype=float)
    e = np.array([0, 1, 1]*10)
    model = protocol.CoxPipeline().fit(x, t, e, ['a','b','c','d','e'], 4, 1.)
    z = model.transform(x)
    reference = CoxPH(alpha=1.).fit(z, t, e)
    np.testing.assert_allclose(model.beta, reference.beta, atol=1e-6)


def test_official_semantics_with_ties_and_censoring():
    t = np.array([1., 1., 2., 3., 4.])
    e = np.array([1, 0, 1, 0, 1])
    p = np.array([1., 2., 2., 2., 5.])
    assert protocol.concordance(t,p,e) == protocol.METRICS['concordance_index'](t,p,e)


def test_historical_probes_and_paired_ablation_reproducible(cohort):
    cases, t, e = cohort
    probes = json.loads((TRAIN/'artifacts/historical_probes_report.json').read_text())
    assert len(probes) == 5
    ids = [c.case_id for c in cases]
    for probe in probes.values():
        selected = np.array([ids.index(cid) for cid in probe['case_ids']])
        p = np.mean(probe['seed_predictions'], axis=0)
        assert probe['metrics'] == protocol.measure(t[selected], p, e[selected])
    full = report('four')
    p = np.array(full['oof_months_order'])
    for row in full['ablations']:
        other = np.mean(row['seed_predictions'], axis=0)
        assert row['paired_bootstrap_95'] == protocol.interval(t, p, e, other)
