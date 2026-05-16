import numpy as np

from mesa.spectral import (
    make_gamma_family,
    spectral_radius,
    variance_amplification,
    worst_case_perron_perturbation,
)


def test_gamma_family_has_requested_radius():
    rng = np.random.default_rng(1)
    gamma = make_gamma_family("rank1", dim=6, rho=0.85, rng=rng)
    assert np.isclose(spectral_radius(gamma), 0.85)


def test_variance_amplification_grows_near_criticality():
    rng = np.random.default_rng(2)
    low = make_gamma_family("block", dim=6, rho=0.5, rng=rng)
    high = make_gamma_family("block", dim=6, rho=0.9, rng=rng)
    assert variance_amplification(high) > variance_amplification(low)


def test_worst_case_perturbation_respects_stability_cap():
    rng = np.random.default_rng(3)
    gamma = make_gamma_family("rank1", dim=4, rho=0.98, rng=rng)
    perturbed = worst_case_perron_perturbation(gamma, epsilon=0.2, rho_max=0.995)
    assert spectral_radius(perturbed) <= 0.995 + 1e-10

