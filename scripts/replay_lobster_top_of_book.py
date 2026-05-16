#!/usr/bin/env python3
"""Run top-of-book replay diagnostics on public LOBSTER samples."""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.lobster_replay import (
    LobsterReplayConfig,
    run_lobster_depth_quote_replay,
    run_lobster_l1_quote_replay,
    run_lobster_priority_depth_sensitivity,
    run_lobster_priority_depth_quote_replay,
    run_lobster_top_of_book_replay,
)
from mesa.plotting import (
    save_lobster_depth_quote_replay_plot,
    save_lobster_l1_quote_replay_plot,
    save_lobster_priority_depth_sensitivity_plot,
    save_lobster_priority_depth_quote_replay_plot,
    save_lobster_top_of_book_replay_plot,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/raw/lobster")
    parser.add_argument("--results", default="results")
    parser.add_argument("--max-events", type=int, default=80_000)
    parser.add_argument("--epsilon", type=float, default=0.02)
    parser.add_argument("--stressed-rho", type=float, default=0.97)
    parser.add_argument(
        "--mode",
        choices=[
            "top-of-book",
            "l1-quote",
            "depth-quote",
            "depth-priority",
            "depth-priority-sensitivity",
            "both",
            "all",
        ],
        default="top-of-book",
    )
    parser.add_argument("--levels", type=int, default=1)
    parser.add_argument("--tick-size", type=float, default=0.01)
    parser.add_argument("--visible-cancel-depletion-fraction", type=float, default=0.25)
    args = parser.parse_args()
    results = Path(args.results)
    cfg = LobsterReplayConfig(
        max_events=args.max_events,
        tick_size=args.tick_size,
        visible_cancel_depletion_fraction=args.visible_cancel_depletion_fraction,
    )
    if args.mode in {"top-of-book", "both", "all"}:
        _, summary = run_lobster_top_of_book_replay(
            data_root=Path(args.data_root),
            results_root=results,
            levels=args.levels,
            epsilon=args.epsilon,
            stressed_rho=args.stressed_rho,
            cfg=cfg,
        )
        save_lobster_top_of_book_replay_plot(results)
        print("\nTop-of-book replay")
        print(summary.round(6).to_string(index=False))
    if args.mode in {"l1-quote", "both", "all"}:
        _, summary = run_lobster_l1_quote_replay(
            data_root=Path(args.data_root),
            results_root=results,
            levels=args.levels,
            epsilon=args.epsilon,
            stressed_rho=args.stressed_rho,
            cfg=cfg,
        )
        save_lobster_l1_quote_replay_plot(results)
        print("\nL1 quote replay")
        print(summary.round(6).to_string(index=False))
    if args.mode in {"depth-quote", "all"}:
        depth_levels = max(args.levels, 2)
        _, summary = run_lobster_depth_quote_replay(
            data_root=Path(args.data_root),
            results_root=results,
            levels=depth_levels,
            epsilon=args.epsilon,
            stressed_rho=args.stressed_rho,
            cfg=cfg,
        )
        save_lobster_depth_quote_replay_plot(results)
        print(f"\nDepth quote replay (levels={depth_levels})")
        print(summary.round(6).to_string(index=False))
    if args.mode in {"depth-priority", "all"}:
        depth_levels = max(args.levels, 2)
        _, summary = run_lobster_priority_depth_quote_replay(
            data_root=Path(args.data_root),
            results_root=results,
            levels=depth_levels,
            epsilon=args.epsilon,
            stressed_rho=args.stressed_rho,
            cfg=cfg,
        )
        save_lobster_priority_depth_quote_replay_plot(results)
        print(f"\nPriority depth quote replay (levels={depth_levels})")
        print(summary.round(6).to_string(index=False))
    if args.mode in {"depth-priority-sensitivity", "all"}:
        depth_levels = max(args.levels, 2)
        _, summary = run_lobster_priority_depth_sensitivity(
            data_root=Path(args.data_root),
            results_root=results,
            levels=depth_levels,
            epsilon=args.epsilon,
            stressed_rho=args.stressed_rho,
            cfg=cfg,
        )
        save_lobster_priority_depth_sensitivity_plot(results)
        print(f"\nPriority depth sensitivity (levels={depth_levels})")
        print(summary.round(6).to_string(index=False))


if __name__ == "__main__":
    main()
