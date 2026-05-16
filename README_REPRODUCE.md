# Reproducing the MESA Experiment Package

All commands are intended to run from the repository root.

## Environment

Use Python 3.12 or newer with NumPy, SciPy, Pandas, Matplotlib, Seaborn,
pytest, and `huggingface_hub`. The first paper experiments use NumPy/SciPy CPU
paths for deterministic float64 numerics.

Install missing basics if needed:

```bash
python3 -m pip install -r requirements.txt
```

Portable make targets are also available:

```bash
make test
make reproduce JOBS=8
make full-reproduce JOBS=12
```

## Tests

```bash
PYTHONPATH=src:. python3 -m pytest
```

Expected current result: all tests pass.

## Quick Referee Run

```bash
PYTHONPATH=src python3 scripts/run_all.py --quick --jobs 8
```

Equivalent:

```bash
make quick JOBS=8
```

This regenerates a small grid under `results/`.

## Paper PDFs

```bash
make paper
```

Install `tectonic` or `pdflatex` if you want to rebuild the PDFs locally.

## Full Local Run

```bash
PYTHONPATH=src python3 scripts/run_all.py --jobs 16
```

## M-Series Benchmark

```bash
PYTHONPATH=src python3 scripts/benchmark_m_series.py --max-workers 16
```

Equivalent:

```bash
make benchmark M_SERIES_WORKERS=16
```

This writes:

- `results/tables/m_series_benchmark.csv`
- `results/tables/m_series_benchmark_environment.csv`
- `paper/m_series_optimization_report.md`

Current full run artifacts:

