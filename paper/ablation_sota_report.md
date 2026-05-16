# Ablation And SOTA Comparison

Target journal: **SIAM Journal on Financial Mathematics**.

## Policy Ablation

The policy ablation uses common random numbers. Each policy is evaluated on the
same Hawkes paths, price-noise draws, and fill-uniform draws within each
`rho, epsilon` scenario.

| Policy | CE | CVaR5 | Mean Wealth Diff vs Nominal | 95% Bootstrap CI |
|---|---:|---:|---:|---:|
| robust_gamma | 31.134 | -0.409 | 12.545 | [11.764, 13.252] |
| robust_vol_only | 19.237 | -10.984 | 0.001 | [0.000, 0.001] |
| nominal_hawkes | 19.236 | -10.985 | baseline | baseline |
| robust_gamma_abs | 8.681 | -27.620 | -2.832 | [-4.755, -0.850] |
| known_true_gamma_no_ambiguity | 7.793 | -24.973 | -9.742 | [-11.425, -8.112] |
| as_poisson | -1.808 | -25.980 | -21.510 | [-22.554, -20.545] |
| liquidity_guard | -7.420 | -33.655 | -25.576 | [-27.023, -24.242] |

The CE/CVaR columns are scenario-level summaries averaged over the stress grid.
The underlying ablation table also reports pooled pathwise mean wealth, pooled
CVaR5, and pooled certainty equivalent so the bootstrap intervals are auditable
without mixing metric definitions.

Current conclusion: the relative-slack robust-Gamma policy is the cleanest
positive result. The renamed `known_true_gamma_no_ambiguity` row knows the
stressed branching ratio but carries no ambiguity premium, so it under-hedges
model risk in this headline stress design. Absolute-Gamma and no-quote guard
variants are intentionally included as controls; the focused `dt` and
Ogata-binned audits show that absolute-Gamma is regime-sensitive rather than
uniformly too conservative.

## Scaling Ablation

| Scaling object | Matrix family | Mean slope |
|---|---|---:|
| relative-slack premium | scalar | -2.000 |
| absolute-Gamma derivative | scalar | -3.000 |
| matrix resolvent | rank1 | -3.424 |
| matrix resolvent | block | -3.430 |
| matrix resolvent | near_degenerate | -3.432 |
| matrix resolvent | sparse | -3.470 |

Current conclusion: the square law is valid for the relative-slack theorem
normalization. Absolute `Gamma` ambiguity is more singular, matching the theory
repair memo.

## Numerical-Method Ablation

Near-critical Hawkes simulations are sensitive to time discretization. The
current table `results/tables/discretization_bias.csv` shows:

| Regime | Coarse dt | Fine dt | Interpretation |
|---|---:|---:|---|
| rho=0.90 | dt=0.08 gives 315% mean-count bias | dt=0.01 gives 3% bias | coarse bins can create spurious amplification |
| rho=0.97 | dt=0.08 gives 1154% mean-count bias | dt=0.005 gives 15% bias | near-critical experiments need Ogata or dt convergence |

This is a useful submission-relevant diagnostic: before comparing robust policies,
Hawkes LOB simulators must prove that their discretization is not creating the
criticality they claim to study.

### Policy `dt` Convergence

The package now includes a focused policy time-step audit:

- table: `results/tables/policy_dt_convergence.csv`
- figure: `results/figures/policy_dt_convergence.png`

For `epsilon=0.02`, the relative-slack robust-Gamma policy remains positive
versus nominal Hawkes across all tested time steps:

| rho_hat | Tested dt range | robust_gamma diff vs nominal |
|---:|---:|---:|
| 0.92 | 0.04 to 0.005 | +0.046 to +0.098 |
| 0.97 | 0.04 to 0.005 | +0.594 to +0.952 |

This does not replace an Ogata policy backtest, but it addresses the immediate
discretization objection for the headline relative-slack policy. Absolute-Gamma
policies remain regime-sensitive, which is consistent with the normalization
warning.

### Ogata Arrival Audit

