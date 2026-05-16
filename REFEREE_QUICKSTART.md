# Referee Quickstart

This is the 10-minute path to check that the core experiment package is real.

```bash
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 scripts/run_all.py --quick --jobs 8
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --validate-estimator
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --diagnostic-max-events 30000 --diagnostics
PYTHONPATH=src python3 scripts/fit_binance_hawkes.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates 2024-01-15 2024-04-15 2024-07-15 --max-events 60000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode both --levels 1 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-quote --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-priority --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-priority-sensitivity --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_deepest_public.py --levels 50 --max-events 200000
PYTHONPATH=src python3 scripts/audit_lobster_orderbook_reconstruction.py --levels 10 --max-events 80000 --compare-every 10 --reanchor-every-events 100
PYTHONPATH=src python3 scripts/benchmark_m_series.py --max-workers 16
```

Then inspect:

- `results/tables/scaling_exponent_fits.csv`
- `results/tables/spectral_gap_ablation_fits.csv`
- `results/tables/policy_stress_metrics.csv`
- `results/tables/policy_pairwise_tests.csv`
- `results/tables/policy_dt_convergence_summary.csv`
- `results/tables/policy_ogata_audit_summary.csv`
- `results/tables/event_queue_backtest_summary.csv`
- `results/tables/lobster_top_of_book_replay_summary.csv`
- `results/tables/lobster_l1_quote_replay_summary.csv`
- `results/tables/lobster_depth_quote_replay_summary.csv`
- `results/tables/lobster_priority_depth_quote_replay_summary.csv`
- `results/tables/lobster_priority_depth_sensitivity_summary.csv`
- `results/tables/lobster_deepest_public_priority_replay_summary.csv`
- `results/tables/lobster_orderbook_reconstruction_summary.csv`
- `results/tables/robust_dp_quotes.csv`
- `results/tables/dp_ablation_table.csv`
- `results/tables/quote_sensitivity_diagnostic_summary.csv`
- `results/tables/m_series_benchmark.csv`
- `results/tables/m_series_benchmark_environment.csv`
- `results/tables/sota_comparison.csv`
- `paper/m_series_optimization_report.md`
- `results/tables/lobster_hawkes_fit_by_event_type.csv`
- `results/tables/lobster_marked_hawkes_estimator_validation.csv`
- `results/tables/lobster_timestamp_resolution_sensitivity.csv`
- `results/tables/lobster_hawkes_multiscale_best.csv`
- `results/tables/lobster_marked_hawkes_multivariate_best.csv`
- `results/tables/lobster_side_marked_hawkes_multivariate_best.csv`
- `results/tables/lobster_side_marked_state_residuals_summary.csv`
- `results/tables/binance_aggtrades_sanity_summary.csv`
- `results/tables/binance_aggtrades_hawkes_best.csv`
- `results/figures/criticality_scaling.png`
- `results/figures/spectral_gap_ablation.png`
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
- `results/figures/robust_dp_quotes.png`
- `results/figures/quote_sensitivity_diagnostic.png`
- `results/figures/lobster_hawkes_event_type_rho_beta.png`
- `results/figures/lobster_marked_hawkes_estimator_validation.png`
- `results/figures/lobster_hawkes_multiscale.png`
- `results/figures/lobster_marked_hawkes_multivariate.png`
- `results/figures/lobster_side_marked_hawkes_multivariate.png`
- `results/figures/lobster_side_marked_state_residuals.png`
- `results/figures/binance_aggtrades_hawkes.png`

The package is intentionally small enough to audit. The current implementation
has a scalar and finite-dimensional Perron reduced-form proof appendix, a
conditional multitype HJBI/control proof chain for the stated exponential
Hawkes class (`paper/control_proof_completion_map.md`), a reduced quote/no-quote
DP, an event-queue stress test, offset-aware L1 public replay, displayed-depth
and residual-volume priority-aware level-10 replay with an auditable
queue-position note (`paper/queue_position_replay_completeness.md`), a
deepest-public level-50 AAPL/MSFT priority replay, a priority-assumption
sensitivity grid, observable order-book reconstruction audit,
state-conditioned residual diagnostics, Binance aggregate-trade event
diagnostics, and a reproducible numerical spine.
It verifies the finite-state Bellman layer, gives a compact truncated
continuous-intensity multitype HJBI bridge under compact-PDMP DPP/comparison
hypotheses, proves an untruncated Lyapunov stability/truncation bridge with
`p>1` tail control, proves weighted comparison for fixed-boundary weighted
subclasses, and gives local differentiability for smooth interior robust quote
optimizers.
The paper claim should therefore be stated as:

> The structural ambiguity premium follows the spectral resolvent in the
> controlled minimal model; full Hawkes simulations confirm near-critical
> amplification, expose normalization-dependent exponent changes, and show why
> public-data Hawkes calibration must be treated as a diagnostic rather than a
> black-box structural input.
