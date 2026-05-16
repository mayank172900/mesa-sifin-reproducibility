"""Observable LOBSTER order-book reconstruction diagnostics.

The public LOBSTER sample files provide message rows and synchronized book
snapshots, but the first snapshot already contains anonymous standing queue.
This module reconstructs the visible top levels from that first snapshot plus
subsequent message events, tracking post-start order IDs exactly where
available and measuring drift against the official snapshots.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from mesa.empirical import load_lobster_message, load_lobster_orderbook


@dataclass(frozen=True)
class ReconstructionConfig:
    levels: int = 10
    max_events: int = 80_000
    compare_every: int = 10
    reanchor_every_events: int = 100
    price_scale: float = 1e-4


@dataclass
class TrackedOrder:
    side: str
    price: int
    size: float


def _lobster_paths(data_root: Path, ticker: str, levels: int) -> tuple[Path, Path]:
    folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
    base = f"{ticker}_2012-06-21_34200000_57600000"
    return folder / f"{base}_message_{levels}.csv", folder / f"{base}_orderbook_{levels}.csv"


def _resting_side(direction: int) -> str | None:
    if direction == 1:
        return "bid"
    if direction == -1:
        return "ask"
    return None


class ObservableBook:
    """Top-level aggregate book plus exact post-start order-id inventory."""

    def __init__(self, orderbook: pd.DataFrame, levels: int, row_idx: int = 0) -> None:
        self.levels = levels
        self.sizes: dict[str, defaultdict[int, float]] = {
            "bid": defaultdict(float),
            "ask": defaultdict(float),
        }
        self.orders: dict[object, TrackedOrder] = {}
        self.known_reductions = 0
        self.anonymous_reductions = 0
        self.missing_reductions = 0
        self.hidden_executions = 0
        self.ignored_events = 0
        self.overshoot_size = 0.0
        self.known_added_size = 0.0
        self.anonymous_reduced_size = 0.0
        self.known_reduced_size = 0.0
        for level in range(1, levels + 1):
            for side in ("bid", "ask"):
                price = int(orderbook.at[row_idx, f"{side}_price_{level}"])
                size = float(orderbook.at[row_idx, f"{side}_size_{level}"])
                if price > 0 and size > 0:
                    self.sizes[side][price] += size

    def apply_message(self, row: pd.Series) -> None:
        event_type = int(row["event_type"])
        order_id = row["order_id"]
        size = float(row["size"])
        price = int(row["price"])
        direction = int(row["direction"])
        if event_type == 1:
            side = _resting_side(direction)
            if side is None or price <= 0 or size <= 0:
                self.ignored_events += 1
                return
            self.sizes[side][price] += size
            self.orders[order_id] = TrackedOrder(side=side, price=price, size=size)
            self.known_added_size += size
            return
        if event_type in {2, 3, 4}:
            self._reduce_order(order_id, price, size, direction, event_type)
            return
        if event_type == 5:
            self.hidden_executions += 1
            return
        self.ignored_events += 1

    def _reduce_order(self, order_id: object, price: int, size: float, direction: int, event_type: int) -> None:
        tracked = self.orders.get(order_id)
        if tracked is not None:
            reduction = tracked.size if event_type == 3 else min(size, tracked.size)
            self._reduce_aggregate(tracked.side, tracked.price, reduction)
            tracked.size = max(tracked.size - reduction, 0.0)
            if tracked.size <= 1e-12 or event_type == 3:
                self.orders.pop(order_id, None)
            self.known_reductions += 1
            self.known_reduced_size += reduction
            return
        side = _resting_side(direction)
        if side is None or price <= 0 or size <= 0:
            self.missing_reductions += 1
            return
        before = self.sizes[side].get(price, 0.0)
        if before <= 1e-12:
            self.missing_reductions += 1
            return
        self._reduce_aggregate(side, price, size)
        self.anonymous_reductions += 1
        self.anonymous_reduced_size += min(size, before)

    def _reduce_aggregate(self, side: str, price: int, size: float) -> None:
        before = self.sizes[side].get(price, 0.0)
        after = before - size
        if after < -1e-9:
            self.overshoot_size += float(-after)
        if after <= 1e-12:
            self.sizes[side].pop(price, None)
        else:
            self.sizes[side][price] = after

    def top_levels(self, side: str, levels: int) -> list[tuple[int, float]]:
        reverse = side == "bid"
        rows = [(p, s) for p, s in self.sizes[side].items() if s > 1e-12]
        rows.sort(key=lambda item: item[0], reverse=reverse)
        if len(rows) < levels:
            rows.extend([(0, 0.0)] * (levels - len(rows)))
        return rows[:levels]


def _snapshot_levels(orderbook: pd.DataFrame, row_idx: int, side: str, levels: int) -> list[tuple[int, float]]:
    return [
        (int(orderbook.at[row_idx, f"{side}_price_{level}"]), float(orderbook.at[row_idx, f"{side}_size_{level}"]))
        for level in range(1, levels + 1)
    ]


def audit_lobster_orderbook_reconstruction(
    message: pd.DataFrame,
    orderbook: pd.DataFrame,
    *,
    ticker: str,
    cfg: ReconstructionConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reconstruct visible book levels from messages and compare to snapshots."""
    cfg = cfg or ReconstructionConfig()
    n = min(len(message), len(orderbook), cfg.max_events)
    if n < 2:
        raise ValueError("at least two synchronized LOBSTER rows are required")
    levels = cfg.levels
    msg = message.iloc[:n].reset_index(drop=True)
    book_df = orderbook.iloc[:n].reset_index(drop=True)
    book = ObservableBook(book_df, levels=levels, row_idx=0)
    rows: list[dict[str, float | int | str]] = []

    for idx in range(1, n):
        book.apply_message(msg.iloc[idx])
        if idx % max(cfg.compare_every, 1) != 0 and idx != n - 1:
            if cfg.reanchor_every_events > 0 and idx % cfg.reanchor_every_events == 0:
                book = ObservableBook(book_df, levels=levels, row_idx=idx)
            continue
        row: dict[str, float | int | str] = {
            "ticker": ticker,
            "row_idx": idx,
            "levels": levels,
            "reanchor_every_events": int(cfg.reanchor_every_events),
        }
        price_matches = []
        size_abs_errors = []
        top1_price_matches = []
        top1_size_errors = []
        for side in ("bid", "ask"):
            reconstructed = book.top_levels(side, levels)
            observed = _snapshot_levels(book_df, idx, side, levels)
            for level_idx, ((rec_price, rec_size), (obs_price, obs_size)) in enumerate(
                zip(reconstructed, observed, strict=True),
                start=1,
            ):
                price_match = int(rec_price == obs_price)
                price_matches.append(price_match)
                size_abs_errors.append(abs(rec_size - obs_size))
                if level_idx == 1:
                    top1_price_matches.append(price_match)
                    top1_size_errors.append(abs(rec_size - obs_size))
                    row[f"{side}_top1_price_match"] = price_match
                    row[f"{side}_top1_size_abs_error"] = abs(rec_size - obs_size)
                    row[f"{side}_top1_rec_price"] = rec_price * cfg.price_scale
                    row[f"{side}_top1_obs_price"] = obs_price * cfg.price_scale
        row.update(
            {
                "level_price_match_rate": float(np.mean(price_matches)),
                "level_size_mae": float(np.mean(size_abs_errors)),
                "top1_price_match_rate": float(np.mean(top1_price_matches)),
                "top1_size_mae": float(np.mean(top1_size_errors)),
                "known_active_orders": len(book.orders),
                "known_reductions": book.known_reductions,
                "anonymous_reductions": book.anonymous_reductions,
                "missing_reductions": book.missing_reductions,
                "hidden_executions": book.hidden_executions,
                "ignored_events": book.ignored_events,
                "overshoot_size": float(book.overshoot_size),
                "known_added_size": float(book.known_added_size),
                "known_reduced_size": float(book.known_reduced_size),
                "anonymous_reduced_size": float(book.anonymous_reduced_size),
            }
        )
        rows.append(row)
        if cfg.reanchor_every_events > 0 and idx % cfg.reanchor_every_events == 0:
            book = ObservableBook(book_df, levels=levels, row_idx=idx)

    raw = pd.DataFrame(rows)
    if raw.empty:
        summary = pd.DataFrame(
            [
                {
                    "ticker": ticker,
                    "levels": levels,
                    "reanchor_every_events": int(cfg.reanchor_every_events),
                    "rows_compared": 0,
                    "events_processed": n - 1,
                }
            ]
        )
    else:
        last = raw.iloc[-1]
        summary = pd.DataFrame(
            [
                {
                    "ticker": ticker,
                    "levels": levels,
                    "reanchor_every_events": int(cfg.reanchor_every_events),
                    "rows_compared": len(raw),
                    "events_processed": n - 1,
                    "mean_level_price_match_rate": float(raw["level_price_match_rate"].mean()),
                    "mean_top1_price_match_rate": float(raw["top1_price_match_rate"].mean()),
                    "mean_level_size_mae": float(raw["level_size_mae"].mean()),
                    "mean_top1_size_mae": float(raw["top1_size_mae"].mean()),
                    "bid_top1_price_match_rate": float(raw["bid_top1_price_match"].mean()),
                    "ask_top1_price_match_rate": float(raw["ask_top1_price_match"].mean()),
                    "bid_top1_size_mae": float(raw["bid_top1_size_abs_error"].mean()),
                    "ask_top1_size_mae": float(raw["ask_top1_size_abs_error"].mean()),
                    "known_active_orders_final": int(last["known_active_orders"]),
                    "known_reductions_final": int(last["known_reductions"]),
                    "anonymous_reductions_final": int(last["anonymous_reductions"]),
                    "missing_reductions_final": int(last["missing_reductions"]),
                    "hidden_executions_final": int(last["hidden_executions"]),
                    "ignored_events_final": int(last["ignored_events"]),
                    "overshoot_size_final": float(last["overshoot_size"]),
                    "known_added_size_final": float(last["known_added_size"]),
                    "known_reduced_size_final": float(last["known_reduced_size"]),
                    "anonymous_reduced_size_final": float(last["anonymous_reduced_size"]),
                }
            ]
        )
    return raw, summary


