"""Finite-scenario robust inventory dynamic programming.

This is a deliberately small robust Bellman solver for the first publishable
MESA paper. It is not the full multitype HJBI. It solves a scalar reduced
inventory problem under a finite set of Hawkes criticality scenarios and is
meant to make the Perron-robust control approximation auditable. Each side can
now choose a quote offset or an explicit no-quote action.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mesa.control import endogenous_variance_proxy


@dataclass(frozen=True)
class RobustDPConfig:
    q_max: int = 5
    steps: int = 60
    horizon: float = 1.0
    quote_min: float = 0.01
    quote_max: float = 1.5
    quote_count: int = 40
    base_arrival: float = 1.0
    fill_decay: float = 8.0
    allow_no_quote: bool = True
    inventory_penalty: float = 0.03
    risk_aversion: float = 0.02
    terminal_penalty: float = 0.05
    max_fill_prob: float = 0.18
    rho_cap: float = 0.999

    @property
    def dt(self) -> float:
        return self.horizon / self.steps

    @property
    def inventory_grid(self) -> np.ndarray:
        return np.arange(-self.q_max, self.q_max + 1)

    @property
    def quote_grid(self) -> np.ndarray:
        return np.linspace(self.quote_min, self.quote_max, self.quote_count)


def worst_case_rho(rho_hat: float, epsilon: float, ambiguity: str, rho_cap: float = 0.999) -> float:
    """Return scalar worst-case criticality for the ambiguity convention."""
    if ambiguity == "relative_slack":
        rho = rho_hat + epsilon * max(1.0 - rho_hat, 0.0)
    elif ambiguity == "absolute_gamma":
        rho = rho_hat + epsilon
    else:
        raise ValueError(f"unknown ambiguity mode: {ambiguity}")
    return float(min(rho, rho_cap))


def solve_scalar_robust_dp(
    rho_hat: float,
    epsilon: float,
    ambiguity: str = "relative_slack",
    config: RobustDPConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Solve the finite-scenario robust inventory DP.

    Returns:
    policy table with rows `(time_index, inventory, bid_offset, ask_offset)`;
        value table with rows `(time_index, inventory, value)`.
    """
    cfg = config or RobustDPConfig()
    q_grid = cfg.inventory_grid
    quotes = cfg.quote_grid
    n_q = len(q_grid)
    dt = cfg.dt
    scenarios = np.array(
        [
            rho_hat,
            worst_case_rho(rho_hat, epsilon, ambiguity, cfg.rho_cap),
        ],
        dtype=float,
    )
    scenario_sigma2 = endogenous_variance_proxy(scenarios)
    scenario_arrivals = cfg.base_arrival / np.maximum(1.0 - scenarios, 1e-6)
    action_offsets = np.concatenate([quotes, [np.nan]]) if cfg.allow_no_quote else quotes.copy()
    action_active = ~np.isnan(action_offsets)
    bid_grid = np.nan_to_num(action_offsets[:, None], nan=0.0)
    ask_grid = np.nan_to_num(action_offsets[None, :], nan=0.0)
    bid_active_grid = action_active[:, None]
    ask_active_grid = action_active[None, :]

    h_next = -cfg.terminal_penalty * q_grid.astype(float) ** 2
    values = np.empty((cfg.steps + 1, n_q), dtype=float)
    bid_policy = np.empty((cfg.steps, n_q), dtype=float)
    ask_policy = np.empty((cfg.steps, n_q), dtype=float)
    values[cfg.steps] = h_next

    for step in range(cfg.steps - 1, -1, -1):
        h_cur = np.empty_like(h_next)
        for qi, q in enumerate(q_grid):
            up_idx = min(qi + 1, n_q - 1)
            down_idx = max(qi - 1, 0)
            worst_matrix = np.full((len(action_offsets), len(action_offsets)), np.inf, dtype=float)
            for arrival, sigma2 in zip(scenario_arrivals, scenario_sigma2, strict=True):
                p_bid = np.where(
                    bid_active_grid,
                    np.minimum(cfg.max_fill_prob, arrival * np.exp(-cfg.fill_decay * bid_grid) * dt),
                    0.0,
                )
                p_ask = np.where(
                    ask_active_grid,
                    np.minimum(cfg.max_fill_prob, arrival * np.exp(-cfg.fill_decay * ask_grid) * dt),
                    0.0,
                )
                total_p = p_bid + p_ask
                shrink = np.minimum(1.0, cfg.max_fill_prob / np.maximum(total_p, 1e-12))
                p_bid = p_bid * shrink
                p_ask = p_ask * shrink
                same = 1.0 - p_bid - p_ask
                inventory_risk = dt * (
                    cfg.inventory_penalty * q**2
                    + 0.5 * cfg.risk_aversion * sigma2 * q**2
                )
                value = (
                    -inventory_risk
                    + p_bid * (bid_grid + h_next[up_idx])
                    + p_ask * (ask_grid + h_next[down_idx])
                    + same * h_next[qi]
                )
                worst_matrix = np.minimum(worst_matrix, value)
            best_flat = int(np.argmax(worst_matrix))
            best_i, best_j = np.unravel_index(best_flat, worst_matrix.shape)
            best_value = float(worst_matrix[best_i, best_j])
            best_bid = float(action_offsets[best_i]) if action_active[best_i] else np.nan
            best_ask = float(action_offsets[best_j]) if action_active[best_j] else np.nan
            h_cur[qi] = best_value
            bid_policy[step, qi] = best_bid
            ask_policy[step, qi] = best_ask
        h_next = h_cur
        values[step] = h_cur

    policy_rows = []
    value_rows = []
    for step in range(cfg.steps):
        for qi, q in enumerate(q_grid):
            bid_active = bool(np.isfinite(bid_policy[step, qi]))
            ask_active = bool(np.isfinite(ask_policy[step, qi]))
            quoted_sides = int(bid_active) + int(ask_active)
            quoted_half_spread = np.nan
            if quoted_sides == 2:
                action = "two_sided"
                half_spread = 0.5 * (bid_policy[step, qi] + ask_policy[step, qi])
                quoted_half_spread = half_spread
            elif bid_active:
                action = "bid_only"
                half_spread = np.nan
                quoted_half_spread = bid_policy[step, qi]
            elif ask_active:
                action = "ask_only"
                half_spread = np.nan
                quoted_half_spread = ask_policy[step, qi]
            else:
                action = "no_quote"
                half_spread = np.nan
            if quoted_sides == 2:
                no_quote_action = "none"
            elif quoted_sides == 0:
                no_quote_action = "both"
            elif not bid_active:
                no_quote_action = "bid"
            else:
                no_quote_action = "ask"
            policy_rows.append(
                {
                    "time_index": step,
                    "inventory": int(q),
                    "rho_hat": rho_hat,
                    "epsilon": epsilon,
                    "ambiguity": ambiguity,
                    "rho_worst": scenarios[1],
                    "bid_offset": bid_policy[step, qi],
                    "ask_offset": ask_policy[step, qi],
                    "bid_active": bid_active,
                    "ask_active": ask_active,
                    "bid_action": "quote" if bid_active else "no_quote",
                    "ask_action": "quote" if ask_active else "no_quote",
                    "quoted_sides": quoted_sides,
                    "action": action,
                    "no_quote_action": no_quote_action,
                    "is_no_quote": quoted_sides < 2,
                    "is_full_no_quote": quoted_sides == 0,
                    "half_spread": half_spread,
                    "quoted_half_spread": quoted_half_spread,
                    "quote_cap_hit": bool(
                        (bid_active and bid_policy[step, qi] >= cfg.quote_max - 1e-12)
                        or (ask_active and ask_policy[step, qi] >= cfg.quote_max - 1e-12)
                    ),
                }
            )
    for step in range(cfg.steps + 1):
        for qi, q in enumerate(q_grid):
            value_rows.append(
                {
                    "time_index": step,
                    "inventory": int(q),
                    "rho_hat": rho_hat,
                    "epsilon": epsilon,
                    "ambiguity": ambiguity,
                    "rho_worst": scenarios[1],
                    "value": values[step, qi],
                }
            )
    return pd.DataFrame(policy_rows), pd.DataFrame(value_rows)