The package now also compares fast binned arrivals with Ogata-thinned event
times binned onto the same decision grid:

- table: `results/tables/policy_ogata_audit.csv`
- figure: `results/figures/policy_ogata_audit.png`

| rho_hat | discrete robust_gamma diff | Ogata-binned robust_gamma diff |
|---:|---:|---:|
| 0.92 | +0.028 | +0.077 |
| 0.97 | +0.495 | +0.546 |

The discrete recursion creates more events in the high-stress case, but the
relative-slack robust-Gamma advantage survives the Ogata-binned audit. This is
stronger than a `dt` convergence check; the package now adds a separate reduced
event-queue backtest, public LOBSTER top-of-book replay, displayed-depth
level-10 replay, residual-volume priority-aware level-10 replay, and a
deepest-public level-50 supplement, though hidden liquidity and anonymous
initial queue priority remain out of scope for public data.

### Reduced Event-Queue Backtest

| rho_hat | Policy | Mean wealth diff vs nominal | Side-time no-quote frac | Fill rate |
|---:|---|---:|---:|---:|
| 0.92 | robust_gamma | 0.019 | 0.074 | 0.927 |
| 0.92 | robust_gamma_abs | 0.523 | 0.074 | 0.927 |
| 0.92 | liquidity_guard | 0.523 | 0.074 | 0.927 |
| 0.97 | robust_gamma | 0.484 | 0.090 | 0.915 |
| 0.97 | robust_gamma_abs | 27.745 | 0.004 | 0.423 |
| 0.97 | liquidity_guard | -3.791 | 1.000 | 0.000 |

The event-queue audit uses Ogata event times, common event paths across policies,
quote updates every `dt=0.02`, and a simple queue-ahead rule. It shows that
quote/no-quote behavior is regime-sensitive: moderate robust widening helps, an
absolute-Gamma policy can be valuable under high stress, and an unconditional
liquidity guard can withdraw too much.

### Spectral-Gap And Visibility Ablation

The spectral-gap ablation now makes the theorem caveat executable. Under a
Perron-aligned adversary, Perron-visible and weakly visible loadings both
recover slope -2.00 after visibility normalization, while a Perron-orthogonal
loading has no positive aligned premium. If the adversary moves the second mode,
the orthogonal loading recovers slope -2.00 only when that second mode is also
near critical. For weakly visible loadings under second-mode ambiguity, the
median normalized coefficient falls from 2.6389 at gap multiple 2 to 0.0365 at
gap multiple 8.

### Public LOBSTER Top-Of-Book Replay

The public-data replay evaluates the same policy family on actual LOBSTER
message/order-book streams. Under calibrated side-aware spectral radii, the
top-of-book activity rule makes all policies coincide. Under the near-critical
stress `rho_hat=0.97`, robust-Gamma remains active while absolute-Gamma and the
liquidity guard fully withdraw:

| Scenario | Policy | Mean wealth diff vs nominal | Side-time no-quote frac | Mean fills |
|---|---|---:|---:|---:|
| calibrated side gamma | robust_gamma_abs | 0.000 | 0.198 | 3071.8 |
| near-critical stress | robust_gamma | 0.000 | 0.198 | 3071.8 |
| near-critical stress | robust_gamma_abs | -341.691 | 1.000 | 0.0 |
| near-critical stress | liquidity_guard | -341.691 | 1.000 | 0.0 |

This is not a displayed-depth queue simulator, but it removes one
synthetic-only weakness by replaying policy withdrawal on real public
message/order-book paths.
I also added an offset-aware L1 replay that classifies each side as join,
improve, away, or withdraw using the policy's continuous quote offsets. Under
calibrated side gamma, tick rounding still makes policy PnL coincide, but the
visible quote-state mix is informative: mean side-time is 0.024 join, 0.428
improve, 0.448 away, and 0.101 withdraw. Under near-critical stress,
absolute-Gamma and the liquidity guard fully withdraw again. This strengthens
the public-data audit while preserving the no-production-claims caveat.

