"""Controles del protocolo de medida, no de las soluciones clínicas."""
import numpy as np
import pytest

from version_final_reto.common.analysis.measure_forms import (
    measure_cell, posterior, sign_test,
)
from version_final_reto.common.chimera_experts.reasoning_task2 import _pipeline


@pytest.mark.parametrize("classes", [2, 3, 4])
def test_numpy_heads_match_existing_model(classes):
    rng = np.random.default_rng(18)
    X = rng.normal(size=(60, 5))
    X[::7, 2] = np.nan
    y = np.arange(60) % classes
    expected = _pipeline().fit(X, y).predict_proba(X[:4])
    actual = posterior(X, y, X[:4])
    np.testing.assert_allclose(actual[:, :classes], expected, atol=3e-4)
    np.testing.assert_allclose(actual.sum(1), 1.)
    assert np.all(actual[:, classes:] == 0)


def test_held_out_label_cannot_change_posterior_or_arbitration():
    X = np.arange(16, dtype=float).reshape(8, 2)
    X[0, 0] = np.nan
    y = np.array([0, 1, 2, 0, 1, 2, 0, 1])
    before = measure_cell((X, y))
    y[0] = 3
    after = measure_cell((X, y))
    for first, second in zip(before, after):
        np.testing.assert_allclose(first[0], second[0], atol=1e-12)


def test_prediction_does_not_fit_imputer_on_test_batch():
    X = np.array([[1., 3.], [2., np.nan], [4., 1.], [7., 2.]])
    y = np.array([0, 0, 1, 1])
    target = np.array([[np.nan, 1.]])
    alone = posterior(X, y, target)
    batch = posterior(X, y, np.vstack([target, [1e9, -1e9]]))
    np.testing.assert_allclose(alone[0], batch[0], atol=1e-12)


def test_sign_test_exact_and_ties():
    result = sign_test([1, 1, 1, 0.5], [0, 0, 0, 0.5])
    assert result == {"delta": .75, "n_sube": 3, "n_baja": 0, "n_empata": 1, "p": .25}
    assert sign_test([1], [1])["p"] == 1.


def test_single_training_class_has_no_invented_probability():
    actual = posterior(np.zeros((3, 2)), np.array([2, 2, 2]), np.ones((2, 2)))
    np.testing.assert_array_equal(actual, [[0, 0, 1, 0], [0, 0, 1, 0]])
