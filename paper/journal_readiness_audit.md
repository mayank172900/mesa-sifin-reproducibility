# Journal Readiness Audit

Target journal: **SIAM Journal on Financial Mathematics**.

Date: 2026-05-16.

## Requirements From The User Request

| Requirement | Current evidence | Status |
|---|---|---|
| Work only inside `16may` | All new package artifacts are under `/Users/goodday/Documents/Projects/16may` | satisfied |
| Use `paper-code-novelty-scout` | `paper/novelty_scout.md`, `paper/web_sota_audit.md`, and subagent synthesis record novelty scan | satisfied |
| Do not use persistent-goal skill | No persistent-goal skill was loaded | satisfied |
| Use at least 8 subagents | `notes/subagents_synthesis.md` lists 8 subagent workstreams | satisfied |
| Build codebase | `src/mesa/*.py`, `scripts/*.py`, `tests/*.py` | satisfied |
| Provide portable reproduction path | `Makefile`, `requirements.txt`, `pyproject.toml`, `README_REPRODUCE.md` | satisfied |
| Optimize for M5 Max | `scripts/run_all.py --jobs 16`, parallel policy/DP workers, BLAS thread caps, and local ARM/M-series throughput benchmark; machine-generation specifics are left to the recorded platform fields | satisfied with hardware-ID caveat |
| Run experiments | `results/raw/*.csv`, `results/tables/*.csv`, `results/figures/*.png`; includes simulator validation, calibration noise, policy `dt` audit, Ogata arrival audit, reduced event-queue backtest, top-of-book, offset-aware L1, displayed-depth level-10, residual-volume priority-aware level-10 public replay, deepest-public level-50 AAPL/MSFT replay, priority-assumption sensitivity, observable order-book reconstruction, explicit no-quote DP diagnostics, interior quote-sensitivity diagnostics, corrected MLE diagnostics, fixed-beta two-scale Hawkes diagnostics, grouped marked multivariate Hawkes diagnostics, side-aware marked Hawkes diagnostics, and state-conditioned residual diagnostics | satisfied |
| Include ablations | `policy_ablation_table.csv`, `scaling_ablation_table.csv`, `dp_ablation_table.csv`, `spectral_gap_ablation_fits.csv` | satisfied |
| Compare with current SOTA | `results/tables/sota_comparison.csv`, `paper/ablation_sota_report.md`, `paper/web_sota_audit.md`; source/code URLs recorded from 2026-05-16 web audit | satisfied |
| Audit references | `paper/reference_audit.md`; 18 bibliography entries checked against source-of-record pages, with 18/18 citation keys matched to bibliography keys | satisfied |
| Validate submission bundle | `scripts/validate_submission_package.py --strict`, `results/tables/submission_artifact_manifest.csv`, `paper/submission_readiness_check.md`, and deterministic `make bundle` handoff; 177 promised code/paper/result artifacts checked with zero missing and zero TeX/citation/SOTA/domain-integrity failures, plus 5 human/external upload items reported separately | satisfied technically; human upload actions remain |
| Use datasets, not only synthetic | LOBSTER samples for AAPL/AMZN/GOOG/INTC/MSFT, Binance aggregate trades for BTCUSDT/ETHUSDT/SOLUSDT, and crypto L2 samples for BTC/ETH/SOL under `data/raw/` | satisfied |
| Produce journal-style paper materials | `paper/mesa_sifin_manuscript.pdf`, `paper/mesa_scalar_theory_appendix.pdf`, `paper/siam_jfm_cover_letter.pdf`, `paper/siam_jfm_submission_checklist.md`, finite-dimensional Perron theorem appendix PDF, reports | satisfied as a working manuscript package |

## Verification Commands

