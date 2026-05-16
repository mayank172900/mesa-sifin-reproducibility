"""Top-of-book replay diagnostics on public LOBSTER samples.

This is a deliberately transparent replay layer. It is not a full exchange
queue simulator, but it evaluates the same quote/no-quote policy family on
actual LOBSTER message and order-book streams rather than simulated Hawkes
event times.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from mesa.control import PolicyParams, quote_offsets
from mesa.empirical import load_lobster_message, load_lobster_orderbook


@dataclass(frozen=True)
class LobsterReplayConfig:
    decision_interval: float = 1.0
    q_max: int = 5
    queue_fraction: float = 0.20
    max_quote_offset: float = 0.08
    inventory_penalty: float = 2.5e-4
    liquidation_penalty: float = 0.01
    max_events: int = 80_000
    min_queue_ahead: float = 0.5
    max_queue_ahead: float = 20.0
    max_fill_lots: float = 1.0
    tick_size: float = 0.01
    visible_cancel_depletion_fraction: float = 0.25
    priority_initial_queue_fraction: float = 1.0
    priority_queue_stress_multiplier: float = 1.0
    crossing_mode: str = "clamp"


def _floor_to_tick(price: float, tick_size: float) -> float:
    return float(np.floor(price / tick_size + 1e-9) * tick_size)


def _ceil_to_tick(price: float, tick_size: float) -> float:
    return float(np.ceil(price / tick_size - 1e-9) * tick_size)


def _mid_from_book(orderbook: pd.DataFrame) -> np.ndarray:
    return 0.5 * (orderbook["ask_price_1"].to_numpy(float) + orderbook["bid_price_1"].to_numpy(float)) * 1e-4


def _execution_size_scale(message: pd.DataFrame) -> float:
    executions = message[message["event_type"].isin([4, 5])]["size"].to_numpy(float)
    if len(executions) == 0:
        return 1.0
    return float(max(np.median(executions), 1.0))


def _queue_ahead_from_book(
    orderbook: pd.DataFrame,
    row_idx: int,
    side: str,
    cfg: LobsterReplayConfig,
    size_scale: float,
) -> float:
    col = "bid_size_1" if side == "bid" else "ask_size_1"
    raw_size = float(orderbook.iloc[row_idx][col])
    scaled = cfg.queue_fraction * raw_size / max(size_scale, 1.0)
    return float(np.clip(scaled, cfg.min_queue_ahead, cfg.max_queue_ahead))


def _available_depth_levels(orderbook: pd.DataFrame) -> int:
    level = 1
    while f"ask_price_{level}" in orderbook.columns and f"bid_price_{level}" in orderbook.columns:
        level += 1
    return level - 1


def _side_ladder(
    orderbook: pd.DataFrame,
    row_idx: int,
    side: str,
    levels: int,
) -> tuple[np.ndarray, np.ndarray]:
    prices = []
    sizes = []
    for level in range(1, levels + 1):
        prices.append(float(orderbook.at[row_idx, f"{side}_price_{level}"]) * 1e-4)
        sizes.append(float(orderbook.at[row_idx, f"{side}_size_{level}"]))
    price_arr = np.asarray(prices, dtype=float)
    size_arr = np.asarray(sizes, dtype=float)
    valid = np.isfinite(price_arr) & np.isfinite(size_arr) & (price_arr > 0.0) & (size_arr >= 0.0)
    return price_arr[valid], size_arr[valid]


def _depth_queue_ahead(
    orderbook: pd.DataFrame,
    row_idx: int,
    side: str,
    quote_price: float,
    cfg: LobsterReplayConfig,
    size_scale: float,
    levels: int,
    same_level_fraction: float | None = None,
    clip_queue: bool = True,
) -> tuple[float, int, float]:
    """Estimate displayed queue ahead up to the quoted depth level."""
    prices, sizes = _side_ladder(orderbook, row_idx, side, levels)
    if len(prices) == 0:
        return np.inf, -1, 0.0
    tick = cfg.tick_size
    if side == "bid":
        better = prices > quote_price + 0.5 * tick
        same = np.abs(prices - quote_price) <= 0.5 * tick
        within_visible = quote_price >= float(np.min(prices)) - 0.5 * tick
        depth_rank = int(np.sum(prices > quote_price + 0.5 * tick) + 1)
    else:
        better = prices < quote_price - 0.5 * tick
        same = np.abs(prices - quote_price) <= 0.5 * tick
        within_visible = quote_price <= float(np.max(prices)) + 0.5 * tick
        depth_rank = int(np.sum(prices < quote_price - 0.5 * tick) + 1)
    if not within_visible:
        return np.inf, -1, 0.0
    same_fraction = cfg.queue_fraction if same_level_fraction is None else same_level_fraction
    raw_ahead = float(np.sum(sizes[better]) + same_fraction * np.sum(sizes[same]))
    scaled = raw_ahead / max(size_scale, 1.0)
    if raw_ahead <= 0.0:
        return 0.0, depth_rank, 0.0
    if not clip_queue:
        return float(scaled), depth_rank, raw_ahead
    return float(np.clip(scaled, cfg.min_queue_ahead, cfg.max_queue_ahead)), depth_rank, raw_ahead


def _same_price(left: float, right: float, tick_size: float) -> bool:
    return bool(np.isfinite(left) and np.isfinite(right) and abs(left - right) <= 0.5 * tick_size)


def _better_price(side: str, price: float, quote_price: float, tick_size: float) -> bool:
    if not np.isfinite(price) or not np.isfinite(quote_price):
        return False
    if side == "bid":
        return bool(price > quote_price + 0.5 * tick_size)
    if side == "ask":
        return bool(price < quote_price - 0.5 * tick_size)
    raise ValueError(f"unknown side: {side}")


def _message_side_for_resting_order(event_type: int, direction: int) -> str | None:
    if event_type in {1, 2, 3}:
        if direction == 1:
            return "bid"
        if direction == -1:
            return "ask"
    return None


def _message_side_for_execution(direction: int) -> str | None:
    if direction == -1:
        return "bid"
    if direction == 1:
        return "ask"
    return None


def _classify_depth_quote(
    side: str,
    target_price: float,
    bid1: float,
    ask1: float,
    active: bool,
    orderbook: pd.DataFrame,
    row_idx: int,
    cfg: LobsterReplayConfig,
    size_scale: float,
    levels: int,
) -> dict[str, float | int | str | bool]:
    """Classify a passive quote against the visible multi-level LOBSTER ladder."""
    if not active:
        return {"state": "withdraw", "price": np.nan, "crossed": False, "queue": np.inf, "depth_rank": -1}
    tick = cfg.tick_size
    crossed = False
    if side == "bid":
        quote_price = _floor_to_tick(target_price, tick)
        if quote_price >= ask1:
            crossed = True
            if cfg.crossing_mode == "withdraw":
                return {"state": "withdraw", "price": np.nan, "crossed": crossed, "queue": np.inf, "depth_rank": -1}
            quote_price = min(_floor_to_tick(ask1 - tick, tick), _floor_to_tick(target_price, tick))
        if quote_price > bid1 + 0.5 * tick and quote_price < ask1:
            return {"state": "improve", "price": quote_price, "crossed": crossed, "queue": 0.0, "depth_rank": 0}
        queue, depth_rank, _ = _depth_queue_ahead(orderbook, row_idx, side, quote_price, cfg, size_scale, levels)
        if np.isfinite(queue):
            state = "join_l1" if quote_price >= bid1 - 0.5 * tick else "depth_visible"
            return {"state": state, "price": quote_price, "crossed": crossed, "queue": queue, "depth_rank": depth_rank}
        return {"state": "outside_depth", "price": quote_price, "crossed": crossed, "queue": np.inf, "depth_rank": -1}
    if side == "ask":
        quote_price = _ceil_to_tick(target_price, tick)
        if quote_price <= bid1:
            crossed = True
            if cfg.crossing_mode == "withdraw":
                return {"state": "withdraw", "price": np.nan, "crossed": crossed, "queue": np.inf, "depth_rank": -1}
            quote_price = max(_ceil_to_tick(bid1 + tick, tick), _ceil_to_tick(target_price, tick))
        if quote_price < ask1 - 0.5 * tick and quote_price > bid1:
            return {"state": "improve", "price": quote_price, "crossed": crossed, "queue": 0.0, "depth_rank": 0}
        queue, depth_rank, _ = _depth_queue_ahead(orderbook, row_idx, side, quote_price, cfg, size_scale, levels)
        if np.isfinite(queue):
            state = "join_l1" if quote_price <= ask1 + 0.5 * tick else "depth_visible"
            return {"state": state, "price": quote_price, "crossed": crossed, "queue": queue, "depth_rank": depth_rank}
        return {"state": "outside_depth", "price": quote_price, "crossed": crossed, "queue": np.inf, "depth_rank": -1}
    raise ValueError(f"unknown side: {side}")


def _policy_state(
    inventory: float,
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policy: str,
    cfg: LobsterReplayConfig,
    params: PolicyParams,
) -> tuple[float, float, bool, bool]:
    bid, ask = quote_offsets(
        np.asarray([inventory], dtype=float),
        rho_hat=rho_hat,
        rho_oracle=rho_true,
        epsilon=epsilon,
        policy=policy,
        params=params,
    )
    bid_offset = float(bid[0])
    ask_offset = float(ask[0])
    bid_active = bool(inventory < cfg.q_max and bid_offset <= cfg.max_quote_offset)
    ask_active = bool(inventory > -cfg.q_max and ask_offset <= cfg.max_quote_offset)
    return bid_offset, ask_offset, bid_active, ask_active


def _classify_l1_quote(
    side: str,
    target_price: float,
    bid1: float,
    ask1: float,
    active: bool,
    cfg: LobsterReplayConfig,
) -> tuple[str, float, bool]:
    """Classify an L1-observable passive quote as join/improve/away/withdraw."""
    if not active:
        return "withdraw", np.nan, False
    tick = cfg.tick_size
    crossed = False
    if side == "bid":
        quote_price = _floor_to_tick(target_price, tick)
        if quote_price >= ask1:
            crossed = True
            if cfg.crossing_mode == "withdraw":
                return "withdraw", np.nan, crossed
            quote_price = min(_floor_to_tick(ask1 - tick, tick), _floor_to_tick(target_price, tick))
        if quote_price > bid1 + 0.5 * tick and quote_price < ask1:
            return "improve", quote_price, crossed
        if quote_price >= bid1 - 0.5 * tick:
            return "join", bid1, crossed
        return "away", quote_price, crossed
    if side == "ask":
        quote_price = _ceil_to_tick(target_price, tick)
        if quote_price <= bid1:
            crossed = True
            if cfg.crossing_mode == "withdraw":
                return "withdraw", np.nan, crossed
            quote_price = max(_ceil_to_tick(bid1 + tick, tick), _ceil_to_tick(target_price, tick))
        if quote_price < ask1 - 0.5 * tick and quote_price > bid1:
            return "improve", quote_price, crossed
        if quote_price <= ask1 + 0.5 * tick:
            return "join", ask1, crossed
        return "away", quote_price, crossed
    raise ValueError(f"unknown side: {side}")


def _l1_quote_state(
    inventory: float,
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policy: str,
    cfg: LobsterReplayConfig,
    params: PolicyParams,
    mid: float,
    bid1: float,
    ask1: float,
) -> dict[str, float | str | bool]:
    bid_offset, ask_offset, bid_active, ask_active = _policy_state(
        inventory, rho_hat, rho_true, epsilon, policy, cfg, params
    )
    target_bid = mid - bid_offset
    target_ask = mid + ask_offset
    bid_state, bid_price, bid_crossed = _classify_l1_quote("bid", target_bid, bid1, ask1, bid_active, cfg)
    ask_state, ask_price, ask_crossed = _classify_l1_quote("ask", target_ask, bid1, ask1, ask_active, cfg)
    return {
        "bid_offset": bid_offset,
        "ask_offset": ask_offset,
        "bid_state": bid_state,
        "ask_state": ask_state,
        "bid_price": bid_price,
        "ask_price": ask_price,
        "bid_crossed": bid_crossed,
        "ask_crossed": ask_crossed,
    }


def evaluate_lobster_top_of_book_policy(
    message: pd.DataFrame,
    orderbook: pd.DataFrame,
    *,
    ticker: str,
    scenario: str,
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policy: str,
    cfg: LobsterReplayConfig | None = None,
    params: PolicyParams | None = None,
) -> dict[str, float | int | str]:
    """Replay a policy on one LOBSTER message/order-book stream."""
    cfg = cfg or LobsterReplayConfig()
    params = params or PolicyParams()
    n = min(len(message), len(orderbook), cfg.max_events)
    if n < 2:
        raise ValueError("at least two synchronized LOBSTER rows are required")
    msg = message.iloc[:n].reset_index(drop=True)
    book = orderbook.iloc[:n].reset_index(drop=True)
    times = msg["time"].to_numpy(float)
    times = times - times[0]
    mids = _mid_from_book(book)
    size_scale = _execution_size_scale(msg)

    cash = 0.0
    inventory = 0.0
    fills = 0
    bid_fills = 0
    ask_fills = 0
    spread_capture = 0.0
    adverse_selection = 0.0
    inventory_penalty = 0.0
    no_quote_side_time = 0.0
    full_no_quote_time = 0.0
    quote_updates = 0

    bid_offset, ask_offset, bid_active, ask_active = _policy_state(
        inventory, rho_hat, rho_true, epsilon, policy, cfg, params
    )
    bid_queue = _queue_ahead_from_book(book, 0, "bid", cfg, size_scale) if bid_active else np.inf
    ask_queue = _queue_ahead_from_book(book, 0, "ask", cfg, size_scale) if ask_active else np.inf
    next_decision = cfg.decision_interval
    quote_updates += 1
    last_t = 0.0

    for idx in range(1, n):
        t = float(max(times[idx], last_t))
        dt = t - last_t
        inventory_penalty += inventory * inventory * dt
        no_quote_side_time += dt * ((0 if bid_active else 1) + (0 if ask_active else 1))
        full_no_quote_time += dt * (0 if (bid_active or ask_active) else 1)

        if t >= next_decision - 1e-12:
            bid_offset, ask_offset, bid_active, ask_active = _policy_state(
                inventory, rho_hat, rho_true, epsilon, policy, cfg, params
            )
            bid_queue = _queue_ahead_from_book(book, idx - 1, "bid", cfg, size_scale) if bid_active else np.inf
            ask_queue = _queue_ahead_from_book(book, idx - 1, "ask", cfg, size_scale) if ask_active else np.inf
            next_decision = (np.floor(t / cfg.decision_interval) + 1.0) * cfg.decision_interval
            quote_updates += 1

        event_type = int(msg.at[idx, "event_type"])
        direction = int(msg.at[idx, "direction"])
        size_lots = min(float(msg.at[idx, "size"]) / max(size_scale, 1.0), cfg.max_fill_lots)
        mid_before = float(mids[idx - 1])
        mid_after = float(mids[idx])
        bid_price = float(book.at[idx - 1, "bid_price_1"]) * 1e-4
        ask_price = float(book.at[idx - 1, "ask_price_1"]) * 1e-4

        if event_type in {4, 5} and direction == 1 and ask_active:
            ask_queue -= max(size_lots, 0.0)
            if ask_queue <= 0.0:
                fill_lots = cfg.max_fill_lots
                cash += fill_lots * ask_price
                inventory -= fill_lots
                fills += 1
                ask_fills += 1
                spread_capture += fill_lots * max(ask_price - mid_before, 0.0)
                adverse_selection += fill_lots * max(mid_after - mid_before, 0.0)
                bid_offset, ask_offset, bid_active, ask_active = _policy_state(
                    inventory, rho_hat, rho_true, epsilon, policy, cfg, params
                )
                bid_queue = _queue_ahead_from_book(book, idx, "bid", cfg, size_scale) if bid_active else np.inf
                ask_queue = _queue_ahead_from_book(book, idx, "ask", cfg, size_scale) if ask_active else np.inf
                quote_updates += 1
        elif event_type in {4, 5} and direction == -1 and bid_active:
            bid_queue -= max(size_lots, 0.0)
            if bid_queue <= 0.0:
                fill_lots = cfg.max_fill_lots
                cash -= fill_lots * bid_price
                inventory += fill_lots
                fills += 1
                bid_fills += 1
                spread_capture += fill_lots * max(mid_before - bid_price, 0.0)
                adverse_selection += fill_lots * max(mid_before - mid_after, 0.0)
                bid_offset, ask_offset, bid_active, ask_active = _policy_state(
                    inventory, rho_hat, rho_true, epsilon, policy, cfg, params
                )
                bid_queue = _queue_ahead_from_book(book, idx, "bid", cfg, size_scale) if bid_active else np.inf
                ask_queue = _queue_ahead_from_book(book, idx, "ask", cfg, size_scale) if ask_active else np.inf
                quote_updates += 1

        last_t = t

    horizon = float(max(times[-1], 1e-12))
    terminal_mid = float(mids[n - 1])
    terminal_wealth = (
        cash
        + inventory * terminal_mid
        - cfg.inventory_penalty * inventory_penalty
        - cfg.liquidation_penalty * abs(inventory)
    )
    return {
        "ticker": ticker,
        "scenario": scenario,
        "policy": policy,
        "rho_hat": float(rho_hat),
        "rho_true": float(rho_true),
        "epsilon": float(epsilon),
        "terminal_wealth": float(terminal_wealth),
        "final_inventory": float(inventory),
        "abs_inventory": float(abs(inventory)),
        "fills": int(fills),
        "bid_fills": int(bid_fills),
        "ask_fills": int(ask_fills),
        "fill_rate": float(fills / max(n, 1)),
        "spread_capture": float(spread_capture),
        "adverse_selection": float(adverse_selection),
        "inventory_penalty": float(inventory_penalty),
        "no_quote_side_time_frac": float(no_quote_side_time / max(2.0 * horizon, 1e-12)),
        "full_no_quote_time_frac": float(full_no_quote_time / max(horizon, 1e-12)),
        "quote_updates": int(quote_updates),
        "n_events": int(n),
        "horizon": horizon,
        "size_scale": float(size_scale),
    }


def evaluate_lobster_l1_quote_policy(
    message: pd.DataFrame,
    orderbook: pd.DataFrame,
    *,
    ticker: str,
    scenario: str,
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policy: str,
    cfg: LobsterReplayConfig | None = None,
    params: PolicyParams | None = None,
) -> dict[str, float | int | str]:
    """Replay a continuous-offset policy on LOBSTER L1 quotes.

    The replay distinguishes joining the visible best quote, improving inside
    the displayed spread, resting away from L1, and withdrawing. Away quotes are
    deliberately not filled because one-level data cannot identify hidden depth.
    """
    cfg = cfg or LobsterReplayConfig()
    params = params or PolicyParams()
    n = min(len(message), len(orderbook), cfg.max_events)
    if n < 2:
        raise ValueError("at least two synchronized LOBSTER rows are required")
    msg = message.iloc[:n].reset_index(drop=True)
    book = orderbook.iloc[:n].reset_index(drop=True)
    times = msg["time"].to_numpy(float)
    times = times - times[0]
    mids = _mid_from_book(book)
    ask_prices = book["ask_price_1"].to_numpy(float) * 1e-4
    bid_prices = book["bid_price_1"].to_numpy(float) * 1e-4
    ask_sizes = book["ask_size_1"].to_numpy(float)
    bid_sizes = book["bid_size_1"].to_numpy(float)
    event_types = msg["event_type"].to_numpy(int)
    directions = msg["direction"].to_numpy(int)
    sizes = msg["size"].to_numpy(float)
    size_scale = _execution_size_scale(msg)

    cash = 0.0
    inventory = 0.0
    fills = 0
    bid_fills = 0
    ask_fills = 0
    spread_capture = 0.0
    adverse_selection = 0.0
    inventory_penalty = 0.0
    quote_updates = 0
    crossing_clamp_count = 0
    exec_depletion = 0.0
    visible_size_drop_depletion = 0.0
    offset_bid_sum = 0.0
    offset_ask_sum = 0.0
    offset_side_time = 0.0
    full_no_quote_time = 0.0
    state_time = {
        "join": 0.0,
        "improve": 0.0,
        "away": 0.0,
        "withdraw": 0.0,
    }

    def reset_quote(row_idx: int) -> tuple[dict[str, float | str | bool], float, float]:
        state = _l1_quote_state(
            inventory,
            rho_hat,
            rho_true,
            epsilon,
            policy,
            cfg,
            params,
            mid=float(mids[row_idx]),
            bid1=float(bid_prices[row_idx]),
            ask1=float(ask_prices[row_idx]),
        )
        bid_queue = (
            _queue_ahead_from_book(book, row_idx, "bid", cfg, size_scale)
            if state["bid_state"] == "join"
            else 0.0
        )
        ask_queue = (
            _queue_ahead_from_book(book, row_idx, "ask", cfg, size_scale)
            if state["ask_state"] == "join"
            else 0.0
        )
        return state, bid_queue, ask_queue

    quote, bid_queue, ask_queue = reset_quote(0)
    crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
    quote_updates += 1
    next_decision = cfg.decision_interval
    last_t = 0.0

    for idx in range(1, n):
        t = float(max(times[idx], last_t))
        dt = t - last_t
        inventory_penalty += inventory * inventory * dt
        for side in ("bid", "ask"):
            state = str(quote[f"{side}_state"])
            state_time[state] += dt
        full_no_quote_time += dt * (
            1.0 if quote["bid_state"] == "withdraw" and quote["ask_state"] == "withdraw" else 0.0
        )
        offset_bid_sum += float(quote["bid_offset"]) * dt
        offset_ask_sum += float(quote["ask_offset"]) * dt
        offset_side_time += dt

        if t >= next_decision - 1e-12:
            quote, bid_queue, ask_queue = reset_quote(idx - 1)
            crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
            next_decision = (np.floor(t / cfg.decision_interval) + 1.0) * cfg.decision_interval
            quote_updates += 1

        if str(quote["bid_state"]) == "join" and bid_prices[idx] == bid_prices[idx - 1]:
            size_drop = max(bid_sizes[idx - 1] - bid_sizes[idx], 0.0)
            depletion = cfg.visible_cancel_depletion_fraction * size_drop / max(size_scale, 1.0)
            bid_queue -= depletion
            visible_size_drop_depletion += depletion
        if str(quote["ask_state"]) == "join" and ask_prices[idx] == ask_prices[idx - 1]:
            size_drop = max(ask_sizes[idx - 1] - ask_sizes[idx], 0.0)
            depletion = cfg.visible_cancel_depletion_fraction * size_drop / max(size_scale, 1.0)
            ask_queue -= depletion
            visible_size_drop_depletion += depletion

        event_type = int(event_types[idx])
        direction = int(directions[idx])
        size_lots = min(float(sizes[idx]) / max(size_scale, 1.0), cfg.max_fill_lots)
        mid_before = float(mids[idx - 1])
        mid_after = float(mids[idx])

        if event_type in {4, 5} and direction == 1 and str(quote["ask_state"]) in {"join", "improve"}:
            if str(quote["ask_state"]) == "join":
                ask_queue -= max(size_lots, 0.0)
                exec_depletion += max(size_lots, 0.0)
                should_fill = ask_queue <= 0.0
            else:
                should_fill = True
            if should_fill:
                fill_lots = cfg.max_fill_lots
                ask_price = float(quote["ask_price"])
                cash += fill_lots * ask_price
                inventory -= fill_lots
                fills += 1
                ask_fills += 1
                spread_capture += fill_lots * max(ask_price - mid_before, 0.0)
                adverse_selection += fill_lots * max(mid_after - mid_before, 0.0)
                quote, bid_queue, ask_queue = reset_quote(idx)
                crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
                quote_updates += 1
        elif event_type in {4, 5} and direction == -1 and str(quote["bid_state"]) in {"join", "improve"}:
            if str(quote["bid_state"]) == "join":
                bid_queue -= max(size_lots, 0.0)
                exec_depletion += max(size_lots, 0.0)
                should_fill = bid_queue <= 0.0
            else:
                should_fill = True
            if should_fill:
                fill_lots = cfg.max_fill_lots
                bid_price = float(quote["bid_price"])
                cash -= fill_lots * bid_price
                inventory += fill_lots
                fills += 1
                bid_fills += 1
                spread_capture += fill_lots * max(mid_before - bid_price, 0.0)
                adverse_selection += fill_lots * max(mid_before - mid_after, 0.0)
                quote, bid_queue, ask_queue = reset_quote(idx)
                crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
                quote_updates += 1

        last_t = t

    horizon = float(max(times[-1], 1e-12))
    terminal_mid = float(mids[n - 1])
    terminal_wealth = (
        cash
        + inventory * terminal_mid
        - cfg.inventory_penalty * inventory_penalty
        - cfg.liquidation_penalty * abs(inventory)
    )
    side_horizon = max(2.0 * horizon, 1e-12)
    return {
        "ticker": ticker,
        "scenario": scenario,
        "policy": policy,
        "rho_hat": float(rho_hat),
        "rho_true": float(rho_true),
        "epsilon": float(epsilon),
        "terminal_wealth": float(terminal_wealth),
        "final_inventory": float(inventory),
        "abs_inventory": float(abs(inventory)),
        "fills": int(fills),
        "bid_fills": int(bid_fills),
        "ask_fills": int(ask_fills),
        "fill_rate": float(fills / max(n, 1)),
        "spread_capture": float(spread_capture),
        "adverse_selection": float(adverse_selection),
        "inventory_penalty": float(inventory_penalty),
        "join_side_time_frac": float(state_time["join"] / side_horizon),
        "improve_side_time_frac": float(state_time["improve"] / side_horizon),
        "away_side_time_frac": float(state_time["away"] / side_horizon),
        "no_quote_side_time_frac": float(state_time["withdraw"] / side_horizon),
        "full_no_quote_time_frac": float(full_no_quote_time / max(horizon, 1e-12)),
        "mean_bid_offset": float(offset_bid_sum / max(offset_side_time, 1e-12)),
        "mean_ask_offset": float(offset_ask_sum / max(offset_side_time, 1e-12)),
        "crossing_clamp_count": int(crossing_clamp_count),
        "queue_depletion_from_exec": float(exec_depletion),
        "queue_depletion_from_visible_size_drop": float(visible_size_drop_depletion),
        "quote_updates": int(quote_updates),
        "n_events": int(n),
        "horizon": horizon,
        "size_scale": float(size_scale),
    }


def evaluate_lobster_depth_quote_policy(
    message: pd.DataFrame,
    orderbook: pd.DataFrame,
    *,
    ticker: str,
    scenario: str,
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policy: str,
    cfg: LobsterReplayConfig | None = None,
    params: PolicyParams | None = None,
) -> dict[str, float | int | str]:
    """Replay a continuous-offset policy against the visible multi-level book.

    This is a depth-aware public-data replay: a quote resting away from L1 can
    fill when it is still inside the displayed LOBSTER ladder and observed
    executions/depth changes deplete the displayed queue ahead. Quotes outside
    the displayed depth remain unobservable and are not filled.
    """
    cfg = cfg or LobsterReplayConfig()
    params = params or PolicyParams()
    n = min(len(message), len(orderbook), cfg.max_events)
    if n < 2:
        raise ValueError("at least two synchronized LOBSTER rows are required")
    levels = _available_depth_levels(orderbook)
    if levels < 2:
        raise ValueError("depth quote replay requires at least two displayed book levels")
    msg = message.iloc[:n].reset_index(drop=True)
    book = orderbook.iloc[:n].reset_index(drop=True)
    times = msg["time"].to_numpy(float)
    times = times - times[0]
    mids = _mid_from_book(book)
    event_types = msg["event_type"].to_numpy(int)
    directions = msg["direction"].to_numpy(int)
    sizes = msg["size"].to_numpy(float)
    size_scale = _execution_size_scale(msg)

    cash = 0.0
    inventory = 0.0
    fills = 0
    bid_fills = 0
    ask_fills = 0
    spread_capture = 0.0
    adverse_selection = 0.0
    inventory_penalty = 0.0
    quote_updates = 0
    crossing_clamp_count = 0
    exec_depletion = 0.0
    visible_depth_depletion = 0.0
    offset_bid_sum = 0.0
    offset_ask_sum = 0.0
    offset_side_time = 0.0
    depth_rank_side_time = 0.0
    depth_rank_time_weight = 0.0
    full_no_quote_time = 0.0
    state_time = {
        "join_l1": 0.0,
        "improve": 0.0,
        "depth_visible": 0.0,
        "outside_depth": 0.0,
        "withdraw": 0.0,
    }

    def reset_quote(row_idx: int) -> tuple[dict[str, float | int | str | bool], float, float]:
        bid_offset, ask_offset, bid_active, ask_active = _policy_state(
            inventory, rho_hat, rho_true, epsilon, policy, cfg, params
        )
        bid1 = float(book.at[row_idx, "bid_price_1"]) * 1e-4
        ask1 = float(book.at[row_idx, "ask_price_1"]) * 1e-4
        mid = float(mids[row_idx])
        bid = _classify_depth_quote(
            "bid",
            mid - bid_offset,
            bid1,
            ask1,
            bid_active,
            book,
            row_idx,
            cfg,
            size_scale,
            levels,
        )
        ask = _classify_depth_quote(
            "ask",
            mid + ask_offset,
            bid1,
            ask1,
            ask_active,
            book,
            row_idx,
            cfg,
            size_scale,
            levels,
        )
        state: dict[str, float | int | str | bool] = {
            "bid_offset": bid_offset,
            "ask_offset": ask_offset,
            "bid_state": str(bid["state"]),
            "ask_state": str(ask["state"]),
            "bid_price": float(bid["price"]),
            "ask_price": float(ask["price"]),
            "bid_depth_rank": int(bid["depth_rank"]),
            "ask_depth_rank": int(ask["depth_rank"]),
            "bid_crossed": bool(bid["crossed"]),
            "ask_crossed": bool(ask["crossed"]),
        }
        return state, float(bid["queue"]), float(ask["queue"])

    quote, bid_queue, ask_queue = reset_quote(0)
    crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
    quote_updates += 1
    next_decision = cfg.decision_interval
    last_t = 0.0

    def apply_visible_depth_depletion(row_idx: int) -> tuple[float, float, float]:
        depletion = 0.0
        new_bid_queue = bid_queue
        new_ask_queue = ask_queue
        if str(quote["bid_state"]) in {"join_l1", "depth_visible"} and np.isfinite(bid_queue):
            estimated, _, _ = _depth_queue_ahead(
                book, row_idx, "bid", float(quote["bid_price"]), cfg, size_scale, levels
            )
            if np.isfinite(estimated):
                drop = max(bid_queue - estimated, 0.0)
                depletion += cfg.visible_cancel_depletion_fraction * drop
                new_bid_queue = bid_queue - cfg.visible_cancel_depletion_fraction * drop
        if str(quote["ask_state"]) in {"join_l1", "depth_visible"} and np.isfinite(ask_queue):
            estimated, _, _ = _depth_queue_ahead(
                book, row_idx, "ask", float(quote["ask_price"]), cfg, size_scale, levels
            )
            if np.isfinite(estimated):
                drop = max(ask_queue - estimated, 0.0)
                depletion += cfg.visible_cancel_depletion_fraction * drop
                new_ask_queue = ask_queue - cfg.visible_cancel_depletion_fraction * drop
        return new_bid_queue, new_ask_queue, depletion

    for idx in range(1, n):
        t = float(max(times[idx], last_t))
        dt = t - last_t
        inventory_penalty += inventory * inventory * dt
        for side in ("bid", "ask"):
            state = str(quote[f"{side}_state"])
            state_time[state] += dt
            rank = int(quote[f"{side}_depth_rank"])
            if rank > 0:
                depth_rank_time_weight += dt * rank
                depth_rank_side_time += dt
        full_no_quote_time += dt * (
            1.0 if quote["bid_state"] == "withdraw" and quote["ask_state"] == "withdraw" else 0.0
        )
        offset_bid_sum += float(quote["bid_offset"]) * dt
        offset_ask_sum += float(quote["ask_offset"]) * dt
        offset_side_time += dt

        if t >= next_decision - 1e-12:
            quote, bid_queue, ask_queue = reset_quote(idx - 1)
            crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
            next_decision = (np.floor(t / cfg.decision_interval) + 1.0) * cfg.decision_interval
            quote_updates += 1

        bid_queue, ask_queue, depletion = apply_visible_depth_depletion(idx)
        visible_depth_depletion += depletion

        event_type = int(event_types[idx])
        direction = int(directions[idx])
        size_lots = min(float(sizes[idx]) / max(size_scale, 1.0), cfg.max_fill_lots)
        mid_before = float(mids[idx - 1])
        mid_after = float(mids[idx])

        if event_type in {4, 5} and direction == 1 and str(quote["ask_state"]) in {
            "join_l1",
            "improve",
            "depth_visible",
        }:
            if str(quote["ask_state"]) == "improve":
                should_fill = True
            else:
                ask_queue -= max(size_lots, 0.0)
                exec_depletion += max(size_lots, 0.0)
                should_fill = ask_queue <= 0.0
            if should_fill:
                fill_lots = cfg.max_fill_lots
                ask_price = float(quote["ask_price"])
                cash += fill_lots * ask_price
                inventory -= fill_lots
                fills += 1
                ask_fills += 1
                spread_capture += fill_lots * max(ask_price - mid_before, 0.0)
                adverse_selection += fill_lots * max(mid_after - mid_before, 0.0)
                quote, bid_queue, ask_queue = reset_quote(idx)
                crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
                quote_updates += 1
        elif event_type in {4, 5} and direction == -1 and str(quote["bid_state"]) in {
            "join_l1",
            "improve",
            "depth_visible",
        }:
            if str(quote["bid_state"]) == "improve":
                should_fill = True
            else:
                bid_queue -= max(size_lots, 0.0)
                exec_depletion += max(size_lots, 0.0)
                should_fill = bid_queue <= 0.0
            if should_fill:
                fill_lots = cfg.max_fill_lots
                bid_price = float(quote["bid_price"])
                cash -= fill_lots * bid_price
                inventory += fill_lots
                fills += 1
                bid_fills += 1
                spread_capture += fill_lots * max(mid_before - bid_price, 0.0)
                adverse_selection += fill_lots * max(mid_before - mid_after, 0.0)
                quote, bid_queue, ask_queue = reset_quote(idx)
                crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
                quote_updates += 1

        last_t = t

    horizon = float(max(times[-1], 1e-12))
    terminal_mid = float(mids[n - 1])
    terminal_wealth = (
        cash
        + inventory * terminal_mid
        - cfg.inventory_penalty * inventory_penalty
        - cfg.liquidation_penalty * abs(inventory)
    )
    side_horizon = max(2.0 * horizon, 1e-12)
    return {
        "ticker": ticker,
        "scenario": scenario,
        "policy": policy,
        "rho_hat": float(rho_hat),
        "rho_true": float(rho_true),
        "epsilon": float(epsilon),
        "levels": int(levels),
        "terminal_wealth": float(terminal_wealth),
        "final_inventory": float(inventory),
        "abs_inventory": float(abs(inventory)),
        "fills": int(fills),
        "bid_fills": int(bid_fills),
        "ask_fills": int(ask_fills),
        "fill_rate": float(fills / max(n, 1)),
        "spread_capture": float(spread_capture),
        "adverse_selection": float(adverse_selection),
        "inventory_penalty": float(inventory_penalty),
        "join_l1_side_time_frac": float(state_time["join_l1"] / side_horizon),
        "improve_side_time_frac": float(state_time["improve"] / side_horizon),
        "depth_visible_side_time_frac": float(state_time["depth_visible"] / side_horizon),
        "outside_depth_side_time_frac": float(state_time["outside_depth"] / side_horizon),
        "no_quote_side_time_frac": float(state_time["withdraw"] / side_horizon),
        "full_no_quote_time_frac": float(full_no_quote_time / max(horizon, 1e-12)),
        "mean_visible_depth_rank": float(depth_rank_time_weight / max(depth_rank_side_time, 1e-12)),
        "mean_bid_offset": float(offset_bid_sum / max(offset_side_time, 1e-12)),
        "mean_ask_offset": float(offset_ask_sum / max(offset_side_time, 1e-12)),
        "crossing_clamp_count": int(crossing_clamp_count),
        "queue_depletion_from_exec": float(exec_depletion),
        "queue_depletion_from_visible_depth": float(visible_depth_depletion),
        "quote_updates": int(quote_updates),
        "n_events": int(n),
        "horizon": horizon,
        "size_scale": float(size_scale),
    }


def evaluate_lobster_priority_depth_quote_policy(
    message: pd.DataFrame,
    orderbook: pd.DataFrame,
    *,
    ticker: str,
    scenario: str,
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policy: str,
    cfg: LobsterReplayConfig | None = None,
    params: PolicyParams | None = None,
) -> dict[str, float | int | str]:
    """Replay visible-depth quotes with message-level displayed priority.

    Existing displayed depth at the quote price is treated as ahead of our
    synthetic order. Later same-price limit orders are tracked by ``order_id``
    as behind us and do not deplete our queue position when cancelled or
    executed. Better-price orders are always ahead. Hidden liquidity and
    initial anonymous order IDs remain unobserved.
    """
    cfg = cfg or LobsterReplayConfig()
    params = params or PolicyParams()
    n = min(len(message), len(orderbook), cfg.max_events)
    if n < 2:
        raise ValueError("at least two synchronized LOBSTER rows are required")
    levels = _available_depth_levels(orderbook)
    if levels < 2:
        raise ValueError("priority depth replay requires at least two displayed book levels")
    msg = message.iloc[:n].reset_index(drop=True)
    book = orderbook.iloc[:n].reset_index(drop=True)
    times = msg["time"].to_numpy(float)
    times = times - times[0]
    mids = _mid_from_book(book)
    event_types = msg["event_type"].to_numpy(int)
    directions = msg["direction"].to_numpy(int)
    sizes = msg["size"].to_numpy(float)
    prices = msg["price"].to_numpy(float) * 1e-4
    order_ids = msg["order_id"].to_numpy()
    size_scale = _execution_size_scale(msg)

    cash = 0.0
    inventory = 0.0
    fills = 0
    bid_fills = 0
    ask_fills = 0
    spread_capture = 0.0
    adverse_selection = 0.0
    inventory_penalty = 0.0
    quote_updates = 0
    crossing_clamp_count = 0
    ahead_additions = 0.0
    ahead_depletion = 0.0
    behind_additions = 0.0
    behind_ignored_depletion = 0.0
    initial_ahead_lots = 0.0
    visible_quote_resets = 0
    min_visible_depth_rank = levels + 1
    max_visible_depth_rank = 0
    priority_queue_fills = 0
    priority_improve_fills = 0
    priority_queue_violation_count = 0
    priority_partial_fill_events = 0
    priority_residual_fill_lots = 0.0
    priority_zero_residual_fill_prevented = 0
    total_fill_lots = 0.0
    bid_fill_lots = 0.0
    ask_fill_lots = 0.0
    offset_bid_sum = 0.0
    offset_ask_sum = 0.0
    offset_side_time = 0.0
    depth_rank_side_time = 0.0
    depth_rank_time_weight = 0.0
    full_no_quote_time = 0.0
    state_time = {
        "join_l1": 0.0,
        "improve": 0.0,
        "depth_visible": 0.0,
        "outside_depth": 0.0,
        "withdraw": 0.0,
    }

    bid_behind: dict[object, float] = {}
    ask_behind: dict[object, float] = {}
    bid_remaining = 0.0
    ask_remaining = 0.0

    def reset_quote(row_idx: int) -> tuple[dict[str, float | int | str | bool], float, float]:
        nonlocal bid_behind, ask_behind, initial_ahead_lots, visible_quote_resets
        nonlocal min_visible_depth_rank, max_visible_depth_rank
        nonlocal bid_remaining, ask_remaining
        bid_behind = {}
        ask_behind = {}
        bid_offset, ask_offset, bid_active, ask_active = _policy_state(
            inventory, rho_hat, rho_true, epsilon, policy, cfg, params
        )
        bid1 = float(book.at[row_idx, "bid_price_1"]) * 1e-4
        ask1 = float(book.at[row_idx, "ask_price_1"]) * 1e-4
        mid = float(mids[row_idx])
        bid = _classify_depth_quote(
            "bid",
            mid - bid_offset,
            bid1,
            ask1,
            bid_active,
            book,
            row_idx,
            cfg,
            size_scale,
            levels,
        )
        ask = _classify_depth_quote(
            "ask",
            mid + ask_offset,
            bid1,
            ask1,
            ask_active,
            book,
            row_idx,
            cfg,
            size_scale,
            levels,
        )
        if str(bid["state"]) in {"join_l1", "depth_visible"}:
            bid_queue, bid_rank, _ = _depth_queue_ahead(
                book,
                row_idx,
                "bid",
                float(bid["price"]),
                cfg,
                size_scale,
                levels,
                same_level_fraction=cfg.priority_initial_queue_fraction,
                clip_queue=False,
            )
            bid_queue *= max(cfg.priority_queue_stress_multiplier, 0.0)
            if np.isfinite(bid_queue):
                initial_ahead_lots += max(float(bid_queue), 0.0)
                visible_quote_resets += 1
                if bid_rank > 0:
                    min_visible_depth_rank = min(min_visible_depth_rank, bid_rank)
                    max_visible_depth_rank = max(max_visible_depth_rank, bid_rank)
        else:
            bid_queue = float(bid["queue"])
            bid_rank = int(bid["depth_rank"])
        if str(ask["state"]) in {"join_l1", "depth_visible"}:
            ask_queue, ask_rank, _ = _depth_queue_ahead(
                book,
                row_idx,
                "ask",
                float(ask["price"]),
                cfg,
                size_scale,
                levels,
                same_level_fraction=cfg.priority_initial_queue_fraction,
                clip_queue=False,
            )
            ask_queue *= max(cfg.priority_queue_stress_multiplier, 0.0)
            if np.isfinite(ask_queue):
                initial_ahead_lots += max(float(ask_queue), 0.0)
                visible_quote_resets += 1
                if ask_rank > 0:
                    min_visible_depth_rank = min(min_visible_depth_rank, ask_rank)
                    max_visible_depth_rank = max(max_visible_depth_rank, ask_rank)
        else:
            ask_queue = float(ask["queue"])
            ask_rank = int(ask["depth_rank"])
        state: dict[str, float | int | str | bool] = {
            "bid_offset": bid_offset,
            "ask_offset": ask_offset,
            "bid_state": str(bid["state"]),
            "ask_state": str(ask["state"]),
            "bid_price": float(bid["price"]),
            "ask_price": float(ask["price"]),
            "bid_depth_rank": bid_rank,
            "ask_depth_rank": ask_rank,
            "bid_crossed": bool(bid["crossed"]),
            "ask_crossed": bool(ask["crossed"]),
        }
        bid_remaining = (
            float(cfg.max_fill_lots)
            if state["bid_state"] in {"join_l1", "improve", "depth_visible"}
            else 0.0
        )
        ask_remaining = (
            float(cfg.max_fill_lots)
            if state["ask_state"] in {"join_l1", "improve", "depth_visible"}
            else 0.0
        )
        return state, bid_queue, ask_queue

    quote, bid_queue, ask_queue = reset_quote(0)
    crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
    quote_updates += 1
    next_decision = cfg.decision_interval
    last_t = 0.0

    def update_priority_queue(
        side: str,
        event_type: int,
        direction: int,
        price: float,
        order_id: object,
        size_lots: float,
    ) -> float:
        nonlocal bid_queue, ask_queue, ahead_additions, ahead_depletion, behind_additions, behind_ignored_depletion
        state = str(quote[f"{side}_state"])
        if state not in {"join_l1", "depth_visible", "improve"}:
            return 0.0
        quote_price = float(quote[f"{side}_price"])
        behind = bid_behind if side == "bid" else ask_behind
        queue_val = bid_queue if side == "bid" else ask_queue
        residual_execution = 0.0
        is_same = _same_price(price, quote_price, cfg.tick_size)
        is_better = _better_price(side, price, quote_price, cfg.tick_size)
        if state == "improve":
            if event_type in {4, 5} and _message_side_for_execution(direction) == side and is_same:
                residual_execution = max(size_lots, 0.0)
            return residual_execution
        if event_type == 1 and _message_side_for_resting_order(event_type, direction) == side:
            if is_same:
                behind[order_id] = behind.get(order_id, 0.0) + size_lots
                behind_additions += size_lots
            elif is_better:
                queue_val += size_lots
                ahead_additions += size_lots
        elif event_type in {2, 3} and _message_side_for_resting_order(event_type, direction) == side:
            if is_same and order_id in behind:
                removed = min(size_lots, behind.get(order_id, 0.0))
                behind[order_id] = max(behind.get(order_id, 0.0) - removed, 0.0)
                if behind[order_id] <= 1e-12:
                    behind.pop(order_id, None)
                behind_ignored_depletion += removed
            elif is_same or is_better:
                ahead_before = max(queue_val, 0.0)
                queue_val = max(queue_val - size_lots, 0.0)
                ahead_depletion += min(size_lots, ahead_before)
        elif event_type in {4, 5} and _message_side_for_execution(direction) == side:
            if is_same and order_id in behind:
                removed = min(size_lots, behind.get(order_id, 0.0))
                behind[order_id] = max(behind.get(order_id, 0.0) - removed, 0.0)
                if behind[order_id] <= 1e-12:
                    behind.pop(order_id, None)
                behind_ignored_depletion += removed
            elif is_same or is_better:
                ahead_before = max(queue_val, 0.0)
                queue_val = max(queue_val - size_lots, 0.0)
                ahead_depletion += min(size_lots, ahead_before)
                if is_same:
                    residual_execution = max(size_lots - ahead_before, 0.0)
        if side == "bid":
            bid_queue = queue_val
        else:
            ask_queue = queue_val
        return residual_execution

    for idx in range(1, n):
        t = float(max(times[idx], last_t))
        dt = t - last_t
        inventory_penalty += inventory * inventory * dt
        for side in ("bid", "ask"):
            state = str(quote[f"{side}_state"])
            state_time[state] += dt
            rank = int(quote[f"{side}_depth_rank"])
            if rank > 0:
                depth_rank_time_weight += dt * rank
                depth_rank_side_time += dt
        full_no_quote_time += dt * (
            1.0 if quote["bid_state"] == "withdraw" and quote["ask_state"] == "withdraw" else 0.0
        )
        offset_bid_sum += float(quote["bid_offset"]) * dt
        offset_ask_sum += float(quote["ask_offset"]) * dt
        offset_side_time += dt

        if t >= next_decision - 1e-12:
            quote, bid_queue, ask_queue = reset_quote(idx - 1)
            crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
            next_decision = (np.floor(t / cfg.decision_interval) + 1.0) * cfg.decision_interval
            quote_updates += 1

        event_type = int(event_types[idx])
        direction = int(directions[idx])
        event_price = float(prices[idx])
        order_id = order_ids[idx]
        size_lots = float(sizes[idx]) / max(size_scale, 1.0)
        mid_before = float(mids[idx - 1])
        mid_after = float(mids[idx])

        ask_residual_execution = update_priority_queue("ask", event_type, direction, event_price, order_id, size_lots)
        bid_residual_execution = update_priority_queue("bid", event_type, direction, event_price, order_id, size_lots)

        if (
            event_type in {4, 5}
            and _message_side_for_execution(direction) == "ask"
            and str(quote["ask_state"]) in {"join_l1", "improve", "depth_visible"}
            and _same_price(event_price, float(quote["ask_price"]), cfg.tick_size)
        ):
            fill_lots = min(max(ask_residual_execution, 0.0), max(ask_remaining, 0.0))
            if fill_lots > 1e-12:
                if fill_lots < ask_remaining - 1e-12:
                    priority_partial_fill_events += 1
                priority_residual_fill_lots += fill_lots
                total_fill_lots += fill_lots
                ask_fill_lots += fill_lots
            elif str(quote["ask_state"]) != "improve" and ask_queue <= 1e-12:
                priority_zero_residual_fill_prevented += 1
            if fill_lots > 1e-12 and str(quote["ask_state"]) == "improve":
                priority_improve_fills += 1
            elif fill_lots > 1e-12 and ask_queue <= 1e-12:
                priority_queue_fills += 1
            elif fill_lots > 1e-12:
                priority_queue_violation_count += 1
            if fill_lots > 1e-12:
                ask_price = float(quote["ask_price"])
                cash += fill_lots * ask_price
                inventory -= fill_lots
                fills += 1
                ask_fills += 1
                ask_remaining = max(ask_remaining - fill_lots, 0.0)
                spread_capture += fill_lots * max(ask_price - mid_before, 0.0)
                adverse_selection += fill_lots * max(mid_after - mid_before, 0.0)
                if ask_remaining <= 1e-12:
                    quote, bid_queue, ask_queue = reset_quote(idx)
                    crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
                    quote_updates += 1
        elif (
            event_type in {4, 5}
            and _message_side_for_execution(direction) == "bid"
            and str(quote["bid_state"]) in {"join_l1", "improve", "depth_visible"}
            and _same_price(event_price, float(quote["bid_price"]), cfg.tick_size)
        ):
            fill_lots = min(max(bid_residual_execution, 0.0), max(bid_remaining, 0.0))
            if fill_lots > 1e-12:
                if fill_lots < bid_remaining - 1e-12:
                    priority_partial_fill_events += 1
                priority_residual_fill_lots += fill_lots
                total_fill_lots += fill_lots
                bid_fill_lots += fill_lots
            elif str(quote["bid_state"]) != "improve" and bid_queue <= 1e-12:
                priority_zero_residual_fill_prevented += 1
            if fill_lots > 1e-12 and str(quote["bid_state"]) == "improve":
                priority_improve_fills += 1
            elif fill_lots > 1e-12 and bid_queue <= 1e-12:
                priority_queue_fills += 1
            elif fill_lots > 1e-12:
                priority_queue_violation_count += 1
            if fill_lots > 1e-12:
                bid_price = float(quote["bid_price"])
                cash -= fill_lots * bid_price
                inventory += fill_lots
                fills += 1
                bid_fills += 1
                bid_remaining = max(bid_remaining - fill_lots, 0.0)
                spread_capture += fill_lots * max(mid_before - bid_price, 0.0)
                adverse_selection += fill_lots * max(mid_before - mid_after, 0.0)
                if bid_remaining <= 1e-12:
                    quote, bid_queue, ask_queue = reset_quote(idx)
                    crossing_clamp_count += int(bool(quote["bid_crossed"])) + int(bool(quote["ask_crossed"]))
                    quote_updates += 1

        last_t = t

    horizon = float(max(times[-1], 1e-12))
    terminal_mid = float(mids[n - 1])
    terminal_wealth = (
        cash
        + inventory * terminal_mid
        - cfg.inventory_penalty * inventory_penalty
        - cfg.liquidation_penalty * abs(inventory)
    )
    side_horizon = max(2.0 * horizon, 1e-12)
    return {
        "ticker": ticker,
        "scenario": scenario,
        "policy": policy,
        "rho_hat": float(rho_hat),
        "rho_true": float(rho_true),
        "epsilon": float(epsilon),
        "levels": int(levels),
        "terminal_wealth": float(terminal_wealth),
        "final_inventory": float(inventory),
        "abs_inventory": float(abs(inventory)),
        "fills": int(fills),
        "bid_fills": int(bid_fills),
        "ask_fills": int(ask_fills),
        "total_fill_lots": float(total_fill_lots),
        "bid_fill_lots": float(bid_fill_lots),
        "ask_fill_lots": float(ask_fill_lots),
        "fill_rate": float(fills / max(n, 1)),
        "spread_capture": float(spread_capture),
        "adverse_selection": float(adverse_selection),
        "inventory_penalty": float(inventory_penalty),
        "join_l1_side_time_frac": float(state_time["join_l1"] / side_horizon),
        "improve_side_time_frac": float(state_time["improve"] / side_horizon),
        "depth_visible_side_time_frac": float(state_time["depth_visible"] / side_horizon),
        "outside_depth_side_time_frac": float(state_time["outside_depth"] / side_horizon),
        "no_quote_side_time_frac": float(state_time["withdraw"] / side_horizon),
        "full_no_quote_time_frac": float(full_no_quote_time / max(horizon, 1e-12)),
        "mean_visible_depth_rank": float(depth_rank_time_weight / max(depth_rank_side_time, 1e-12)),
        "mean_bid_offset": float(offset_bid_sum / max(offset_side_time, 1e-12)),
        "mean_ask_offset": float(offset_ask_sum / max(offset_side_time, 1e-12)),
        "crossing_clamp_count": int(crossing_clamp_count),
        "priority_ahead_additions": float(ahead_additions),
        "priority_ahead_depletion": float(ahead_depletion),
        "priority_behind_additions": float(behind_additions),
        "priority_behind_depletion_ignored": float(behind_ignored_depletion),
        "priority_initial_ahead_lots": float(initial_ahead_lots),
        "priority_visible_quote_resets": int(visible_quote_resets),
        "priority_mean_initial_ahead_lots": float(initial_ahead_lots / max(visible_quote_resets, 1)),
        "priority_visible_levels_used": int(levels),
        "priority_min_visible_depth_rank": int(min_visible_depth_rank if visible_quote_resets else 0),
        "priority_max_visible_depth_rank": int(max_visible_depth_rank),
        "priority_queue_fills": int(priority_queue_fills),
        "priority_improve_fills": int(priority_improve_fills),
        "priority_queue_violation_count": int(priority_queue_violation_count),
        "priority_partial_fill_events": int(priority_partial_fill_events),
        "priority_residual_fill_lots": float(priority_residual_fill_lots),
        "priority_zero_residual_fill_prevented": int(priority_zero_residual_fill_prevented),
        "priority_initial_queue_fraction": float(cfg.priority_initial_queue_fraction),
        "priority_queue_stress_multiplier": float(cfg.priority_queue_stress_multiplier),
        "quote_updates": int(quote_updates),
        "n_events": int(n),
        "horizon": horizon,
        "size_scale": float(size_scale),
    }


def _lobster_paths(data_root: Path, ticker: str, levels: int) -> tuple[Path, Path]:
    folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
    message_matches = sorted(folder.glob(f"{ticker}_2012-06-21_*_*_message_{levels}.csv"))
    orderbook_matches = sorted(folder.glob(f"{ticker}_2012-06-21_*_*_orderbook_{levels}.csv"))
    if message_matches and orderbook_matches:
        return message_matches[0], orderbook_matches[0]
    base = f"{ticker}_2012-06-21_34200000_57600000"
    return folder / f"{base}_message_{levels}.csv", folder / f"{base}_orderbook_{levels}.csv"


def _rho_by_ticker(results_root: Path, tickers: tuple[str, ...]) -> dict[str, float]:
    table = results_root / "tables" / "lobster_side_marked_hawkes_multivariate_best.csv"
    if not table.exists():
        return {ticker: 0.60 for ticker in tickers}
    df = pd.read_csv(table)
    return {
        ticker: float(df.loc[df["ticker"] == ticker, "spectral_radius"].iloc[0])
        if ticker in set(df["ticker"])
        else 0.60
        for ticker in tickers
    }


def run_lobster_top_of_book_replay(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    policies: tuple[str, ...] = ("as_poisson", "nominal_hawkes", "robust_gamma", "robust_gamma_abs", "liquidity_guard"),
    epsilon: float = 0.02,
    stressed_rho: float = 0.97,
    cfg: LobsterReplayConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run public LOBSTER top-of-book replay over calibrated and stressed rhos."""
    cfg = cfg or LobsterReplayConfig()
    rho_lookup = _rho_by_ticker(results_root, tickers)
    rows: list[dict[str, float | int | str]] = []
    for ticker in tickers:
        msg_path, book_path = _lobster_paths(data_root, ticker, levels)
        if not msg_path.exists() or not book_path.exists():
            raise FileNotFoundError(f"missing LOBSTER files for {ticker}: {msg_path}, {book_path}")
        message = load_lobster_message(msg_path)
        orderbook = load_lobster_orderbook(book_path, levels=levels)
        scenarios = {
            "calibrated_side_gamma": rho_lookup[ticker],
            "near_critical_stress": stressed_rho,
        }
        for scenario, rho in scenarios.items():
            for policy in policies:
                rows.append(
                    evaluate_lobster_top_of_book_policy(
                        message,
                        orderbook,
                        ticker=ticker,
                        scenario=scenario,
                        rho_hat=rho,
                        rho_true=rho,
                        epsilon=epsilon,
                        policy=policy,
                        cfg=cfg,
                    )
                )
    raw = pd.DataFrame(rows)
    nominal = raw[raw["policy"] == "nominal_hawkes"][
        ["ticker", "scenario", "terminal_wealth"]
    ].rename(columns={"terminal_wealth": "nominal_terminal_wealth"})
    raw = raw.merge(nominal, on=["ticker", "scenario"], how="left")
    raw["wealth_diff_vs_nominal"] = raw["terminal_wealth"] - raw["nominal_terminal_wealth"]
    summary = (
        raw.groupby(["scenario", "policy"], as_index=False)
        .agg(
            tickers=("ticker", "nunique"),
            mean_terminal_wealth=("terminal_wealth", "mean"),
            mean_wealth_diff_vs_nominal=("wealth_diff_vs_nominal", "mean"),
            mean_abs_inventory=("abs_inventory", "mean"),
            mean_fills=("fills", "mean"),
            mean_fill_rate=("fill_rate", "mean"),
            mean_no_quote_side_time_frac=("no_quote_side_time_frac", "mean"),
            mean_full_no_quote_time_frac=("full_no_quote_time_frac", "mean"),
            mean_spread_capture=("spread_capture", "mean"),
            mean_adverse_selection=("adverse_selection", "mean"),
        )
    )
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    raw.to_csv(results_root / "raw" / "lobster_top_of_book_replay.csv", index=False)
    summary.to_csv(results_root / "tables" / "lobster_top_of_book_replay_summary.csv", index=False)
    return raw, summary


