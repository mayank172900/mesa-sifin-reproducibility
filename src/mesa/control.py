"""Robust market-making approximations for MESA experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PolicyParams:
    base_half_spread: float = 0.02
    risk_aversion: float = 0.02
    inventory_skew: float = 0.015
    fill_decay: float = 8.0
    variance_spread_scale: float = 2.0e-6
    robust_scale: float = 5.0e-3
    max_half_spread: float = 1.5


def endogenous_variance_proxy(
    rho: np.ndarray | float,
    base_vol: float = 1.0,
    exponent: float = 2.0,
) -> np.ndarray:
    """Near-critical Hawkes variance proxy.

    The default exponent two corresponds to the normalized-throughput
    square-law used in the theorem repair appendix. If stationary throughput is
    also allowed to diverge, experiments should increase this exponent.
    """
    rho_arr = np.asarray(rho, dtype=float)
    return base_vol / np.maximum(1.0 - rho_arr, 1e-6) ** exponent


def variance_sensitivity_proxy(
    rho: np.ndarray | float,
    base_vol: float = 1.0,
    exponent: float = 2.0,
) -> np.ndarray:
    """Derivative of the critical variance proxy with respect to rho."""
    rho_arr = np.asarray(rho, dtype=float)
    gap = np.maximum(1.0 - rho_arr, 1e-6)
    return exponent * base_vol / gap ** (exponent + 1.0)


def mesa_robust_premium(
    epsilon: np.ndarray | float,
    rho: np.ndarray | float,
    risk_aversion: float = 0.02,
    scale: float = 0.08,
    ambiguity: str = "relative_slack",
    exponent: float = 2.0,
) -> np.ndarray:
    """Structural-uncertainty premium used by the minimal MESA policy.

    ``relative_slack`` is the repaired interpretation under which the headline
    square law is valid: epsilon is a fraction of the remaining distance to
    criticality. ``absolute_gamma`` treats epsilon as an absolute perturbation
    of the branching matrix/Perron root, adding one critical derivative factor.
    """
    eps_arr = np.asarray(epsilon, dtype=float)
    if ambiguity == "relative_slack":
        amplification = endogenous_variance_proxy(rho, exponent=exponent)
    elif ambiguity == "absolute_gamma":
        amplification = variance_sensitivity_proxy(rho, exponent=exponent)
    else:
        raise ValueError(f"unknown ambiguity mode: {ambiguity}")
    return risk_aversion * scale * eps_arr * amplification


def quote_offsets(
    inventory: np.ndarray,
    rho_hat: float,
    epsilon: float,
    policy: str,
    params: PolicyParams | None = None,
    rho_oracle: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return bid/ask half-spread offsets for a named policy."""
    p = params or PolicyParams()
    inv = np.asarray(inventory, dtype=float)

    if policy == "as_poisson":
        sigma2 = endogenous_variance_proxy(0.35)
        premium = 0.0
    elif policy == "nominal_hawkes":
        sigma2 = endogenous_variance_proxy(rho_hat)
        premium = 0.0
    elif policy == "robust_vol_only":
        sigma2 = endogenous_variance_proxy(rho_hat)
        premium = p.risk_aversion * p.robust_scale * epsilon
    elif policy == "robust_gamma":
        sigma2 = endogenous_variance_proxy(rho_hat)
        premium = mesa_robust_premium(epsilon, rho_hat, p.risk_aversion, p.robust_scale)
    elif policy == "robust_gamma_abs":
        sigma2 = endogenous_variance_proxy(rho_hat)
        premium = mesa_robust_premium(
            epsilon,
            rho_hat,
            p.risk_aversion,
            p.robust_scale,
            ambiguity="absolute_gamma",
        )
    elif policy == "liquidity_guard":
        sigma2 = endogenous_variance_proxy(rho_hat)
        premium = mesa_robust_premium(
            epsilon,
            rho_hat,
            p.risk_aversion,
            p.robust_scale,
            ambiguity="absolute_gamma",
        )
        if float(np.asarray(premium)) > 0.12:
            premium = p.max_half_spread
    elif policy in {"oracle_gamma", "known_true_gamma_no_ambiguity"}:
        sigma2 = endogenous_variance_proxy(rho_oracle if rho_oracle is not None else rho_hat)
        premium = 0.0
    else:
        raise ValueError(f"unknown policy: {policy}")

    half = p.base_half_spread + p.variance_spread_scale * sigma2 + premium
    half = np.minimum(half, p.max_half_spread)
    bid = np.maximum(0.01, half + p.inventory_skew * inv)
    ask = np.maximum(0.01, half - p.inventory_skew * inv)
    return bid, ask


def certainty_equivalent(wealth: np.ndarray, risk_aversion: float = 0.02) -> float:
    """Exponential-utility certainty equivalent with overflow protection."""
    w = np.asarray(wealth, dtype=float)
    centered = w - np.mean(w)
    utility = -np.exp(np.clip(-risk_aversion * centered, -60, 60))
    return float(np.mean(w) - np.log(-np.mean(utility)) / risk_aversion)
