# MESA Criticality Experiments

This folder contains the local research package for MESA: criticality, phase
transitions, and robust control in Hawkes-driven limit order books.

The current code focuses on a defensible first paper:

- rigorous minimal-model tests of the repaired scaling laws:
  relative critical-slack ambiguity gives
  `robustness premium ~ epsilon_rel / (1-rho)^2`, while absolute branching
  matrix ambiguity gives one extra critical factor;
- Monte Carlo checks that Hawkes count variability diverges near criticality;
- robust-vs-nominal market-making stress tests under structural misspecification;
- policy time-step convergence audits for the stressed near-critical cases;
- Ogata-binned arrival audits for headline robust policy comparisons;
- reduced event-queue backtests with quote/no-quote side-time accounting;
- public LOBSTER top-of-book, offset-aware L1, displayed-depth level-10,
  residual-volume priority-aware level-10, deepest-public level-50 AAPL/MSFT,
  and priority-assumption sensitivity replay with transparent queue-position
  diagnostics;
- observable level-10 order-book reconstruction audits against official
  LOBSTER snapshots;
- a finite-scenario robust DP with explicit bid/ask quote/no-quote actions;
- an interior quote-map sensitivity diagnostic matching the smooth optimizer
  derivative theorem and flagging capped/no-quote regions as nonsmooth;
- finite-population error proxies for the mean-field degradation claim;
- Ogata simulator validation, discretization-bias checks, and corrected
  public-data Hawkes calibration diagnostics on LOBSTER samples, including
  grouped and side-aware marked multivariate Hawkes fits plus
  state-conditioned residual diagnostics;
- public Binance BTCUSDT/ETHUSDT/SOLUSDT aggregate-trade event panels with
  one-second clustering summaries and fixed-beta Hawkes diagnostics.

Run everything:

```bash
PYTHONPATH=src python3 scripts/run_all.py --quick --jobs 8
```

Run tests:

```bash
PYTHONPATH=src pytest
```

Validate the current submission bundle:

```bash
PYTHONPATH=src:. python3 scripts/validate_submission_package.py --strict
```

Benchmark local Apple Silicon/M-series throughput:

```bash
PYTHONPATH=src python3 scripts/benchmark_m_series.py --max-workers 16
```

Outputs are written under `results/`.

Public-data calibration diagnostics:

```bash
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --validate-estimator
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --diagnostic-max-events 30000 --diagnostics
PYTHONPATH=src python3 scripts/fetch_binance_aggtrades.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates 2024-01-15 2024-04-15 2024-07-15
PYTHONPATH=src python3 scripts/fit_binance_hawkes.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates 2024-01-15 2024-04-15 2024-07-15 --max-events 60000
```

Paper-facing artifacts:

- `paper/novelty_scout.md`
- `paper/web_sota_audit.md`
- `paper/reference_audit.md`
- `paper/submission_readiness_check.md`
- `paper/control_proof_completion_map.md`
- `paper/queue_position_replay_completeness.md`
- `paper/m_series_optimization_report.md`
- `paper/siam_macro_conversion_note.md`
- `paper/mesa_sifin_manuscript_siam.tex`
- `paper/siam_jfm_submission_checklist.md`
- `paper/siam_jfm_submission_metadata.md`
- `paper/siam_jfm_ai_disclosure.md`
- `paper/siam_jfm_cover_letter.pdf`
- `paper/theory_repair.md`
- `paper/experiment_report.md`
- `paper/ablation_sota_report.md`
- `paper/datasets_and_empirical_scope.md`
- `paper/mesa_scalar_theory_appendix.pdf`
- `paper/mesa_sifin_manuscript.pdf`
- `paper/mesa_sifin_draft.md`
- `README_REPRODUCE.md`
- `REFEREE_QUICKSTART.md`

The current scientific stance is deliberately conservative: the first
publishable paper should center the reduced scalar and finite-dimensional
Perron-visible Hawkes robust-control theorem, reproducible Perron/multitype
experiments, and honest calibration diagnostics. The appendix now verifies the
finite-state robust Bellman layer, compact truncated continuous-intensity
multitype HJBI bridge, untruncated Lyapunov stability/truncation bridge,
weighted comparison for the untruncated HJBI in the corresponding weighted
class, local differentiability for strictly concave interior robust quote
optimizers with a smooth active worst-case selector, and an assembled
end-to-end multitype control theorem for that stated class. The broader
graphon/MFG, boundary/no-quote active-set smoothness, and richer
state-dependent Hawkes extensions remain follow-up work unless fully proved.