def run_lobster_orderbook_reconstruction_audit(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 10,
    max_events: int = 80_000,
    compare_every: int = 10,
    reanchor_every_events: int = 100,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run reconstruction diagnostics over the public LOBSTER panel."""
    raw_frames = []
    summary_frames = []
    cfg = ReconstructionConfig(
        levels=levels,
        max_events=max_events,
        compare_every=compare_every,
        reanchor_every_events=reanchor_every_events,
    )
    for ticker in tickers:
        msg_path, book_path = _lobster_paths(data_root, ticker, levels)
        if not msg_path.exists() or not book_path.exists():
            raise FileNotFoundError(f"missing LOBSTER files for {ticker}: {msg_path}, {book_path}")
        message = load_lobster_message(msg_path)
        orderbook = load_lobster_orderbook(book_path, levels=levels)
        raw, summary = audit_lobster_orderbook_reconstruction(message, orderbook, ticker=ticker, cfg=cfg)
        raw_frames.append(raw)
        summary_frames.append(summary)
    raw_all = pd.concat(raw_frames, ignore_index=True)
    summary_all = pd.concat(summary_frames, ignore_index=True).sort_values("ticker")
    panel = pd.DataFrame(
        [
            {
                "ticker": "PANEL",
                "levels": levels,
                "reanchor_every_events": int(reanchor_every_events),
                "rows_compared": int(summary_all["rows_compared"].sum()),
                "events_processed": int(summary_all["events_processed"].sum()),
                "mean_level_price_match_rate": float(summary_all["mean_level_price_match_rate"].mean()),
                "mean_top1_price_match_rate": float(summary_all["mean_top1_price_match_rate"].mean()),
                "mean_level_size_mae": float(summary_all["mean_level_size_mae"].mean()),
                "mean_top1_size_mae": float(summary_all["mean_top1_size_mae"].mean()),
                "bid_top1_price_match_rate": float(summary_all["bid_top1_price_match_rate"].mean()),
                "ask_top1_price_match_rate": float(summary_all["ask_top1_price_match_rate"].mean()),
                "bid_top1_size_mae": float(summary_all["bid_top1_size_mae"].mean()),
                "ask_top1_size_mae": float(summary_all["ask_top1_size_mae"].mean()),
                "known_active_orders_final": int(summary_all["known_active_orders_final"].sum()),
                "known_reductions_final": int(summary_all["known_reductions_final"].sum()),
                "anonymous_reductions_final": int(summary_all["anonymous_reductions_final"].sum()),
                "missing_reductions_final": int(summary_all["missing_reductions_final"].sum()),
                "hidden_executions_final": int(summary_all["hidden_executions_final"].sum()),
                "ignored_events_final": int(summary_all["ignored_events_final"].sum()),
                "overshoot_size_final": float(summary_all["overshoot_size_final"].sum()),
                "known_added_size_final": float(summary_all["known_added_size_final"].sum()),
                "known_reduced_size_final": float(summary_all["known_reduced_size_final"].sum()),
                "anonymous_reduced_size_final": float(summary_all["anonymous_reduced_size_final"].sum()),
            }
        ]
    )
    summary_out = pd.concat([summary_all, panel], ignore_index=True)
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    raw_all.to_csv(results_root / "raw" / "lobster_orderbook_reconstruction.csv", index=False)
    summary_out.to_csv(results_root / "tables" / "lobster_orderbook_reconstruction_summary.csv", index=False)
    return raw_all, summary_out
