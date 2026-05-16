# Displayed-depth queue-position replay completion note

Date: 2026-05-16

This note records the strongest queue-position replay claim supported by the
public LOBSTER samples in this package.

## Completed public-data replay

The priority-aware LOBSTER replay uses all displayed levels present in the
loaded order-book file. For the public panel this is the level-10 LOBSTER
sample; a separate deepest-public supplement also runs the available level-50
AAPL/MSFT samples. At each quote reset it:

- rounds the policy quote to the tick grid and classifies it as L1, inside
  spread, displayed depth, outside displayed depth, or withdrawn;
- places the synthetic quote behind all better displayed levels and behind the
  configured fraction of same-price displayed size;
- tracks later same-price limit orders by `order_id` as behind the synthetic
  quote;
- ignores cancellations/executions of those behind orders when updating queue
  position;
- depletes queue ahead only through same-price or better-price events that are
  not known to be behind;
- fills queued quotes only with residual same-price execution volume after
  displayed queue ahead has been depleted, while inside-spread improve quotes
  can fill immediately at their displayed price;
- credits partial fills when residual volume is smaller than the synthetic
  order size, and records exact queue-exhaustion events that do not fill because
  no residual execution volume remains.

## Auditable diagnostics now written to artifacts

The raw and summary replay tables include:

- `priority_initial_ahead_lots`;
- `priority_visible_quote_resets`;
- `priority_mean_initial_ahead_lots`;
- `priority_visible_levels_used`;
- `priority_min_visible_depth_rank`;
- `priority_max_visible_depth_rank`;
- `priority_queue_fills`;
- `priority_improve_fills`;
- `priority_queue_violation_count`;
- `priority_partial_fill_events`;
- `priority_residual_fill_lots`;
- `priority_zero_residual_fill_prevented`;
- `total_fill_lots`.

The raw artifacts expose the implementation-level guard:

```text
priority_queue_violation_count == 0
```

for every row, plus separate queued-fill and inside-spread-improve fill
counts. The replay also records cases where the displayed queue is exhausted
but the triggering execution has no residual volume, preventing a fill. These
counters are not an independent market-data proof by themselves; they are
auditable diagnostics of the replay code path. The stronger evidence is the
combination of these artifacts, unit tests that construct exact-exhaustion and
partial-fill cases, and the implementation rule that non-improve fills are only
credited from residual same-price execution volume after displayed queue ahead
is depleted.

## Honest boundary

This is a full replay of the displayed depths present in the public files, not
a claim of exchange-private full-depth priority. The uniform five-ticker panel
uses public level-10 books; the deepest-public supplement uses the available
level-50 AAPL/MSFT books on their shorter one-hour window. Hidden liquidity,
anonymous queue already present before the synthetic quote, and venues' private
matching-engine state remain unobserved in public samples, so the paper keeps
production execution claims out of scope.