- `results/raw/scaling_premiums.csv`
- `results/raw/spectral_gap_ablation.csv`
- `results/raw/hawkes_variance.csv`
- `results/raw/finite_n_error_proxy.csv`
- `results/raw/quote_sensitivity_diagnostic.csv`
- `results/raw/robust_dp_policy_grid.csv`
- `results/raw/robust_dp_values.csv`
- `results/raw/event_queue_backtest_path_wealth.csv`
- `results/raw/lobster_top_of_book_replay.csv`
- `results/raw/lobster_l1_quote_replay.csv`
- `results/raw/lobster_depth_quote_replay.csv`
- `results/raw/lobster_priority_depth_quote_replay.csv`
- `results/raw/lobster_priority_depth_sensitivity.csv`
- `results/raw/lobster_deepest_public_priority_replay.csv`
- `results/raw/lobster_orderbook_reconstruction.csv`
- `results/raw/policy_dt_convergence_path_wealth.csv`
- `results/raw/policy_ogata_audit_path_wealth.csv`
- `results/tables/scaling_exponent_fits.csv`
- `results/tables/spectral_gap_ablation_fits.csv`
- `results/tables/hawkes_variance_exponent_fits.csv`
- `results/tables/policy_stress_metrics.csv`
- `results/tables/policy_bootstrap_ci.csv`
- `results/tables/policy_pairwise_tests.csv`
- `results/tables/policy_dt_convergence.csv`
- `results/tables/policy_dt_convergence_summary.csv`
- `results/tables/policy_ogata_audit.csv`
- `results/tables/policy_ogata_audit_summary.csv`
- `results/tables/event_queue_backtest.csv`
- `results/tables/event_queue_backtest_summary.csv`
- `results/tables/lobster_top_of_book_replay_summary.csv`
- `results/tables/lobster_l1_quote_replay_summary.csv`
- `results/tables/lobster_depth_quote_replay_summary.csv`
- `results/tables/lobster_priority_depth_quote_replay_summary.csv`
- `results/tables/lobster_priority_depth_sensitivity_summary.csv`
- `results/tables/lobster_deepest_public_priority_replay_summary.csv`
- `results/tables/lobster_orderbook_reconstruction_summary.csv`
- `results/tables/policy_ablation_table.csv`
- `results/tables/scaling_ablation_table.csv`
- `results/tables/dp_ablation_table.csv`
- `results/tables/simulator_validation.csv`
- `results/tables/discretization_bias.csv`
- `results/tables/calibration_noise.csv`
- `results/tables/lobster_hawkes_estimator_validation.csv`
- `results/tables/lobster_marked_hawkes_estimator_validation.csv`
- `results/tables/lobster_hawkes_fit.csv`
- `results/tables/lobster_hawkes_fit_by_event_type.csv`
- `results/tables/lobster_hawkes_fixed_beta_sensitivity.csv`
- `results/tables/lobster_timestamp_resolution_sensitivity.csv`
- `results/tables/lobster_hawkes_multiscale_sensitivity.csv`
- `results/tables/lobster_hawkes_multiscale_best.csv`
- `results/tables/lobster_marked_hawkes_multivariate.csv`
- `results/tables/lobster_marked_hawkes_multivariate_best.csv`
- `results/tables/lobster_side_marked_hawkes_multivariate.csv`
- `results/tables/lobster_side_marked_hawkes_multivariate_best.csv`
- `results/tables/lobster_side_marked_state_residuals.csv`
- `results/tables/lobster_side_marked_state_residuals_summary.csv`
- `results/tables/lobster_size_side_marked_hawkes_multivariate.csv`
- `results/tables/lobster_size_side_marked_hawkes_multivariate_best.csv`
- `results/tables/binance_aggtrades_sanity_summary.csv`
- `results/tables/binance_aggtrades_cross_date_sanity_summary.csv`
- `results/tables/binance_aggtrades_hawkes_fixed_beta.csv`
- `results/tables/binance_aggtrades_hawkes_best.csv`
- `results/tables/binance_aggtrades_hawkes_cross_date_best.csv`
- `results/tables/binance_aggtrades_hawkes_cross_date_summary.csv`
- `results/tables/sota_comparison.csv`
- `results/tables/robust_dp_quotes.csv`
- `results/tables/finite_n_error_fit.csv`
- `results/tables/quote_sensitivity_diagnostic_summary.csv`
- `results/tables/m_series_benchmark.csv`
- `results/tables/m_series_benchmark_environment.csv`
- `results/figures/criticality_scaling.png`
- `results/figures/spectral_gap_ablation.png`
- `results/figures/hawkes_variance.png`
- `results/figures/policy_stress.png`
- `results/figures/policy_dt_convergence.png`
- `results/figures/policy_ogata_audit.png`
- `results/figures/event_queue_backtest.png`
- `results/figures/lobster_top_of_book_replay.png`
- `results/figures/lobster_l1_quote_replay.png`
- `results/figures/lobster_depth_quote_replay.png`
- `results/figures/lobster_priority_depth_quote_replay.png`
- `results/figures/lobster_priority_depth_sensitivity.png`
- `results/figures/lobster_orderbook_reconstruction.png`
- `results/figures/finite_n_heatmap.png`
- `results/figures/quote_sensitivity_diagnostic.png`
- `results/figures/robust_dp_quotes.png`
- `results/figures/simulator_validation.png`
- `results/figures/discretization_bias.png`
- `results/figures/calibration_noise.png`
- `results/figures/lobster_hawkes_estimator_validation.png`
- `results/figures/lobster_marked_hawkes_estimator_validation.png`
- `results/figures/lobster_hawkes_event_type_rho_beta.png`
- `results/figures/lobster_beta_profile_likelihood.png`
- `results/figures/lobster_timestamp_resolution_sensitivity.png`
- `results/figures/lobster_hawkes_multiscale.png`
- `results/figures/lobster_marked_hawkes_multivariate.png`
- `results/figures/lobster_side_marked_hawkes_multivariate.png`
- `results/figures/lobster_side_marked_state_residuals.png`
- `results/figures/lobster_size_side_marked_multivariate.png`
- `results/figures/binance_aggtrades_hawkes.png`
- `results/figures/binance_aggtrades_cross_date_hawkes.png`

The robust-DP outputs now include explicit side-level quote/no-quote actions.
In the current full run, `results/raw/robust_dp_policy_grid.csv` contains
9,947 two-sided quote states, 4,241 bid-only states, 4,241 ask-only states, and
579 full no-quote states.

The reduced event-queue backtest uses Ogata event times with common event paths
across policies. The current full run writes 480 path-policy rows and 8 summary
rows.

## Public Data Sanity Checks

Fetch one-level LOBSTER sample panels from Hugging Face:

```bash
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker AAPL --levels 1
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker AMZN --levels 1
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker GOOG --levels 1
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker INTC --levels 1
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker MSFT --levels 1
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker AAPL --levels 10
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker AMZN --levels 10
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker GOOG --levels 10
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker INTC --levels 10
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker MSFT --levels 10
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker AAPL --levels 50
PYTHONPATH=src python3 scripts/fetch_lobster_sample.py --ticker MSFT --levels 50
PYTHONPATH=src python3 scripts/fetch_crypto_depth.py --symbols BTC ETH SOL
PYTHONPATH=src python3 scripts/fetch_binance_aggtrades.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates 2024-01-15 2024-04-15 2024-07-15
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode both --levels 1 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-quote --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-priority --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-priority-sensitivity --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_deepest_public.py --levels 50 --max-events 200000
PYTHONPATH=src python3 scripts/audit_lobster_orderbook_reconstruction.py --levels 10 --max-events 80000 --compare-every 10 --reanchor-every-events 100
```

