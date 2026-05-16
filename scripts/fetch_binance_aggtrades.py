#!/usr/bin/env python3
"""Fetch and summarize public Binance spot aggregate trade events."""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.empirical import run_binance_aggtrade_cross_date_sanity, run_binance_aggtrade_sanity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    parser.add_argument("--date", default="2024-01-15")
    parser.add_argument("--dates", nargs="+")
    parser.add_argument("--data-root", default="data/raw/binance/aggTrades")
    parser.add_argument("--results", default="results")
    args = parser.parse_args()
    if args.dates:
        panel = run_binance_aggtrade_cross_date_sanity(
            data_root=Path(args.data_root),
            results_root=Path(args.results),
            symbols=tuple(args.symbols),
            dates=tuple(args.dates),
        )
        cols = [
            "symbol",
            "date",
            "rows",
            "agg_trade_rate_per_second",
            "underlying_trade_rate_per_second",
            "event_count_fano",
            "event_count_acf1",
            "buyer_maker_share",
        ]
    else:
        panel = run_binance_aggtrade_sanity(
            data_root=Path(args.data_root),
            results_root=Path(args.results),
            symbols=tuple(args.symbols),
            date=args.date,
        )
        cols = [
            "symbol",
            "rows",
            "agg_trade_rate_per_second",
            "underlying_trade_rate_per_second",
            "event_count_fano",
            "event_count_acf1",
            "buyer_maker_share",
        ]
    print(
        panel[cols]
        .round(6)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
