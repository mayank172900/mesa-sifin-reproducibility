import numpy as np

from mesa.control import PolicyParams, mesa_robust_premium, quote_offsets


def test_premium_is_monotone_in_rho_and_epsilon():
    assert mesa_robust_premium(0.02, 0.9) > mesa_robust_premium(0.02, 0.5)
    assert mesa_robust_premium(0.04, 0.8) > mesa_robust_premium(0.02, 0.8)


def test_absolute_gamma_premium_has_extra_critical_factor():
    rho = 0.9
    rel = mesa_robust_premium(0.01, rho, ambiguity="relative_slack")
    absolute = mesa_robust_premium(0.01, rho, ambiguity="absolute_gamma")
    assert np.isclose(absolute / rel, 2.0 / (1.0 - rho))


def test_robust_quotes_are_wider_than_nominal():
    inv = np.array([-2.0, 0.0, 2.0])
    nominal_bid, nominal_ask = quote_offsets(inv, rho_hat=0.85, epsilon=0.02, policy="nominal_hawkes")
    robust_bid, robust_ask = quote_offsets(inv, rho_hat=0.85, epsilon=0.02, policy="robust_gamma")
    assert np.all(robust_bid >= nominal_bid)
    assert np.all(robust_ask >= nominal_ask)


def test_smooth_quote_sensitivity_matches_explicit_derivative():
    params = PolicyParams(max_half_spread=100.0)
    rho = 0.8
    epsilon = 0.01
    h = 1.0e-5

    def half_spread(rho_hat: float) -> float:
        bid, ask = quote_offsets(
            np.array([0.0]),
            rho_hat=rho_hat,
            epsilon=epsilon,
            policy="robust_gamma",
            params=params,
        )
        return float(0.5 * (bid[0] + ask[0]))

    finite_diff = (half_spread(rho + h) - half_spread(rho - h)) / (2.0 * h)
    coeff = params.variance_spread_scale + params.risk_aversion * params.robust_scale * epsilon
    expected = 2.0 * coeff / (1.0 - rho) ** 3
    assert np.isclose(finite_diff, expected, rtol=1e-7, atol=1e-9)