The package now also runs a displayed-depth replay on the uniform level-10
LOBSTER sample panel. Away-from-L1 quotes can fill if their rounded quote price
rests inside the visible 10-level ladder and observed executions/depth changes
deplete displayed queue ahead. Under calibrated side gamma, mean side-time is
0.018 at L1, 0.428 improving, 0.408 at visible depth, and 0.146 withdrawn, with
mean visible depth rank 2.431 and mean fills 1420.2. Under `rho_hat=0.97`,
absolute-Gamma and the liquidity guard fully withdraw with mean wealth
difference -120.216 versus nominal. This removes the L1-only limitation, but it
still does not observe hidden liquidity or exact exchange priority.

The stricter priority-aware level-10 replay removes the capped same-level queue
shortcut. It places the synthetic quote behind the full displayed same-price
size and tracks later same-price orders by order id as being behind us. Queued
fills now require residual same-price execution volume after displayed queue
ahead is depleted; exact queue exhaustion without residual volume is recorded
but does not fill, and partial fills are credited by residual lots. Under
calibrated side gamma, mean fill events are 21.6 but mean filled lots are only
15.53, mean terminal wealth is -7.839, and side-time is 0.019 at L1, 0.530
improving, 0.422 at visible depth, and 0.029 withdrawn. Under `rho_hat=0.97`,
absolute-Gamma and the liquidity guard fully withdraw and avoid the nominal
loss, giving mean wealth difference +5.964. This is a useful negative result:
public displayed books support priority stress testing, but not hidden-liquidity
or full anonymous initial-queue reconstruction.

I also added a deepest-public priority replay for the available level-50
AAPL/MSFT samples. These files cover a shorter one-hour public window, so they
are a supplement rather than a replacement for the five-ticker uniform level-10
panel. The level-50 supplement records mean fill events 23.0, mean filled lots
16.82, mean queued fills 2.5, mean improve fills 20.5, and max queue-violation
count 0.

The priority-assumption sensitivity grid quantifies that remaining blind spot.
For the nominal calibrated replay, changing initial same-price queue fraction
from 0 to 1 and the displayed queue-stress multiplier from 1 to 2 moves mean
filled lots only from 16.53 to 14.87. The multiplier is a conservative stress
on the public queue-ahead proxy, not observed hidden depth. The limited movement
is itself diagnostic: the public samples rarely show enough residual same-price
execution volume to make the synthetic priority assumption empirically
identifiable.

I also added an observable order-book reconstruction audit. Starting from the
official level-10 snapshot and re-anchoring every 100 messages, the message
stream reconstructs the top-of-book price with panel mean match rate 0.9997
over 399,995 processed events, while the full 10-level price match is 0.9376.
Top-of-book size MAE is 0.056 shares after re-anchoring, but full-depth size
MAE is 38.1 shares. This is the right nuance for publication: near-touch
priority replay is locally auditable from public messages, while deeper queue
claims still need either more depth or exchange-grade reconstruction.

## Robust-DP Quote/No-Quote Ablation

| Ambiguity | Mean q=0 quoted half-spread | Max q=0 quoted half-spread | Mean no-quote rate | Full no-quote rate |
|---|---:|---:|---:|---:|
| relative_slack | 0.236 | 0.370 | 0.457 | 0.029 |
| absolute_gamma | 0.246 | 0.472 | 0.496 | 0.032 |

The DP now contains a literal side-level quote/no-quote action space. In the
full refreshed action grid, the solver selects 9,947 two-sided quote states,
4,241 bid-only states, 4,241 ask-only states, and 579 full no-quote states.
This is still a reduced Bellman approximation rather than a production
queue-calibrated quote-refusal simulator comparable one-for-one with
Wang--Ventre--Polukarov.

The smooth quote-map sensitivity diagnostic adds a local optimizer bridge:
nominal Hawkes and relative-Gamma robust policies recover exponent 3.000 for
`d half-spread / d rho`, while absolute-Gamma robust policies approach exponent
4.000 in the uncapped interior region. Spread caps and no-quote switches are
reported as nonsmooth active-set behavior.

## Public-Data Hawkes Calibration Ablation

