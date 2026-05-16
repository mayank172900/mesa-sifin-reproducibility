# Datasets And Empirical Scope

## Current Public Data Panels

### LOBSTER Equity Event Samples

Source: public LOBSTER sample files mirrored on Hugging Face
(`totalorganfailure/lobster-data`). The package currently fetches one-level
message/order-book samples for AAPL, AMZN, GOOG, INTC, and MSFT.

The resulting summary is saved at:

```text
results/tables/lobster_panel_sanity_summary.csv
results/tables/lobster_hawkes_fit.csv
results/tables/lobster_hawkes_fit_by_event_type.csv
results/tables/lobster_hawkes_fixed_beta_sensitivity.csv
results/tables/lobster_timestamp_resolution_sensitivity.csv
results/tables/lobster_hawkes_multiscale_best.csv
results/tables/lobster_marked_hawkes_multivariate_best.csv
results/tables/lobster_side_marked_hawkes_multivariate_best.csv
results/tables/lobster_side_marked_state_residuals_summary.csv
results/tables/lobster_top_of_book_replay_summary.csv
results/tables/lobster_l1_quote_replay_summary.csv
results/tables/lobster_depth_quote_replay_summary.csv
results/tables/lobster_priority_depth_quote_replay_summary.csv
results/tables/lobster_priority_depth_sensitivity_summary.csv
results/tables/lobster_orderbook_reconstruction_summary.csv
```

What this panel supports:

- event clustering and overdispersion;
- rough spread and event-rate sanity checks;
- corrected single-exponential Hawkes calibration diagnostics;
- evidence that raw unmarked message arrivals mix event clocks and timestamp
  bursts, because fitted decay is highly timestamp-resolution sensitive;
- fixed-beta two-scale diagnostics showing fast excitation dominates execution
  events;
- grouped marked multivariate Hawkes diagnostics over limit, cancel/delete, and
  execution event groups, with stable estimated branching matrices;
- side-aware marked multivariate Hawkes diagnostics over buy/sell direction
  labels for the same event groups;
- state-conditioned residual diagnostics showing that spread, size, depth, and
  imbalance strata still explain fit errors;
- top-of-book policy replay on public message/order-book streams, using a
  transparent queue-ahead proxy and observed execution sizes;
- offset-aware L1 quote replay that separates join, improve, away, and
  withdrawal side-time using only observable L1 prices and sizes;
- displayed-depth level-10 replay that lets away-from-L1 quotes fill when they
  rest inside the visible 10-level book and observed executions/depth changes
  deplete displayed queue ahead;
- residual-volume priority-aware level-10 replay that places the synthetic
  quote behind the full displayed same-price queue, tracks later same-price
  order ids as behind the synthetic quote, requires residual same-price
  execution volume for queued fills, and credits partial fills by residual lots;
- deepest-public level-50 AAPL/MSFT priority replay on the shorter public
  one-hour files, used as a depth supplement rather than a uniform five-ticker
  headline panel;
- priority-assumption sensitivity over initial same-price displayed priority
  and displayed queue-stress multipliers;
- observable level-10 order-book reconstruction from messages, re-anchored
  every 100 events and checked against official LOBSTER snapshots;
- a reproducible public-data motivation section.

What this panel does not support:

- participant-type calibration;
- causal proof of structural `Gamma` uncertainty;
- a production-grade structural Hawkes calibration without size-aware,
  queue-position-aware, or richer multiscale kernels and residual diagnostics;
- exchange-grade fill modeling with hidden liquidity and exact priority for
  anonymous queue already present before the synthetic quote;
- journal-grade empirical universality across equities.

### Binance Spot Aggregate Trades

Source: public Binance data archive
(`data.binance.vision/data/spot/daily/aggTrades`). The package currently
fetches BTCUSDT, ETHUSDT, and SOLUSDT aggregate trades for 2024-01-15,
2024-04-15, and 2024-07-15.

The resulting summaries are saved at:

```text
results/tables/binance_aggtrades_sanity_summary.csv
results/tables/binance_aggtrades_cross_date_sanity_summary.csv
results/tables/binance_aggtrades_hawkes_fixed_beta.csv
results/tables/binance_aggtrades_hawkes_best.csv
results/tables/binance_aggtrades_hawkes_cross_date_best.csv
results/tables/binance_aggtrades_hawkes_cross_date_summary.csv
results/figures/binance_aggtrades_hawkes.png
results/figures/binance_aggtrades_cross_date_hawkes.png
```

What this panel supports:

- real public crypto event clustering rather than snapshot-only evidence;
- one-second aggregate-trade overdispersion and lag-one count autocorrelation;
- fixed-beta Hawkes diagnostics by all, buy-aggressor, and sell-aggressor
  trade groups;
- cross-date robustness over 2024-01-15, 2024-04-15, and 2024-07-15;
- cross-asset plausibility that self-exciting event flow is relevant outside
  the LOBSTER equity samples.

What this panel does not support:

- queue-position replay, because aggregate trades do not include full order-book
  message flow;
- order-placement/cancellation calibration;
- participant identity or hidden-liquidity inference;
- production execution claims.

### Crypto L2 Depth Samples

Source: public Hugging Face crypto order-book depth samples
(`AdamAtractor/crypto-l2-orderbook-30-levels`). The package currently fetches
BTC, ETH, and SOL.

The resulting summary is saved at:

```text
results/tables/crypto_l2_sanity_summary.csv
```

What this panel supports:

- liquidity-state overdispersion across non-equity order books;
- spread/depth sanity checks in a 24/7 market;
- robustness of the motivation beyond one asset class.

What this panel does not support:

- Hawkes event calibration, because these are snapshots rather than raw event
  messages;
- direct comparison with institutional equity data;
- agent-type inference.

## Why Synthetic Data Remains Necessary

The core MESA claim concerns ambiguity over the true Hawkes branching matrix.
Public LOBSTER, Binance, and crypto depth datasets do not reveal the true
`Gamma`, and public equity samples do not reveal trader identities. Binance
aggregate trades add real public crypto event evidence, but not the full
order-book state needed to identify a queue-aware structural `Gamma`.
Synthetic Hawkes experiments are therefore not a shortcut; they are the only
controlled way to test:

- whether the scaling exponent is `-2` or `-3`;
- whether Perron-aligned perturbations dominate random perturbations;
- whether robust-Gamma quoting improves tail outcomes under known
  misspecification.

The manuscript should use synthetic data for theorem validation and public data
for empirical plausibility.
