# MESA Experiment Report

Generated from the local code in `src/mesa` with:

```bash
PYTHONPATH=src python3 scripts/run_all.py
```

## Artifacts

- Raw scaling data: `results/raw/scaling_premiums.csv`
- Scaling fits: `results/tables/scaling_exponent_fits.csv`
- Spectral-gap ablation data: `results/raw/spectral_gap_ablation.csv`
- Spectral-gap ablation fits: `results/tables/spectral_gap_ablation_fits.csv`
- Hawkes variance data: `results/raw/hawkes_variance.csv`
- Hawkes variance fits: `results/tables/hawkes_variance_exponent_fits.csv`
- Simulator validation: `results/tables/simulator_validation.csv`
- Discretization bias: `results/tables/discretization_bias.csv`
- Calibration noise: `results/tables/calibration_noise.csv`
- Policy stress metrics: `results/tables/policy_stress_metrics.csv`
- Public LOBSTER top-of-book replay paths: `results/raw/lobster_top_of_book_replay.csv`
- Public LOBSTER top-of-book replay summary: `results/tables/lobster_top_of_book_replay_summary.csv`
- Public LOBSTER L1 quote replay paths: `results/raw/lobster_l1_quote_replay.csv`
- Public LOBSTER L1 quote replay summary: `results/tables/lobster_l1_quote_replay_summary.csv`
- Public LOBSTER displayed-depth replay paths: `results/raw/lobster_depth_quote_replay.csv`
- Public LOBSTER displayed-depth replay summary: `results/tables/lobster_depth_quote_replay_summary.csv`
- Public LOBSTER priority-depth replay paths: `results/raw/lobster_priority_depth_quote_replay.csv`
- Public LOBSTER priority-depth replay summary: `results/tables/lobster_priority_depth_quote_replay_summary.csv`
- Public LOBSTER priority-depth sensitivity paths: `results/raw/lobster_priority_depth_sensitivity.csv`
- Public LOBSTER priority-depth sensitivity summary: `results/tables/lobster_priority_depth_sensitivity_summary.csv`
- Public LOBSTER deepest-public priority replay paths: `results/raw/lobster_deepest_public_priority_replay.csv`
- Public LOBSTER deepest-public priority replay summary: `results/tables/lobster_deepest_public_priority_replay_summary.csv`
- Public LOBSTER observable-book reconstruction paths: `results/raw/lobster_orderbook_reconstruction.csv`
- Public LOBSTER observable-book reconstruction summary: `results/tables/lobster_orderbook_reconstruction_summary.csv`
- Finite-N proxy: `results/raw/finite_n_error_proxy.csv`
- Finite-N fit: `results/tables/finite_n_error_fit.csv`
- Quote sensitivity diagnostic: `results/raw/quote_sensitivity_diagnostic.csv`
- Quote sensitivity summary: `results/tables/quote_sensitivity_diagnostic_summary.csv`
- Pathwise policy outcomes: `results/raw/policy_path_wealth.csv`
- Bootstrap policy CIs: `results/tables/policy_bootstrap_ci.csv`
- Paired policy tests: `results/tables/policy_pairwise_tests.csv`
- Policy ablation table: `results/tables/policy_ablation_table.csv`
- Scaling ablation table: `results/tables/scaling_ablation_table.csv`
- Robust-DP ablation table: `results/tables/dp_ablation_table.csv`
- SOTA comparison table: `results/tables/sota_comparison.csv`
- Public LOBSTER panel summary: `results/tables/lobster_panel_sanity_summary.csv`
- Public crypto L2 depth summary: `results/tables/crypto_l2_sanity_summary.csv`
- Public Binance aggregate-trade summary: `results/tables/binance_aggtrades_sanity_summary.csv`
- Public Binance aggregate-trade Hawkes fits: `results/tables/binance_aggtrades_hawkes_best.csv`
- Public Binance cross-date aggregate-trade summary: `results/tables/binance_aggtrades_cross_date_sanity_summary.csv`
- Public Binance cross-date Hawkes summary: `results/tables/binance_aggtrades_hawkes_cross_date_summary.csv`
- Corrected Hawkes MLE validation: `results/tables/lobster_hawkes_estimator_validation.csv`
- Marked Hawkes MLE validation: `results/tables/lobster_marked_hawkes_estimator_validation.csv`
- Corrected all-event LOBSTER Hawkes fits: `results/tables/lobster_hawkes_fit.csv`
- Event-type LOBSTER Hawkes fits: `results/tables/lobster_hawkes_fit_by_event_type.csv`
- Fixed-beta LOBSTER sensitivity: `results/tables/lobster_hawkes_fixed_beta_sensitivity.csv`
- Timestamp-resolution LOBSTER sensitivity: `results/tables/lobster_timestamp_resolution_sensitivity.csv`
- Two-scale fixed-beta Hawkes sensitivity: `results/tables/lobster_hawkes_multiscale_sensitivity.csv`
- Best two-scale fixed-beta Hawkes fits: `results/tables/lobster_hawkes_multiscale_best.csv`
- Grouped marked multivariate Hawkes fits: `results/tables/lobster_marked_hawkes_multivariate.csv`
- Best grouped marked multivariate Hawkes fits: `results/tables/lobster_marked_hawkes_multivariate_best.csv`
- Side-aware marked multivariate Hawkes fits: `results/tables/lobster_side_marked_hawkes_multivariate.csv`
- Best side-aware marked multivariate Hawkes fits: `results/tables/lobster_side_marked_hawkes_multivariate_best.csv`
- Side-aware state-conditioned residuals: `results/tables/lobster_side_marked_state_residuals.csv`
- Side-aware state residual summary: `results/tables/lobster_side_marked_state_residuals_summary.csv`
- Optional 12-mark event/side/size fit: `results/tables/lobster_size_side_marked_hawkes_multivariate_best.csv`
- Figures: `results/figures/*.png`