```bash
cd /Users/goodday/Documents/Projects/16may
PYTHONPATH=src:. python3 -m pytest -q
PYTHONPATH=src python3 scripts/fetch_public_data.py
PYTHONPATH=src python3 scripts/fetch_binance_aggtrades.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates 2024-01-15 2024-04-15 2024-07-15
PYTHONPATH=src python3 scripts/run_all.py --jobs 16
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --validate-estimator
PYTHONPATH=src python3 scripts/fit_lobster_hawkes.py --skip-panel --diagnostic-max-events 30000 --diagnostics
PYTHONPATH=src python3 scripts/fit_binance_hawkes.py --symbols BTCUSDT ETHUSDT SOLUSDT --dates 2024-01-15 2024-04-15 2024-07-15 --max-events 60000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode both --levels 1 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-quote --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-priority --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/replay_lobster_top_of_book.py --mode depth-priority-sensitivity --levels 10 --max-events 80000
PYTHONPATH=src python3 scripts/audit_lobster_orderbook_reconstruction.py --levels 10 --max-events 80000 --compare-every 10 --reanchor-every-events 100
PYTHONPATH=src python3 scripts/benchmark_m_series.py --max-workers 16
make paper
python3 /Users/goodday/.codex/skills/latex-to-pdf/scripts/compile_latex.py \
  --tex-file paper/mesa_sifin_manuscript.tex \
  --output-dir paper \
  --output-name mesa_sifin_manuscript
python3 /Users/goodday/.codex/skills/latex-to-pdf/scripts/compile_latex.py \
  --tex-file paper/mesa_scalar_theory_appendix.tex \
  --output-dir paper \
  --output-name mesa_scalar_theory_appendix
python3 /Users/goodday/.codex/skills/latex-to-pdf/scripts/compile_latex.py \
  --tex-file paper/siam_jfm_cover_letter.tex \
  --output-dir paper \
  --output-name siam_jfm_cover_letter
```

Observed evidence:

- Tests: `51 passed`.
- Submission validator: `PASS_WITH_EXTERNAL_ACTIONS`, 173 promised artifacts present, zero missing,
  zero TeX warning hits, zero citation-integrity failures, zero SOTA-table
  integrity failures, and zero queue/benchmark/proof-scope domain failures.
- Full run: 16 workers; 240 scaling rows, 90 spectral-gap rows, 168 policy rows, 56 policy-`dt` rows, 28 policy-Ogata rows, 8 event-queue rows, 48 robust-DP summary rows, 20 discretization-bias rows, 12 calibration-noise rows.
- Spectral-gap/Perron-visibility ablation: `results/tables/spectral_gap_ablation_fits.csv` shows Perron-visible aligned perturbations recover slope -2.00, Perron-orthogonal loadings have no positive aligned premium, and second-mode adversaries matter only when the second mode is near critical.
- Reduced event-queue backtest: `results/raw/event_queue_backtest_path_wealth.csv`
  has 480 path-policy rows. At `rho_hat=0.97`, mean wealth differences versus
  nominal are 0.484 for relative-slack robust-Gamma, 27.745 for absolute-Gamma,
  and -3.791 for the liquidity guard; the guard fully withdraws while
  absolute-Gamma remains active with a lower fill rate.
- Robust-DP no-quote diagnostics: `results/raw/robust_dp_policy_grid.csv`
  contains 9,947 two-sided quote states, 4,241 bid-only states, 4,241 ask-only
  states, and 579 full no-quote states; `results/tables/dp_ablation_table.csv`
  reports mean no-quote rates of 0.457 under relative-slack ambiguity and 0.496
  under absolute-Gamma ambiguity.
- Interior quote-sensitivity diagnostic:
  `results/tables/quote_sensitivity_diagnostic_summary.csv` matches the smooth
  implemented quote-map derivatives. Nominal and relative-Gamma policies have
  estimated critical exponent 3.000 for `d half-spread / d rho`; absolute-Gamma
  policies approach exponent 4.000 in the uncapped smooth region, with capped
  points explicitly marked nonsmooth.
