"""Lightweight Hawkes calibration utilities for public event samples."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from scipy.stats import kstest

from mesa.empirical import load_binance_agg_trades, load_lobster_message, load_lobster_orderbook_1
from mesa.hawkes import HawkesParams, simulate_ogata_hawkes
from mesa.spectral import spectral_radius


EVENT_GROUPS: dict[str, tuple[int, ...] | None] = {
    "all": None,
    "limit": (1,),
    "cancel_delete": (2, 3),
    "execution": (4, 5),
}
MARKED_EVENT_GROUPS: dict[str, tuple[int, ...]] = {
    "limit": (1,),
    "cancel_delete": (2, 3),
    "execution": (4, 5),
}
SIDE_MARK_GROUPS: tuple[str, ...] = (
    "limit_buy",
    "cancel_delete_buy",
    "execution_buy",
    "limit_sell",
    "cancel_delete_sell",
    "execution_sell",
)
SIDE_MARK_SIDES: dict[str, str] = {
    "limit_buy": "buy",
    "cancel_delete_buy": "buy",
    "execution_buy": "buy",
    "limit_sell": "sell",
    "cancel_delete_sell": "sell",
    "execution_sell": "sell",
}
SIDE_MARK_EVENT_GROUPS: dict[str, str] = {
    "limit_buy": "limit",
    "cancel_delete_buy": "cancel_delete",
    "execution_buy": "execution",
    "limit_sell": "limit",
    "cancel_delete_sell": "cancel_delete",
    "execution_sell": "execution",
}
SIZE_BUCKETS: tuple[str, ...] = ("small", "large")
SIZE_SIDE_MARK_GROUPS: tuple[str, ...] = tuple(
    f"{event}_{side}_{bucket}"
    for event in ("limit", "cancel_delete", "execution")
    for side in ("buy", "sell")
    for bucket in SIZE_BUCKETS
)


@dataclass(frozen=True)
class HawkesFit:
    mu: float
    rho: float
    beta: float
    neg_loglik: float
    success: bool
    n_events: int
    horizon: float
    hit_beta_upper: bool
    residual_mean: float
    residual_variance: float
    residual_ks_stat: float
    residual_ks_pvalue: float


@dataclass(frozen=True)
class MultiScaleHawkesFit:
    mu: float
    rho: float
    rho_slow: float
    rho_fast: float
    beta_slow: float
    beta_fast: float
    neg_loglik: float
    success: bool
    n_events: int
    horizon: float
    residual_mean: float
    residual_variance: float
    residual_ks_stat: float
    residual_ks_pvalue: float


@dataclass(frozen=True)
class MarkedHawkesFit:
    mu: np.ndarray
    gamma: np.ndarray
    beta: float
    neg_loglik: float
    success: bool
    n_events: int
    horizon: float
    spectral_radius: float
    residual_mean: float
    residual_variance: float
    residual_ks_stat: float
    residual_ks_pvalue: float
    mark_log_loss: float
    baseline_mark_log_loss: float
    mark_log_loss_improvement: float


def _prepare_times(times: np.ndarray) -> np.ndarray:
    times = np.sort(np.asarray(times, dtype=float))
    if len(times) == 0:
        raise ValueError("at least one event time is required")
    times = times - times[0]
    # Real order-book feeds can have same-time messages. Add deterministic
    # microscopic jitter so the simple point-process likelihood is well-defined.
    if len(times) > 1:
        times = times + np.arange(len(times)) * 1e-9
    return times


def exponential_hawkes_neg_loglik(theta: np.ndarray, times: np.ndarray, horizon: float) -> float:
    """Negative log-likelihood for univariate exponential Hawkes."""
    mu = np.exp(theta[0])
    rho = 0.999 * expit(theta[1])
    beta = np.exp(theta[2])
    if not (mu > 0 and 0 <= rho < 1 and beta > 0):
        return np.inf

    z = 0.0
    last = 0.0
    log_sum = 0.0
    for t in times:
        dt = t - last
        if dt < 0:
            return np.inf
        z *= np.exp(-beta * dt)
        lam = mu + beta * rho * z
        if lam <= 0 or not np.isfinite(lam):
            return np.inf
        log_sum += np.log(lam)
        z += 1.0
        last = t
    integral = mu * horizon + rho * np.sum(1.0 - np.exp(-beta * np.maximum(horizon - times, 0.0)))
    return float(integral - log_sum)


def compensator_increments(times: np.ndarray, mu: float, rho: float, beta: float) -> np.ndarray:
    """Return event-to-event compensator increments for an exponential Hawkes fit."""
    prepared = _prepare_times(times)
    z = 0.0
    last = 0.0
    increments: list[float] = []
    for t in prepared:
        dt = t - last
        if dt < 0:
            raise ValueError("event times must be sorted")
        inc = mu * dt
        if beta > 0:
            inc += rho * z * (1.0 - np.exp(-beta * dt))
        increments.append(float(inc))
        z = z * np.exp(-beta * dt) + 1.0
        last = t
    # The first event is treated conditionally after shifting the sample start,
    # so its compensator increment is exactly zero and is not a GOF residual.
    return np.asarray(increments[1:], dtype=float)


def hawkes_residual_diagnostics(times: np.ndarray, mu: float, rho: float, beta: float) -> dict[str, float]:
    """Compute lightweight time-rescaling diagnostics against Exp(1)."""
    increments = compensator_increments(times, mu=mu, rho=rho, beta=beta)
    increments = increments[np.isfinite(increments)]
    if len(increments) < 8:
        return {
            "residual_mean": np.nan,
            "residual_variance": np.nan,
            "residual_ks_stat": np.nan,
            "residual_ks_pvalue": np.nan,
        }
    ks = kstest(increments, "expon", method="asymp")
    return {
        "residual_mean": float(increments.mean()),
        "residual_variance": float(increments.var(ddof=1)),
        "residual_ks_stat": float(ks.statistic),
        "residual_ks_pvalue": float(ks.pvalue),
    }


def _prepare_fit_times(event_times: np.ndarray, max_events: int | None) -> tuple[np.ndarray, float]:
    times = _prepare_times(event_times)
    if max_events is not None and len(times) > max_events:
        idx = np.linspace(0, len(times) - 1, max_events).astype(int)
        times = times[idx]
    horizon = float(max(times[-1], 1e-9))
    return times, horizon


def _prepare_marked_events(
    event_times: np.ndarray,
    marks: np.ndarray,
    max_events: int | None,
) -> tuple[np.ndarray, np.ndarray, float]:
    times = np.asarray(event_times, dtype=float)
    marks = np.asarray(marks, dtype=int)
    if len(times) == 0:
        raise ValueError("at least one marked event is required")
    if len(times) != len(marks):
        raise ValueError("event_times and marks must have the same length")
    order = np.lexsort((np.arange(len(times)), times))
    times = times[order]
    marks = marks[order]
    times = times - times[0]
    if len(times) > 1:
        times = times + np.arange(len(times)) * 1e-9
    if max_events is not None and len(times) > max_events:
        idx = np.linspace(0, len(times) - 1, max_events).astype(int)
        times = times[idx]
        marks = marks[idx]
    horizon = float(max(times[-1], 1e-9))
    return times, marks, horizon


def fit_univariate_exponential_hawkes(
    event_times: np.ndarray,
    max_events: int | None = 150_000,
    multistart: bool = True,
) -> HawkesFit:
    """Fit a univariate exponential Hawkes model by maximum likelihood."""
    times, horizon = _prepare_fit_times(event_times, max_events)
    rate = len(times) / horizon
    init_mu = max(rate * 0.5, 1e-6)
    starts = [(init_mu, 0.5, 1.0)]
    if multistart:
        starts.extend(
            [
                (max(rate * 0.8, 1e-6), 0.2, 0.5),
                (max(rate * 0.3, 1e-6), 0.8, 5.0),
                (max(rate * 0.1, 1e-6), 0.95, 25.0),
            ]
        )
    beta_upper_log = 5.0
    result = None
    for mu0, rho0, beta0 in starts:
        x0 = np.array([np.log(mu0), logit(rho0 / 0.999), np.log(beta0)])
        candidate = minimize(
            exponential_hawkes_neg_loglik,
            x0,
            args=(times, horizon),
            method="L-BFGS-B",
            bounds=[(-20, 10), (-12, 12), (-5, beta_upper_log)],
            options={"maxiter": 200, "ftol": 1e-7},
        )
        if result is None or candidate.fun < result.fun:
            result = candidate
    if result is None:
        raise RuntimeError("Hawkes optimizer did not run")
    theta = result.x
    mu = float(np.exp(theta[0]))
    rho = float(0.999 * expit(theta[1]))
    beta = float(np.exp(theta[2]))
    diagnostics = hawkes_residual_diagnostics(times, mu=mu, rho=rho, beta=beta)
    return HawkesFit(
        mu=mu,
        rho=rho,
        beta=beta,
        neg_loglik=float(result.fun),
        success=bool(result.success),
        n_events=int(len(times)),
        horizon=horizon,
        hit_beta_upper=bool(abs(theta[2] - beta_upper_log) < 1e-5),
        **diagnostics,
    )


def _fit_fixed_beta(event_times: np.ndarray, beta: float, max_events: int | None) -> HawkesFit:
    times, horizon = _prepare_fit_times(event_times, max_events)
    rate = len(times) / horizon
    x0 = np.array([np.log(max(rate * 0.5, 1e-6)), logit(0.5 / 0.999)])

    def objective(theta: np.ndarray) -> float:
        return exponential_hawkes_neg_loglik(np.array([theta[0], theta[1], np.log(beta)]), times, horizon)

    result = minimize(
        objective,
        x0,
        method="L-BFGS-B",
        bounds=[(-20, 10), (-12, 12)],
        options={"maxiter": 200, "ftol": 1e-7},
    )
    mu = float(np.exp(result.x[0]))
    rho = float(0.999 * expit(result.x[1]))
    diagnostics = hawkes_residual_diagnostics(times, mu=mu, rho=rho, beta=beta)
    return HawkesFit(
        mu=mu,
        rho=rho,
        beta=float(beta),
        neg_loglik=float(result.fun),
        success=bool(result.success),
        n_events=int(len(times)),
        horizon=horizon,
        hit_beta_upper=False,
        **diagnostics,
    )


def _fixed_beta_recursions(times: np.ndarray, beta_values: np.ndarray) -> np.ndarray:
    """Precompute pre-event excitation recursions for fixed beta values."""
    beta_values = np.asarray(beta_values, dtype=float)
    z = np.zeros(len(beta_values), dtype=float)
    last = 0.0
    rec = np.empty((len(times), len(beta_values)), dtype=float)
    for idx, t in enumerate(times):
        dt = t - last
        if dt < 0:
            raise ValueError("event times must be sorted")
        z *= np.exp(-beta_values * dt)
        rec[idx] = z
        z += 1.0
        last = t
    return rec


def multiscale_hawkes_neg_loglik_fixed_betas(
    theta: np.ndarray,
    times: np.ndarray,
    horizon: float,
    beta_values: np.ndarray,
    recursions: np.ndarray | None = None,
) -> float:
    """Negative log-likelihood for a two-scale Hawkes model with fixed betas."""
    beta_values = np.asarray(beta_values, dtype=float)
    if beta_values.shape != (2,):
        raise ValueError("beta_values must contain exactly two decay rates")
    if np.any(beta_values <= 0):
        return np.inf
    rec = _fixed_beta_recursions(times, beta_values) if recursions is None else recursions
    mu = float(np.exp(theta[0]))
    rho = float(0.999 * expit(theta[1]))
    fast_share = float(expit(theta[2]))
    weights = np.array([1.0 - fast_share, fast_share], dtype=float)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        kernel = rec @ (beta_values * weights)
    if not np.all(np.isfinite(kernel)):
        return np.inf
    intensity = mu + rho * kernel
    if np.any(intensity <= 0) or not np.all(np.isfinite(intensity)):
        return np.inf
    tail = np.sum(1.0 - np.exp(-np.outer(np.maximum(horizon - times, 0.0), beta_values)), axis=0)
    integral = mu * horizon + rho * float(weights @ tail)
    return float(integral - np.log(intensity).sum())


def multiscale_compensator_increments(
    times: np.ndarray,
    mu: float,
    rho_components: np.ndarray,
    beta_values: np.ndarray,
) -> np.ndarray:
    """Event-to-event compensator increments for fixed-beta multiscale Hawkes."""
    prepared = _prepare_times(times)
    rho_components = np.asarray(rho_components, dtype=float)
    beta_values = np.asarray(beta_values, dtype=float)
    z = np.zeros(len(beta_values), dtype=float)
    last = 0.0
    increments: list[float] = []
    for t in prepared:
        dt = t - last
        if dt < 0:
            raise ValueError("event times must be sorted")
        decay_loss = 1.0 - np.exp(-beta_values * dt)
        inc = mu * dt + float(np.sum(rho_components * z * decay_loss))
        increments.append(float(inc))
        z = z * np.exp(-beta_values * dt) + 1.0
        last = t
    return np.asarray(increments[1:], dtype=float)


def multiscale_hawkes_residual_diagnostics(
    times: np.ndarray,
    mu: float,
    rho_components: np.ndarray,
    beta_values: np.ndarray,
) -> dict[str, float]:
    increments = multiscale_compensator_increments(times, mu, rho_components, beta_values)
    increments = increments[np.isfinite(increments)]
    if len(increments) < 8:
        return {
            "residual_mean": np.nan,
            "residual_variance": np.nan,
            "residual_ks_stat": np.nan,
            "residual_ks_pvalue": np.nan,
        }
    ks = kstest(increments, "expon", method="asymp")
    return {
        "residual_mean": float(increments.mean()),
        "residual_variance": float(increments.var(ddof=1)),
        "residual_ks_stat": float(ks.statistic),
        "residual_ks_pvalue": float(ks.pvalue),
    }


def fit_fixed_beta_multiscale_hawkes(
    event_times: np.ndarray,
    beta_slow: float = 1.0,
    beta_fast: float = 100.0,
    max_events: int | None = 60_000,
) -> MultiScaleHawkesFit:
    """Fit a two-scale Hawkes model with fixed slow/fast decay rates."""
    if beta_slow <= 0 or beta_fast <= 0:
        raise ValueError("beta_slow and beta_fast must be positive")
    if beta_slow >= beta_fast:
        raise ValueError("expected beta_slow < beta_fast")
    times, horizon = _prepare_fit_times(event_times, max_events)
    beta_values = np.array([beta_slow, beta_fast], dtype=float)
    rec = _fixed_beta_recursions(times, beta_values)
    rate = len(times) / horizon
    starts = [
        (max(rate * 0.5, 1e-6), 0.5, 0.5),
        (max(rate * 0.35, 1e-6), 0.75, 0.25),
        (max(rate * 0.65, 1e-6), 0.35, 0.75),
        (max(rate * 0.2, 1e-6), 0.9, 0.5),
    ]
    result = None
    for mu0, rho0, fast_share0 in starts:
        x0 = np.array([np.log(mu0), logit(rho0 / 0.999), logit(fast_share0)])
        candidate = minimize(
            multiscale_hawkes_neg_loglik_fixed_betas,
            x0,
            args=(times, horizon, beta_values, rec),
            method="L-BFGS-B",
            bounds=[(-20, 10), (-12, 12), (-12, 12)],
            options={"maxiter": 200, "ftol": 1e-7},
        )
        if result is None or candidate.fun < result.fun:
            result = candidate
    if result is None:
        raise RuntimeError("multiscale Hawkes optimizer did not run")
    mu = float(np.exp(result.x[0]))
    rho = float(0.999 * expit(result.x[1]))
    fast_share = float(expit(result.x[2]))
    rho_slow = float(rho * (1.0 - fast_share))
    rho_fast = float(rho * fast_share)
    diagnostics = multiscale_hawkes_residual_diagnostics(
        times,
        mu=mu,
        rho_components=np.array([rho_slow, rho_fast]),
        beta_values=beta_values,
    )
    return MultiScaleHawkesFit(
        mu=mu,
        rho=rho,
        rho_slow=rho_slow,
        rho_fast=rho_fast,
        beta_slow=float(beta_slow),
        beta_fast=float(beta_fast),
        neg_loglik=float(result.fun),
        success=bool(result.success),
        n_events=int(len(times)),
        horizon=horizon,
        **diagnostics,
    )


def fit_lobster_multiscale_hawkes_sensitivity(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    event_groups: tuple[str, ...] = ("all", "limit", "cancel_delete", "execution"),
    beta_pairs: tuple[tuple[float, float], ...] = ((1.0, 100.0), (5.0, 100.0), (1.0, 20.0)),
    max_events: int | None = 40_000,
) -> pd.DataFrame:
    """Fit fixed-beta two-scale Hawkes diagnostics to LOBSTER event groups."""
    rows = []
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        for event_group in event_groups:
            sub = _filter_event_group(msg, event_group)
            if len(sub) < 10:
                continue
            times = sub["time"].to_numpy()
            for beta_slow, beta_fast in beta_pairs:
                fit = fit_fixed_beta_multiscale_hawkes(
                    times,
                    beta_slow=beta_slow,
                    beta_fast=beta_fast,
                    max_events=max_events,
                )
                event_types = EVENT_GROUPS[event_group]
                rows.append(
                    {
                        "ticker": ticker,
                        "event_group": event_group,
                        "event_types": "all" if event_types is None else ",".join(map(str, event_types)),
                        "beta_pair": f"{beta_slow:g},{beta_fast:g}",
                        "n_events_raw": int(len(sub)),
                        "event_share": float(len(sub) / len(msg)),
                        "mu": fit.mu,
                        "rho": fit.rho,
                        "rho_slow": fit.rho_slow,
                        "rho_fast": fit.rho_fast,
                        "fast_share": fit.rho_fast / max(fit.rho, 1e-12),
                        "beta_slow": fit.beta_slow,
                        "beta_fast": fit.beta_fast,
                        "neg_loglik": fit.neg_loglik,
                        "aic": 2.0 * 3.0 + 2.0 * fit.neg_loglik,
                        "success": fit.success,
                        "n_events_fit": fit.n_events,
                        "horizon": fit.horizon,
                        "event_rate_fit": fit.n_events / fit.horizon,
                        "residual_mean": fit.residual_mean,
                        "residual_variance": fit.residual_variance,
                        "residual_ks_stat": fit.residual_ks_stat,
                        "residual_ks_pvalue": fit.residual_ks_pvalue,
                    }
                )
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_hawkes_multiscale_sensitivity.csv", index=False)
    if len(df):
        best = (
            df.sort_values(["ticker", "event_group", "aic"])
            .groupby(["ticker", "event_group"], as_index=False)
            .first()
        )
        best.to_csv(results_root / "tables" / "lobster_hawkes_multiscale_best.csv", index=False)
    return df


def _fixed_beta_mark_recursions(times: np.ndarray, marks: np.ndarray, dim: int, beta: float) -> np.ndarray:
    """Precompute pre-event source-type recursions for a marked Hawkes model."""
    if beta <= 0:
        raise ValueError("beta must be positive")
    marks = np.asarray(marks, dtype=int)
    if np.any((marks < 0) | (marks >= dim)):
        raise ValueError("marks must be in [0, dim)")
    z = np.zeros(dim, dtype=float)
    last = 0.0
    rec = np.empty((len(times), dim), dtype=float)
    for idx, (t, mark) in enumerate(zip(times, marks, strict=True)):
        dt = t - last
        if dt < 0:
            raise ValueError("event times must be sorted")
        z *= np.exp(-beta * dt)
        rec[idx] = z
        z[mark] += 1.0
        last = t
    return rec


def marked_multivariate_hawkes_neg_loglik_fixed_beta(
    theta: np.ndarray,
    times: np.ndarray,
    marks: np.ndarray,
    horizon: float,
    beta: float,
    dim: int,
    recursions: np.ndarray | None = None,
    source_tail: np.ndarray | None = None,
    stability_cap: float = 0.999,
) -> float:
    """Negative log-likelihood for a marked multivariate Hawkes model.

    The fixed-beta exponential kernel uses ``gamma[target, source]`` as the
    integrated branching weight from source events into target intensities.
    """
    if beta <= 0 or dim <= 0:
        return np.inf
    theta = np.asarray(theta, dtype=float)
    expected = dim + dim * dim
    if theta.shape != (expected,):
        raise ValueError(f"theta must have shape {(expected,)}")
    mu = np.exp(theta[:dim])
    gamma = np.exp(theta[dim:]).reshape(dim, dim)
    rho = spectral_radius(gamma)
    if not np.isfinite(rho):
        return np.inf
    if rho >= stability_cap:
        return float(1e8 + 1e8 * (rho - stability_cap + 1e-6) ** 2 + 1e4 * np.sum(gamma))
    rec = _fixed_beta_mark_recursions(times, marks, dim, beta) if recursions is None else recursions
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        intensity_at_marks = mu[marks] + beta * np.sum(rec * gamma[marks], axis=1)
    if np.any(intensity_at_marks <= 0) or not np.all(np.isfinite(intensity_at_marks)):
        return np.inf
    if source_tail is None:
        tail_weights = 1.0 - np.exp(-beta * np.maximum(horizon - times, 0.0))
        prepared_source_tail = np.bincount(marks, weights=tail_weights, minlength=dim)
    else:
        prepared_source_tail = source_tail
    integral = float(mu.sum() * horizon + gamma.sum(axis=0) @ prepared_source_tail)
    return float(integral - np.log(intensity_at_marks).sum())


def marked_multivariate_compensator_increments(
    times: np.ndarray,
    marks: np.ndarray,
    mu: np.ndarray,
    gamma: np.ndarray,
    beta: float,
) -> np.ndarray:
    """Total-intensity compensator increments for a marked Hawkes fit."""
    dim = int(len(mu))
    prepared_times, prepared_marks, _ = _prepare_marked_events(times, marks, max_events=None)
    gamma_colsum = np.asarray(gamma, dtype=float).sum(axis=0)
    z = np.zeros(dim, dtype=float)
    last = 0.0
    increments: list[float] = []
    for t, mark in zip(prepared_times, prepared_marks, strict=True):
        dt = t - last
        if dt < 0:
            raise ValueError("event times must be sorted")
        decay_loss = 1.0 - np.exp(-beta * dt)
        inc = float(np.sum(mu) * dt + gamma_colsum @ (z * decay_loss))
        increments.append(inc)
        z = z * np.exp(-beta * dt)
        z[mark] += 1.0
        last = t
    return np.asarray(increments[1:], dtype=float)


def marked_multivariate_hawkes_residual_diagnostics(
    times: np.ndarray,
    marks: np.ndarray,
    mu: np.ndarray,
    gamma: np.ndarray,
    beta: float,
) -> dict[str, float]:
    """Time-rescaling and conditional-mark diagnostics for a marked fit."""
    dim = int(len(mu))
    prepared_times, prepared_marks, _ = _prepare_marked_events(times, marks, max_events=None)
    increments = marked_multivariate_compensator_increments(prepared_times, prepared_marks, mu, gamma, beta)
    increments = increments[np.isfinite(increments)]
    if len(increments) < 8:
        residual = {
            "residual_mean": np.nan,
            "residual_variance": np.nan,
            "residual_ks_stat": np.nan,
            "residual_ks_pvalue": np.nan,
        }
    else:
        ks = kstest(increments, "expon", method="asymp")
        residual = {
            "residual_mean": float(increments.mean()),
            "residual_variance": float(increments.var(ddof=1)),
            "residual_ks_stat": float(ks.statistic),
            "residual_ks_pvalue": float(ks.pvalue),
        }

    rec = _fixed_beta_mark_recursions(prepared_times, prepared_marks, dim, beta)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        lam = mu[None, :] + beta * (rec @ gamma.T)
        total = lam.sum(axis=1)
        probs = lam[np.arange(len(prepared_marks)), prepared_marks] / total
    probs = np.clip(probs[1:], 1e-12, 1.0)
    counts = np.bincount(prepared_marks, minlength=dim).astype(float)
    baseline_probs = np.clip(counts / max(counts.sum(), 1.0), 1e-12, 1.0)
    baseline_at_marks = baseline_probs[prepared_marks[1:]]
    mark_log_loss = float(-np.mean(np.log(probs))) if len(probs) else np.nan
    baseline_mark_log_loss = float(-np.mean(np.log(baseline_at_marks))) if len(baseline_at_marks) else np.nan
    residual.update(
        {
            "mark_log_loss": mark_log_loss,
            "baseline_mark_log_loss": baseline_mark_log_loss,
            "mark_log_loss_improvement": baseline_mark_log_loss - mark_log_loss,
        }
    )
    return residual


def fit_fixed_beta_marked_multivariate_hawkes(
    event_times: np.ndarray,
    marks: np.ndarray,
    dim: int,
    beta: float = 20.0,
    max_events: int | None = 20_000,
    stability_cap: float = 0.999,
) -> MarkedHawkesFit:
    """Fit a fixed-beta marked multivariate Hawkes model by MLE."""
    if dim <= 0:
        raise ValueError("dim must be positive")
    times, prepared_marks, horizon = _prepare_marked_events(event_times, marks, max_events=max_events)
    if np.any((prepared_marks < 0) | (prepared_marks >= dim)):
        raise ValueError("marks must be in [0, dim)")
    rec = _fixed_beta_mark_recursions(times, prepared_marks, dim, beta)
    tail_weights = 1.0 - np.exp(-beta * np.maximum(horizon - times, 0.0))
    source_tail = np.bincount(prepared_marks, weights=tail_weights, minlength=dim)
    counts = np.bincount(prepared_marks, minlength=dim).astype(float)
    rates = np.maximum(counts / horizon, 1e-6)
    eye_start = 0.20 * np.eye(dim)
    weak_cross = np.full((dim, dim), 0.04 / max(dim, 1), dtype=float)
    np.fill_diagonal(weak_cross, 0.18)
    broad_cross = np.full((dim, dim), 0.12 / max(dim, 1), dtype=float)
    np.fill_diagonal(broad_cross, 0.10)
    starts = [np.zeros((dim, dim), dtype=float) + 1e-4, eye_start, weak_cross, broad_cross]
    result = None
    upper_gamma_log = np.log(0.95)
    for gamma0 in starts:
        gamma0 = np.clip(gamma0, 1e-6, 0.95)
        rho0 = spectral_radius(gamma0)
        if rho0 >= stability_cap:
            gamma0 = gamma0 * (0.5 * stability_cap / rho0)
        mu0 = np.maximum((np.eye(dim) - gamma0) @ rates, 1e-6)
        x0 = np.r_[np.log(mu0), np.log(gamma0).ravel()]
        candidate = minimize(
            marked_multivariate_hawkes_neg_loglik_fixed_beta,
            x0,
            args=(times, prepared_marks, horizon, beta, dim, rec, source_tail, stability_cap),
            method="L-BFGS-B",
            bounds=[(-20, 10)] * dim + [(-12, upper_gamma_log)] * (dim * dim),
            options={"maxiter": 250, "ftol": 1e-6},
        )
        if result is None or candidate.fun < result.fun:
            result = candidate
    if result is None:
        raise RuntimeError("marked Hawkes optimizer did not run")
    mu = np.exp(result.x[:dim])
    gamma = np.exp(result.x[dim:]).reshape(dim, dim)
    rho = spectral_radius(gamma)
    diagnostics = marked_multivariate_hawkes_residual_diagnostics(
        times,
        prepared_marks,
        mu=mu,
        gamma=gamma,
        beta=beta,
    )
    return MarkedHawkesFit(
        mu=mu,
        gamma=gamma,
        beta=float(beta),
        neg_loglik=float(result.fun),
        success=bool(result.success and rho < stability_cap),
        n_events=int(len(times)),
        horizon=horizon,
        spectral_radius=float(rho),
        **diagnostics,
    )


def _lobster_marked_events(
    msg: pd.DataFrame,
    mark_groups: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    mark_lookup: dict[int, int] = {}
    for mark, name in enumerate(mark_groups):
        if name not in MARKED_EVENT_GROUPS:
            raise ValueError(f"unknown marked event group {name!r}")
        for event_type in MARKED_EVENT_GROUPS[name]:
            mark_lookup[event_type] = mark
    sub = msg[msg["event_type"].isin(mark_lookup)].copy()
    marks = sub["event_type"].map(mark_lookup).to_numpy(dtype=int)
    return sub["time"].to_numpy(dtype=float), marks, {name: idx for idx, name in enumerate(mark_groups)}


def _lobster_side_marked_events(
    msg: pd.DataFrame,
    mark_groups: tuple[str, ...] = SIDE_MARK_GROUPS,
) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    """Map LOBSTER event type and direction into side-aware event marks."""
    event_to_group = {
        1: "limit",
        2: "cancel_delete",
        3: "cancel_delete",
        4: "execution",
        5: "execution",
    }
    mark_index = {name: idx for idx, name in enumerate(mark_groups)}
    rows = []
    marks = []
    for row in msg.itertuples(index=False):
        event_group = event_to_group.get(int(row.event_type))
        if event_group is None:
            continue
        if int(row.direction) == 1:
            side = "buy"
        elif int(row.direction) == -1:
            side = "sell"
        else:
            continue
        mark_name = f"{event_group}_{side}"
        if mark_name not in mark_index:
            continue
        rows.append(float(row.time))
        marks.append(mark_index[mark_name])
    return np.asarray(rows, dtype=float), np.asarray(marks, dtype=int), mark_index


def fit_lobster_marked_multivariate_hawkes(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    mark_groups: tuple[str, ...] = ("limit", "cancel_delete", "execution"),
    beta_grid: tuple[float, ...] = (1.0, 5.0, 20.0, 100.0),
    max_events: int | None = 20_000,
) -> pd.DataFrame:
    """Fit marked multivariate fixed-beta Hawkes diagnostics to LOBSTER events."""
    rows = []
    dim = len(mark_groups)
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        times, marks, mark_index = _lobster_marked_events(msg, mark_groups)
        if len(times) < 20:
            continue
        counts = np.bincount(marks, minlength=dim)
        for beta in beta_grid:
            fit = fit_fixed_beta_marked_multivariate_hawkes(
                times,
                marks,
                dim=dim,
                beta=beta,
                max_events=max_events,
            )
            row = {
                "ticker": ticker,
                "beta_fixed": float(beta),
                "mark_groups": "|".join(mark_groups),
                "n_events_raw": int(len(times)),
                "n_events_fit": fit.n_events,
                "horizon": fit.horizon,
                "event_rate_fit": fit.n_events / fit.horizon,
                "neg_loglik": fit.neg_loglik,
                "aic": 2.0 * (dim + dim * dim) + 2.0 * fit.neg_loglik,
                "success": fit.success,
                "spectral_radius": fit.spectral_radius,
                "residual_mean": fit.residual_mean,
                "residual_variance": fit.residual_variance,
                "residual_ks_stat": fit.residual_ks_stat,
                "residual_ks_pvalue": fit.residual_ks_pvalue,
                "mark_log_loss": fit.mark_log_loss,
                "baseline_mark_log_loss": fit.baseline_mark_log_loss,
                "mark_log_loss_improvement": fit.mark_log_loss_improvement,
            }
            for name, idx in mark_index.items():
                row[f"count_{name}"] = int(counts[idx])
                row[f"mu_{name}"] = float(fit.mu[idx])
                row[f"branching_in_{name}"] = float(fit.gamma[idx, :].sum())
                row[f"branching_from_{name}"] = float(fit.gamma[:, idx].sum())
            for target, target_idx in mark_index.items():
                for source, source_idx in mark_index.items():
                    row[f"gamma_{target}_from_{source}"] = float(fit.gamma[target_idx, source_idx])
            rows.append(row)
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_marked_hawkes_multivariate.csv", index=False)
    if len(df):
        best = df.sort_values(["ticker", "aic"]).groupby("ticker", as_index=False).first()
        best.to_csv(results_root / "tables" / "lobster_marked_hawkes_multivariate_best.csv", index=False)
    return df


def _add_marked_fit_row_fields(
    row: dict[str, object],
    fit: MarkedHawkesFit,
    counts: np.ndarray,
    mark_index: dict[str, int],
) -> None:
    for name, idx in mark_index.items():
        row[f"count_{name}"] = int(counts[idx])
        row[f"mu_{name}"] = float(fit.mu[idx])
        row[f"branching_in_{name}"] = float(fit.gamma[idx, :].sum())
        row[f"branching_from_{name}"] = float(fit.gamma[:, idx].sum())
    for target, target_idx in mark_index.items():
        for source, source_idx in mark_index.items():
            row[f"gamma_{target}_from_{source}"] = float(fit.gamma[target_idx, source_idx])


def _add_side_aggregate_fields(
    row: dict[str, object],
    fit: MarkedHawkesFit,
    mark_index: dict[str, int],
) -> None:
    side_indices = {
        "buy": [idx for name, idx in mark_index.items() if SIDE_MARK_SIDES.get(name) == "buy"],
        "sell": [idx for name, idx in mark_index.items() if SIDE_MARK_SIDES.get(name) == "sell"],
    }
    event_indices = {
        event_group: [
            idx
            for name, idx in mark_index.items()
            if SIDE_MARK_EVENT_GROUPS.get(name) == event_group
        ]
        for event_group in ("limit", "cancel_delete", "execution")
    }
    for target_side, target_idx in side_indices.items():
        row[f"branching_in_side_{target_side}"] = float(fit.gamma[target_idx, :].sum())
        for source_side, source_idx in side_indices.items():
            row[f"gamma_side_{target_side}_from_{source_side}"] = float(
                fit.gamma[np.ix_(target_idx, source_idx)].sum()
            )
    for source_side, source_idx in side_indices.items():
        row[f"branching_from_side_{source_side}"] = float(fit.gamma[:, source_idx].sum())
    for target_event, target_idx in event_indices.items():
        row[f"branching_in_event_{target_event}"] = float(fit.gamma[target_idx, :].sum())
        for source_event, source_idx in event_indices.items():
            row[f"gamma_event_{target_event}_from_{source_event}"] = float(
                fit.gamma[np.ix_(target_idx, source_idx)].sum()
            )
    for source_event, source_idx in event_indices.items():
        row[f"branching_from_event_{source_event}"] = float(fit.gamma[:, source_idx].sum())


def _mark_attr(name: str, position: int) -> str:
    parts = name.split("_")
    if len(parts) == 2:
        return parts[position]
    if parts[0] == "cancel" and len(parts) >= 3:
        return "cancel_delete" if position == 0 else parts[position + 1]
    return parts[position]


def _add_name_aggregate_fields(
    row: dict[str, object],
    fit: MarkedHawkesFit,
    mark_index: dict[str, int],
    *,
    attribute_name: str,
    labels: tuple[str, ...],
    label_lookup: dict[str, str],
) -> None:
    indices = {
        label: [idx for name, idx in mark_index.items() if label_lookup.get(name) == label]
        for label in labels
    }
    for target_label, target_idx in indices.items():
        row[f"branching_in_{attribute_name}_{target_label}"] = float(fit.gamma[target_idx, :].sum())
        for source_label, source_idx in indices.items():
            row[f"gamma_{attribute_name}_{target_label}_from_{source_label}"] = float(
                fit.gamma[np.ix_(target_idx, source_idx)].sum()
            )
    for source_label, source_idx in indices.items():
        row[f"branching_from_{attribute_name}_{source_label}"] = float(fit.gamma[:, source_idx].sum())


def _lobster_size_side_marked_events(
    msg: pd.DataFrame,
    mark_groups: tuple[str, ...] = SIZE_SIDE_MARK_GROUPS,
) -> tuple[np.ndarray, np.ndarray, dict[str, int], float]:
    """Map LOBSTER events into event-type/side/size-bucket marks."""
    event_to_group = {
        1: "limit",
        2: "cancel_delete",
        3: "cancel_delete",
        4: "execution",
        5: "execution",
    }
    mark_index = {name: idx for idx, name in enumerate(mark_groups)}
    eligible = msg[msg["event_type"].isin(event_to_group)].copy()
    if eligible.empty:
        return np.array([], dtype=float), np.array([], dtype=int), mark_index, np.nan
    size_threshold = float(eligible["size"].median())
    rows = []
    marks = []
    for row in eligible.itertuples(index=False):
        event_group = event_to_group.get(int(row.event_type))
        if event_group is None:
            continue
        if int(row.direction) == 1:
            side = "buy"
        elif int(row.direction) == -1:
            side = "sell"
        else:
            continue
        bucket = "large" if float(row.size) > size_threshold else "small"
        mark_name = f"{event_group}_{side}_{bucket}"
        if mark_name not in mark_index:
            continue
        rows.append(float(row.time))
        marks.append(mark_index[mark_name])
    return np.asarray(rows, dtype=float), np.asarray(marks, dtype=int), mark_index, size_threshold


def _lobster_side_marked_state_frame(
    msg: pd.DataFrame,
    orderbook: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return side-aware marked LOBSTER events with state covariates."""
    event_to_group = {
        1: "limit",
        2: "cancel_delete",
        3: "cancel_delete",
        4: "execution",
        5: "execution",
    }
    mark_index = {name: idx for idx, name in enumerate(SIDE_MARK_GROUPS)}
    if orderbook is not None and len(orderbook) != len(msg):
        orderbook = None
    spreads = imbalances = top_depths = None
    if orderbook is not None:
        ask = orderbook["ask_price_1"].to_numpy(dtype=float) * 1e-4
        bid = orderbook["bid_price_1"].to_numpy(dtype=float) * 1e-4
        ask_size = orderbook["ask_size_1"].to_numpy(dtype=float)
        bid_size = orderbook["bid_size_1"].to_numpy(dtype=float)
        spreads = ask - bid
        top_depths = ask_size + bid_size
        with np.errstate(divide="ignore", invalid="ignore"):
            imbalances = (bid_size - ask_size) / top_depths

    rows: list[dict[str, object]] = []
    for idx, row in enumerate(msg.itertuples(index=False)):
        event_group = event_to_group.get(int(row.event_type))
        if event_group is None:
            continue
        if int(row.direction) == 1:
            side = "buy"
        elif int(row.direction) == -1:
            side = "sell"
        else:
            continue
        mark_name = f"{event_group}_{side}"
        rows.append(
            {
                "row_index": idx,
                "time": float(row.time),
                "event_group": event_group,
                "side": side,
                "mark_name": mark_name,
                "mark": mark_index[mark_name],
                "size": float(row.size),
                "spread": float(spreads[idx]) if spreads is not None else np.nan,
                "imbalance": float(imbalances[idx]) if imbalances is not None else np.nan,
                "top_depth": float(top_depths[idx]) if top_depths is not None else np.nan,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame, mark_index

    size_threshold = float(frame["size"].median())
    frame["size_threshold"] = size_threshold
    frame["size_bucket"] = np.where(frame["size"] > size_threshold, "large", "small")
    if frame["spread"].notna().any():
        spread_threshold = float(frame["spread"].median())
        frame["spread_threshold"] = spread_threshold
        frame["spread_bucket"] = np.where(frame["spread"] > spread_threshold, "wide", "tight")
    else:
        frame["spread_threshold"] = np.nan
        frame["spread_bucket"] = "unknown"
    if frame["top_depth"].notna().any():
        depth_threshold = float(frame["top_depth"].median())
        frame["depth_threshold"] = depth_threshold
        frame["depth_bucket"] = np.where(frame["top_depth"] > depth_threshold, "high", "low")
    else:
        frame["depth_threshold"] = np.nan
        frame["depth_bucket"] = "unknown"
    frame["imbalance_bucket"] = np.select(
        [frame["imbalance"] > 0.1, frame["imbalance"] < -0.1],
        ["bid_heavy", "ask_heavy"],
        default="neutral",
    )
    frame.loc[frame["imbalance"].isna(), "imbalance_bucket"] = "unknown"
    return frame, mark_index


def _prepare_marked_state_frame(frame: pd.DataFrame, max_events: int | None) -> pd.DataFrame:
    """Sort/subsample a state frame exactly like the marked Hawkes fitter."""
    if frame.empty:
        return frame.copy()
    order = np.lexsort((np.arange(len(frame)), frame["time"].to_numpy(dtype=float)))
    out = frame.iloc[order].reset_index(drop=True).copy()
    prepared_time = out["time"].to_numpy(dtype=float)
    prepared_time = prepared_time - prepared_time[0]
    if len(prepared_time) > 1:
        prepared_time = prepared_time + np.arange(len(prepared_time)) * 1e-9
    out["prepared_time"] = prepared_time
    if max_events is not None and len(out) > max_events:
        idx = np.linspace(0, len(out) - 1, max_events).astype(int)
        out = out.iloc[idx].reset_index(drop=True).copy()
    return out


def _fit_from_side_marked_row(row: pd.Series, mark_index: dict[str, int]) -> MarkedHawkesFit:
    mu = np.array([float(row[f"mu_{name}"]) for name in mark_index], dtype=float)
    gamma = np.array(
        [
            [float(row[f"gamma_{target}_from_{source}"]) for source in mark_index]
            for target in mark_index
        ],
        dtype=float,
    )
    return MarkedHawkesFit(
        mu=mu,
        gamma=gamma,
        beta=float(row["beta_fixed"]),
        neg_loglik=float(row["neg_loglik"]),
        success=bool(row["success"]),
        n_events=int(row["n_events_fit"]),
        horizon=float(row["horizon"]),
        spectral_radius=float(row["spectral_radius"]),
        residual_mean=float(row["residual_mean"]),
        residual_variance=float(row["residual_variance"]),
        residual_ks_stat=float(row["residual_ks_stat"]),
        residual_ks_pvalue=float(row["residual_ks_pvalue"]),
        mark_log_loss=float(row["mark_log_loss"]),
        baseline_mark_log_loss=float(row["baseline_mark_log_loss"]),
        mark_log_loss_improvement=float(row["mark_log_loss_improvement"]),
    )


def _load_cached_side_marked_fits(results_root: Path, mark_index: dict[str, int]) -> dict[str, MarkedHawkesFit]:
    table = results_root / "tables" / "lobster_side_marked_hawkes_multivariate_best.csv"
    if not table.exists():
        return {}
    df = pd.read_csv(table)
    fits: dict[str, MarkedHawkesFit] = {}
    for _, row in df.iterrows():
        needed = [f"mu_{name}" for name in mark_index] + [
            f"gamma_{target}_from_{source}" for target in mark_index for source in mark_index
        ]
        if all(col in row.index for col in needed):
            fits[str(row["ticker"])] = _fit_from_side_marked_row(row, mark_index)
    return fits


def _state_residual_event_frame(prepared: pd.DataFrame, fit: MarkedHawkesFit) -> pd.DataFrame:
    times = prepared["prepared_time"].to_numpy(dtype=float)
    marks = prepared["mark"].to_numpy(dtype=int)
    dim = len(fit.mu)
    if len(times) < 2:
        return prepared.iloc[0:0].copy()
    gamma_colsum = np.asarray(fit.gamma, dtype=float).sum(axis=0)
    z = np.zeros(dim, dtype=float)
    last = 0.0
    increments: list[float] = []
    for t, mark in zip(times, marks, strict=True):
        dt = t - last
        decay_loss = 1.0 - np.exp(-fit.beta * dt)
        increments.append(float(np.sum(fit.mu) * dt + gamma_colsum @ (z * decay_loss)))
        z *= np.exp(-fit.beta * dt)
        z[mark] += 1.0
        last = t

    rec = _fixed_beta_mark_recursions(times, marks, dim, fit.beta)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        lam = fit.mu[None, :] + fit.beta * (rec @ fit.gamma.T)
        total = lam.sum(axis=1)
        model_probs = lam[np.arange(len(marks)), marks] / total
    counts = np.bincount(marks, minlength=dim).astype(float)
    baseline_probs = np.clip(counts / max(counts.sum(), 1.0), 1e-12, 1.0)

    event_frame = prepared.iloc[1:].reset_index(drop=True).copy()
    event_frame["residual_increment"] = np.asarray(increments[1:], dtype=float)
    event_frame["model_mark_prob"] = np.clip(model_probs[1:], 1e-12, 1.0)
    event_frame["baseline_mark_prob"] = np.clip(baseline_probs[marks[1:]], 1e-12, 1.0)
    return event_frame


def _summarize_state_residual_events(
    event_frame: pd.DataFrame,
    state_variables: tuple[str, ...],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for state_variable in state_variables:
        if state_variable not in event_frame:
            continue
        for state_bucket, sub in event_frame.groupby(state_variable, sort=True):
            increments = sub["residual_increment"].to_numpy(dtype=float)
            increments = increments[np.isfinite(increments)]
            if len(increments) < 2:
                continue
            if len(increments) >= 8:
                ks = kstest(increments, "expon", method="asymp")
                ks_stat = float(ks.statistic)
                ks_pvalue = float(ks.pvalue)
            else:
                ks_stat = np.nan
                ks_pvalue = np.nan
            model_probs = np.clip(sub["model_mark_prob"].to_numpy(dtype=float), 1e-12, 1.0)
            baseline_probs = np.clip(sub["baseline_mark_prob"].to_numpy(dtype=float), 1e-12, 1.0)
            mark_log_loss = float(-np.mean(np.log(model_probs)))
            baseline_mark_log_loss = float(-np.mean(np.log(baseline_probs)))
            rows.append(
                {
                    "state_variable": state_variable,
                    "state_bucket": str(state_bucket),
                    "n_events": int(len(sub)),
                    "residual_mean": float(np.mean(increments)),
                    "residual_mean_minus_one": float(np.mean(increments) - 1.0),
                    "residual_variance": float(np.var(increments, ddof=1)) if len(increments) > 1 else np.nan,
                    "residual_ks_stat": ks_stat,
                    "residual_ks_pvalue": ks_pvalue,
                    "mark_log_loss": mark_log_loss,
                    "baseline_mark_log_loss": baseline_mark_log_loss,
                    "mark_log_loss_improvement": baseline_mark_log_loss - mark_log_loss,
                }
            )
    return rows


def fit_lobster_side_marked_state_residual_diagnostics(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    max_events: int | None = 30_000,
    beta_grid: tuple[float, ...] = (100.0,),
    use_cached_fit: bool = True,
    state_variables: tuple[str, ...] = (
        "event_group",
        "side",
        "size_bucket",
        "spread_bucket",
        "imbalance_bucket",
        "depth_bucket",
    ),
) -> pd.DataFrame:
    """Diagnose side-aware marked Hawkes residuals by LOB state strata."""
    rows: list[dict[str, object]] = []
    cached: dict[str, MarkedHawkesFit] = {}
    canonical_mark_index = {name: idx for idx, name in enumerate(SIDE_MARK_GROUPS)}
    if use_cached_fit:
        cached = _load_cached_side_marked_fits(results_root, canonical_mark_index)
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        ob_path = folder / f"{ticker}_2012-06-21_34200000_57600000_orderbook_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        orderbook = load_lobster_orderbook_1(ob_path) if ob_path.exists() else None
        state_frame, mark_index = _lobster_side_marked_state_frame(msg, orderbook)
        if len(state_frame) < 20:
            continue
        prepared = _prepare_marked_state_frame(state_frame, max_events=max_events)
        fit = cached.get(ticker)
        if fit is None:
            fits = [
                fit_fixed_beta_marked_multivariate_hawkes(
                    prepared["prepared_time"].to_numpy(dtype=float),
                    prepared["mark"].to_numpy(dtype=int),
                    dim=len(mark_index),
                    beta=beta,
                    max_events=None,
                )
                for beta in beta_grid
            ]
            fit = min(fits, key=lambda item: 2.0 * (len(mark_index) + len(mark_index) ** 2) + 2.0 * item.neg_loglik)
        event_frame = _state_residual_event_frame(prepared, fit)
        for row in _summarize_state_residual_events(event_frame, state_variables):
            row.update(
                {
                    "ticker": ticker,
                    "beta_fixed": fit.beta,
                    "spectral_radius": fit.spectral_radius,
                    "n_events_fit": fit.n_events,
                    "size_threshold": float(prepared["size_threshold"].iloc[0]),
                    "spread_threshold": float(prepared["spread_threshold"].iloc[0]),
                    "depth_threshold": float(prepared["depth_threshold"].iloc[0]),
                }
            )
            rows.append(row)
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_side_marked_state_residuals.csv", index=False)
    if len(df):
        summary = (
            df.groupby(["state_variable", "state_bucket"], as_index=False)
            .agg(
                ticker_count=("ticker", "nunique"),
                total_events=("n_events", "sum"),
                median_residual_mean=("residual_mean", "median"),
                median_abs_residual_mean_error=("residual_mean_minus_one", lambda x: float(np.median(np.abs(x)))),
                median_residual_ks_stat=("residual_ks_stat", "median"),
                median_mark_log_loss_improvement=("mark_log_loss_improvement", "median"),
            )
            .sort_values(["state_variable", "state_bucket"])
        )
        summary.to_csv(results_root / "tables" / "lobster_side_marked_state_residuals_summary.csv", index=False)
    return df


def fit_lobster_side_marked_multivariate_hawkes(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    beta_grid: tuple[float, ...] = (20.0, 100.0),
    max_events: int | None = 30_000,
) -> pd.DataFrame:
    """Fit side-aware marked multivariate Hawkes diagnostics to LOBSTER events."""
    rows = []
    dim = len(SIDE_MARK_GROUPS)
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        times, marks, mark_index = _lobster_side_marked_events(msg)
        if len(times) < 20:
            continue
        counts = np.bincount(marks, minlength=dim)
        for beta in beta_grid:
            fit = fit_fixed_beta_marked_multivariate_hawkes(
                times,
                marks,
                dim=dim,
                beta=beta,
                max_events=max_events,
            )
            row: dict[str, object] = {
                "ticker": ticker,
                "beta_fixed": float(beta),
                "mark_groups": "|".join(SIDE_MARK_GROUPS),
                "n_events_raw": int(len(times)),
                "n_events_fit": fit.n_events,
                "horizon": fit.horizon,
                "event_rate_fit": fit.n_events / fit.horizon,
                "neg_loglik": fit.neg_loglik,
                "aic": 2.0 * (dim + dim * dim) + 2.0 * fit.neg_loglik,
                "success": fit.success,
                "spectral_radius": fit.spectral_radius,
                "residual_mean": fit.residual_mean,
                "residual_variance": fit.residual_variance,
                "residual_ks_stat": fit.residual_ks_stat,
                "residual_ks_pvalue": fit.residual_ks_pvalue,
                "mark_log_loss": fit.mark_log_loss,
                "baseline_mark_log_loss": fit.baseline_mark_log_loss,
                "mark_log_loss_improvement": fit.mark_log_loss_improvement,
            }
            _add_marked_fit_row_fields(row, fit, counts, mark_index)
            _add_side_aggregate_fields(row, fit, mark_index)
            rows.append(row)
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_side_marked_hawkes_multivariate.csv", index=False)
    if len(df):
        best = df.sort_values(["ticker", "aic"]).groupby("ticker", as_index=False).first()
        best.to_csv(results_root / "tables" / "lobster_side_marked_hawkes_multivariate_best.csv", index=False)
    return df


def fit_lobster_size_side_marked_multivariate_hawkes(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    beta_grid: tuple[float, ...] = (100.0,),
    max_events: int | None = 30_000,
) -> pd.DataFrame:
    """Fit size- and side-aware marked Hawkes diagnostics to LOBSTER events."""
    rows = []
    dim = len(SIZE_SIDE_MARK_GROUPS)
    side_lookup = {name: ("buy" if "_buy_" in name else "sell") for name in SIZE_SIDE_MARK_GROUPS}
    size_lookup = {name: ("large" if name.endswith("_large") else "small") for name in SIZE_SIDE_MARK_GROUPS}
    event_lookup = {
        name: ("cancel_delete" if name.startswith("cancel_delete") else name.split("_", 1)[0])
        for name in SIZE_SIDE_MARK_GROUPS
    }
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        times, marks, mark_index, size_threshold = _lobster_size_side_marked_events(msg)
        if len(times) < 20:
            continue
        counts = np.bincount(marks, minlength=dim)
        for beta in beta_grid:
            fit = fit_fixed_beta_marked_multivariate_hawkes(
                times,
                marks,
                dim=dim,
                beta=beta,
                max_events=max_events,
            )
            row: dict[str, object] = {
                "ticker": ticker,
                "beta_fixed": float(beta),
                "size_threshold": size_threshold,
                "mark_groups": "|".join(SIZE_SIDE_MARK_GROUPS),
                "n_events_raw": int(len(times)),
                "n_events_fit": fit.n_events,
                "horizon": fit.horizon,
                "event_rate_fit": fit.n_events / fit.horizon,
                "neg_loglik": fit.neg_loglik,
                "aic": 2.0 * (dim + dim * dim) + 2.0 * fit.neg_loglik,
                "success": fit.success,
                "spectral_radius": fit.spectral_radius,
                "residual_mean": fit.residual_mean,
                "residual_variance": fit.residual_variance,
                "residual_ks_stat": fit.residual_ks_stat,
                "residual_ks_pvalue": fit.residual_ks_pvalue,
                "mark_log_loss": fit.mark_log_loss,
                "baseline_mark_log_loss": fit.baseline_mark_log_loss,
                "mark_log_loss_improvement": fit.mark_log_loss_improvement,
            }
            _add_marked_fit_row_fields(row, fit, counts, mark_index)
            _add_name_aggregate_fields(
                row,
                fit,
                mark_index,
                attribute_name="side",
                labels=("buy", "sell"),
                label_lookup=side_lookup,
            )
            _add_name_aggregate_fields(
                row,
                fit,
                mark_index,
                attribute_name="event",
                labels=("limit", "cancel_delete", "execution"),
                label_lookup=event_lookup,
            )
            _add_name_aggregate_fields(
                row,
                fit,
                mark_index,
                attribute_name="size",
                labels=SIZE_BUCKETS,
                label_lookup=size_lookup,
            )
            rows.append(row)
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_size_side_marked_hawkes_multivariate.csv", index=False)
    if len(df):
        best = df.sort_values(["ticker", "aic"]).groupby("ticker", as_index=False).first()
        best.to_csv(results_root / "tables" / "lobster_size_side_marked_hawkes_multivariate_best.csv", index=False)
    return df


def fit_lobster_panel_hawkes(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    max_events: int | None = 150_000,
    multistart: bool = True,
) -> pd.DataFrame:
    """Fit univariate Hawkes models to public LOBSTER sample event times."""
    rows = []
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        fit = fit_univariate_exponential_hawkes(msg["time"].to_numpy(), max_events=max_events, multistart=multistart)
        rows.append(
            {
                "ticker": ticker,
                "mu": fit.mu,
                "rho": fit.rho,
                "beta": fit.beta,
                "neg_loglik": fit.neg_loglik,
                "success": fit.success,
                "hit_beta_upper": fit.hit_beta_upper,
                "n_events_fit": fit.n_events,
                "horizon": fit.horizon,
                "event_rate_fit": fit.n_events / fit.horizon,
                "residual_mean": fit.residual_mean,
                "residual_variance": fit.residual_variance,
                "residual_ks_stat": fit.residual_ks_stat,
                "residual_ks_pvalue": fit.residual_ks_pvalue,
            }
        )
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_hawkes_fit.csv", index=False)
    return df


def _fit_binance_aggtrade_hawkes_rows(
    data_root: Path = Path("data/raw/binance/aggTrades"),
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
    dates: tuple[str, ...] = ("2024-01-15",),
    event_groups: tuple[str, ...] = ("all", "buy_aggressor", "sell_aggressor"),
    beta_grid: tuple[float, ...] = (1.0, 5.0, 20.0, 100.0),
    max_events: int | None = 60_000,
) -> pd.DataFrame:
    """Fit fixed-beta Hawkes rows to public Binance aggregate trades."""
    rows = []
    for date in dates:
        for symbol in symbols:
            path = data_root / f"{symbol.upper()}-aggTrades-{date}.zip"
            if not path.exists():
                raise FileNotFoundError(f"missing Binance aggTrades file: {path}")
            trades = load_binance_agg_trades(path)
            for event_group in event_groups:
                if event_group == "all":
                    sub = trades
                elif event_group == "buy_aggressor":
                    sub = trades[trades["aggressor_side"] == "buy"]
                elif event_group == "sell_aggressor":
                    sub = trades[trades["aggressor_side"] == "sell"]
                else:
                    raise ValueError(f"unknown Binance event group: {event_group}")
                if len(sub) < 10:
                    continue
                times = sub["event_time_seconds"].to_numpy(dtype=float)
                for beta in beta_grid:
                    fit = _fit_fixed_beta(times, beta=beta, max_events=max_events)
                    rows.append(
                        {
                            "symbol": symbol.upper(),
                            "date": date,
                            "event_group": event_group,
                            "beta_fixed": float(beta),
                            "n_events_raw": int(len(sub)),
                            "event_share": float(len(sub) / max(len(trades), 1)),
                            "mu": fit.mu,
                            "rho": fit.rho,
                            "neg_loglik": fit.neg_loglik,
                            "aic": 2.0 * 2.0 + 2.0 * fit.neg_loglik,
                            "success": fit.success,
                            "n_events_fit": fit.n_events,
                            "horizon": fit.horizon,
                            "event_rate_fit": fit.n_events / fit.horizon,
                            "residual_mean": fit.residual_mean,
                            "residual_variance": fit.residual_variance,
                            "residual_ks_stat": fit.residual_ks_stat,
                            "residual_ks_pvalue": fit.residual_ks_pvalue,
                        }
                    )
    return pd.DataFrame(rows)


def fit_binance_aggtrade_hawkes(
    data_root: Path = Path("data/raw/binance/aggTrades"),
    results_root: Path = Path("results"),
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
    date: str = "2024-01-15",
    event_groups: tuple[str, ...] = ("all", "buy_aggressor", "sell_aggressor"),
    beta_grid: tuple[float, ...] = (1.0, 5.0, 20.0, 100.0),
    max_events: int | None = 60_000,
) -> pd.DataFrame:
    """Fit fixed-beta Hawkes diagnostics to one Binance aggregate-trade date."""
    df = _fit_binance_aggtrade_hawkes_rows(
        data_root=data_root,
        symbols=symbols,
        dates=(date,),
        event_groups=event_groups,
        beta_grid=beta_grid,
        max_events=max_events,
    )
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "binance_aggtrades_hawkes_fixed_beta.csv", index=False)
    if len(df):
        best = (
            df.sort_values(["symbol", "event_group", "aic"])
            .groupby(["symbol", "event_group"], as_index=False)
            .first()
        )
        best.to_csv(results_root / "tables" / "binance_aggtrades_hawkes_best.csv", index=False)
    return df


def fit_binance_aggtrade_hawkes_cross_date(
    data_root: Path = Path("data/raw/binance/aggTrades"),
    results_root: Path = Path("results"),
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
    dates: tuple[str, ...] = ("2024-01-15", "2024-04-15", "2024-07-15"),
    event_groups: tuple[str, ...] = ("all", "buy_aggressor", "sell_aggressor"),
    beta_grid: tuple[float, ...] = (1.0, 5.0, 20.0, 100.0),
    max_events: int | None = 60_000,
    legacy_date: str = "2024-01-15",
) -> pd.DataFrame:
    """Fit fixed-beta Hawkes diagnostics across several Binance dates."""
    df = _fit_binance_aggtrade_hawkes_rows(
        data_root=data_root,
        symbols=symbols,
        dates=dates,
        event_groups=event_groups,
        beta_grid=beta_grid,
        max_events=max_events,
    )
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "binance_aggtrades_hawkes_cross_date_fixed_beta.csv", index=False)
    if len(df):
        best = (
            df.sort_values(["symbol", "date", "event_group", "aic"])
            .groupby(["symbol", "date", "event_group"], as_index=False)
            .first()
        )
        best.to_csv(results_root / "tables" / "binance_aggtrades_hawkes_cross_date_best.csv", index=False)
        summary = (
            best.groupby(["symbol", "event_group"], as_index=False)
            .agg(
                dates=("date", "nunique"),
                beta_fixed_median=("beta_fixed", "median"),
                rho_median=("rho", "median"),
                rho_min=("rho", "min"),
                rho_max=("rho", "max"),
                residual_ks_median=("residual_ks_stat", "median"),
                residual_ks_max=("residual_ks_stat", "max"),
            )
        )
        summary.to_csv(results_root / "tables" / "binance_aggtrades_hawkes_cross_date_summary.csv", index=False)
        legacy = df[df["date"] == legacy_date]
        if not legacy.empty:
            legacy.to_csv(results_root / "tables" / "binance_aggtrades_hawkes_fixed_beta.csv", index=False)
            legacy_best = (
                legacy.sort_values(["symbol", "event_group", "aic"])
                .groupby(["symbol", "event_group"], as_index=False)
                .first()
            )
            legacy_best.to_csv(results_root / "tables" / "binance_aggtrades_hawkes_best.csv", index=False)
    return df


def _filter_event_group(msg: pd.DataFrame, event_group: str) -> pd.DataFrame:
    if event_group not in EVENT_GROUPS:
        raise ValueError(f"unknown event group {event_group!r}; expected one of {sorted(EVENT_GROUPS)}")
    event_types = EVENT_GROUPS[event_group]
    if event_types is None:
        return msg
    return msg[msg["event_type"].isin(event_types)]


def fit_lobster_panel_hawkes_by_event_type(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    event_groups: tuple[str, ...] = ("all", "limit", "cancel_delete", "execution"),
    max_events: int | None = 100_000,
    multistart: bool = False,
) -> pd.DataFrame:
    """Fit Hawkes models separately to major LOBSTER message-event groups."""
    rows = []
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        for event_group in event_groups:
            sub = _filter_event_group(msg, event_group)
            if len(sub) < 10:
                continue
            fit = fit_univariate_exponential_hawkes(
                sub["time"].to_numpy(),
                max_events=max_events,
                multistart=multistart,
            )
            event_types = EVENT_GROUPS[event_group]
            rows.append(
                {
                    "ticker": ticker,
                    "event_group": event_group,
                    "event_types": "all" if event_types is None else ",".join(map(str, event_types)),
                    "n_events_raw": int(len(sub)),
                    "event_share": float(len(sub) / len(msg)),
                    "mu": fit.mu,
                    "rho": fit.rho,
                    "beta": fit.beta,
                    "neg_loglik": fit.neg_loglik,
                    "success": fit.success,
                    "hit_beta_upper": fit.hit_beta_upper,
                    "n_events_fit": fit.n_events,
                    "horizon": fit.horizon,
                    "event_rate_fit": fit.n_events / fit.horizon,
                    "residual_mean": fit.residual_mean,
                    "residual_variance": fit.residual_variance,
                    "residual_ks_stat": fit.residual_ks_stat,
                    "residual_ks_pvalue": fit.residual_ks_pvalue,
                }
            )
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_hawkes_fit_by_event_type.csv", index=False)
    return df


def fit_lobster_fixed_beta_sensitivity(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    event_groups: tuple[str, ...] = ("all", "limit", "cancel_delete", "execution"),
    beta_grid: tuple[float, ...] = (1.0, 5.0, 20.0, 100.0),
    max_events: int | None = 60_000,
) -> pd.DataFrame:
    """Estimate branching ratios over a fixed decay-rate grid for sensitivity checks."""
    rows = []
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        for event_group in event_groups:
            sub = _filter_event_group(msg, event_group)
            if len(sub) < 10:
                continue
            for beta in beta_grid:
                fit = _fit_fixed_beta(sub["time"].to_numpy(), beta=beta, max_events=max_events)
                rows.append(
                    {
                        "ticker": ticker,
                        "event_group": event_group,
                        "beta_fixed": beta,
                        "n_events_raw": int(len(sub)),
                        "mu": fit.mu,
                        "rho": fit.rho,
                        "neg_loglik": fit.neg_loglik,
                        "success": fit.success,
                        "n_events_fit": fit.n_events,
                        "horizon": fit.horizon,
                        "event_rate_fit": fit.n_events / fit.horizon,
                        "residual_mean": fit.residual_mean,
                        "residual_variance": fit.residual_variance,
                        "residual_ks_stat": fit.residual_ks_stat,
                        "residual_ks_pvalue": fit.residual_ks_pvalue,
                    }
                )
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_hawkes_fixed_beta_sensitivity.csv", index=False)
    return df


def validate_hawkes_estimator(
    results_root: Path = Path("results"),
    scenarios: tuple[tuple[float, float, float, float], ...] = (
        (0.30, 2.0, 0.8, 800.0),
        (0.70, 4.0, 0.8, 800.0),
        (0.90, 8.0, 0.6, 500.0),
    ),
    reps: int = 12,
    seed: int = 7400,
) -> pd.DataFrame:
    """Validate MLE recovery on synthetic Ogata Hawkes samples."""
    rows = []
    for scenario_id, (rho_true, beta_true, mu_true, horizon) in enumerate(scenarios):
        params = HawkesParams(
            mu=np.array([mu_true], dtype=float),
            gamma=np.array([[rho_true]], dtype=float),
            beta=beta_true,
            dt=0.01,
            horizon=horizon,
        )
        for rep in range(reps):
            out = simulate_ogata_hawkes(params, seed=seed + scenario_id * 1000 + rep)
            times = out["times"]
            if len(times) < 20:
                continue
            fit = fit_univariate_exponential_hawkes(times, max_events=None)
            rows.append(
                {
                    "scenario": scenario_id,
                    "rep": rep,
                    "mu_true": mu_true,
                    "rho_true": rho_true,
                    "beta_true": beta_true,
                    "horizon": horizon,
                    "n_events": int(len(times)),
                    "mu_hat": fit.mu,
                    "rho_hat": fit.rho,
                    "beta_hat": fit.beta,
                    "mu_relative_error": (fit.mu - mu_true) / mu_true,
                    "rho_error": fit.rho - rho_true,
                    "beta_relative_error": (fit.beta - beta_true) / beta_true,
                    "hit_beta_upper": fit.hit_beta_upper,
                    "success": fit.success,
                    "residual_mean": fit.residual_mean,
                    "residual_variance": fit.residual_variance,
                    "residual_ks_stat": fit.residual_ks_stat,
                    "residual_ks_pvalue": fit.residual_ks_pvalue,
                }
            )
    df = pd.DataFrame(rows)
    summary = (
        df.groupby(["scenario", "mu_true", "rho_true", "beta_true", "horizon"], as_index=False)
        .agg(
            reps=("rep", "count"),
            mean_n_events=("n_events", "mean"),
            mu_hat_mean=("mu_hat", "mean"),
            rho_hat_mean=("rho_hat", "mean"),
            beta_hat_mean=("beta_hat", "mean"),
            mu_mape=("mu_relative_error", lambda x: float(np.mean(np.abs(x)))),
            rho_mae=("rho_error", lambda x: float(np.mean(np.abs(x)))),
            beta_mape=("beta_relative_error", lambda x: float(np.mean(np.abs(x)))),
            beta_cap_rate=("hit_beta_upper", "mean"),
            success_rate=("success", "mean"),
            residual_ks_mean=("residual_ks_stat", "mean"),
        )
        if len(df)
        else pd.DataFrame()
    )
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "raw" / "lobster_hawkes_estimator_validation_reps.csv", index=False)
    summary.to_csv(results_root / "tables" / "lobster_hawkes_estimator_validation.csv", index=False)
    return summary


