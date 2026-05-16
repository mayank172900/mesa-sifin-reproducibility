#!/usr/bin/env python3
"""Run priority replay on the deepest public LOBSTER samples available locally."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from mesa.empirical import load_lobster_message, load_lobster_orderbook
from mesa.lobster_replay import (
    LobsterReplayConfig,
    _lobster_paths,
    _rho_by_ticker,
    evaluate_lobster_priority_depth_quote_policy,
)


def _summary(raw: pd.DataFrame) -> pd.DataFrame:
    return (
        raw.groupby(["scenario", "policy"], as_index=False)
        .agg(
            tickers=("ticker", "nunique"),
            levels=("levels", "max"),
            mean_terminal_wealth=("terminal_wealth", "mean"),
            mean_abs_inventory=("abs_inventory", "mean"),
            mean_fills=("fills", "mean"),
            mean_total_fill_lots=("total_fill_lots", "mean"),
            mean_fill_rate=("fill_rate", "mean"),
            mean_depth_visible_side_time_frac=("depth_visible_side_time_frac", "mean"),
            mean_no_quote_side_time_frac=("no_quote_side_time_frac", "mean"),
            mean_visible_depth_rank=("mean_visible_depth_rank", "mean"),
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/raw/lobster")
    parser.add_argument("--results", default="results")
    parser.add_argument("--tickers", nargs="+", default=["AAPL", "MSFT"])
    parser.add_argument("--levels", type=int, default=50)
    parser.add_argument("--max-events", type=int, default=200_000)
    parser.add_argument("--epsilon", type=float, default=0.02)
    parser.add_argument("--stressed-rho", type=float, default=0.97)
    args = parser.parse_args()

    data_root = Path(args.data_root)
    results_root = Path(args.results)
    cfg = LobsterReplayConfig(max_events=args.max_events)
    rho_lookup = _rho_by_ticker(results_root, tuple(args.tickers))
    policies = ("as_poisson", "nominal_hawkes", "robust_gamma", "robust_gamma_abs", "liquidity_guard")
    rows: list[dict[str, float | int | str]] = []
    for ticker in args.tickers:
        msg_path, book_path = _lobster_paths(data_root, ticker, args.levels)
        if not msg_path.exists() or not book_path.exists():
            raise FileNotFoundError(f"missing deepest public LOBSTER files for {ticker}: {msg_path}, {book_path}")
        message = load_lobster_message(msg_path)
        orderbook = load_lobster_orderbook(book_path, levels=args.levels)
        scenarios = {
            "calibrated_side_gamma": rho_lookup.get(ticker, 0.60),
            "near_critical_stress": args.stressed_rho,
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
                        epsilon=args.epsilon,
                        policy=policy,
                        cfg=cfg,
                    )
                )
    raw = pd.DataFrame(rows)
    summary = _summary(raw)
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    raw.to_csv(results_root / "raw" / "lobster_deepest_public_priority_replay.csv", index=False)
    summary.to_csv(results_root / "tables" / "lobster_deepest_public_priority_replay_summary.csv", index=False)
    print(summary.round(6).to_string(index=False))


if __name__ == "__main__":
    main()