- Corrected Hawkes MLE diagnostics: scalar estimator validation passes without beta-cap failures; fixed-beta marked multivariate Ogata validation recovers three-type spectral radii with MAE 0.025 and 0.023 at true rho 0.35 and 0.65; raw all-message LOBSTER fits remain beta-bound and are documented as misspecification diagnostics; event-type/fixed-beta/timestamp sensitivity and fixed-beta two-scale tables are included. The two-scale diagnostic selects `(1, 100)` across tested ticker/event-group panels, with median fast-excitation shares of 0.764 for all messages and 0.871 for executions.
- Grouped marked multivariate Hawkes diagnostics: `results/tables/lobster_marked_hawkes_multivariate_best.csv` fits stable three-mark branching matrices over limit, cancel/delete, and execution events. Best fixed beta is 100 for all five tickers; spectral radii range from 0.367 to 0.622, and conditional mark log-loss improves over event-frequency baselines by 0.005 to 0.114 nats per event.
- Side-aware marked multivariate Hawkes diagnostics: `results/tables/lobster_side_marked_hawkes_multivariate_best.csv` fits six-mark branching matrices over buy/sell-side limit, cancel/delete, and execution events. Best fixed beta is 100 for all five tickers; spectral radii range from 0.369 to 0.624, and conditional mark log-loss improves over event-frequency baselines by 0.101 to 0.292 nats per event.
- State-conditioned residual diagnostics: `results/tables/lobster_side_marked_state_residuals_summary.csv` conditions the six-mark fit's residuals on event group, side, size, spread, imbalance, and depth. Wide-spread states have median residual KS 0.220 versus 0.092 for tight-spread states, and large-size events have residual mean 0.828 versus 1.018 for small events; this supports the diagnostic-not-production framing.
- Public Binance aggregate-trade diagnostics: `results/tables/binance_aggtrades_sanity_summary.csv` and `results/tables/binance_aggtrades_hawkes_best.csv` add public crypto event evidence for BTCUSDT, ETHUSDT, and SOLUSDT on 2024-01-15. One-second Fano factors range from 12.24 to 200.27, lag-one count autocorrelations range from 0.201 to 0.342, and fixed-beta all-event Hawkes branching ratios are 0.153 to 0.351. The artifact is explicitly framed as event-clustering evidence, not a queue-aware execution benchmark.
- Public Binance cross-date robustness: `results/tables/binance_aggtrades_cross_date_sanity_summary.csv`, `results/tables/binance_aggtrades_hawkes_cross_date_best.csv`, and `results/tables/binance_aggtrades_hawkes_cross_date_summary.csv` repeat the BTCUSDT/ETHUSDT/SOLUSDT aggregate-trade diagnostics on 2024-01-15, 2024-04-15, and 2024-07-15. All-event branching ranges are 0.172-0.380, 0.198-0.521, and 0.117-0.328 respectively.
- Public LOBSTER top-of-book replay: `results/tables/lobster_top_of_book_replay_summary.csv` replays five public message/order-book streams. Under calibrated side-aware spectral radii, all policies remain active and coincide; under `rho_hat=0.97`, absolute-Gamma and the liquidity guard fully withdraw, with mean wealth difference -341.691 versus nominal and side-time no-quote share 1.000.
- Public LOBSTER L1 quote replay: `results/tables/lobster_l1_quote_replay_summary.csv` uses policy offsets to classify visible quote states as join, improve, away, or withdraw. Under calibrated side-aware spectral radii, tick rounding still makes policies coincide, but the replay now explains the behavior: mean side-time is 0.024 join, 0.428 improve, 0.448 away, and 0.101 withdrawn. Under `rho_hat=0.97`, absolute-Gamma and the liquidity guard fully withdraw.
- Public LOBSTER displayed-depth replay: `results/tables/lobster_depth_quote_replay_summary.csv` uses uniform level-10 public LOBSTER books for all five tickers. Under calibrated side-aware spectral radii, mean side-time is 0.018 at L1, 0.428 improving, 0.408 at visible depth, and 0.146 withdrawn; mean visible depth rank is 2.431 and mean fills are 1420.2. Under `rho_hat=0.97`, absolute-Gamma and the liquidity guard fully withdraw, with mean wealth difference -120.216 versus nominal.
- Public LOBSTER priority-aware depth replay: `results/tables/lobster_priority_depth_quote_replay_summary.csv` places the synthetic quote behind full displayed same-price size and tracks later same-price order ids as behind it. Queued fills now require residual same-price execution volume after the displayed queue ahead is depleted, and partial fills are credited by residual volume rather than as full-lot fills. Under calibrated side-aware spectral radii, mean fill events are 21.6 but mean filled lots are only 15.53, mean terminal wealth is -7.839, and mean side-time is 0.019 at L1, 0.530 improving, 0.422 at visible depth, and 0.029 withdrawn. The queue audit records mean initial displayed queue ahead 62.03 lots across 1810.4 visible quote resets, with mean queued fills 1.2, mean improve fills 20.4, mean partial-fill events 7.6, max zero-residual prevented fills 1, and max queue-violation count 0. Under `rho_hat=0.97`, absolute-Gamma and the liquidity guard fully withdraw and avoid the nominal priority-replay loss, with mean wealth difference +5.964.
- Public LOBSTER deepest-public priority replay: `results/tables/lobster_deepest_public_priority_replay_summary.csv` repeats the residual-volume priority replay on the available public level-50 AAPL/MSFT samples, whose public files cover a shorter one-hour window. The calibrated two-ticker supplement uses 50 displayed levels, records mean fill events 23.0, mean filled lots 16.82, mean queued fills 2.5, mean improve fills 20.5, mean partial-fill events 8.0, max queue-violation count 0, and max visible depth rank 5.
- Public LOBSTER priority sensitivity: `results/tables/lobster_priority_depth_sensitivity_summary.csv` varies the nominal replay's initial same-price queue fraction over 0, 0.5, and 1 and a displayed queue-stress multiplier over 1, 1.5, and 2. Mean filled lots range from 14.87 to 16.53 under calibrated side-aware spectral radii, showing that public level-10 samples rarely identify enough same-price residual volume for priority assumptions to dominate.
- Public LOBSTER order-book reconstruction: `results/tables/lobster_orderbook_reconstruction_summary.csv` reconstructs observable level-10 books from messages and re-anchors every 100 events. Across 399,995 processed events and 40,000 compared snapshots, panel mean top-of-book price match is 0.9997, full 10-level price match is 0.9376, top-of-book size MAE is 0.056 shares, and full-depth size MAE is 38.1 shares.
- Local ARM/M-series benchmark: `results/tables/m_series_benchmark.csv`, `results/tables/m_series_benchmark_environment.csv`, and `paper/m_series_optimization_report.md` record representative kernel throughput with BLAS thread caps set to one and process-parallel spectral sweeps up to 16 workers. The report no longer treats process-pool speedup as direct kernel speedup.
- Manuscript PDF: `paper/mesa_sifin_manuscript.pdf`.
- Scalar and finite-dimensional Perron proof appendix PDF: `paper/mesa_scalar_theory_appendix.pdf`.
- SIFIN submission packet: `paper/siam_jfm_submission_checklist.md`,
  `paper/siam_jfm_submission_metadata.md`,
  `paper/siam_jfm_ai_disclosure.md`, and
  `paper/siam_jfm_cover_letter.pdf` incorporate the official 2026 SIFIN/SIAM
  requirements checked on 2026-05-16: manuscript and cover letter PDFs,
  inline figures, under-250-word abstract, keywords, MSC codes, abbreviated
  title, originality representation, and AI-use disclosure for human-author
  review.