def validate_marked_hawkes_estimator(
    results_root: Path = Path("results"),
    scenarios: tuple[tuple[float, float, float], ...] = (
        (0.35, 3.0, 500.0),
        (0.65, 3.0, 500.0),
    ),
    reps: int = 6,
    seed: int = 9400,
) -> pd.DataFrame:
    """Validate fixed-beta marked Hawkes recovery on synthetic Ogata samples."""
    base_gamma = np.array(
        [
            [0.25, 0.08, 0.04],
            [0.06, 0.20, 0.07],
            [0.05, 0.04, 0.18],
        ],
        dtype=float,
    )
    mu_true = np.array([0.6, 0.5, 0.45], dtype=float)
    rows = []
    for scenario_id, (rho_true, beta_true, horizon) in enumerate(scenarios):
        gamma_true = base_gamma * (rho_true / spectral_radius(base_gamma))
        params = HawkesParams(
            mu=mu_true,
            gamma=gamma_true,
            beta=beta_true,
            dt=0.01,
            horizon=horizon,
        )
        for rep in range(reps):
            out = simulate_ogata_hawkes(params, seed=seed + scenario_id * 1000 + rep)
            if len(out["times"]) < 50:
                continue
            fit = fit_fixed_beta_marked_multivariate_hawkes(
                out["times"],
                out["marks"],
                dim=3,
                beta=beta_true,
                max_events=None,
            )
            gamma_error = fit.gamma - gamma_true
            rows.append(
                {
                    "scenario": scenario_id,
                    "rep": rep,
                    "dim": 3,
                    "rho_true": rho_true,
                    "beta_true": beta_true,
                    "horizon": horizon,
                    "n_events": int(len(out["times"])),
                    "rho_hat": fit.spectral_radius,
                    "rho_error": fit.spectral_radius - rho_true,
                    "gamma_relative_frobenius_error": float(
                        np.linalg.norm(gamma_error, ord="fro") / max(np.linalg.norm(gamma_true, ord="fro"), 1e-12)
                    ),
                    "mu_mape": float(np.mean(np.abs((fit.mu - mu_true) / mu_true))),
                    "success": fit.success,
                    "residual_mean": fit.residual_mean,
                    "residual_variance": fit.residual_variance,
                    "residual_ks_stat": fit.residual_ks_stat,
                    "residual_ks_pvalue": fit.residual_ks_pvalue,
                    "mark_log_loss": fit.mark_log_loss,
                    "baseline_mark_log_loss": fit.baseline_mark_log_loss,
                    "mark_log_loss_improvement": fit.mark_log_loss_improvement,
                }
            )
    df = pd.DataFrame(rows)
    summary = (
        df.groupby(["scenario", "dim", "rho_true", "beta_true", "horizon"], as_index=False)
        .agg(
            reps=("rep", "count"),
            mean_n_events=("n_events", "mean"),
            rho_hat_mean=("rho_hat", "mean"),
            rho_mae=("rho_error", lambda x: float(np.mean(np.abs(x)))),
            gamma_relative_frobenius_mean=("gamma_relative_frobenius_error", "mean"),
            mu_mape=("mu_mape", "mean"),
            success_rate=("success", "mean"),
            residual_ks_mean=("residual_ks_stat", "mean"),
            mark_log_loss_gain_mean=("mark_log_loss_improvement", "mean"),
        )
        if len(df)
        else pd.DataFrame()
    )
    (results_root / "raw").mkdir(parents=True, exist_ok=True)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "raw" / "lobster_marked_hawkes_estimator_validation_reps.csv", index=False)
    summary.to_csv(results_root / "tables" / "lobster_marked_hawkes_estimator_validation.csv", index=False)
    return summary