## Main Results From Current Full Run

### Structural Premium Scaling

The theorem-level relative-slack formula recovers slope `-2.00` for all epsilon
values:

```text
premium = epsilon * constant * (1-rho)^(-2)
```

The absolute-Gamma derivative formula recovers slope `-3.00`. Matrix resolvent
experiments currently have mean slopes between about `-3.42` and `-3.47`,
depending on matrix family. This is exactly the corrected-theory warning: a
relative critical-slack ambiguity gives the square law, while an absolute
branching-matrix ambiguity adds an extra critical derivative factor.

### Spectral-Gap And Perron-Visibility Ablation

I added the missing lower-bound caveat experiment:

- raw data: `results/raw/spectral_gap_ablation.csv`
- fits: `results/tables/spectral_gap_ablation_fits.csv`
- figure: `results/figures/spectral_gap_ablation.png`

The ablation uses two-mode branching matrices with eigenvalues `rho` and
`1 - k * (1-rho)` for `k in {2, 4, 8}`. The result separates three cases:

```text
Perron-visible loading + Perron adversary: slope -2.00
Weak Perron-visible loading + Perron adversary: slope -2.00 after visibility normalization
Perron-orthogonal loading + Perron adversary: no positive premium
Perron-orthogonal loading + second-mode adversary: slope -2.00
```

For weakly visible loadings under a second-mode adversary, the normalized
coefficient falls as the second mode moves away from criticality:

```text
gap multiple k=2: median coefficient 2.6389
gap multiple k=4: median coefficient 0.3038
gap multiple k=8: median coefficient 0.0365
```

This makes the theorem caveat concrete: the lower bound needs Perron visibility
and an ambiguity set that can activate the Perron direction. Without that, the
leading coefficient can vanish or shift to another near-critical mode.

### Hawkes Count Variance

The full discrete Hawkes count simulation produced:

```text
total variance slope: -3.21
Fano factor slope:    -1.83
```

Interpretation: the raw count process can be more singular than the headline
premium proxy. This is not a failure; it is evidence that the paper must specify
exactly whether uncertainty is placed on `Gamma`, `rho`, variance, or a
relative/renormalized risk measure.

### Simulator Validation And Discretization Bias

I added a slow Ogata-thinning reference simulator. In a short-horizon scalar
validation, Ogata tracks the theoretical mean well near `rho=0.9`, while the
fast binned simulator can over-amplify counts. This is now an explicit numerical
finding, not a hidden weakness.

The discretization-bias ablation shows the issue clearly:

```text
rho=0.90, dt=0.08:  relative mean-count bias = 3.15
rho=0.90, dt=0.01:  relative mean-count bias = 0.03
rho=0.97, dt=0.08:  relative mean-count bias = 11.54
rho=0.97, dt=0.005: relative mean-count bias = 0.15
```

This suggests a methodological contribution: Hawkes market-making simulations
near criticality need Ogata validation or an explicit `dt` convergence protocol,
otherwise they can manufacture spurious criticality.

### Calibration Noise