- Portable make targets: `make test`, `make reproduce JOBS=8`, and
  `make full-reproduce JOBS=12`.
- Local TeX compilation used the available `tectonic` fallback because
  `pdflatex` is not installed on this machine. Current TeX logs have no
  overfull boxes, unresolved references, or citation warnings.

## Honest Remaining Journal Risks

These do not block the current research package, but they would block a final
submission if left unresolved:

1. The scalar and finite-dimensional Perron-visible reduced-form proof bridge,
   finite-state robust Bellman verification theorem, compact truncated
   continuous-intensity multitype HJBI verification theorem, untruncated
   Hawkes Lyapunov stability/truncation theorem, weighted comparison theorem
   for the untruncated HJBI, local differentiability of smooth interior
   robust quote optimizers, and an assembled end-to-end multitype control
   theorem are now stated in the appendix. The remaining proof risks are
   no-quote/boundary active-set differentiability and rechecking the weighted
   comparison assumptions for richer state-dependent, power-law, or learned
   Hawkes kernels.
2. The public data panels now include grouped and side-aware marked
   multivariate Hawkes calibration plus state-conditioned residual diagnostics,
   but the fit is still fixed-beta, message-side, and not queue-position-aware.
   A submission should keep empirical claims modest unless this is extended to
   richer production calibration.
3. The policy stress tests use the fast discrete Hawkes simulator. Focused
   `dt`, Ogata-binned, reduced event-queue, public top-of-book, offset-aware
   L1, displayed-depth level-10, residual-volume priority-aware level-10
   LOBSTER replay, deepest-public level-50 AAPL/MSFT replay, and observable
   order-book reconstruction audits now show the result is not solely a binning
   artifact, but a final submission should still avoid exchange-private claims
   about hidden liquidity and anonymous initial queue priority.
4. The robust-DP now has a literal reduced quote/no-quote action, a finite-state
   Bellman verification theorem, a compact HJBI bridge, an untruncated Lyapunov
   bridge, and weighted comparison theorem, but it is still a finite-scenario
   approximation rather than a production-calibrated quote-refusal solver. The
   paper must state that clearly.

## Current Decision

This is now a credible **working manuscript and reproducible research package**
for SIAM Journal on Financial Mathematics. The reduced-form spectral theorem is
connected to a multitype control proof for the stated exponential Hawkes model
class through compact HJBI verification, untruncated Lyapunov stability,
weighted comparison, interior optimizer sensitivity, and the assembled
end-to-end multitype control theorem. The final submission scope should keep
richer kernels, no-quote active-set smoothness, and
exchange-grade hidden-priority simulation as extensions rather than completed
claims.
