#!/usr/bin/env python3
"""Fetch and summarize a public LOBSTER sample."""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.empirical import run_lobster_sanity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="INTC")
    parser.add_argument("--levels", type=int, default=1)
    parser.add_argument("--data-root", default="data/raw/lobster")
    parser.add_argument("--results", default="results")
    args = parser.parse_args()
    _, summary = run_lobster_sanity(
        data_root=Path(args.data_root),
        results_root=Path(args.results),
        ticker=args.ticker,
        levels=args.levels,
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

