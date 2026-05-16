"""Reduced event-driven queue backtest for MESA policies.

This module is intentionally small. It is not a production limit-order-book
simulator, but it evaluates quote/no-quote policies on Ogata Hawkes event times
with a simple queue-ahead mechanism and common event paths across policies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from mesa.control import PolicyParams, endogenous_variance_proxy, quote_offsets
from mesa.hawkes import HawkesParams, simulate_ogata_hawkes


@dataclass(frozen=True)
class EventQueueConfig:
    horizon: float = 8.0
    decision_dt: float = 0.02
    q_max: int = 5
    initial_mid: float = 100.0
    queue_ahead_base: float = 0.35
    mean_event_size: float = 1.15
    price_impact: float = 0.015
    price_noise_scale: float = 0.0025
    inventory_penalty: float = 0.05
    liquidation_penalty: float = 0.015
    no_quote_threshold: float = 1.45
    max_events: int = 300_000


def _queue_ahead(offset: float, params: PolicyParams, cfg: EventQueueConfig) -> float:
    return float(cfg.queue_ahead_base * np.exp(params.fill_decay * max(offset, 0.0)))


def _quote_state(
    inventory: float,
    rho_hat: float,
    epsilon: float,
    policy: str,
    params: PolicyParams,
    cfg: EventQueueConfig,
    rho_true: float,
) -> tuple[float, float, bool, bool, float, float]:
    bid, ask = quote_offsets(
        np.asarray([inventory], dtype=float),
        rho_hat=rho_hat,
        epsilon=epsilon,
        policy=policy,
        params=params,
        rho_oracle=rho_true,
    )
    bid_offset = float(bid[0])
    ask_offset = float(ask[0])
    bid_active = bool(inventory < cfg.q_max and bid_offset < cfg.no_quote_threshold)
    ask_active = bool(inventory > -cfg.q_max and ask_offset < cfg.no_quote_threshold)
    bid_queue = _queue_ahead(bid_offset, params, cfg) if bid_active else np.inf
    ask_queue = _queue_ahead(ask_offset, params, cfg) if ask_active else np.inf
    return bid_offset, ask_offset, bid_active, ask_active, bid_queue, ask_queue


def evaluate_event_queue_policy(
    times: np.ndarray,
    marks: np.ndarray,
    event_sizes: np.ndarray,
    price_noise: np.ndarray,
    *,
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policy: str,
    cfg: EventQueueConfig | None = None,
    params: PolicyParams | None = None,
) -> dict[str, float | int | str]:
    """Evaluate one policy on one fixed event path.

    Mark ``0`` is interpreted as a buy market order that can hit the ask quote;
    mark ``1`` is interpreted as a sell market order that can hit the bid quote.
    """
    cfg = cfg or EventQueueConfig()
    params = params or PolicyParams()
    times = np.asarray(times, dtype=float)
    marks = np.asarray(marks, dtype=int)
    event_sizes = np.asarray(event_sizes, dtype=float)
    price_noise = np.asarray(price_noise, dtype=float)
    if not (len(times) == len(marks) == len(event_sizes) == len(price_noise)):
        raise ValueError("times, marks, event_sizes, and price_noise must have the same length")

    cash = 0.0
    inventory = 0.0
    mid = cfg.initial_mid
    fills = 0
    bid_fills = 0
    ask_fills = 0
    spread_capture = 0.0
    adverse_selection = 0.0
    inventory_penalty = 0.0
    no_quote_side_time = 0.0
    full_no_quote_time = 0.0
    quote_updates = 0

    last_t = 0.0
    next_decision = 0.0
    bid_offset, ask_offset, bid_active, ask_active, bid_queue, ask_queue = _quote_state(
        inventory, rho_hat, epsilon, policy, params, cfg, rho_true
    )
    quote_updates += 1

    for idx, (t_raw, mark_raw) in enumerate(zip(times, marks, strict=True)):
        t = float(min(max(t_raw, 0.0), cfg.horizon))
        if t < last_t:
            continue
        dt = t - last_t
        inventory_penalty += inventory * inventory * dt
        no_quote_side_time += dt * ((0 if bid_active else 1) + (0 if ask_active else 1))
        full_no_quote_time += dt * (0 if (bid_active or ask_active) else 1)

        if t >= next_decision - 1e-12:
            bid_offset, ask_offset, bid_active, ask_active, bid_queue, ask_queue = _quote_state(
                inventory, rho_hat, epsilon, policy, params, cfg, rho_true
            )
            quote_updates += 1
            next_decision = (np.floor(t / cfg.decision_dt) + 1.0) * cfg.decision_dt

        mark = int(mark_raw)
        size = float(max(event_sizes[idx], 1.0))
        sign = 1.0 if mark == 0 else -1.0
        mid_before = mid
        mid_after = mid_before + sign * cfg.price_impact + cfg.price_noise_scale * price_noise[idx] * np.sqrt(max(dt, 1e-8))

        if mark == 0 and ask_active:
            ask_queue -= size
            if ask_queue <= 0.0:
                cash += mid_before + ask_offset
                inventory -= 1.0
                fills += 1
                ask_fills += 1
                spread_capture += ask_offset
                adverse_selection += max(mid_after - mid_before, 0.0)
                ask_queue += _queue_ahead(ask_offset, params, cfg)
        elif mark == 1 and bid_active:
            bid_queue -= size
            if bid_queue <= 0.0:
                cash -= mid_before - bid_offset
                inventory += 1.0
                fills += 1
                bid_fills += 1
                spread_capture += bid_offset
                adverse_selection += max(mid_before - mid_after, 0.0)
                bid_queue += _queue_ahead(bid_offset, params, cfg)

        mid = mid_after
        last_t = t

    tail_dt = max(cfg.horizon - last_t, 0.0)
    inventory_penalty += inventory * inventory * tail_dt
    no_quote_side_time += tail_dt * ((0 if bid_active else 1) + (0 if ask_active else 1))
    full_no_quote_time += tail_dt * (0 if (bid_active or ask_active) else 1)

    terminal_wealth = (
        cash
        + inventory * mid
        - cfg.inventory_penalty * inventory_penalty
        - cfg.liquidation_penalty * abs(inventory)
    )
    n_events = int(len(times))
    return {
        "policy": policy,
        "terminal_wealth": float(terminal_wealth),
        "final_inventory": float(inventory),
        "abs_inventory": float(abs(inventory)),
        "fills": int(fills),
        "bid_fills": int(bid_fills),
        "ask_fills": int(ask_fills),
        "fill_rate": float(fills / max(n_events, 1)),
        "spread_capture": float(spread_capture),
        "adverse_selection": float(adverse_selection),
        "inventory_penalty": float(inventory_penalty),
        "no_quote_side_time_frac": float(no_quote_side_time / max(2.0 * cfg.horizon, 1e-12)),
        "full_no_quote_time_frac": float(full_no_quote_time / max(cfg.horizon, 1e-12)),
        "quote_updates": int(quote_updates),
        "n_events": n_events,
    }


def run_event_queue_backtest(
    hawkes_params: HawkesParams,
    *,
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policies: list[str],
    n_paths: int,
    seed: int,
    cfg: EventQueueConfig | None = None,
) -> pd.DataFrame:
    """Run event-driven queue evaluation with common event paths across policies."""
    cfg = cfg or EventQueueConfig(horizon=hawkes_params.horizon)
    rows: list[dict[str, float | int | str]] = []
    for path_id in range(n_paths):
        out = simulate_ogata_hawkes(
            hawkes_params,
            seed=seed + path_id,
            max_events=cfg.max_events,
        )
        times = out["times"]
        marks = out["marks"]
        rng = np.random.default_rng(seed + 100_000 + path_id)
        event_sizes = 1.0 + rng.poisson(max(cfg.mean_event_size - 1.0, 0.0), size=len(times))
        price_noise = rng.standard_normal(size=len(times))
        for policy in policies:
            row = evaluate_event_queue_policy(
                times,
                marks,
                event_sizes,
                price_noise,
                rho_hat=rho_hat,
                rho_true=rho_true,
                epsilon=epsilon,
                policy=policy,
                cfg=cfg,
            )
            row.update(
                {
                    "path_id": path_id,
                    "rho_hat": rho_hat,
                    "rho_true": rho_true,
                    "epsilon": epsilon,
                    "horizon": cfg.horizon,
                    "decision_dt": cfg.decision_dt,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)
