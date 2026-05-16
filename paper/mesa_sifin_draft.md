# Structural Ambiguity Amplification in Near-Critical Hawkes Market Making

Target venue: **SIAM Journal on Financial Mathematics**.

## Abstract Draft

Market-making models with robust controls usually treat uncertainty as
parametric ambiguity in drift, volatility, or fill rates. We study a different
source of uncertainty: ambiguity in the self-excitation structure of order flow.
In a Hawkes-driven limit order book, this structure is encoded by the branching
matrix `Gamma`, whose spectral radius determines proximity to criticality. We
show, in scalar and finite-dimensional Perron-visible exponential Hawkes
market-making models, that the robust quoting premium is governed by the
Hawkes resolvent `(I-Gamma)^(-1)`.
Under simple Perron-root and alignment assumptions, structural uncertainty is
therefore amplified as `rho(Gamma) -> 1`. Numerical experiments confirm the
spectral amplification mechanism, show when the nominal exponent changes under
absolute `Gamma` perturbations, and demonstrate that a robust-Gamma quoting
policy improves tail outcomes in near-critical synthetic stress tests.

## Contributions

1. Formulate structural uncertainty over Hawkes branching structure for market
   making.
2. Derive a resolvent/Perron-mode ambiguity premium near criticality.
3. Clarify the normalization issue: `epsilon/(1-rho)^2` is not unconditional
   for absolute `Gamma` balls.
4. Provide a reproducible experiment suite with scaling, policy stress,
   finite-N degradation, Ogata validation, reduced event-queue backtests, and
   public-data calibration diagnostics.
5. Include ablation tables against Poisson, nominal Hawkes, volatility-only
   robust, absolute-Gamma robust, no-quote guard, and reduced robust-DP
   variants.
6. Include a SOTA comparison table against 2019-2026 Hawkes/robust market-making
   competitors.

## Paper Outline

### 1. Introduction

Lead with the practical claim: near-critical self-exciting order flow prices
model uncertainty. Small ambiguity in the order-flow interaction structure can
make a robust market maker quote much wider or withdraw liquidity.

### 2. Related Work

State clearly:

- Hawkes market-making control already exists.
- Robust market making already exists.
- Near-critical Hawkes limits already exist.
- MESA contributes the intersection: robust market making under structural
  Hawkes ambiguity with spectral criticality.

### 3. Minimal Model

Use scalar or finite-dimensional exponential Hawkes order flow, finite inventory,
cash/price separation, compact quote controls, and ambiguity over a stable
branching parameter or matrix.

### 4. Main Theorem

Prove the resolvent amplification bound:

```text
premium <= C epsilon ||(I-Gamma)^(-1)||^2
```

and a matching lower bound under Perron simplicity, eigengap, and price-impact
alignment. State separately the stronger singularity that appears for absolute
`rho` perturbations of variance.

### 5. Numerical Method

Use finite-scenario Perron-robust inventory dynamic programming as the main
computational method, with full Hawkes simulation for evaluation.

### 6. Experiments

- Scaling experiment: recover exponent under theorem-level proxy.
- Matrix-resolvent experiment: test rank-one, block, sparse, near-degenerate
  `Gamma`.
- Spectral-gap ablation: show the lower-bound coefficient vanishes without
  Perron visibility or active Perron-direction ambiguity.
- Hawkes variance experiment: expose normalization-dependent exponent.
- Robust-vs-nominal market making: compare CE, tail PnL, inventory, fill rate,
  using common random numbers and paired bootstrap tests.
- Event-queue backtest: replay common Ogata event paths through a reduced
  queue-ahead model and record quote/no-quote side-time.
- Public LOBSTER replay: replay the same policies on actual message/order-book
  streams with transparent top-of-book, offset-aware L1, displayed-depth
  level-10, residual-volume priority-aware level-10, deepest-public level-50,
  and priority-assumption sensitivity queue proxies.
- Observable order-book reconstruction: reconstruct level-10 books from
  messages with 100-event re-anchoring and compare to official LOBSTER
  snapshots.
- Robust-DP experiment: solve the reduced finite-scenario inventory Bellman
  problem, use the finite-state Bellman and compact continuous-intensity HJBI
  verification theorems plus the untruncated Lyapunov and weighted-comparison
  bridges, and show near-critical quote/no-quote regions.
- Finite-N proxy: quantify mean-field degradation near criticality.
- Public data sanity panels: AAPL, AMZN, GOOG, INTC, MSFT LOBSTER event
  clustering, BTC/ETH/SOL crypto L2 depth overdispersion, and public Binance
  BTCUSDT/ETHUSDT/SOLUSDT aggregate-trade event clustering.
- Corrected LOBSTER Hawkes MLE diagnostics: estimator validation, event-type
  splits, fixed-beta sensitivity, timestamp aggregation, two-scale profiles,
  grouped marked multivariate branching matrices, side-aware six-mark
  branching matrices using LOBSTER direction labels, and state-conditioned
  residual diagnostics.
- Binance aggregate-trade Hawkes diagnostics: fixed-beta event fits by all,
  buy-aggressor, and sell-aggressor trade groups to separate public crypto
  event clustering from snapshot-only depth evidence.
- Marked multivariate Ogata validation: check spectral-radius and
  branching-matrix recovery on known three-type Hawkes paths.

### 7. Discussion

Discuss empirical testing with LOBSTER/ITCH or crypto order-book data, while
avoiding participant-type claims unless trader identity data exists.

## Claims To Avoid

- "First Hawkes market-making paper."
- "First robust market-making paper."
- "Unconditional `Theta(epsilon/(1-rho)^2)` for absolute `Gamma` uncertainty."
- "Graphon/MFG theorem" unless proved.
- "Classical optimizer differentiability at no-quote boundaries, spread caps,
  or active-adversary switches" unless proved.
- "State-dependent or learned Hawkes global HJBI theorem" unless the weighted
  comparison assumptions are rechecked for that richer model.
- "Empirical proof" from public sample data.
