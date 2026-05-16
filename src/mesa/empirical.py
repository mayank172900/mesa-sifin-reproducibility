"""Empirical sanity checks for public LOBSTER sample data."""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
import pandas as pd


MESSAGE_COLUMNS = ["time", "event_type", "order_id", "size", "price", "direction"]
ORDERBOOK_COLUMNS_1 = ["ask_price_1", "ask_size_1", "bid_price_1", "bid_size_1"]
BINANCE_AGG_TRADE_COLUMNS = [
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "is_buyer_maker",
    "is_best_match",
]
DEFAULT_BINANCE_AGGTRADE_DATE = "2024-01-15"
DEFAULT_BINANCE_AGGTRADE_DATES = ("2024-01-15", "2024-04-15", "2024-07-15")
LOBSTER_HF_REPO_ID = "totalorganfailure/lobster-data"


def load_lobster_message(path: Path) -> pd.DataFrame:
    """Load a LOBSTER message CSV with canonical column names."""
    return pd.read_csv(path, header=None, names=MESSAGE_COLUMNS)


def load_lobster_orderbook_1(path: Path) -> pd.DataFrame:
    """Load a one-level LOBSTER orderbook CSV with canonical column names."""
    return load_lobster_orderbook(path, levels=1)


def load_lobster_orderbook(path: Path, levels: int) -> pd.DataFrame:
    """Load a LOBSTER orderbook CSV with canonical per-level column names."""
    cols: list[str] = []
    for level in range(1, levels + 1):
        cols.extend([f"ask_price_{level}", f"ask_size_{level}", f"bid_price_{level}", f"bid_size_{level}"])
    return pd.read_csv(path, header=None, names=cols)