The current combined panel is saved at:

- `results/tables/lobster_panel_sanity_summary.csv`
- `results/tables/crypto_l2_sanity_summary.csv`
- `results/tables/binance_aggtrades_sanity_summary.csv`
- `results/tables/binance_aggtrades_cross_date_sanity_summary.csv`
- `results/tables/lobster_top_of_book_replay_summary.csv`
- `results/tables/lobster_l1_quote_replay_summary.csv`
- `results/tables/lobster_depth_quote_replay_summary.csv`
- `results/tables/lobster_priority_depth_quote_replay_summary.csv`
- `results/tables/lobster_priority_depth_sensitivity_summary.csv`
- `results/tables/lobster_deepest_public_priority_replay_summary.csv`
- `results/tables/lobster_orderbook_reconstruction_summary.csv`

## Corrected LOBSTER Hawkes Calibration Diagnostics

Validate the single-exponential Hawkes MLE on synthetic Ogata samples and fit
public LOBSTER diagnostics:

```bash
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --validate-estimator
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --diagnostic-max-events 30000 --diagnostics
PYTHONPATH=src python3 scripts/fit_binance_hawkes.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates 2024-01-15 2024-04-15 2024-07-15 --max-events 60000
```

Optional high-dimensional robustness check:

```bash
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --diagnostic-max-events 15000 --diagnostics --size-side-robustness
```

The current interpretation is deliberately conservative. Corrected all-message
fits still hit the beta upper bound for the five public LOBSTER samples, while
event-type splits and timestamp aggregation show that decay and branching are
sensitive to event mixing and timestamp bursts. The fixed-beta two-scale
diagnostic selects `(1, 100)` across tested ticker/event groups and assigns most
execution excitation to the fast component. The grouped marked multivariate
diagnostic fits stable three-by-three branching matrices over limit,
cancel/delete, and execution event groups; best fixed beta is 100 for all five
tickers, with spectral radii between 0.367 and 0.622. The side-aware six-mark
diagnostic using LOBSTER direction labels also selects beta 100 for all five
tickers, with spectral radii between 0.369 and 0.624. Treat these as
calibration diagnostics, not as production-grade proof of a true size- and
queue-aware branching matrix. The state-conditioned residual audit now reports
where the six-mark model misses: wide-spread states have median residual KS
about `0.220`, tight-spread states about `0.092`, and large-size event
residual means are about `0.828` versus `1.018` for small events.
An optional 12-mark event/side/size robustness fit is also saved, but four of
five optimizer success flags are false under the 15k-event cap, so it should be
reported only as exploratory robustness evidence.

The Binance aggregate-trade panel adds a public crypto event stream rather
than only crypto snapshots. On 2024-01-15, BTCUSDT, ETHUSDT, and SOLUSDT have
218k to 1.36m aggregate trades, one-second event-count Fano factors from
12.24 to 200.27, and positive lag-one count autocorrelation from 0.201 to
0.342. The fixed-beta Hawkes diagnostic selects beta 100 in the current grid;
all-event branching ratios are 0.351 for BTCUSDT, 0.313 for ETHUSDT, and
0.153 for SOLUSDT. This supports real crypto event clustering, but aggregate
trades are not full order-book messages and cannot support queue-position
execution claims.

The cross-date Binance robustness panel repeats this check on 2024-01-15,
2024-04-15, and 2024-07-15. Across all-event fits, median branching ratios are
0.351 for BTCUSDT, 0.313 for ETHUSDT, and 0.153 for SOLUSDT, with cross-date
ranges of 0.172-0.380, 0.198-0.521, and 0.117-0.328 respectively.

## Current Scientific Interpretation

The minimal structural-premium experiment recovers the intended exponent
`-2` exactly because it tests the controlled theorem-level proxy
`epsilon * ||(I-Gamma)^(-1)||^2`.

The Hawkes count-variance experiment is steeper in the full simulation:
current fitted slopes are about `-3.21` for total variance and `-1.83` for the
Fano factor. This supports the repaired-theory warning that absolute
branching-matrix uncertainty can produce exponents different from the draft
headline, depending on what is being perturbed and normalized.
