"""Aceptación de 5.2: reglas auditables y orden conservado sin invocar al juez."""
import ast
import itertools
from pathlib import Path

import numpy as np
import pytest

from delete_final_versions_task.common.chimera_experts import dataset_task3 as ds
from delete_final_versions_task.common.chimera_experts import features_surgical as surgical
from delete_final_versions_task.common.chimera_experts.io import Case, load_case, load_cases
from delete_final_versions_task.common.chimera_experts.survival import (
    CoxPH, bootstrap_ci, c_index, monotone_calibrate,
)

ROOT = Path(__file__).resolve().parents[3]
OFFICIAL = Path.home() / 'PycharmProjects/CHIMERA-agent-eval/evaluation/evaluate.py'


@pytest.fixture(scope='module')
def cases():
    return load_cases(ROOT / 'data/task3', task=3)


def test_capra_t3_001(cases):
    case = next(c for c in cases if c.case_id == 'T3-001')
    f = surgical.extract(case.clinical)
    assert case.prompt['psa'] == 86
    assert (f['prim'], f['sec'], f['epe'], f['svi'], f['margins'], f['ln']) == (4, 3, 1, 1, 1, 1)
    assert surgical.capra_s(86, f) == {'score': 11, 'group': 'alto', 'ln_unknown': 0}


def test_parse_all_75(cases):
    assert len(cases) == 75
    rows = [surgical.extract(c.clinical) for c in cases]
    assert sum(f['ln_unknown'] for f in rows) == 43
    for f in rows:
        for key in ('prim', 'sec', 'isup_rp', 'pt', 'epe', 'margins', 'svi', 'lvi'):
            assert np.isfinite(f[key]), key
        assert np.isnan(f['ln']) == bool(f['ln_unknown'])


def test_missing_negative_and_pnx():
    empty = surgical.extract({})
    assert all(np.isnan(v) for v in empty.values())
    f = surgical.extract({'surgical_pathology_report': 'Gleason 3+3. ISUP grade group 1. pathological stage pT2. no extraprostatic extension; surgical margins were negative; seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.',
                          'pathology_report': 'Gleason pattern and ISUP report missing'})
    assert f['epe'] == f['margins'] == f['svi'] == f['lvi'] == 0
    assert np.isnan(f['ln']) and f['ln_unknown'] == 1
    assert np.isnan(f['upgrade_bx_to_rp'])
    assert surgical.capra_s(6, f)['score'] == 0
    assert surgical.capra_s(6, f)['ln_unknown'] == 1
    for psa, expected in [(6, 0), (6.1, 1), (10, 1), (10.1, 2), (20, 2), (20.1, 3)]:
        assert surgical.capra_s(psa, f)['score'] == expected
    for prim, sec, expected in [(3, 3, 0), (3, 4, 1), (4, 3, 2), (4, 4, 3), (4, 5, 3), (5, 5, 3)]:
        assert surgical.capra_s(0, dict(f, prim=prim, sec=sec))['score'] == expected
    assert surgical.extract({'surgical_pathology_report': 'with tertiary pattern 4'})['tertiary_pattern_5'] == 0
    assert surgical.extract({'surgical_pathology_report': 'with tertiary pattern 5'})['tertiary_pattern_5'] == 1


def test_matches_official_concordance():
    # Compila literalmente la función oficial aislada: no importa deepeval ni
    # inicia servicios del juez. Si falta el evaluador, este test falla.
    tree = ast.parse(OFFICIAL.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'concordance_index')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(OFFICIAL), 'exec'), namespace)
    official = namespace['concordance_index']
    rng = np.random.default_rng(52)
    t, pred, e = rng.integers(1, 30, 75), rng.integers(1, 20, 75), rng.integers(0, 2, 75)
    assert c_index(t, pred, e) == official(t, pred, e)
    assert c_index(t, pred, np.zeros(75)) is official(t, pred, np.zeros(75)) is None


def test_calibration_preserves_exact_concordance(cases):
    t, e = ds.build_labels(cases)
    risk = np.random.default_rng(52).integers(0, 20, len(t)).astype(float)
    calibrate = monotone_calibrate(risk, t, e)
    grid = np.unique(np.r_[-10, risk, 40, 100])
    assert np.all(np.diff(calibrate(grid)) < 0)
    assert c_index(t, -risk, e) == c_index(t, calibrate(risk), e)
    assert calibrate([3, 3])[0] == calibrate([3, 3])[1]