def summarize_lobster_sample(
    message: pd.DataFrame,
    orderbook: pd.DataFrame | None = None,
    bin_seconds: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute event-count and spread sanity summaries from LOBSTER sample data."""
    msg = message.copy()
    msg["bin"] = np.floor((msg["time"] - msg["time"].min()) / bin_seconds).astype(int)
    msg["is_execution"] = msg["event_type"].isin([4, 5])
    msg["is_limit"] = msg["event_type"].eq(1)
    msg["is_cancel_delete"] = msg["event_type"].isin([2, 3])
    msg["is_buy_side"] = msg["direction"].eq(1)
    msg["is_sell_side"] = msg["direction"].eq(-1)

    binned = msg.groupby("bin").agg(
        start_time=("time", "min"),
        end_time=("time", "max"),
        events=("event_type", "size"),
        executions=("is_execution", "sum"),
        limits=("is_limit", "sum"),
        cancels_deletes=("is_cancel_delete", "sum"),
        buy_side=("is_buy_side", "sum"),
        sell_side=("is_sell_side", "sum"),
        volume=("size", "sum"),
    )
    binned = binned.reset_index()
    if len(binned) > 1:
        binned["event_count_lag1"] = binned["events"].shift(1)
        acf1 = binned[["events", "event_count_lag1"]].dropna().corr().iloc[0, 1]
    else:
        acf1 = np.nan
    fano = float(binned["events"].var(ddof=1) / max(binned["events"].mean(), 1e-12))

    summary = {
        "rows": len(msg),
        "start_seconds": float(msg["time"].min()),
        "end_seconds": float(msg["time"].max()),
        "duration_seconds": float(msg["time"].max() - msg["time"].min()),
        "bin_seconds": bin_seconds,
        "event_rate_per_second": float(len(msg) / max(msg["time"].max() - msg["time"].min(), 1e-12)),
        "execution_share": float(msg["is_execution"].mean()),
        "limit_share": float(msg["is_limit"].mean()),
        "cancel_delete_share": float(msg["is_cancel_delete"].mean()),
        "event_count_fano": fano,
        "event_count_acf1": float(acf1),
        "criticality_proxy_acf1_clipped": float(np.clip(acf1, 0.0, 0.999)) if np.isfinite(acf1) else np.nan,
    }

    if orderbook is not None and len(orderbook) == len(msg):
        ob = orderbook.copy()
        ob["mid"] = 0.5 * (ob["ask_price_1"] + ob["bid_price_1"]) * 1e-4
        ob["spread"] = (ob["ask_price_1"] - ob["bid_price_1"]) * 1e-4
        summary.update(
            {
                "mean_spread": float(ob["spread"].mean()),
                "median_spread": float(ob["spread"].median()),
                "mean_mid": float(ob["mid"].mean()),
                "mid_return_std": float(ob["mid"].diff().dropna().std()),
            }
        )

    return binned, pd.DataFrame([summary])


def _lobster_hf_filenames(ticker: str, levels: int) -> tuple[str, str]:
    """Resolve public LOBSTER message/orderbook names for variable sample windows."""
    from huggingface_hub import HfApi

    folder = f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
    files = HfApi().list_repo_files(LOBSTER_HF_REPO_ID, repo_type="dataset")
    prefix = f"{folder}/"
    messages = sorted(
        path for path in files if path.startswith(prefix) and path.endswith(f"_message_{levels}.csv")
    )
    orderbooks = sorted(
        path for path in files if path.startswith(prefix) and path.endswith(f"_orderbook_{levels}.csv")
    )
    if not messages or not orderbooks:
        raise FileNotFoundError(f"no public LOBSTER sample found for {ticker} at {levels} levels")
    return messages[0], orderbooks[0]


def download_lobster_sample(data_root: Path, ticker: str = "INTC", levels: int = 1) -> tuple[Path, Path]:
    """Download a small LOBSTER sample from the public Hugging Face mirror."""
    from huggingface_hub import hf_hub_download

    message_name, orderbook_name = _lobster_hf_filenames(ticker, levels)
    data_root.mkdir(parents=True, exist_ok=True)
    message = hf_hub_download(
        repo_id=LOBSTER_HF_REPO_ID,
        repo_type="dataset",
        filename=message_name,
        local_dir=data_root,
    )
    orderbook = hf_hub_download(
        repo_id=LOBSTER_HF_REPO_ID,
        repo_type="dataset",
        filename=orderbook_name,
        local_dir=data_root,
    )
    return Path(message), Path(orderbook)


def run_lobster_sanity(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    ticker: str = "INTC",
    levels: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download and summarize a public LOBSTER sample."""
    message_path, orderbook_path = download_lobster_sample(data_root, ticker=ticker, levels=levels)
    message = load_lobster_message(message_path)
    orderbook = load_lobster_orderbook(orderbook_path, levels=levels)
    binned, summary = summarize_lobster_sample(message, orderbook)
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    binned.to_csv(results_root / "raw" / f"lobster_{ticker}_{levels}_binned_events.csv", index=False)
    summary.to_csv(results_root / "tables" / f"lobster_{ticker}_{levels}_sanity_summary.csv", index=False)
    return binned, summary


def run_lobster_panel(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
) -> pd.DataFrame:
    """Download and summarize a panel of public LOBSTER samples."""
    frames = []
    for ticker in tickers:
        _, summary = run_lobster_sanity(data_root, results_root, ticker=ticker, levels=levels)
        summary.insert(0, "ticker", ticker)
        frames.append(summary)
    panel = pd.concat(frames, ignore_index=True).sort_values("ticker")
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    panel.to_csv(results_root / "tables" / "lobster_panel_sanity_summary.csv", index=False)
    return panel


def summarize_crypto_depth(path: Path, symbol: str) -> pd.DataFrame:
    """Summarize one public crypto L2 depth CSV."""
    df = pd.read_csv(path)
    required = {"bid_1_px", "ask_1_px", "bid_1_sz", "ask_1_sz"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing columns in {path}: {sorted(missing)}")
    mid = 0.5 * (df["bid_1_px"] + df["ask_1_px"])
    spread = df["ask_1_px"] - df["bid_1_px"]
    top_imbalance = (df["bid_1_sz"] - df["ask_1_sz"]) / (df["bid_1_sz"] + df["ask_1_sz"]).replace(0, np.nan)
    depth_cols = [c for c in df.columns if c.endswith("_sz")]
    total_depth = df[depth_cols].sum(axis=1)
    returns = mid.pct_change().dropna()
    return pd.DataFrame(
        [
            {
                "dataset": "crypto_l2_depth30",
                "symbol": symbol,
                "rows": len(df),
                "start_timestamp": str(df["timestamp"].iloc[0]) if "timestamp" in df else "",
                "end_timestamp": str(df["timestamp"].iloc[-1]) if "timestamp" in df else "",
                "mean_mid": float(mid.mean()),
                "mean_spread": float(spread.mean()),
                "median_spread": float(spread.median()),
                "relative_spread_bps": float((spread / mid).mean() * 1e4),
                "mid_return_std": float(returns.std()),
                "top_imbalance_mean": float(top_imbalance.mean()),
                "top_imbalance_std": float(top_imbalance.std()),
                "total_depth_mean": float(total_depth.mean()),
                "total_depth_fano": float(total_depth.var(ddof=1) / max(total_depth.mean(), 1e-12)),
            }
        ]
    )


def download_crypto_depth_sample(
    data_root: Path,
    symbol: str = "BTC",
    repo_id: str = "AdamAtractor/crypto-l2-orderbook-30-levels",
) -> Path:
    """Download a one-minute 30-level crypto L2 sample from Hugging Face."""
    from huggingface_hub import hf_hub_download

    data_root.mkdir(parents=True, exist_ok=True)
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename=f"{symbol}_1m_depth30.csv",
            local_dir=data_root,
        )
    )