I added a Fano-based criticality estimator stress test. It is intentionally
simple, but it shows the sampling problem:

```text
rho_true=0.97, horizon=5:  rho_hat_mean=0.912, bias=-0.058
rho_true=0.97, horizon=20: rho_hat_mean=0.979, bias= 0.009
rho_true=0.97, horizon=80: rho_hat_mean=0.997, bias= 0.027
```

The takeaway is not that this estimator is final. It demonstrates that
near-critical calibration is fragile and must be reported with uncertainty.

### Marked Multivariate Ogata Validation

I upgraded the estimator validation from scalar-only to marked multivariate
Ogata paths. The validation uses known three-type branching matrices with fixed
`beta=3` and fits the same fixed-beta marked estimator used for the LOBSTER
diagnostics:

```text
rho_true  mean events  rho_MAE  gamma_rel_F_error  mu_MAPE  success
0.35      1209.8       0.025    0.234              0.077    1.000
0.65      2171.2       0.023    0.133              0.113    1.000
```

This closes the previous scalar-only validation gap. The marked estimator is
not perfect on finite paths, but it recovers the spectral radius well and
keeps residual KS statistics small on controlled Ogata data.

### Corrected Public-Data Hawkes MLE Diagnostics

I corrected the univariate Hawkes likelihood so events are evaluated at
pre-event intensity. The estimator was then validated on synthetic Ogata paths:

```text
rho_true beta_true rho_MAE beta_MAPE beta_cap_rate
0.30     2.0       0.043   0.201     0.000
0.70     4.0       0.019   0.026     0.000
0.90     8.0       0.016   0.039     0.000
```

The corrected all-message LOBSTER fits still hit the beta upper bound for all
five tickers under the 100k-event cap, with `rho` roughly `0.64-0.76`. That is
now interpreted as a misspecification diagnostic rather than empirical proof of
structural criticality.

Event-type splits and timestamp aggregation make the story sharper:

```text
timestamp median beta: raw=148.4, 100us=104.5, 1ms=23.4, 10ms=1.46
timestamp median rho:  raw=0.575, 100us=0.445, 1ms=0.397, 10ms=0.558
```

The best publishable interpretation is: raw unmarked LOBSTER message arrivals
mix multiple clocks, event types, and timestamp-level bursts. They support the
need for self-exciting order-flow models, but robust market-making calibration
should use marked/multiscale Hawkes diagnostics or report the residual,
timestamp-sensitivity, and two-scale sensitivity tables.

I also added a constrained two-scale diagnostic with fixed decay pairs. Among
the tested pairs, all ticker/event-group panels select `(1, 100)` as the best
slow/fast pair. The median fitted fast-excitation share is:

```text
event group      rho     rho_slow  rho_fast  fast_share  residual_KS
all              0.7205  0.1742    0.5648    0.7642      0.1642
limit            0.6879  0.1891    0.4942    0.7233      0.1936
cancel/delete    0.6790  0.2254    0.4372    0.6599      0.1358
execution        0.7999  0.1010    0.6841    0.8714      0.4152
```

The result is useful but not a final structural calibration. It says execution
events are especially fast-scale dominated, while residual diagnostics still
reject the idea that a univariate two-exponential Hawkes fit is enough for
production-grade `Gamma`.

The stronger empirical addition is a grouped marked multivariate Hawkes fit on
limit, cancel/delete, and execution events. For each ticker I fit fixed-beta
three-mark exponential Hawkes models over `beta in {1, 5, 20, 100}` and select
by AIC. The best fixed beta is `100` for every ticker:

```text
ticker  beta  spectral_radius  mark_log_loss_gain  residual_KS
AAPL    100   0.3671           0.0250              0.0501
AMZN    100   0.5376           0.0606              0.1456
GOOG    100   0.6217           0.1142              0.2119
INTC    100   0.5252           0.0050              0.1751
MSFT    100   0.5410           0.0096              0.2165
```

Median branching matrix, with target intensity in rows and source event group
in columns:

```text
                limit  cancel_delete  execution
limit          0.2211         0.1483     0.3218
cancel_delete  0.1402         0.1365     0.1353
execution      0.0261         0.0143     0.3305
```

This gives the paper a real marked `Gamma` diagnostic. I then extended it to a
six-mark side-aware model using LOBSTER direction labels:

```text
ticker  beta  spectral_radius  mark_log_loss_gain  residual_KS
AAPL    100   0.3687           0.1007              0.0493
AMZN    100   0.5473           0.1645              0.1454
GOOG    100   0.6238           0.2919              0.2110
INTC    100   0.5297           0.1571              0.1756
MSFT    100   0.5464           0.1809              0.2159
```

