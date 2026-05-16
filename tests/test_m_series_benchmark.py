from argparse import Namespace

import numpy as np

from scripts.benchmark_m_series import run_benchmarks


def test_m_series_benchmark_schema_tiny_run():
    args = Namespace(
        max_workers=1,
        dim=3,
        spectral_repetitions=2,
        parallel_repetitions_per_worker=1,
        quote_size=16,
        quote_repetitions=1,
        n_paths=4,
        horizon=0.04,
        repeats=1,
    )
    results, env = run_benchmarks(args)
    required = {
        "benchmark",
        "workers",
        "seconds",
        "work_units",
        "throughput_units_per_second",
        "checksum",
        "speedup_vs_single_worker",
        "parallel_efficiency",
    }
    assert required.issubset(results.columns)
    assert {"spectral_resolvent", "quote_vectorization", "hawkes_totals"}.issubset(
        set(results["benchmark"])
    )
    assert np.isfinite(results["throughput_units_per_second"]).all()
    assert (results["throughput_units_per_second"] > 0).all()
    env_map = dict(zip(env["key"], env["value"], strict=True))
    assert env_map["VECLIB_MAXIMUM_THREADS"] == "1"
    assert env_map["OMP_NUM_THREADS"] == "1"
