#!/usr/bin/env python3
"""Fetch and summarize public crypto L2 depth samples."""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.empirical import run_crypto_depth_sanity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["BTC", "ETH", "SOL"])
    parser.add_argument("--data-root", default="data/raw/crypto_l2")
    parser.add_argument("--results", default="results")
    args = parser.parse_args()
    panel = run_crypto_depth_sanity(
        data_root=Path(args.data_root),
        results_root=Path(args.results),
        symbols=tuple(args.symbols),
    )
    print(panel.round(6).to_string(index=False))


if __name__ == "__main__":
    main()