Median side-aggregated branching, with target side in rows and source side in
columns:

```text
             buy_source  sell_source
buy_target       1.3542       0.4141
sell_target      0.4915       1.4031
```

These side aggregates can exceed one because they sum many target/source mark
pairs; the stability check is the spectral radius of the full six-mark matrix.
The caveat is now narrower: the calibration is side-aware, but still fixed-beta
and not queue-position-aware or power-law/multiscale.

I added a state-conditioned residual diagnostic on top of the six-mark model
instead of treating a higher-dimensional fit as automatically better. It
conditions time-rescaling residuals and conditional mark log-loss on event
group, side, within-ticker size bucket, spread bucket, imbalance bucket, and
top-depth bucket:

```text
state bucket         residual_mean  residual_KS  mark_log_loss_gain
wide spread          0.886          0.220        0.296
tight spread         1.110          0.092        0.097
large size           0.828          0.171        0.169
small size           1.018          0.155        0.131
execution marks      1.017          0.153        0.384
bid-heavy imbalance  0.983          0.220        0.171
```

This is useful negative evidence. The side-aware Hawkes fit predicts marks
better than unconditional frequencies, but residuals still vary materially by
spread, size, depth, and imbalance. That makes the empirical story more
journal-defensible: the public LOBSTER calibration is a diagnostic input for
stress testing, not a final production branching matrix.

I also ran an optional 12-mark event/side/size robustness fit with a 15k-event
cap. The fitted matrices are stable, with spectral radii from 0.270 to 0.500,
and mark-log-loss gains from 0.086 to 0.205 nats per event. However, optimizer
success is false for four of five tickers. This is useful as a warning against
over-parameterizing the public sample; the state-conditioned residual audit is
the stronger journal-facing result.

### Robust Market-Making Stress Test

The policy experiment now uses common random numbers across policies within each
`rho, epsilon` scenario and saves pathwise wealth for paired tests.

Average metrics over the full stress grid:

```text
policy                         CE       CVaR5    paired mean wealth diff vs nominal
robust_gamma                   31.13    -0.41    +12.55  [11.76, 13.25]
robust_vol_only                19.24   -10.98     +0.00  [0.00, 0.00]
nominal_hawkes                 19.24   -10.98      baseline
robust_gamma_abs                8.68   -27.62     -2.83  [-4.75, -0.85]
known_true_gamma_no_ambiguity   7.79   -24.97     -9.74  [-11.42, -8.11]
as_poisson                     -1.81   -25.98    -21.51  [-22.55, -20.55]
liquidity_guard                -7.42   -33.66    -25.58  [-27.02, -24.24]
```

The CE/CVaR columns above are averages of scenario-level risk metrics. The
artifact `results/tables/policy_ablation_table.csv` now also carries pooled
pathwise columns (`pooled_mean_wealth`, `pooled_cvar_5`, and
`pooled_certainty_equivalent`) so reviewers do not have to infer why pooled
bootstrap intervals differ numerically from averaged scenario summaries.

The relative-slack robust-Gamma policy is the cleanest headline synthetic
stress-test result. The absolute-Gamma and liquidity-guard variants are
regime-sensitive controls rather than uniformly better policies, which is useful
evidence for the paper: the normalization of ambiguity is not cosmetic; it
changes policy quality.

### Policy Time-Step Audit

I added `results/tables/policy_dt_convergence.csv` and
`results/figures/policy_dt_convergence.png` to answer the strongest numerical
objection: the headline policy table uses the fast binned Hawkes simulator even
though near-critical binned Hawkes counts can be biased.

The focused audit reruns the stressed `epsilon=0.02` scenarios for
`rho_hat=0.92` and `rho_hat=0.97` across `dt = 0.04, 0.02, 0.01, 0.005`.
The relative-slack robust-Gamma policy remains positive versus nominal at all
tested time steps:

```text
rho_hat=0.92: robust_gamma diff range = +0.046 to +0.098
rho_hat=0.97: robust_gamma diff range = +0.594 to +0.952
```

This time-step check materially strengthens the claim that the robust-Gamma
advantage is not a pure artifact of the default `dt=0.02` grid. The
absolute-Gamma policy is highly regime-sensitive in this audit, reinforcing the
normalization warning rather than replacing the main relative-slack result.

### Ogata Arrival Policy Audit

