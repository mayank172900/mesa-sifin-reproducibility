#!/usr/bin/env python3
"""Run the MESA experiment suite."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

# Keep BLAS from oversubscribing every worker process on Apple Silicon. These
# must be set before NumPy/SciPy are imported through project modules.
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

from mesa.experiments import ExperimentConfig, run_all
from mesa.plotting import save_all_figures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run a smaller smoke-test grid.")
    parser.add_argument("--results", default="results", help="Results directory.")
    parser.add_argument("--jobs", type=int, default=0, help="Parallel worker count; 0 uses most local CPU cores.")
    args = parser.parse_args()

    config = ExperimentConfig(quick=args.quick, n_jobs=args.jobs)
    results_root = Path(args.results)
    outputs = run_all(config, results_root)
    save_all_figures(results_root)

    print(f"MESA run complete using {config.resolved_jobs()} worker(s)")
    for name, frame in outputs.items():
        print(f"{name}: {frame.shape[0]} rows")
    print(f"results: {results_root.resolve()}")


if __name__ == "__main__":
    main()
