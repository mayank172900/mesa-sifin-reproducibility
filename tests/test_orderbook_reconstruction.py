import pandas as pd

from mesa.orderbook_reconstruction import ReconstructionConfig, audit_lobster_orderbook_reconstruction


def _book_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ask_price_1": [10100, 10100, 10100, 10100],
            "ask_size_1": [100, 100, 100, 100],
            "bid_price_1": [9900, 10000, 9900, 9900],
            "bid_size_1": [100, 50, 100, 70],
            "ask_price_2": [10200, 10200, 10200, 10200],
            "ask_size_2": [100, 100, 100, 100],
            "bid_price_2": [9800, 9900, 9800, 9800],
            "bid_size_2": [100, 100, 100, 100],
        }
    )


def test_observable_reconstruction_tracks_post_start_order_ids():
    message = pd.DataFrame(
        {
            "time": [0.0, 0.1, 0.2, 0.3],
            "event_type": [1, 1, 3, 2],
            "order_id": [1, 42, 42, 0],
            "size": [100, 50, 50, 30],
            "price": [9900, 10000, 10000, 9900],
            "direction": [1, 1, 1, 1],
        }
    )
    raw, summary = audit_lobster_orderbook_reconstruction(
        message,
        _book_rows(),
        ticker="TST",
        cfg=ReconstructionConfig(levels=2, max_events=4, compare_every=1),
    )
    assert len(raw) == 3
    assert summary.loc[0, "mean_top1_price_match_rate"] == 1.0
    assert summary.loc[0, "mean_level_price_match_rate"] == 1.0
    assert summary.loc[0, "known_reductions_final"] == 1
    assert summary.loc[0, "anonymous_reductions_final"] == 1
    assert summary.loc[0, "missing_reductions_final"] == 0