I added an event-driven arrival audit:

- table: `results/tables/policy_ogata_audit.csv`
- summary: `results/tables/policy_ogata_audit_summary.csv`
- figure: `results/figures/policy_ogata_audit.png`

The audit simulates arrivals two ways for the stressed `epsilon=0.02` scenarios:
the fast binned Hawkes recursion and Ogata-thinned event times binned onto the
same decision grid. The binned recursion produces more events in high stress,
which is consistent with the discretization-bias warning. Crucially,
`robust_gamma` remains positive versus nominal under both generators:

```text
rho_hat=0.92: discrete +0.028, Ogata-binned +0.077
rho_hat=0.97: discrete +0.495, Ogata-binned +0.546
```

This directly addresses the objection that the robust-Gamma result could be only
an artifact of the fast binned Hawkes recursion.

### Event-Queue Backtest

I added a reduced event-time queue backtest:

- raw paths: `results/raw/event_queue_backtest_path_wealth.csv`
- summary: `results/tables/event_queue_backtest_summary.csv`
- figure: `results/figures/event_queue_backtest.png`

The backtest reuses each Ogata event path across policies, updates quotes every
`dt=0.02`, tracks queue-ahead before fills, and records side-time spent not
quoting. The current full run has 480 path-policy rows. Mean wealth differences
versus nominal are:

```text
rho_hat=0.92: robust_gamma +0.019, robust_gamma_abs +0.523, liquidity_guard +0.523
rho_hat=0.97: robust_gamma +0.484, robust_gamma_abs +27.745, liquidity_guard -3.791
```

At `rho_hat=0.97`, the liquidity guard spends all side-time in full no-quote and
forgoes profitable flow, while absolute-Gamma cuts the fill rate and improves
mean wealth. This is still reduced and not production queue-calibrated, but it
is now a genuine event-time execution stress test.

### Public LOBSTER Top-Of-Book Replay

I added a replay diagnostic that uses actual LOBSTER message and order-book
streams instead of simulated Hawkes event paths:

- raw paths: `results/raw/lobster_top_of_book_replay.csv`
- summary: `results/tables/lobster_top_of_book_replay_summary.csv`
- figure: `results/figures/lobster_top_of_book_replay.png`
- offset-aware raw paths: `results/raw/lobster_l1_quote_replay.csv`
- offset-aware summary: `results/tables/lobster_l1_quote_replay_summary.csv`
- offset-aware figure: `results/figures/lobster_l1_quote_replay.png`

The replay posts active policies at the displayed best bid/ask, uses observed
execution sizes to deplete a simple queue-ahead proxy, caps inventory, and marks
to the observed midprice. With calibrated side-aware spectral radii, all
policies remain inside the top-of-book activity threshold, so the current
replay intentionally shows no artificial separation:

```text
mean terminal wealth: 341.691
mean fills:           3071.8
side no-quote share:  0.198
```

Under the near-critical stress setting `rho_hat=0.97`, nominal and
relative-slack robust-Gamma remain active, while absolute-Gamma and the
liquidity guard fully withdraw on the same public event streams:

```text
policy             wealth diff vs nominal   fills   side no-quote
robust_gamma          0.000                  3071.8  0.198
robust_gamma_abs   -341.691                     0.0  1.000
liquidity_guard    -341.691                     0.0  1.000
```

This is an important upgrade from purely synthetic queue replay, but it is still
top-of-book and proxy-queue based rather than a displayed-depth simulator.
I therefore added an L1 quote replay that uses each policy's continuous offsets
to classify quotes as joining the visible best quote, improving inside the
spread, resting away from L1, or withdrawing. Away quotes are not filled because
one-level data cannot identify hidden depth. Under calibrated side-aware
spectral radii, tick rounding still makes all policies coincide, but the replay
now explains the state mix:

```text
side-time join:      0.024
side-time improve:   0.428
side-time away:      0.448
side-time withdraw:  0.101
mean fills:          3517.0
```

Under `rho_hat=0.97`, absolute-Gamma and the liquidity guard again fully
withdraw. The relative-slack robust-Gamma policy widens its mean bid/ask
offsets, but not enough to change the L1 state after tick rounding on this
public sample. This is a useful negative result: the public replay can audit
withdrawal and visible quote placement, but it is not yet a production
execution benchmark.

I then added a displayed-depth replay using the uniform level-10 public LOBSTER
sample panel for all five tickers. This directly addresses the L1 limitation:
away-from-L1 quotes are now allowed to fill when their rounded quote price is
still inside the displayed 10-level ladder. Queue-ahead is initialized from all
better displayed levels plus a configurable same-level queue fraction, and both
observed executions and visible depth changes can deplete it.

