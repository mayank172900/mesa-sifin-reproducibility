import pandas as pd
from pathlib import Path

from mesa.empirical import summarize_binance_agg_trades, summarize_crypto_depth, summarize_lobster_sample


def test_lobster_summary_has_burstiness_columns():
    message = pd.DataFrame(
        {
            "time": [1.0, 1.1, 1.4, 2.2, 3.0],
            "event_type": [1, 4, 3, 5, 2],
            "order_id": [1, 2, 3, 4, 5],
            "size": [10, 20, 30, 40, 50],
            "price": [100, 101, 102, 103, 104],
            "direction": [1, -1, 1, -1, 1],
        }
    )
    binned, summary = summarize_lobster_sample(message, bin_seconds=1.0)
    assert "events" in binned.columns
    assert "event_count_fano" in summary.columns
    assert summary.loc[0, "rows"] == 5


def test_crypto_depth_summary():
    df = pd.DataFrame(
        {
            "timestamp": ["t0", "t1", "t2"],
            "bid_1_px": [99.0, 100.0, 101.0],
            "ask_1_px": [101.0, 102.0, 103.0],
            "bid_1_sz": [1.0, 2.0, 3.0],
            "ask_1_sz": [2.0, 2.0, 1.0],
            "bid_2_sz": [1.0, 1.0, 1.0],
            "ask_2_sz": [1.0, 1.0, 1.0],
        }
    )
    path = "/tmp/mesa_crypto_depth_test.csv"
    df.to_csv(path, index=False)
    summary = summarize_crypto_depth(Path(path), "TEST")
    assert summary.loc[0, "symbol"] == "TEST"
    assert summary.loc[0, "rows"] == 3


def test_binance_aggtrade_summary(tmp_path):
    df = pd.DataFrame(
        {
            0: [1, 2, 3, 4],
            1: [100.0, 100.5, 100.25, 100.75],
            2: [0.2, 0.3, 0.1, 0.4],
            3: [10, 11, 12, 13],
            4: [10, 12, 12, 15],
            5: [1_700_000_000_000, 1_700_000_000_500, 1_700_000_001_000, 1_700_000_002_000],
            6: [True, False, True, False],
            7: [True, True, True, True],
        }
    )
    path = tmp_path / "TEST-aggTrades-2024-01-15.csv"
    df.to_csv(path, header=False, index=False)
    binned, summary = summarize_binance_agg_trades(path, "TEST", "2024-01-15", bin_seconds=1.0)
    assert summary.loc[0, "symbol"] == "TEST"
    assert summary.loc[0, "rows"] == 4
    assert summary.loc[0, "underlying_trades"] == 7
    assert "agg_trades" in binned.columns
