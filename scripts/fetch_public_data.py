#!/usr/bin/env python3
"""Fetch every public-data panel used in the MESA package."""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.empirical import run_public_data_panel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/raw")
    parser.add_argument("--results", default="results")
    args = parser.parse_args()
    lobster, crypto, binance = run_public_data_panel(Path(args.data_root), Path(args.results))
    print("LOBSTER panel")
    print(
        lobster[
            [
                "ticker",
                "rows",
                "event_rate_per_second",
                "event_count_fano",
                "event_count_acf1",
                "mean_spread",
            ]
        ]
        .round(4)
        .to_string(index=False)
    )
    print("\nCrypto L2 panel")
    print(
        crypto[
            [
                "symbol",
                "rows",
                "relative_spread_bps",
                "mid_return_std",
                "top_imbalance_std",
                "total_depth_fano",
            ]
        ]
        .round(6)
        .to_string(index=False)
    )
    print("\nBinance aggregate trade panel")
    print(
        binance[
            [
                "symbol",
                "rows",
                "agg_trade_rate_per_second",
                "event_count_fano",
                "event_count_acf1",
            ]
        ]
        .round(6)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