- raw paths: `results/raw/lobster_depth_quote_replay.csv`
- summary: `results/tables/lobster_depth_quote_replay_summary.csv`
- figure: `results/figures/lobster_depth_quote_replay.png`

Under calibrated side-aware spectral radii, policies still coincide after tick
rounding, but the mechanism is now materially richer:

```text
mean terminal wealth:      120.216
mean fills:                1420.2
side-time join L1:         0.018
side-time improve:         0.428
side-time visible depth:   0.408
side-time withdraw:        0.146
mean visible depth rank:   2.431
```

Under `rho_hat=0.97`, nominal and relative-slack robust-Gamma stay active while
absolute-Gamma and the liquidity guard fully withdraw, with mean wealth
difference `-120.216` versus nominal and no fills. This is still not an
exchange-grade queue simulator because hidden liquidity and exact priority are
unobserved, but it is no longer an L1-only replay: it uses actual displayed
depth and permits fills away from the best quote when the public book supports
them.

I then tightened the level-10 replay into a priority-aware diagnostic. At each
quote reset, the synthetic order is placed behind the full displayed size at
the same price. Later same-price limit orders are tracked by order id as being
behind us, and later cancellations/executions of those behind orders are not
allowed to deplete our queue. This is much stricter than the displayed-depth
heuristic because it removes the capped same-level queue shortcut. The replay
now also requires residual same-price execution volume after displayed
queue-ahead depletion; exact queue exhaustion without residual volume is
recorded but does not fill, and partial fills are credited by residual lots.

- raw paths: `results/raw/lobster_priority_depth_quote_replay.csv`
- summary: `results/tables/lobster_priority_depth_quote_replay_summary.csv`
- figure: `results/figures/lobster_priority_depth_quote_replay.png`

Under calibrated side-aware spectral radii, the stricter priority accounting
exposes a hard realism result:

```text
mean terminal wealth:             -7.839
mean fill events:                 21.6
mean filled lots:                 15.526
side-time join L1:                0.019
side-time improve:                0.530
side-time visible depth:          0.422
side-time withdraw:               0.029
mean visible depth rank:          2.148
mean initial queue ahead:         62.027 lots
mean queued fills:                1.2
mean improve fills:               20.4
mean partial-fill events:         7.6
max zero-residual prevented fills: 1
max queue violations:             0
```

Under `rho_hat=0.97`, absolute-Gamma and the liquidity guard fully withdraw and
avoid the nominal priority-replay loss, giving mean wealth difference `+5.964`
versus nominal. This is still not exchange-grade exact priority because hidden
liquidity and anonymous queue already present before the synthetic quote are
not observable in public samples, but the invariant columns now make the
displayed-depth queue-position claim auditable: queued fills are credited only
from residual execution volume after displayed queue depletion, and the
regenerated public replay has zero queue-violation rows.

As a depth supplement, I added a deepest-public replay for the available level-50
AAPL/MSFT files. These public files use a shorter one-hour window, so they are
not a replacement for the uniform five-ticker level-10 panel. The supplement is
saved to `results/tables/lobster_deepest_public_priority_replay_summary.csv`;
under calibrated side-aware spectral radii it records mean fill events `23.0`,
mean filled lots `16.82`, mean queued fills `2.5`, mean improve fills `20.5`,
mean partial-fill events `8.0`, and max queue violations `0` while using all
50 displayed levels in those files.

To keep that caveat quantitative, I added a priority-assumption sensitivity
grid for the nominal policy. It varies the initial same-price displayed queue
fraction placed ahead of the synthetic order over `{0, 0.5, 1}` and a
queue-stress multiplier over `{1, 1.5, 2}`. The multiplier is applied to the
displayed queue-ahead proxy as a conservative stress test, not as observed
hidden depth.

- raw paths: `results/raw/lobster_priority_depth_sensitivity.csv`
- summary: `results/tables/lobster_priority_depth_sensitivity_summary.csv`
- figure: `results/figures/lobster_priority_depth_sensitivity.png`

On the calibrated level-10 panel, the best-case displayed-priority assumption
(`0` same-price queue fraction, multiplier `1`) has mean filled lots `16.53`.
The strict displayed-priority baseline (`1`, `1`) has mean filled lots `15.53`.
The most conservative tested queue-stress setting (`1`, `2`) has mean filled
lots `14.87`. These differences are small because public executions rarely
leave enough residual same-price volume after displayed queue depletion for the
synthetic quote to fill; that negative finding is useful because it shows
exactly where public displayed-depth replay runs out of execution-identification
power.