def collapse_times_to_resolution(times: np.ndarray, resolution_seconds: float) -> np.ndarray:
    """Collapse multiple messages into one event per timestamp bucket."""
    prepared = np.sort(np.asarray(times, dtype=float))
    if resolution_seconds <= 0:
        return prepared
    buckets = np.floor((prepared - prepared[0]) / resolution_seconds).astype(np.int64)
    keep = np.r_[True, np.diff(buckets) > 0]
    return prepared[keep]


def fit_lobster_timestamp_sensitivity(
    data_root: Path = Path("data/raw/lobster"),
    results_root: Path = Path("results"),
    tickers: tuple[str, ...] = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT"),
    levels: int = 1,
    resolutions: tuple[float, ...] = (0.0, 1e-6, 1e-4, 1e-3, 1e-2),
    max_events: int | None = 80_000,
    multistart: bool = False,
) -> pd.DataFrame:
    """Fit all-message Hawkes after collapsing event bursts at time resolutions."""
    rows = []
    for ticker in tickers:
        folder = data_root / f"LOBSTER_SampleFile_{ticker}_2012-06-21_{levels}"
        msg_path = folder / f"{ticker}_2012-06-21_34200000_57600000_message_{levels}.csv"
        if not msg_path.exists():
            raise FileNotFoundError(f"missing LOBSTER message file: {msg_path}")
        msg = load_lobster_message(msg_path)
        raw_times = msg["time"].to_numpy()
        for resolution in resolutions:
            times = collapse_times_to_resolution(raw_times, resolution)
            if len(times) < 10:
                continue
            fit = fit_univariate_exponential_hawkes(times, max_events=max_events, multistart=multistart)
            rows.append(
                {
                    "ticker": ticker,
                    "resolution_seconds": resolution,
                    "n_events_raw": int(len(raw_times)),
                    "n_events_collapsed": int(len(times)),
                    "retained_share": float(len(times) / len(raw_times)),
                    "mu": fit.mu,
                    "rho": fit.rho,
                    "beta": fit.beta,
                    "neg_loglik": fit.neg_loglik,
                    "success": fit.success,
                    "hit_beta_upper": fit.hit_beta_upper,
                    "n_events_fit": fit.n_events,
                    "horizon": fit.horizon,
                    "event_rate_fit": fit.n_events / fit.horizon,
                    "residual_mean": fit.residual_mean,
                    "residual_variance": fit.residual_variance,
                    "residual_ks_stat": fit.residual_ks_stat,
                    "residual_ks_pvalue": fit.residual_ks_pvalue,
                }
            )
    df = pd.DataFrame(rows)
    (results_root / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(results_root / "tables" / "lobster_timestamp_resolution_sensitivity.csv", index=False)
    return df
