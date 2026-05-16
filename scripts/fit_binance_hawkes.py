#!/usr/bin/env python3
"""Fit Hawkes diagnostics to public Binance aggregate trade events."""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.calibration import fit_binance_aggtrade_hawkes, fit_binance_aggtrade_hawkes_cross_date
from mesa.plotting import save_binance_aggtrade_cross_date_plot, save_binance_aggtrade_hawkes_plot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    parser.add_argument("--date", default="2024-01-15")
    parser.add_argument("--dates", nargs="+")
    parser.add_argument("--data-root", default="data/raw/binance/aggTrades")
    parser.add_argument("--results", default="results")
    parser.add_argument("--max-events", type=int, default=60_000)
    args = parser.parse_args()
    max_events = None if args.max_events <= 0 else args.max_events
    if args.dates:
        fits = fit_binance_aggtrade_hawkes_cross_date(
            data_root=Path(args.data_root),
            results_root=Path(args.results),
            symbols=tuple(args.symbols),
            dates=tuple(args.dates),
            max_events=max_events,
        )
        save_binance_aggtrade_hawkes_plot(Path(args.results))
        save_binance_aggtrade_cross_date_plot(Path(args.results))
        best = (
            fits.sort_values(["symbol", "date", "event_group", "aic"])
            .groupby(["symbol", "date", "event_group"], as_index=False)
            .first()[["symbol", "date", "event_group", "beta_fixed", "rho", "residual_ks_stat", "n_events_fit"]]
        )
    else:
        fits = fit_binance_aggtrade_hawkes(
            data_root=Path(args.data_root),
            results_root=Path(args.results),
            symbols=tuple(args.symbols),
            date=args.date,
            max_events=max_events,
        )
        save_binance_aggtrade_hawkes_plot(Path(args.results))
        best = (
            fits.sort_values(["symbol", "event_group", "aic"])
            .groupby(["symbol", "event_group"], as_index=False)
            .first()[["symbol", "event_group", "beta_fixed", "rho", "residual_ks_stat", "n_events_fit"]]
        )
    print(best.round(6).to_string(index=False))


if __name__ == "__main__":
    main()