Finally, I added an observable order-book reconstruction audit. It initializes
the level-10 book from the official first LOBSTER snapshot, applies subsequent
message events while tracking post-start order IDs exactly, and re-anchors to
official snapshots every 100 messages to measure local reconstruction quality
rather than 80,000-message truncation drift.

- raw paths: `results/raw/lobster_orderbook_reconstruction.csv`
- summary: `results/tables/lobster_orderbook_reconstruction_summary.csv`
- figure: `results/figures/lobster_orderbook_reconstruction.png`

Across the five-ticker level-10 panel, the re-anchored audit processes 399,995
events and compares 40,000 snapshots. Mean top-of-book price match is `0.9997`
and mean full 10-level price match is `0.9376`. Top-of-book size MAE is only
`0.056` shares after re-anchoring, while full-depth size MAE is `38.1` shares.
This supports local message-level queue reconstruction near the best quote, but
also says deeper visible levels still carry truncation and anonymous-queue
drift. That is exactly the scope the priority replay should claim.

### Robust Inventory DP

The finite-scenario robust DP now solves a scalar reduced inventory problem for
relative-slack and absolute-Gamma ambiguity with explicit side-level no-quote
actions. The proof appendix now includes a finite-state robust Bellman
verification theorem for this finite-regime approximation and a compact
continuous-intensity multitype Hawkes HJBI verification theorem for the
truncated control game: under compact intensity state, compact controls and
ambiguity, bounded Lipschitz rates/rewards, and stable branching matrices, the
robust value is the unique bounded viscosity solution of the HJBI equation.
I also added an untruncated Lyapunov bridge: under a common subcriticality
vector `v > 0` satisfying `Gamma.T v <= (1-kappa) v` for every ambiguity
scenario, and controlled mark rates bounded by the Hawkes intensity, the
unprojected Hawkes PDMP is nonexplosive, has finite weighted moments, and
compact truncation errors are controlled by `C_T W_v(lambda)/R`.
The appendix now also adds weighted viscosity comparison for the same
untruncated model class, assuming compact controls/ambiguity, locally Lipschitz
rates and jump maps, linear `W_v` growth, and the weighted boundary condition
at infinity.
The refreshed full run produced the following action counts across the raw DP
policy grid:

```text
two_sided: 9947
bid_only:  4241
ask_only:  4241
no_quote:   579
```

The first-step, zero-inventory policy switches to full no-quote for
`rho_hat >= 0.97` across tested ambiguity radii. Mean no-quote rates over the
full DP grid are `0.457` for relative-slack ambiguity and `0.496` for
absolute-Gamma ambiguity; full two-sided withdrawal rates are `0.029` and
`0.032`. The finite Bellman layer, compact HJBI bridge, untruncated Lyapunov
bridge, weighted comparison theorem, smooth interior optimizer
differentiability theorem, and assembled end-to-end multitype control theorem
are now auditable for the stated model class. The remaining theory gaps are
no-quote/boundary active-set differentiability and extension of the same
weighted comparison checks to richer state-dependent or learned Hawkes kernels.

I added an implemented quote-map sensitivity diagnostic to connect that local
theory to the code path:

- raw: `results/raw/quote_sensitivity_diagnostic.csv`
- summary: `results/tables/quote_sensitivity_diagnostic_summary.csv`
- figure: `results/figures/quote_sensitivity_diagnostic.png`

For `d half-spread / d rho`, nominal Hawkes and relative-Gamma robust policies
match exponent `3.000` exactly on the smooth grid. Absolute-Gamma robust
policies approach exponent `4.000` in the uncapped smooth region; the largest
epsilon fit gives `3.974` before the spread cap/no-quote nonsmoothness binds.

### Finite-N Error Proxy

The finite-N proxy now uses the closed-form Gaussian absolute-error moment
instead of Monte Carlo sampling, making the table deterministic:

```text
mean error ~ N^(-0.500) * (1-rho)^(-1.000)
```

This matches the intended finite-population warning: mean-field error decays at
root-`N` rate, but the constant grows sharply near criticality.

### Public LOBSTER Sanity Panel