The corrected single-exponential Hawkes MLE was validated on synthetic Ogata
samples before being applied to LOBSTER. It recovered known parameters with no
beta cap hits in three scenarios:

| rho true | beta true | rho MAE | beta MAPE | beta cap rate |
|---:|---:|---:|---:|---:|
| 0.30 | 2.0 | 0.043 | 0.201 | 0.000 |
| 0.70 | 4.0 | 0.019 | 0.026 | 0.000 |
| 0.90 | 8.0 | 0.016 | 0.039 | 0.000 |

The fixed-beta marked multivariate estimator was also validated on controlled
three-type Ogata paths before being applied to LOBSTER. At true spectral radii
0.35 and 0.65 with beta 3, the spectral-radius MAE is 0.025 and 0.023,
relative branching-matrix Frobenius error is 0.234 and 0.133, and success rate
is 1.000 in both scenarios.

On raw LOBSTER message arrivals, corrected all-message fits still hit the beta
upper bound for all five tickers under the 100k-event cap. Event-type splits
partially reduce the issue, and timestamp aggregation materially changes the
fit:

| Resolution | Median rho | Median beta | Median retained share |
|---:|---:|---:|---:|
| raw | 0.575 | 148.413 | 1.000 |
| 1us | 0.558 | 148.413 | 0.926 |
| 100us | 0.445 | 104.464 | 0.828 |
| 1ms | 0.397 | 23.393 | 0.614 |
| 10ms | 0.558 | 1.462 | 0.439 |

The fixed-beta two-scale diagnostic adds one more check. Across the tested
slow/fast pairs, all ticker/event-group panels select `(1, 100)`. Median
fast-excitation share is 0.764 for all messages, 0.723 for limit orders, 0.660
for cancel/delete events, and 0.871 for executions; execution residual KS
statistics remain large, with median 0.415.

A grouped marked multivariate Hawkes diagnostic now estimates a three-by-three
branching matrix over limit, cancel/delete, and execution events. AIC selects
fixed beta 100 for all five tickers. Spectral radii range from 0.367 to 0.622,
conditional mark log-loss improves over event-frequency baselines by 0.005 to
0.114 nats per event, and the median branching matrix has its strongest source
column from executions. Residual KS statistics still range from 0.050 to 0.217.

Current conclusion: the package now includes a genuine marked multivariate
`Gamma` diagnostic and a side-aware six-mark extension using LOBSTER direction
labels. The side-aware fits also select beta 100 for all tickers, with spectral
radii from 0.369 to 0.624 and conditional mark log-loss gains from 0.101 to
0.292 nats per event.

I then added a state-conditioned residual audit for the side-aware six-mark
fit. Wide-spread states have median residual mean 0.886 and median KS statistic
0.220, versus 1.110 and 0.092 for tight-spread states. Large-size events have
median residual mean 0.828 versus 1.018 for small events, and execution marks
have median conditional mark-log-loss gain 0.384 nats per event. Publication
claims can use this as calibration evidence while still treating the fitted
`Gamma` as diagnostic because residuals vary with size and L1 book state.

An exploratory 12-mark event/side/size fit was also run with a 15k-event cap.
It returns stable spectral radii between 0.270 and 0.500 and mark-log-loss
gains between 0.086 and 0.205, but four of five optimizer success flags are
false. I would keep it as robustness evidence that motivates state-dependent
models, not as a primary calibration table.

The Binance aggregate-trade event panel adds a separate public crypto event
check. On 2024-01-15, BTCUSDT, ETHUSDT, and SOLUSDT have one-second Fano
factors of 200.27, 29.73, and 12.24 and lag-one count autocorrelations of
0.342, 0.241, and 0.201. Fixed-beta Hawkes fits over all aggregate trades
select beta 100 in the current grid, with branching ratios 0.351, 0.313, and
0.153. Buy/sell-aggressor splits show larger sell-aggressor branching for
BTCUSDT and ETHUSDT. This is useful cross-asset event-clustering evidence, but
it is not a queue-aware LOB calibration because Binance aggregate trades do not
contain order-placement and cancellation messages.

