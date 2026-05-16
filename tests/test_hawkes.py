import numpy as np

from mesa.hawkes import (
    HawkesParams,
    ogata_binned_counts,
    ogata_counts,
    simulate_discrete_hawkes,
    simulate_ogata_hawkes,
    stationary_intensity,
)


def test_stationary_intensity_positive():
    gamma = np.array([[0.2, 0.1], [0.1, 0.2]])
    mu = np.array([0.5, 0.7])
    lam = stationary_intensity(mu, gamma)
    assert np.all(lam > 0)


def test_simulator_shape_and_nonnegative_counts():
    gamma = np.array([[0.2, 0.1], [0.1, 0.2]])
    mu = np.array([0.5, 0.7])
    params = HawkesParams(mu=mu, gamma=gamma, horizon=1.0, dt=0.05)
    out = simulate_discrete_hawkes(params, n_paths=8, seed=5)
    assert out["counts"].shape == (8, 20, 2)
    assert np.all(out["counts"] >= 0)


def test_ogata_path_is_ordered_and_marked():
    gamma = np.array([[0.1, 0.02], [0.03, 0.1]])
    mu = np.array([0.8, 0.6])
    params = HawkesParams(mu=mu, gamma=gamma, horizon=3.0, dt=0.05)
    out = simulate_ogata_hawkes(params, seed=11)
    assert np.all(np.diff(out["times"]) > 0)
    assert np.all((out["marks"] >= 0) & (out["marks"] < 2))


def test_ogata_counts_shape():
    gamma = np.array([[0.05]])
    mu = np.array([0.8])
    params = HawkesParams(mu=mu, gamma=gamma, horizon=2.0, dt=0.05)
    counts = ogata_counts(params, n_paths=4, seed=12)
    assert counts.shape == (4, 1)
    assert np.all(counts >= 0)


def test_ogata_binned_counts_shape_and_nonnegative():
    gamma = np.array([[0.1, 0.05], [0.05, 0.1]])
    mu = np.array([0.5, 0.4])
    params = HawkesParams(mu=mu, gamma=gamma, beta=2.0, horizon=2.0, dt=0.1)
    counts = ogata_binned_counts(params, n_paths=2, seed=11)
    assert counts.shape == (2, params.steps, 2)
    assert np.issubdtype(counts.dtype, np.integer)
    assert np.all(counts >= 0)