I fetched one-level public LOBSTER sample data for AAPL, AMZN, GOOG, INTC, and
MSFT from the Hugging Face mirror of LOBSTER sample files. This panel is not
used to claim empirical proof of MESA, but it checks that public order-book
events show clustered, overdispersed flow:

```text
ticker rows    events/sec  Fano     lag1 count proxy  mean spread
AAPL   118497    5.06       19.46    0.278             0.155
AMZN    57515    2.46       13.33    0.134             0.136
GOOG    49482    2.11       17.18    0.308             0.311
INTC   404986   17.31      220.65    0.109             0.013
MSFT   411409   17.58      196.49    0.081             0.013
```

The right claim is modest: the public samples motivate self-exciting order-flow
models and provide a sanity check for event clustering. They do not identify
agent types or prove structural `Gamma` uncertainty.

### Public Crypto L2 Depth Panel

I also fetched public one-minute, 30-level crypto L2 depth samples for BTC, ETH,
and SOL from Hugging Face. These are not event-message data, so they are used
for liquidity-state sanity checks rather than Hawkes calibration.

```text
symbol rows   mean spread  rel spread bps  return std  depth Fano
BTC    10081  1.354        0.163           0.000687    33.99
ETH    10081  0.112        0.591           0.000910   513.70
SOL    10080  0.012        0.911           0.001110  1697.61
```

This broadens the empirical section beyond one equity dataset family: equity
message data shows clustered events; crypto L2 snapshots show strongly
overdispersed depth/liquidity states.

### Public Binance Aggregate-Trade Event Panel

To avoid relying on crypto snapshots alone, I added a public Binance spot
aggregate-trade panel for BTCUSDT, ETHUSDT, and SOLUSDT on 2024-01-15:

- raw files: `data/raw/binance/aggTrades/*-aggTrades-2024-01-15.zip`
- one-second summaries: `results/raw/binance_*_2024-01-15_aggtrades_1s.csv`
- sanity summary: `results/tables/binance_aggtrades_sanity_summary.csv`
- Hawkes fits: `results/tables/binance_aggtrades_hawkes_best.csv`
- figure: `results/figures/binance_aggtrades_hawkes.png`

The panel gives a real public crypto event stream, not just order-book
snapshots:

```text
symbol   aggregate trades  underlying trades  agg trades/sec  Fano   ACF1
BTCUSDT  1,364,603         1,657,611          15.79           200.27 0.342
ETHUSDT    597,417           789,378           6.91            29.73 0.241
SOLUSDT    218,278           434,916           2.53            12.24 0.201
```

I fit fixed-beta univariate Hawkes diagnostics over all aggregate trades,
buy-aggressor trades, and sell-aggressor trades. The current grid selects
`beta=100` for every symbol/group. Best all-event branching ratios are:

```text
BTCUSDT rho=0.351, KS=0.071
ETHUSDT rho=0.313, KS=0.093
SOLUSDT rho=0.153, KS=0.036
```

Sell-aggressor fits are larger for BTCUSDT and ETHUSDT (`rho=0.493` and
`0.463`), while SOLUSDT is lower (`rho=0.264`). This strengthens the empirical
motivation for self-exciting order-flow models across asset classes. It does
not provide a full LOB event stream, queue state, or participant identity, so it
should be reported as event-clustering and Hawkes-diagnostic evidence rather
than as an execution benchmark.

I also expanded the Binance check to three public dates: 2024-01-15,
2024-04-15, and 2024-07-15. The cross-date panel is saved at
`results/tables/binance_aggtrades_cross_date_sanity_summary.csv`; the Hawkes
robustness outputs are `results/tables/binance_aggtrades_hawkes_cross_date_best.csv`,
`results/tables/binance_aggtrades_hawkes_cross_date_summary.csv`, and
`results/figures/binance_aggtrades_cross_date_hawkes.png`. Across all-event
fits, the branching ranges are:

```text
BTCUSDT: rho 0.172 to 0.380, median 0.351
ETHUSDT: rho 0.198 to 0.521, median 0.313
SOLUSDT: rho 0.117 to 0.328, median 0.153
```

This keeps the crypto event evidence from resting on a single trading day.

## What Needs Upgrading Next

- Extend the side-aware fixed-beta marked residual diagnostics to fitted
  state-dependent, queue-position-aware, multiscale or power-law Hawkes kernels
  and external package cross-checks where environment compatibility permits.
- Exchange-grade hidden-liquidity and anonymous-priority reconstruction remains
  outside what public LOBSTER samples can certify; any production calibration of
  no-quote thresholds should use venue-grade order-lifecycle data.