## SOTA Comparison

The SOTA table was web-verified on 2026-05-16 against primary arXiv/DOI pages
and visible repository pages; the machine-readable version is
`results/tables/sota_comparison.csv`, and the source/code audit is
`paper/web_sota_audit.md`. The important correction is that El Karmi's 2025
Hawkes LOB simulator has a visible public repository with source, configs,
docs, tests, Makefile/CMake, and quick-start guidance. MESA should therefore
not claim simulator primacy. Its defensible position is a spectral
ambiguity-risk layer that can complement simulator-realism baselines.

| Work | Hawkes MM | Robust MM | Gamma uncertainty | Critical exponent | MESA position |
|---|---:|---:|---:|---:|---|
| Law & Viens 2019/2020 | yes | no | no | no | Hawkes/point-process MM exists; MESA adds structural Gamma ambiguity. |
| Wang, Ventre, Polukarov 2025 quote/no-quote | no | yes | no | no | Robust/no-quote MM exists; MESA adds spectral Hawkes uncertainty. |
| Wang, Ventre, Polukarov 2025 Hawkes ARL | yes | yes | no | no | Closest RL competitor; MESA needs theorem plus Gamma ambiguity. |
| Jain et al. 2025 Hawkes impulse control | yes | no | no | no | Closest HJB-QVI competitor; no structural robustness law. |
| Lalor & Swishchuk 2025 neural Hawkes LOB | yes | no | no | no | Strong simulator baseline; MESA adds ambiguity amplification diagnostics. |
| Guo, Lin & Huang 2023 Attn-LOB DRL | no | no | no | no | LOB-feature DRL baseline; MESA studies structural Hawkes ambiguity rather than alpha learning. |
| Jiang et al. 2025 Relaver latency/inventory RL | no | yes | no | no | Latency-aware neural MM benchmark; MESA is a reduced-form uncertainty stress test. |
| Raffaelli et al. 2026 multivariate Hawkes BTC LOB | no | no | no | no | Current multivariate LOB calibration/forecasting benchmark; MESA adds robust control stress tests. |
| El Karmi 2025 deterministic Hawkes LOB simulator | no | no | no | no | Simulator-realism baseline; MESA adds robustness and residual-stress diagnostics. |
| Noble, Rosenbaum & Souilmi 2026 realism gap | no | no | no | no | Strong simulator-realism framing; MESA is a complementary risk layer. |
| Kimura 2026 state-dependent Hawkes | no | no | no | yes | State-dependent Hawkes with tick-data volatility-signature evidence supports structural diagnostics. |
| Szymanski & Xu 2025 nearly unstable Hawkes | no | no | no | yes | Near-critical Hawkes limits exist; MESA adds market-making control. |
| El Karmi 2026 bivariate nearly unstable Hawkes | no | no | no | yes | Related limit theory; MESA targets robust market-making premiums. |
| MESA reduced-form package | yes | yes | yes | yes | Reduced-form theorem, compact/untruncated HJBI bridges, interior quote-sensitivity checks, policy stress tests, and public-data calibration diagnostics. |

## Dataset Panel

Current data sources:

- Synthetic Hawkes paths: theorem and ablation laboratory with known `Gamma`.
- Public LOBSTER samples: AAPL, AMZN, GOOG, INTC, MSFT event-message and
  level-1/level-10 order-book summaries, plus level-50 AAPL/MSFT deepest-public
  priority replay on the shorter public window.
- Public crypto L2 depth samples: BTC, ETH, SOL one-minute 30-level depth.
- Public Binance spot aggregate trades: BTCUSDT, ETHUSDT, SOLUSDT on
  2024-01-15, 2024-04-15, and 2024-07-15, with event clustering and fixed-beta
  Hawkes diagnostics.

The paper should be honest about what each can prove. Only synthetic data has
known `Gamma`, so only it can test the structural-ambiguity theorem directly.
LOBSTER, Binance, and crypto depth data establish realistic
clustering/liquidity-state motivation and can support calibration plausibility,
not causal proof.