def test_calibration_censoring_and_exact_loss():
    r, t, e = np.array([0., 1., 2.]), np.array([30., 8., 20.]), np.array([0, 1, 1])
    def loss(pred):
        error = np.where(e, abs(pred-t), np.maximum(t-pred, 0))
        return np.minimum(error/np.maximum(t, 1), 1).sum()
    levels = np.unique(np.r_[0, t, 2*t])
    optimum = min(loss(np.array(p)) for p in itertools.product(levels, repeat=3) if p[0] >= p[1] >= p[2])
    pred = monotone_calibrate(r, t, e)(r)
    assert loss(pred) == pytest.approx(optimum, abs=1e-7)
    # Con riesgos iguales y mayoría censurada, una media daría menos de 100.
    assert monotone_calibrate([1, 1, 1], [100, 100, 10], [0, 0, 1])([1])[0] >= 100
    single = monotone_calibrate([1], [10], [0])
    assert np.all(np.diff(single([-1, 0, 1, 2, 3])) < 0)


def test_cox_breslow_and_elastic_net():
    X = np.zeros((4, 1))
    model = CoxPH().fit(X, [1, 1, 2, 3], [1, 1, 1, 0])
    times, survival = model.baseline_survival()
    np.testing.assert_array_equal(times, [1, 2])
    np.testing.assert_allclose(survival, np.exp(-np.array([2/4, 2/4+1/2])))
    np.testing.assert_array_equal(model.risk(X), np.ones(4))
    X = np.arange(12.)[:, None]
    for ratio in (0, 0.5, 1):
        model = CoxPH(alpha=0.01, l1_ratio=ratio).fit(X, np.arange(12, 0, -1), np.ones(12))
        assert model.beta[0] > 0
        assert c_index(np.arange(12, 0, -1), -model.risk(X), np.ones(12)) == 1
    sparse = CoxPH(alpha=100, l1_ratio=1).fit(X, np.arange(12, 0, -1), np.ones(12))
    np.testing.assert_allclose(sparse.beta, 0, atol=1e-10)
    with pytest.raises(ValueError):
        CoxPH().fit(X, np.arange(12), np.zeros(12))


def test_dataset_sources_labels_and_pruning(cases):
    X, names = ds.build_matrix(cases, 'ASGDE', drop_constant=False)
    assert X.shape == (75, len(names))
    for tag, (source, dim) in ds.SOURCES.items():
        columns = [names.index(f'emb_{tag}_{j:04d}') for j in range(dim)]
        for i, case in enumerate(cases):
            if case.embeddings.get(source):
                np.testing.assert_allclose(X[i, columns], np.mean(case.embeddings[source], axis=0))
            else:
                assert np.isnan(X[i, columns]).all()
    assert np.isnan(X[:, names.index('dre_suspicious')]).sum() == 23
    assert np.isnan(X[:, names.index('active_treatment_prior_to_surgery')]).sum() == 73
    assert X[0, names.index('bx_isup')] == 4
    assert X[0, names.index('upgrade_bx_to_rp')] == -1
    np.testing.assert_allclose(
        X[0, [names.index(k) for k in ('rad_volume', 'rad_psad', 'rad_pirads', 'rad_cspca')]],
        [37.29, 2.306, 5, 0.9527162],
    )
    assert sum(bool(c.embeddings.get('Biopsy slide')) for c in cases) == 51
    reduced, kept = ds.build_matrix(cases, 'ASGDE')
    for j, name in enumerate(kept):
        np.testing.assert_array_equal(reduced[:, j], X[:, names.index(name)])
        assert np.isfinite(reduced[:, j]).sum() >= 6
        assert np.nanstd(reduced[:, j]) > 1e-12
    assert 'active_treatment_prior_to_surgery' not in kept
    t, e = ds.build_labels(cases)
    assert t.shape == e.shape == (75,)
    assert e.sum() == 19
    assert ds.completeness_vector([Case('empty', 3)])[0] == 0
    assert np.all((ds.completeness_vector(cases) > 0) & (ds.completeness_vector(cases) <= 1))


def test_io_backward_compatibility(tmp_path):
    import json
    from delete_final_versions_task.common.chimera_experts.io import DECISION_FILENAME
    for task, label in [(1, 'yes'), (2, 'active_treatment'), (3, {'months_to_recurrence': 12., 'event': 0})]:
        gt = tmp_path / str(task) / 'ground_truth' / 'case'
        gt.mkdir(parents=True)
        (gt / DECISION_FILENAME[task]).write_text(json.dumps(label))
        assert load_case(tmp_path / str(task), 'case', task).label == label


def test_bootstrap_paired_reproducible():
    x = np.arange(20)
    assert bootstrap_ci(lambda a, b: np.mean(b-a), x, x+3, n=50) == (3, 3)
    assert bootstrap_ci(np.mean, x, n=50) == bootstrap_ci(np.mean, x, n=50)
    assert all(np.isnan(bootstrap_ci(lambda a: None, x, n=5)))