def run_lobster_l1_quote_replay(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    policies: tuple[str, ...] = ("as_poisson", "nominal_hawkes", "robust_gamma", "robust_gamma_abs", "liquidity_guard"),
    epsilon: float = 0.02,
    stressed_rho: float = 0.97,
    cfg: LobsterReplayConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run L1 offset-aware replay over calibrated and stressed rhos."""
    cfg = cfg or LobsterReplayConfig()
    rho_lookup = _rho_by_ticker(results_root, tickers)
    rows: list[dict[str, float | int | str]] = []
    for ticker in tickers:
        msg_path, book_path = _lobster_paths(data_root, ticker, levels)
        if not msg_path.exists() or not book_path.exists():
            raise FileNotFoundError(f"missing LOBSTER files for {ticker}: {msg_path}, {book_path}")
        message = load_lobster_message(msg_path)
        orderbook = load_lobster_orderbook(book_path, levels=levels)
        scenarios = {
            "calibrated_side_gamma": rho_lookup[ticker],
            "near_critical_stress": stressed_rho,
        }
        for scenario, rho in scenarios.items():
            for policy in policies:
                rows.append(
                    evaluate_lobster_l1_quote_policy(
                        message,
                        orderbook,
                        ticker=ticker,
                        scenario=scenario,
                        rho_hat=rho,
                        rho_true=rho,
                        epsilon=epsilon,
                        policy=policy,
                        cfg=cfg,
                    )
                )
    raw = pd.DataFrame(rows)
    nominal = raw[raw["policy"] == "nominal_hawkes"][
        ["ticker", "scenario", "terminal_wealth"]
    ].rename(columns={"terminal_wealth": "nominal_terminal_wealth"})
    raw = raw.merge(nominal, on=["ticker", "scenario"], how="left")
    raw["wealth_diff_vs_nominal"] = raw["terminal_wealth"] - raw["nominal_terminal_wealth"]
    summary = (
        raw.groupby(["scenario", "policy"], as_index=False)
        .agg(
            tickers=("ticker", "nunique"),
            mean_terminal_wealth=("terminal_wealth", "mean"),
            mean_wealth_diff_vs_nominal=("wealth_diff_vs_nominal", "mean"),
            mean_abs_inventory=("abs_inventory", "mean"),
            mean_fills=("fills", "mean"),
            mean_fill_rate=("fill_rate", "mean"),
            mean_join_side_time_frac=("join_side_time_frac", "mean"),
            mean_improve_side_time_frac=("improve_side_time_frac", "mean"),
            mean_away_side_time_frac=("away_side_time_frac", "mean"),
            mean_no_quote_side_time_frac=("no_quote_side_time_frac", "mean"),
            mean_full_no_quote_time_frac=("full_no_quote_time_frac", "mean"),
            mean_bid_offset=("mean_bid_offset", "mean"),
            mean_ask_offset=("mean_ask_offset", "mean"),
            mean_crossing_clamp_count=("crossing_clamp_count", "mean"),
            mean_queue_depletion_from_exec=("queue_depletion_from_exec", "mean"),
            mean_queue_depletion_from_visible_size_drop=("queue_depletion_from_visible_size_drop", "mean"),
            mean_spread_capture=("spread_capture", "mean"),
            mean_adverse_selection=("adverse_selection", "mean"),
        )
    )
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    raw.to_csv(results_root / "raw" / "lobster_l1_quote_replay.csv", index=False)
    summary.to_csv(results_root / "tables" / "lobster_l1_quote_replay_summary.csv", index=False)
    return raw, summary


def run_lobster_depth_quote_replay(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 10,
    policies: tuple[str, ...] = ("as_poisson", "nominal_hawkes", "robust_gamma", "robust_gamma_abs", "liquidity_guard"),
    epsilon: float = 0.02,
    stressed_rho: float = 0.97,
    cfg: LobsterReplayConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run depth-aware quote replay over calibrated and stressed rhos."""
    cfg = cfg or LobsterReplayConfig()
    rho_lookup = _rho_by_ticker(results_root, tickers)
    rows: list[dict[str, float | int | str]] = []
    for ticker in tickers:
        msg_path, book_path = _lobster_paths(data_root, ticker, levels)
        if not msg_path.exists() or not book_path.exists():
            raise FileNotFoundError(f"missing LOBSTER files for {ticker}: {msg_path}, {book_path}")
        message = load_lobster_message(msg_path)
        orderbook = load_lobster_orderbook(book_path, levels=levels)
        scenarios = {
            "calibrated_side_gamma": rho_lookup[ticker],
            "near_critical_stress": stressed_rho,
        }
        for scenario, rho in scenarios.items():
            for policy in policies:
                rows.append(
                    evaluate_lobster_depth_quote_policy(
                        message,
                        orderbook,
                        ticker=ticker,
                        scenario=scenario,
                        rho_hat=rho,
                        rho_true=rho,
                        epsilon=epsilon,
                        policy=policy,
                        cfg=cfg,
                    )
                )
    raw = pd.DataFrame(rows)
    nominal = raw[raw["policy"] == "nominal_hawkes"][
        ["ticker", "scenario", "terminal_wealth"]
    ].rename(columns={"terminal_wealth": "nominal_terminal_wealth"})
    raw = raw.merge(nominal, on=["ticker", "scenario"], how="left")
    raw["wealth_diff_vs_nominal"] = raw["terminal_wealth"] - raw["nominal_terminal_wealth"]
    summary = (
        raw.groupby(["scenario", "policy"], as_index=False)
        .agg(
            tickers=("ticker", "nunique"),
            levels=("levels", "max"),
            mean_terminal_wealth=("terminal_wealth", "mean"),
            mean_wealth_diff_vs_nominal=("wealth_diff_vs_nominal", "mean"),
            mean_abs_inventory=("abs_inventory", "mean"),
            mean_fills=("fills", "mean"),
            mean_fill_rate=("fill_rate", "mean"),
            mean_join_l1_side_time_frac=("join_l1_side_time_frac", "mean"),
            mean_improve_side_time_frac=("improve_side_time_frac", "mean"),
            mean_depth_visible_side_time_frac=("depth_visible_side_time_frac", "mean"),
            mean_outside_depth_side_time_frac=("outside_depth_side_time_frac", "mean"),
            mean_no_quote_side_time_frac=("no_quote_side_time_frac", "mean"),
            mean_full_no_quote_time_frac=("full_no_quote_time_frac", "mean"),
            mean_visible_depth_rank=("mean_visible_depth_rank", "mean"),
            mean_bid_offset=("mean_bid_offset", "mean"),
            mean_ask_offset=("mean_ask_offset", "mean"),
            mean_crossing_clamp_count=("crossing_clamp_count", "mean"),
            mean_queue_depletion_from_exec=("queue_depletion_from_exec", "mean"),
            mean_queue_depletion_from_visible_depth=("queue_depletion_from_visible_depth", "mean"),
            mean_spread_capture=("spread_capture", "mean"),
            mean_adverse_selection=("adverse_selection", "mean"),
        )
    )
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    raw.to_csv(results_root / "raw" / "lobster_depth_quote_replay.csv", index=False)
    summary.to_csv(results_root / "tables" / "lobster_depth_quote_replay_summary.csv", index=False)
    return raw, summary


def run_lobster_priority_depth_quote_replay(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 10,
    policies: tuple[str, ...] = ("as_poisson", "nominal_hawkes", "robust_gamma", "robust_gamma_abs", "liquidity_guard"),
    epsilon: float = 0.02,
    stressed_rho: float = 0.97,
    cfg: LobsterReplayConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run order-id priority-aware depth replay over calibrated and stressed rhos."""
    cfg = cfg or LobsterReplayConfig()
    rho_lookup = _rho_by_ticker(results_root, tickers)
    rows: list[dict[str, float | int | str]] = []
    for ticker in tickers:
        msg_path, book_path = _lobster_paths(data_root, ticker, levels)
        if not msg_path.exists() or not book_path.exists():
            raise FileNotFoundError(f"missing LOBSTER files for {ticker}: {msg_path}, {book_path}")
        message = load_lobster_message(msg_path)
        orderbook = load_lobster_orderbook(book_path, levels=levels)
        scenarios = {
            "calibrated_side_gamma": rho_lookup[ticker],
            "near_critical_stress": stressed_rho,
        }
        for scenario, rho in scenarios.items():
            for policy in policies:
                rows.append(
                    evaluate_lobster_priority_depth_quote_policy(
                        message,
                        orderbook,
                        ticker=ticker,
                        scenario=scenario,
                        rho_hat=rho,
                        rho_true=rho,
                        epsilon=epsilon,
                        policy=policy,
                        cfg=cfg,
                    )
                )
    raw = pd.DataFrame(rows)
    nominal = raw[raw["policy"] == "nominal_hawkes"][
        ["ticker", "scenario", "terminal_wealth"]
    ].rename(columns={"terminal_wealth": "nominal_terminal_wealth"})
    raw = raw.merge(nominal, on=["ticker", "scenario"], how="left")
    raw["wealth_diff_vs_nominal"] = raw["terminal_wealth"] - raw["nominal_terminal_wealth"]
    summary = (
        raw.groupby(["scenario", "policy"], as_index=False)
        .agg(
            tickers=("ticker", "nunique"),
            levels=("levels", "max"),
            mean_terminal_wealth=("terminal_wealth", "mean"),
            mean_wealth_diff_vs_nominal=("wealth_diff_vs_nominal", "mean"),
            mean_abs_inventory=("abs_inventory", "mean"),
            mean_fills=("fills", "mean"),
            mean_fill_rate=("fill_rate", "mean"),
            mean_join_l1_side_time_frac=("join_l1_side_time_frac", "mean"),
            mean_improve_side_time_frac=("improve_side_time_frac", "mean"),
            mean_depth_visible_side_time_frac=("depth_visible_side_time_frac", "mean"),
            mean_outside_depth_side_time_frac=("outside_depth_side_time_frac", "mean"),
            mean_no_quote_side_time_frac=("no_quote_side_time_frac", "mean"),
            mean_full_no_quote_time_frac=("full_no_quote_time_frac", "mean"),
            mean_visible_depth_rank=("mean_visible_depth_rank", "mean"),
            mean_bid_offset=("mean_bid_offset", "mean"),
            mean_ask_offset=("mean_ask_offset", "mean"),
            mean_crossing_clamp_count=("crossing_clamp_count", "mean"),
            mean_total_fill_lots=("total_fill_lots", "mean"),
            mean_priority_ahead_additions=("priority_ahead_additions", "mean"),
            mean_priority_ahead_depletion=("priority_ahead_depletion", "mean"),
            mean_priority_behind_additions=("priority_behind_additions", "mean"),
            mean_priority_behind_depletion_ignored=("priority_behind_depletion_ignored", "mean"),
            mean_priority_initial_ahead_lots=("priority_initial_ahead_lots", "mean"),
            mean_priority_visible_quote_resets=("priority_visible_quote_resets", "mean"),
            mean_priority_mean_initial_ahead_lots=("priority_mean_initial_ahead_lots", "mean"),
            max_priority_visible_levels_used=("priority_visible_levels_used", "max"),
            min_priority_visible_depth_rank=("priority_min_visible_depth_rank", "min"),
            max_priority_visible_depth_rank=("priority_max_visible_depth_rank", "max"),
            mean_priority_queue_fills=("priority_queue_fills", "mean"),
            mean_priority_improve_fills=("priority_improve_fills", "mean"),
            max_priority_queue_violation_count=("priority_queue_violation_count", "max"),
            mean_priority_partial_fill_events=("priority_partial_fill_events", "mean"),
            mean_priority_residual_fill_lots=("priority_residual_fill_lots", "mean"),
            max_priority_zero_residual_fill_prevented=("priority_zero_residual_fill_prevented", "max"),
            mean_spread_capture=("spread_capture", "mean"),
            mean_adverse_selection=("adverse_selection", "mean"),
        )
    )
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    raw.to_csv(results_root / "raw" / "lobster_priority_depth_quote_replay.csv", index=False)
    summary.to_csv(results_root / "tables" / "lobster_priority_depth_quote_replay_summary.csv", index=False)
    return raw, summary


def run_lobster_priority_depth_sensitivity(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 10,
    policies: tuple[str, ...] = ("nominal_hawkes",),
    initial_queue_fractions: tuple[float, ...] = (0.0, 0.5, 1.0),
    queue_stress_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0),
    epsilon: float = 0.02,
    stressed_rho: float = 0.97,
    cfg: LobsterReplayConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ablate public-data priority assumptions in the level-depth replay."""
    cfg = cfg or LobsterReplayConfig()
    rho_lookup = _rho_by_ticker(results_root, tickers)
    rows: list[dict[str, float | int | str]] = []
    for ticker in tickers:
        msg_path, book_path = _lobster_paths(data_root, ticker, levels)
        if not msg_path.exists() or not book_path.exists():
            raise FileNotFoundError(f"missing LOBSTER files for {ticker}: {msg_path}, {book_path}")
        message = load_lobster_message(msg_path)
        orderbook = load_lobster_orderbook(book_path, levels=levels)
        scenarios = {
            "calibrated_side_gamma": rho_lookup[ticker],
            "near_critical_stress": stressed_rho,
        }
        for initial_fraction in initial_queue_fractions:
            for queue_stress_multiplier in queue_stress_multipliers:
                scenario_cfg = replace(
                    cfg,
                    priority_initial_queue_fraction=float(initial_fraction),
                    priority_queue_stress_multiplier=float(queue_stress_multiplier),
                )
                for scenario, rho in scenarios.items():
                    for policy in policies:
                        rows.append(
                            evaluate_lobster_priority_depth_quote_policy(
                                message,
                                orderbook,
                                ticker=ticker,
                                scenario=scenario,
                                rho_hat=rho,
                                rho_true=rho,
                                epsilon=epsilon,
                                policy=policy,
                                cfg=scenario_cfg,
                            )
                        )
    raw = pd.DataFrame(rows)
    summary = (
        raw.groupby(
            [
                "scenario",
                "policy",
                "priority_initial_queue_fraction",
                "priority_queue_stress_multiplier",
            ],
            as_index=False,
        )
        .agg(
            tickers=("ticker", "nunique"),
            levels=("levels", "max"),
            mean_terminal_wealth=("terminal_wealth", "mean"),
            mean_abs_inventory=("abs_inventory", "mean"),
            mean_fills=("fills", "mean"),
            mean_total_fill_lots=("total_fill_lots", "mean"),
            mean_fill_rate=("fill_rate", "mean"),
            mean_join_l1_side_time_frac=("join_l1_side_time_frac", "mean"),
            mean_improve_side_time_frac=("improve_side_time_frac", "mean"),
            mean_depth_visible_side_time_frac=("depth_visible_side_time_frac", "mean"),
            mean_no_quote_side_time_frac=("no_quote_side_time_frac", "mean"),
            mean_visible_depth_rank=("mean_visible_depth_rank", "mean"),
            mean_priority_ahead_additions=("priority_ahead_additions", "mean"),
            mean_priority_ahead_depletion=("priority_ahead_depletion", "mean"),
            mean_priority_behind_additions=("priority_behind_additions", "mean"),
            mean_priority_behind_depletion_ignored=("priority_behind_depletion_ignored", "mean"),
            mean_priority_initial_ahead_lots=("priority_initial_ahead_lots", "mean"),
            mean_priority_visible_quote_resets=("priority_visible_quote_resets", "mean"),
            mean_priority_mean_initial_ahead_lots=("priority_mean_initial_ahead_lots", "mean"),
            max_priority_visible_levels_used=("priority_visible_levels_used", "max"),
            min_priority_visible_depth_rank=("priority_min_visible_depth_rank", "min"),
            max_priority_visible_depth_rank=("priority_max_visible_depth_rank", "max"),
            mean_priority_queue_fills=("priority_queue_fills", "mean"),
            mean_priority_improve_fills=("priority_improve_fills", "mean"),
            max_priority_queue_violation_count=("priority_queue_violation_count", "max"),
            mean_priority_partial_fill_events=("priority_partial_fill_events", "mean"),
            mean_priority_residual_fill_lots=("priority_residual_fill_lots", "mean"),
            max_priority_zero_residual_fill_prevented=("priority_zero_residual_fill_prevented", "max"),
        )
    )
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    raw.to_csv(results_root / "raw" / "lobster_priority_depth_sensitivity.csv", index=False)
    summary.to_csv(results_root / "tables" / "lobster_priority_depth_sensitivity_summary.csv", index=False)
    return raw, summary