def run_crypto_depth_sanity(
    data_root: Path = Path("data/raw/crypto_l2"),
    results_root: Path = Path("results"),
    symbols: tuple[str, ...] = ("BTC", "ETH", "SOL"),
) -> pd.DataFrame:
    """Download and summarize public crypto L2 samples."""
    frames = []
    for symbol in symbols:
        path = download_crypto_depth_sample(data_root, symbol=symbol)
        frames.append(summarize_crypto_depth(path, symbol=symbol))
    panel = pd.concat(frames, ignore_index=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    panel.to_csv(results_root / "tables" / "crypto_l2_sanity_summary.csv", index=False)
    return panel


def binance_aggtrade_url(symbol: str, date: str) -> str:
    """Return the public Binance spot daily aggTrades ZIP URL."""
    symbol = symbol.upper()
    return (
        "https://data.binance.vision/data/spot/daily/aggTrades/"
        f"{symbol}/{symbol}-aggTrades-{date}.zip"
    )


def download_binance_agg_trades(data_root: Path, symbol: str = "BTCUSDT", date: str = "2024-01-15") -> Path:
    """Download one public Binance spot daily aggTrades ZIP."""
    symbol = symbol.upper()
    data_root.mkdir(parents=True, exist_ok=True)
    path = data_root / f"{symbol}-aggTrades-{date}.zip"
    if not path.exists():
        urlretrieve(binance_aggtrade_url(symbol, date), path)
    return path


def load_binance_agg_trades(path: Path) -> pd.DataFrame:
    """Load a Binance aggTrades CSV/ZIP with canonical columns."""
    compression = "zip" if path.suffix == ".zip" else "infer"
    df = pd.read_csv(path, header=None, names=BINANCE_AGG_TRADE_COLUMNS, compression=compression)
    numeric_cols = ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id", "timestamp"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["timestamp", "price", "quantity"]).reset_index(drop=True)
    df["is_buyer_maker"] = df["is_buyer_maker"].astype(str).str.lower().isin(["true", "1"])
    df["is_best_match"] = df["is_best_match"].astype(str).str.lower().isin(["true", "1"])
    df["underlying_trades"] = (df["last_trade_id"] - df["first_trade_id"] + 1).clip(lower=1)
    ts = df["timestamp"].to_numpy(dtype=float)
    divisor = 1e6 if np.nanmedian(ts) > 1e14 else 1e3
    df["time_seconds"] = ts / divisor
    df["event_time_seconds"] = df["time_seconds"] - float(df["time_seconds"].iloc[0])
    df["notional"] = df["price"] * df["quantity"]
    df["aggressor_side"] = np.where(df["is_buyer_maker"], "sell", "buy")
    return df


def summarize_binance_agg_trades(
    path: Path,
    symbol: str,
    date: str,
    bin_seconds: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize public Binance aggregate trade events."""
    trades = load_binance_agg_trades(path)
    trades["bin"] = np.floor(trades["event_time_seconds"] / bin_seconds).astype(int)
    binned = (
        trades.groupby("bin")
        .agg(
            start_seconds=("event_time_seconds", "min"),
            end_seconds=("event_time_seconds", "max"),
            agg_trades=("agg_trade_id", "size"),
            underlying_trades=("underlying_trades", "sum"),
            buy_aggressor=("aggressor_side", lambda x: int((x == "buy").sum())),
            sell_aggressor=("aggressor_side", lambda x: int((x == "sell").sum())),
            base_volume=("quantity", "sum"),
            notional=("notional", "sum"),
            vwap=("price", "mean"),
        )
        .reset_index()
    )
    if len(binned) > 1:
        binned["agg_trades_lag1"] = binned["agg_trades"].shift(1)
        acf1 = binned[["agg_trades", "agg_trades_lag1"]].dropna().corr().iloc[0, 1]
    else:
        acf1 = np.nan
    fano = float(binned["agg_trades"].var(ddof=1) / max(binned["agg_trades"].mean(), 1e-12))
    price_returns = trades["price"].pct_change().dropna()
    duration = float(max(trades["event_time_seconds"].iloc[-1], 1e-12))
    summary = pd.DataFrame(
        [
            {
                "dataset": "binance_spot_daily_aggTrades",
                "symbol": symbol.upper(),
                "date": date,
                "rows": int(len(trades)),
                "underlying_trades": int(trades["underlying_trades"].sum()),
                "duration_seconds": duration,
                "bin_seconds": bin_seconds,
                "agg_trade_rate_per_second": float(len(trades) / duration),
                "underlying_trade_rate_per_second": float(trades["underlying_trades"].sum() / duration),
                "event_count_fano": fano,
                "event_count_acf1": float(acf1),
                "buyer_maker_share": float(trades["is_buyer_maker"].mean()),
                "mean_price": float(trades["price"].mean()),
                "price_return_std": float(price_returns.std()),
                "total_base_volume": float(trades["quantity"].sum()),
                "total_notional": float(trades["notional"].sum()),
            }
        ]
    )
    return binned, summary


def run_binance_aggtrade_sanity(
    data_root: Path = Path("data/raw/binance/aggTrades"),
    results_root: Path = Path("results"),
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
    date: str = DEFAULT_BINANCE_AGGTRADE_DATE,
    summary_filename: str | None = "binance_aggtrades_sanity_summary.csv",
) -> pd.DataFrame:
    """Download and summarize a panel of public Binance aggregate trades."""
    frames = []
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        path = download_binance_agg_trades(data_root, symbol=symbol, date=date)
        binned, summary = summarize_binance_agg_trades(path, symbol=symbol, date=date)
        binned.to_csv(results_root / "raw" / f"binance_{symbol.upper()}_{date}_aggtrades_1s.csv", index=False)
        frames.append(summary)
    panel = pd.concat(frames, ignore_index=True).sort_values("symbol")
    if summary_filename is not None:
        panel.to_csv(results_root / "tables" / summary_filename, index=False)
    return panel


def run_binance_aggtrade_cross_date_sanity(
    data_root: Path = Path("data/raw/binance/aggTrades"),
    results_root: Path = Path("results"),
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
    dates: tuple[str, ...] = DEFAULT_BINANCE_AGGTRADE_DATES,
    legacy_date: str = DEFAULT_BINANCE_AGGTRADE_DATE,
) -> pd.DataFrame:
    """Download and summarize Binance aggregate trades across multiple dates."""
    frames = []
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    for date in dates:
        panel = run_binance_aggtrade_sanity(
            data_root=data_root,
            results_root=results_root,
            symbols=symbols,
            date=date,
            summary_filename=None,
        )
        frames.append(panel)
    cross_date = pd.concat(frames, ignore_index=True).sort_values(["symbol", "date"])
    cross_date.to_csv(results_root / "tables" / "binance_aggtrades_cross_date_sanity_summary.csv", index=False)
    legacy = cross_date[cross_date["date"] == legacy_date].sort_values("symbol")
    if not legacy.empty:
        legacy.to_csv(results_root / "tables" / "binance_aggtrades_sanity_summary.csv", index=False)
    return cross_date


def run_public_data_panel(
    data_root: Path = Path("data/raw"),
    results_root: Path = Path("results"),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fetch all public data panels used by the manuscript."""
    lobster = run_lobster_panel(data_root / "lobster", results_root)
    crypto = run_crypto_depth_sanity(data_root / "crypto_l2", results_root)
    binance = run_binance_aggtrade_sanity(data_root / "binance" / "aggTrades", results_root)
    return lobster, crypto, binance
