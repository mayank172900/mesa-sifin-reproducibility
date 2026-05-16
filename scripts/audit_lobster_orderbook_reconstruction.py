#!/usr/bin/env python3
"""Audit observable order-book reconstruction on public LOBSTER samples."""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.orderbook_reconstruction import run_lobster_orderbook_reconstruction_audit
from mesa.plotting import save_lobster_orderbook_reconstruction_plot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/raw/lobster")
    parser.add_argument("--results", default="results")
    parser.add_argument("--levels", type=int, default=10)
    parser.add_argument("--max-events", type=int, default=80_000)
    parser.add_argument("--compare-every", type=int, default=10)
    parser.add_argument("--reanchor-every-events", type=int, default=100)
    args = parser.parse_args()
    results = Path(args.results)
    _, summary = run_lobster_orderbook_reconstruction_audit(
        data_root=Path(args.data_root),
        results_root=results,
        levels=args.levels,
        max_events=args.max_events,
        compare_every=args.compare_every,
        reanchor_every_events=args.reanchor_every_events,
    )
    save_lobster_orderbook_reconstruction_plot(results)
    print("\nLOBSTER observable order-book reconstruction")
    print(summary.round(6).to_string(index=False))


if __name__ == "__main__":
    main()
