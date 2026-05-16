# Local ARM/M-Series Throughput Benchmark

This report records local throughput for representative MESA kernels:
Perron/resolvent sweeps, vectorized quote maps, memory-light Hawkes
simulations, and process-parallel spectral sweeps. It is not a whole-run
profile and does not identify the machine model beyond the recorded
platform fields.

## Environment

- `python`: `3.12.5`
- `platform`: `macOS-26.4-arm64-arm-64bit`
- `processor`: `arm`
- `cpu_count`: `18`
- `max_workers_tested`: `16`
- `numpy`: `2.2.6`
- `VECLIB_MAXIMUM_THREADS`: `1`
- `OMP_NUM_THREADS`: `1`
- `OPENBLAS_NUM_THREADS`: `1`
- `NUMEXPR_NUM_THREADS`: `1`

## Results

- `spectral_resolvent` workers=1: 18,225.9 units/s over 0.0132s (8x8 Perron perturbation and resolvent kernels)
- `quote_vectorization` workers=1: 706,141,963.6 units/s over 0.0061s (vectorized quote_offsets over inventory grids)
- `hawkes_totals` workers=1: 43,598,433.3 units/s over 0.0188s (memory-light discrete Hawkes total-count simulation)
- `parallel_spectral_resolvent` workers=1: 700.1 units/s over 0.2285s (process-parallel Perron perturbation and resolvent sweep)
- `parallel_spectral_resolvent` workers=2: 1,306.1 units/s over 0.2450s (process-parallel Perron perturbation and resolvent sweep)
- `parallel_spectral_resolvent` workers=4: 2,461.4 units/s over 0.2600s (process-parallel Perron perturbation and resolvent sweep)
- `parallel_spectral_resolvent` workers=8: 4,210.2 units/s over 0.3040s (process-parallel Perron perturbation and resolvent sweep)
- `parallel_spectral_resolvent` workers=16: 7,042.2 units/s over 0.3635s (process-parallel Perron perturbation and resolvent sweep)

## Interpretation

The best measured process-pool spectral sweep used `16` worker(s),
with process-pool speedup `10.06` and parallel efficiency `0.63`
relative to the one-worker process-pool row. This is not a speedup over the
direct single-process spectral kernel above. BLAS thread caps are intentionally
set to one so Python worker processes do not oversubscribe CPU threads.
