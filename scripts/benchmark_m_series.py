#!/usr/bin/env python3
"""Benchmark MESA compute kernels on Apple Silicon style local machines."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import os
import platform
from pathlib import Path
import sys
import time

# Keep BLAS from oversubscribing each process when parallel workers are used.
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import pandas as pd

from mesa.control import quote_offsets
from mesa.hawkes import HawkesParams, simulate_discrete_hawkes_totals
from mesa.spectral import make_gamma_family, variance_amplification, worst_case_perron_perturbation


@dataclass(frozen=True)
class TimedResult:
    benchmark: str
    workers: int
    seconds: float
    work_units: float
    throughput_units_per_second: float
    checksum: float
    note: str


def _time_call(fn, repeats: int = 1) -> tuple[float, float, float]:
    best_seconds = float("inf")
    best_units = 0.0
    best_checksum = 0.0
    for _ in range(max(1, repeats)):
        start = time.perf_counter()
        units, checksum = fn()
        seconds = time.perf_counter() - start
        if seconds < best_seconds:
            best_seconds = seconds
            best_units = float(units)
            best_checksum = float(checksum)
    return best_seconds, best_units, best_checksum


def _spectral_kernel(dim: int, repetitions: int, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    checksum = 0.0
    for idx in range(repetitions):
        rho = 0.70 + 0.25 * ((idx % 11) / 10.0)
        gamma = make_gamma_family("block", dim=dim, rho=rho, rng=rng)
        checksum += variance_amplification(gamma)
        perturbed = worst_case_perron_perturbation(gamma, epsilon=0.005, rho_max=0.995)
        checksum += variance_amplification(perturbed)
    work_units = float(repetitions * 2)
    return work_units, checksum


def _parallel_spectral_worker(args: tuple[int, int, int]) -> tuple[float, float]:
    dim, repetitions, seed = args
    return _spectral_kernel(dim, repetitions, seed)


def benchmark_spectral(dim: int, repetitions: int, repeats: int) -> TimedResult:
    seconds, units, checksum = _time_call(lambda: _spectral_kernel(dim, repetitions, seed=11), repeats=repeats)
    return TimedResult(
        benchmark="spectral_resolvent",
        workers=1,
        seconds=seconds,
        work_units=units,
        throughput_units_per_second=units / seconds,
        checksum=checksum,
        note=f"{dim}x{dim} Perron perturbation and resolvent kernels",
    )


def benchmark_quote_vectorization(size: int, repetitions: int, repeats: int) -> TimedResult:
    inventory = np.linspace(-12.0, 12.0, size)

    def run() -> tuple[float, float]:
        checksum = 0.0
        units = 0.0
        for idx in range(repetitions):
            rho = 0.82 + 0.13 * ((idx % 7) / 6.0)
            epsilon = 0.005 + 0.015 * ((idx % 5) / 4.0)
            for policy in ("nominal_hawkes", "robust_gamma", "robust_gamma_abs"):
                bid, ask = quote_offsets(inventory, rho_hat=rho, epsilon=epsilon, policy=policy)
                checksum += float(np.mean(bid) + np.mean(ask))
                units += inventory.size
        return units, checksum

    seconds, units, checksum = _time_call(run, repeats=repeats)
    return TimedResult(
        benchmark="quote_vectorization",
        workers=1,
        seconds=seconds,
        work_units=units,
        throughput_units_per_second=units / seconds,
        checksum=checksum,
        note="vectorized quote_offsets over inventory grids",
    )


def benchmark_hawkes_totals(dim: int, n_paths: int, horizon: float, repeats: int) -> TimedResult:
    rng = np.random.default_rng(23)
    gamma = make_gamma_family("rank1", dim=dim, rho=0.65, rng=rng)
    params = HawkesParams(mu=np.full(dim, 0.08), gamma=gamma, beta=2.0, dt=0.02, horizon=horizon)

    def run() -> tuple[float, float]:
        totals = simulate_discrete_hawkes_totals(params, n_paths=n_paths, seed=29)
        work_units = float(n_paths * params.steps * dim)
        return work_units, float(np.sum(totals))

    seconds, units, checksum = _time_call(run, repeats=repeats)
    return TimedResult(
        benchmark="hawkes_totals",
        workers=1,
        seconds=seconds,
        work_units=units,
        throughput_units_per_second=units / seconds,
        checksum=checksum,
        note="memory-light discrete Hawkes total-count simulation",
    )


def benchmark_parallel_spectral(dim: int, repetitions_per_worker: int, workers: int) -> TimedResult:
    tasks = [(dim, repetitions_per_worker, 10_000 + idx) for idx in range(workers)]
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        outputs = list(pool.map(_parallel_spectral_worker, tasks))
    seconds = time.perf_counter() - start
    units = float(sum(item[0] for item in outputs))
    checksum = float(sum(item[1] for item in outputs))
    return TimedResult(
        benchmark="parallel_spectral_resolvent",
        workers=workers,
        seconds=seconds,
        work_units=units,
        throughput_units_per_second=units / seconds,
        checksum=checksum,
        note="process-parallel Perron perturbation and resolvent sweep",
    )


def make_environment_table(max_workers: int) -> pd.DataFrame:
    rows = [
        {"key": "python", "value": sys.version.split()[0]},
        {"key": "platform", "value": platform.platform()},
        {"key": "processor", "value": platform.processor()},
        {"key": "cpu_count", "value": str(os.cpu_count() or "")},
        {"key": "max_workers_tested", "value": str(max_workers)},
        {"key": "numpy", "value": np.__version__},
    ]
    for key in ["VECLIB_MAXIMUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        rows.append({"key": key, "value": os.environ.get(key, "")})
    return pd.DataFrame(rows)


def run_benchmarks(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_workers = max(1, min(args.max_workers, os.cpu_count() or 1))
    worker_grid = sorted({1, min(2, max_workers), min(4, max_workers), min(8, max_workers), max_workers})
    worker_grid = [workers for workers in worker_grid if workers >= 1]

    rows = [
        benchmark_spectral(args.dim, args.spectral_repetitions, args.repeats),
        benchmark_quote_vectorization(args.quote_size, args.quote_repetitions, args.repeats),
        benchmark_hawkes_totals(args.dim, args.n_paths, args.horizon, args.repeats),
    ]
    parallel_rows = [
        benchmark_parallel_spectral(args.dim, args.parallel_repetitions_per_worker, workers)
        for workers in worker_grid
    ]
    rows.extend(parallel_rows)
    df = pd.DataFrame([row.__dict__ for row in rows])
    df["speedup_vs_single_worker"] = np.nan
    df["parallel_efficiency"] = np.nan
    baseline = df[(df["benchmark"] == "parallel_spectral_resolvent") & (df["workers"] == 1)]
    if not baseline.empty:
        base_throughput = float(baseline["throughput_units_per_second"].iloc[0])
        mask = df["benchmark"] == "parallel_spectral_resolvent"
        df.loc[mask, "speedup_vs_single_worker"] = df.loc[mask, "throughput_units_per_second"] / base_throughput
        df.loc[mask, "parallel_efficiency"] = df.loc[mask, "speedup_vs_single_worker"] / df.loc[mask, "workers"]
    env = make_environment_table(max_workers)
    return df, env


def write_report(results: pd.DataFrame, env: pd.DataFrame, out_path: Path) -> None:
    best_parallel = results[results["benchmark"] == "parallel_spectral_resolvent"].sort_values(
        "throughput_units_per_second", ascending=False
    )
    best_row = best_parallel.iloc[0] if not best_parallel.empty else None
    lines = [
        "# Local ARM/M-Series Throughput Benchmark",
        "",
        "This report records local throughput for representative MESA kernels:",
        "Perron/resolvent sweeps, vectorized quote maps, memory-light Hawkes",
        "simulations, and process-parallel spectral sweeps. It is not a whole-run",
        "profile and does not identify the machine model beyond the recorded",
        "platform fields.",
        "",
        "## Environment",
        "",
    ]
    for row in env.itertuples(index=False):
        lines.append(f"- `{row.key}`: `{row.value}`")
    lines.extend(["", "## Results", ""])
    for row in results.itertuples(index=False):
        lines.append(
            f"- `{row.benchmark}` workers={row.workers}: "
            f"{row.throughput_units_per_second:,.1f} units/s "
            f"over {row.seconds:.4f}s ({row.note})"
        )
    if best_row is not None:
        speedup = best_row.speedup_vs_single_worker
        efficiency = best_row.parallel_efficiency
        lines.extend(
            [
                "",
                "## Interpretation",
                "",
                f"The best measured process-pool spectral sweep used `{int(best_row.workers)}` worker(s),",
                f"with process-pool speedup `{speedup:.2f}` and parallel efficiency `{efficiency:.2f}`",
                "relative to the one-worker process-pool row. This is not a speedup over the",
                "direct single-process spectral kernel above. BLAS thread caps are intentionally",
                "set to one so Python worker processes do not oversubscribe CPU threads.",
            ]
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results", help="Results directory.")
    parser.add_argument("--dim", type=int, default=8)
    parser.add_argument("--spectral-repetitions", type=int, default=120)
    parser.add_argument("--parallel-repetitions-per-worker", type=int, default=80)
    parser.add_argument("--quote-size", type=int, default=120_000)
    parser.add_argument("--quote-repetitions", type=int, default=12)
    parser.add_argument("--n-paths", type=int, default=256)
    parser.add_argument("--horizon", type=float, default=8.0)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=16)
    args = parser.parse_args()

    results_root = Path(args.results)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    (Path("paper")).mkdir(parents=True, exist_ok=True)
    results, env = run_benchmarks(args)
    results.to_csv(results_root / "tables" / "m_series_benchmark.csv", index=False)
    env.to_csv(results_root / "tables" / "m_series_benchmark_environment.csv", index=False)
    write_report(results, env, Path("paper") / "m_series_optimization_report.md")
    print(results.to_string(index=False))
    print(f"wrote {results_root / 'tables' / 'm_series_benchmark.csv'}")
    print(f"wrote {Path('paper') / 'm_series_optimization_report.md'}")


if __name__ == "__main__":
    main()
