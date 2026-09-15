import itertools
import math

import numpy as np
import pytest

from version_final_reto.common import uncertainty_forms as u
from version_final_reto.common.chimera_experts import uncertainty as original


def test_reuses_uncertainty():
    for name in ('rubin_pool', 'ladder', 'completeness_score', 'brier_score',
                 'expected_calibration_error', 'ladder_table'):
        assert getattr(u, name) is getattr(original, name)


def test_one_expert_and_units():
    verdict = original.make_verdict(np.array([[.2, .6], [.3, .7]])).to_dict()
    b = u.pool_variance([verdict])
    assert b.panel == 0
    assert b.model == pytest.approx(verdict['epistemic_model'] ** 2)
    assert b.missing == pytest.approx(verdict['epistemic_missing'] ** 2)
    assert b.epistemic == pytest.approx(math.sqrt(b.model + b.missing))


def test_panel_and_absence():
    v = dict(epistemic_model=.1, epistemic_missing=.2, aleatoric=.8)
    b = u.pool_variance([dict(v, p=.2), dict(v, p=.8),
                         dict(v, p=1., abstained=True), dict(v, p=0., available=False), {}, None])
    assert b.panel == pytest.approx(.18)
    assert b.epistemic == pytest.approx(math.sqrt(.01 + .04 + .18))
    assert u.pool_variance([]) == u.VarianceBudget(0, 0, 0, 0)


def test_perfect_rung_and_ceiling():
    b = u.VarianceBudget(1, 1, 1, .9)
    assert u.confidence_from_rung('perfect', b, {'perfect': 1.}, cohort_sigma_q66=.1)[0] == 'clear'
    assert u.confidence_from_rung('weak', b, {'weak': .64}, cohort_sigma_q66=.1)[0] == 'uncertain'
    assert u.confidence_from_rung('weak', b, {'weak': .64})[0] != 'clear'
    assert u.confidence_from_rung('weighted_panel', b, {'weighted_panel': 1.})[0] != 'clear'
    assert u.confidence_from_rung('unknown', b, {})[0] == 'uncertain'


def test_quantile_boundary():
    b = u.VarianceBudget(.04, 0, 0, 1)
    assert u.confidence_from_rung('r', b, {'r': .8}, cohort_sigma_q66=.2)[0] == 'clear'
    assert u.confidence_from_rung('r', b, {'r': .8}, cohort_sigma_q66=.19)[0] == 'borderline'


def test_task2_ceilings():
    assert u.RUNG_CEILING_TASK2 == {
        'cancer': 'clear', 'treat': 'borderline', 'fit': 'uncertain'}
    b = u.VarianceBudget(0, 0, 0, 0)
    for rung, ceiling in u.RUNG_CEILING_TASK2.items():
        assert u.confidence_from_rung(rung, b, {rung: 1.})[0] == ceiling


@pytest.mark.parametrize('acc', [.94, 1.])
@pytest.mark.parametrize('budget', [u.VarianceBudget(0, 0, 0, 0),
                                    u.VarianceBudget(1, 2, 3, 1)])
@pytest.mark.parametrize('q66', [0., math.inf])
def test_fit_ceiling_overrides_high_accuracy(acc, budget, q66):
    # Misma precisión/dispersión en un peldaño sin techo: la diferencia
    # procede del mecanismo de techo, incluso con acierto perfecto.
    assert u.confidence_from_rung('fit', budget, {'fit': acc},
                                  cohort_sigma_q66=q66)[0] == 'uncertain'
    assert u.confidence_from_rung('unrestricted', budget, {'unrestricted': acc},
                                  cohort_sigma_q66=q66)[0] in {'clear', 'borderline'}


def test_arbitration_ties_missing_reports_and_purity():
    learned = {'a': 'important', 'b': 'decisive', 'c': 'not_used'}
    mode = dict.fromkeys(learned, 'noted')
    weights, flags = u.arbitrate_cells(learned, mode, {'a': {'loo': .9, 'moda': .8},
                                                      'b': {'loo': .8, 'moda': .8}})
    assert weights == {'a': 'important', 'b': 'noted', 'c': 'noted'}
    assert flags == {'a': True, 'b': False, 'c': False}
    assert mode == dict.fromkeys(learned, 'noted')


def exact_f1(s, posterior):
    result = 0.
    keys = list(posterior)
    for bits in itertools.product((0, 1), repeat=len(keys)):
        truth = {k for k, bit in zip(keys, bits) if bit}
        probability = math.prod(posterior[k] if bit else 1-posterior[k] for k, bit in zip(keys, bits))
        score = 2 * len(s & truth) / (len(s) + len(truth)) if s or truth else 1.
        result += probability * score
    return result


@pytest.mark.parametrize('posterior', [dict(a=.9, b=.8, c=.1), dict.fromkeys('abcd', .3),
                                       {}, dict(a=0., b=0.), dict(a=1., b=.5), dict(a=.1)])
def test_f1_against_exhaustive_all_subsets(posterior):
    found = u.expected_f1_set(posterior)
    best = max(exact_f1({k for k, b in zip(posterior, bits) if b}, posterior)
               for bits in itertools.product((0, 1), repeat=len(posterior)))
    assert exact_f1(found, posterior) == pytest.approx(best)


def test_f1_examples_and_hand_calculation():
    assert u.expected_f1_set(dict(a=.9, b=.8, c=.1)) == {'a', 'b'}
    p = dict.fromkeys('abcd', .3)
    # K~Binomial(4,.3): E[2K/(4+K)] = .422674..., vacío = .7**4 = .2401.
    hand = sum(math.comb(4, k)*.3**k*.7**(4-k)*2*k/(4+k) for k in range(5))
    assert hand > .7**4
    assert u.expected_f1_set(p) == set('abcd')


def test_grounding():
    w = {'pirads': 'decisive'}
    got, changes = u.project_feasible(w, [], {'pirads': 'radiology_report'}, set(), 'pirads')
    assert got == {'pirads': 'not_used'}
    assert len(changes) == 1
    assert w == {'pirads': 'decisive'}


def test_coherence_and_conflict():
    w = {'a': 'not_used', 'b': 'decisive', 'c': 'decisive'}
    got, _ = u.project_feasible(w, [], {}, {'a'}, 'c')
    assert got == {'a': 'noted', 'b': 'important', 'c': 'decisive'}
    got, changes = u.project_feasible({'a': 'not_used'}, [], {'a': 'closed'}, {'a'}, None)
    assert got['a'] == 'not_used'
    assert 'retirar' in changes[0]
    assert u.project_feasible(got, [], {'a': 'closed'}, set(), None)[1] == []


@pytest.mark.parametrize('p', [-.1, 1.1, float('nan')])
def test_invalid_posterior(p):
    with pytest.raises(ValueError):
        u.expected_f1_set({'a': p})
