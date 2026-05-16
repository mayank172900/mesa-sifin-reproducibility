"""Experiment runners for the MESA research package."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import platform
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import sys

import numpy as np
import pandas as pd
from scipy import stats

from mesa.control import (
    PolicyParams,
    certainty_equivalent,
    endogenous_variance_proxy,
    mesa_robust_premium,
    quote_offsets,
)
from mesa.hawkes import (
    HawkesParams,
    count_summary,
    ogata_binned_counts,
    ogata_counts,
    simulate_discrete_hawkes,
    simulate_discrete_hawkes_totals,
)
from mesa.spectral import (
    make_gamma_family,
    perron_data,
    resolvent,
    spectral_radius,
    variance_amplification,
    worst_case_perron_perturbation,
)
from mesa.dp import RobustDPConfig, solve_scalar_robust_dp
from mesa.event_queue import EventQueueConfig, run_event_queue_backtest


RHO_GRID = np.array([0.30, 0.50, 0.70, 0.85, 0.92, 0.97, 0.985, 0.995])
EPS_GRID = np.array([0.0025, 0.005, 0.01, 0.02, 0.05])
POLICIES = [
    "as_poisson",
    "nominal_hawkes",
    "robust_vol_only",
    "robust_gamma",
    "robust_gamma_abs",
    "liquidity_guard",
    "known_true_gamma_no_ambiguity",
]
EVENT_QUEUE_POLICIES = [
    "nominal_hawkes",
    "robust_gamma",
    "robust_gamma_abs",
    "liquidity_guard",
]
QUOTE_SENSITIVITY_POLICIES = [
    "nominal_hawkes",
    "robust_gamma",
    "robust_gamma_abs",
]


@dataclass(frozen=True)
class ExperimentConfig:
    seed: int = 7
    quick: bool = False
    dim: int = 6
    beta: float = 4.0
    dt: float = 0.02
    horizon: float = 20.0
    n_paths: int = 400
    n_jobs: int = 0

    def resolved_paths(self) -> int:
        return 160 if self.quick else self.n_paths

    def resolved_rhos(self) -> np.ndarray:
        return RHO_GRID[:5] if self.quick else RHO_GRID

    def resolved_jobs(self) -> int:
        if self.n_jobs > 0:
            return self.n_jobs
        cpus = os.cpu_count() or 2
        return max(1, min(cpus - 2, 16))


def ensure_dirs(root: Path) -> None:
    for sub in ["raw", "tables", "figures"]:
        (root / sub).mkdir(parents=True, exist_ok=True)


def run_quote_sensitivity_diagnostic(config: ExperimentConfig, results_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Check the implemented smooth quote map against its rho derivative."""
    ensure_dirs(results_root)
    params = PolicyParams()
    eps_grid = EPS_GRID[:3] if config.quick else EPS_GRID
    rows = []

    def half_spread(policy: str, rho: float, epsilon: float) -> float:
        bid, ask = quote_offsets(np.array([0.0]), rho_hat=rho, epsilon=epsilon, policy=policy, params=params)
        return float(0.5 * (bid[0] + ask[0]))

    for epsilon in eps_grid:
        for rho in config.resolved_rhos():
            gap = max(1.0 - float(rho), 1e-6)
            h = min(1.0e-5, 0.1 * gap)
            rho_lo = max(0.0, float(rho) - h)
            rho_hi = min(0.999999, float(rho) + h)
            for policy in QUOTE_SENSITIVITY_POLICIES:
                variance_half = params.variance_spread_scale / gap**2
                variance_derivative = 2.0 * params.variance_spread_scale / gap**3
                if policy == "nominal_hawkes":
                    premium = 0.0
                    premium_derivative = 0.0
                    expected_exponent = 3.0
                elif policy == "robust_gamma":
                    coeff = params.risk_aversion * params.robust_scale * float(epsilon)
                    premium = coeff / gap**2
                    premium_derivative = 2.0 * coeff / gap**3
                    expected_exponent = 3.0
                elif policy == "robust_gamma_abs":
                    coeff = params.risk_aversion * params.robust_scale * float(epsilon)
                    premium = 2.0 * coeff / gap**3
                    premium_derivative = 6.0 * coeff / gap**4
                    expected_exponent = 4.0
                else:  # pragma: no cover - guarded by constant policy list.
                    raise ValueError(f"unsupported sensitivity policy: {policy}")

                raw_half = params.base_half_spread + variance_half + premium
                capped = raw_half >= params.max_half_spread
                analytic_local = 0.0 if capped else variance_derivative + premium_derivative
                finite = (half_spread(policy, rho_hi, float(epsilon)) - half_spread(policy, rho_lo, float(epsilon))) / (
                    rho_hi - rho_lo
                )
                smooth_region = (not capped) and np.isfinite(finite)
                rows.append(
                    {
                        "policy": policy,
                        "epsilon": float(epsilon),
                        "rho": float(rho),
                        "one_minus_rho": gap,
                        "half_spread": half_spread(policy, float(rho), float(epsilon)),
                        "raw_uncapped_half_spread": raw_half,
                        "capped": bool(capped),
                        "smooth_region": bool(smooth_region),
                        "finite_diff_d_half_drho": finite,
                        "analytic_uncapped_d_half_drho": variance_derivative + premium_derivative,
                        "analytic_local_d_half_drho": analytic_local,
                        "abs_derivative_error": abs(finite - analytic_local),
                        "expected_critical_exponent": expected_exponent,
                    }
                )

    raw = pd.DataFrame(rows)
    fit_rows = []
    for (policy, epsilon), sub in raw[raw["smooth_region"]].groupby(["policy", "epsilon"]):
        usable = sub[sub["analytic_uncapped_d_half_drho"] > 0.0]
        if usable.shape[0] < 3:
            continue
        x = np.log(usable["one_minus_rho"].to_numpy())
        y = np.log(usable["analytic_uncapped_d_half_drho"].to_numpy())
        slope, intercept = np.polyfit(x, y, 1)
        pred = intercept + slope * x
        ss_res = float(np.sum((y - pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        fit_rows.append(
            {
                "policy": policy,
                "epsilon": float(epsilon),
                "n_smooth_points": int(usable.shape[0]),
                "estimated_critical_exponent": float(-slope),
                "expected_critical_exponent": float(usable["expected_critical_exponent"].iloc[0]),
                "loglog_r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0,
                "max_abs_derivative_error": float(usable["abs_derivative_error"].max()),
                "max_raw_uncapped_half_spread": float(usable["raw_uncapped_half_spread"].max()),
            }
        )
    summary = pd.DataFrame(fit_rows)
    raw.to_csv(results_root / "raw" / "quote_sensitivity_diagnostic.csv", index=False)
    summary.to_csv(results_root / "tables" / "quote_sensitivity_diagnostic_summary.csv", index=False)
    return raw, summary


def fit_power_law(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Fit log(y)=a+b log(x), returning b as the exponent."""
    mask = (x > 0) & (y > 0) & np.isfinite(x) & np.isfinite(y)
    slope, intercept, r, p, stderr = stats.linregress(np.log(x[mask]), np.log(y[mask]))
    return {
        "intercept": float(intercept),
        "slope": float(slope),
        "r2": float(r**2),
        "p_value": float(p),
        "stderr": float(stderr),
    }


def run_scaling_experiment(config: ExperimentConfig, results_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute analytic and matrix-based criticality scaling diagnostics."""
    rows: list[dict[str, float | str]] = []
    rng = np.random.default_rng(config.seed)
    for epsilon in EPS_GRID:
        for rho in config.resolved_rhos():
            premium = mesa_robust_premium(epsilon, rho, ambiguity="relative_slack")
            rows.append(
                {
                    "experiment": "minimal_relative_slack",
                    "family": "scalar",
                    "rho": rho,
                    "epsilon": epsilon,
                    "one_minus_rho": 1.0 - rho,
                    "premium": float(premium),
                    "spectral_gap": np.nan,
                    "perron_condition": np.nan,
                    "rho_worst": min(rho + epsilon, 0.999),
                }
            )
            absolute_premium = mesa_robust_premium(epsilon, rho, ambiguity="absolute_gamma")
            rows.append(
                {
                    "experiment": "absolute_gamma_derivative",
                    "family": "scalar",
                    "rho": rho,
                    "epsilon": epsilon,
                    "one_minus_rho": 1.0 - rho,
                    "premium": float(absolute_premium),
                    "spectral_gap": np.nan,
                    "perron_condition": np.nan,
                    "rho_worst": min(rho + epsilon, 0.999),
                }
            )
            for family in ["rank1", "block", "near_degenerate", "sparse"]:
                gamma = make_gamma_family(family, config.dim, rho, rng)
                data = perron_data(gamma)
                worst = worst_case_perron_perturbation(gamma, epsilon)
                matrix_premium = 0.02 * 0.08 * max(
                    variance_amplification(worst) - variance_amplification(gamma),
                    0.0,
                )
                rows.append(
                    {
                        "experiment": "matrix_resolvent",
                        "family": family,
                        "rho": rho,
                        "epsilon": epsilon,
                        "one_minus_rho": 1.0 - rho,
                        "premium": float(matrix_premium),
                        "spectral_gap": data.gap,
                        "perron_condition": data.condition,
                        "rho_worst": spectral_radius(worst),
                    }
                )

    df = pd.DataFrame(rows)
    fits = []
    for (experiment, family, epsilon), group in df.groupby(["experiment", "family", "epsilon"]):
        if len(group) >= 4:
            fit = fit_power_law(group["one_minus_rho"].to_numpy(), group["premium"].to_numpy())
            fits.append({"experiment": experiment, "family": family, "epsilon": epsilon, **fit})
    fit_df = pd.DataFrame(fits)
    df.to_csv(results_root / "raw" / "scaling_premiums.csv", index=False)
    fit_df.to_csv(results_root / "tables" / "scaling_exponent_fits.csv", index=False)
    return df, fit_df


def _two_mode_gamma(rho: float, gap_multiple: float) -> tuple[np.ndarray, float]:
    """Return a symmetric two-mode Gamma with a controlled second eigenvalue."""
    delta = 1.0 - rho
    lambda2 = 1.0 - gap_multiple * delta
    if lambda2 <= -rho:
        raise ValueError("gap_multiple produces a negative diagonal in the two-mode construction")
    a = 0.5 * (rho + lambda2)
    b = 0.5 * (rho - lambda2)
    gamma = np.array([[a, b], [b, a]], dtype=float)
    return gamma, lambda2


def _directional_resolvent_risk(gamma: np.ndarray, loading: np.ndarray) -> float:
    """Squared norm of the resolvent seen by a risk/loading direction."""
    res = resolvent(gamma)
    vec = np.asarray(loading, dtype=float) @ res
    return float(vec @ vec)


def run_spectral_gap_ablation_experiment(
    config: ExperimentConfig,
    results_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ablate Perron visibility and adversary direction in two-mode matrices."""
    ensure_dirs(results_root)
    rows: list[dict[str, float | str]] = []
    fit_rows: list[dict[str, float | str]] = []
    rhos = np.array([0.85, 0.92, 0.97, 0.985, 0.995])
    gap_multiples = np.array([2.0, 4.0, 8.0])
    epsilon_rel = 0.20
    perron = np.array([1.0, 1.0], dtype=float) / np.sqrt(2.0)
    second = np.array([1.0, -1.0], dtype=float) / np.sqrt(2.0)
    loading_specs = {
        "perron_visible": perron,
        "weak_perron_visible": np.sqrt(0.10) * perron + np.sqrt(0.90) * second,
        "perron_orthogonal": second,
    }
    adversary_specs = {
        "perron_aligned": np.outer(perron, perron),
        "second_mode": np.outer(second, second),
    }
    for gap_multiple in gap_multiples:
        for rho in rhos:
            gamma, lambda2 = _two_mode_gamma(float(rho), float(gap_multiple))
            data = perron_data(gamma)
            eps_abs = epsilon_rel * (1.0 - rho)
            for loading_name, loading in loading_specs.items():
                visibility = float(abs(loading @ perron))
                base_risk = _directional_resolvent_risk(gamma, loading)
                theorem_proxy = epsilon_rel * visibility**2 / max((1.0 - rho) ** 2, 1e-12)
                for adversary_name, direction in adversary_specs.items():
                    candidate = gamma + eps_abs * direction
                    premium = max(_directional_resolvent_risk(candidate, loading) - base_risk, 0.0)
                    rows.append(
                        {
                            "rho": float(rho),
                            "one_minus_rho": float(1.0 - rho),
                            "gap_multiple": float(gap_multiple),
                            "second_eigenvalue": float(lambda2),
                            "spectral_gap": float(data.gap),
                            "loading": loading_name,
                            "perron_visibility": visibility,
                            "adversary": adversary_name,
                            "epsilon_rel": epsilon_rel,
                            "premium": float(premium),
                            "theorem_proxy": float(theorem_proxy),
                            "premium_to_proxy": float(premium / theorem_proxy) if theorem_proxy > 0 else np.nan,
                        }
                    )
    df = pd.DataFrame(rows)
    for (gap_multiple, loading, adversary), group in df.groupby(["gap_multiple", "loading", "adversary"]):
        positive = group[group["premium"] > 1e-10]
        ratios = group["premium_to_proxy"].dropna()
        median_ratio = float(ratios.median()) if len(ratios) else np.nan
        if len(positive) >= 3:
            fit = fit_power_law(positive["one_minus_rho"].to_numpy(), positive["premium"].to_numpy())
            fit_rows.append(
                {
                    "gap_multiple": float(gap_multiple),
                    "loading": loading,
                    "adversary": adversary,
                    "n_positive": int(len(positive)),
                    "median_perron_visibility": float(group["perron_visibility"].median()),
                    "median_premium_to_proxy": median_ratio,
                    **fit,
                }
            )
        else:
            fit_rows.append(
                {
                    "gap_multiple": float(gap_multiple),
                    "loading": loading,
                    "adversary": adversary,
                    "n_positive": int(len(positive)),
                    "median_perron_visibility": float(group["perron_visibility"].median()),
                    "median_premium_to_proxy": median_ratio,
                    "intercept": np.nan,
                    "slope": np.nan,
                    "r2": np.nan,
                    "p_value": np.nan,
                    "stderr": np.nan,
                }
            )
    fit_df = pd.DataFrame(fit_rows)
    df.to_csv(results_root / "raw" / "spectral_gap_ablation.csv", index=False)
    fit_df.to_csv(results_root / "tables" / "spectral_gap_ablation_fits.csv", index=False)
    return df, fit_df


def run_hawkes_variance_experiment(config: ExperimentConfig, results_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monte Carlo estimate of Hawkes count variance blow-up."""
    rows: list[dict[str, float | int | str]] = []
    rhos = config.resolved_rhos()
    n_paths = config.resolved_paths()
    for i, rho in enumerate(rhos):
        gamma = np.array([[0.50, 0.50], [0.50, 0.50]], dtype=float) * (rho / 1.0)
        mu = np.array([0.8, 0.8], dtype=float)
        params = HawkesParams(mu=mu, gamma=gamma, beta=config.beta, dt=config.dt, horizon=config.horizon)
        totals_by_type = simulate_discrete_hawkes_totals(params, n_paths=n_paths, seed=config.seed + 100 + i)
        summary = count_summary(totals_by_type[:, None, :])
        rows.append(
            {
                "rho": rho,
                "one_minus_rho": 1.0 - rho,
                "n_paths": n_paths,
                "total_mean": summary["total_mean"],
                "total_var": summary["total_var"],
                "fano_factor": summary["total_var"] / max(summary["total_mean"], 1e-12),
            }
        )
    df = pd.DataFrame(rows)
    fit_df = pd.DataFrame(
        [
            {
                "quantity": "total_var",
                **fit_power_law(df["one_minus_rho"].to_numpy(), df["total_var"].to_numpy()),
            },
            {
                "quantity": "fano_factor",
                **fit_power_law(df["one_minus_rho"].to_numpy(), df["fano_factor"].to_numpy()),
            },
        ]
    )
    df.to_csv(results_root / "raw" / "hawkes_variance.csv", index=False)
    fit_df.to_csv(results_root / "tables" / "hawkes_variance_exponent_fits.csv", index=False)
    return df, fit_df


def _rho_from_fano(mean_count: float, var_count: float) -> float:
    fano = var_count / max(mean_count, 1e-12)
    return float(np.clip(1.0 - 1.0 / np.sqrt(max(fano, 1.0)), 0.0, 0.999))


def run_simulator_validation_experiment(
    config: ExperimentConfig,
    results_root: Path,
) -> pd.DataFrame:
    """Compare the fast discrete simulator with slow Ogata thinning."""
    rows = []
    rhos = np.array([0.30, 0.70, 0.90])
    n_paths = 80 if config.quick else 160
    horizon = 6.0 if config.quick else 10.0
    for i, rho in enumerate(rhos):
        gamma = np.array([[rho]], dtype=float)
        mu = np.array([1.0], dtype=float)
        params = HawkesParams(mu=mu, gamma=gamma, beta=config.beta, dt=0.01, horizon=horizon)
        discrete = simulate_discrete_hawkes_totals(params, n_paths=n_paths, seed=config.seed + 500 + i)
        ogata = ogata_counts(params, n_paths=n_paths, seed=config.seed + 800 + i)
        for name, counts in [("discrete", discrete), ("ogata", ogata)]:
            totals = counts.reshape(n_paths, -1).sum(axis=1)
            mean_count = float(np.mean(totals))
            var_count = float(np.var(totals, ddof=1))
            rows.append(
                {
                    "rho": rho,
                    "method": name,
                    "n_paths": n_paths,
                    "horizon": horizon,
                    "mean_count": mean_count,
                    "var_count": var_count,
                    "fano": var_count / max(mean_count, 1e-12),
                    "rho_fano_estimate": _rho_from_fano(mean_count, var_count),
                }
            )
    df = pd.DataFrame(rows)
    df.to_csv(results_root / "tables" / "simulator_validation.csv", index=False)
    return df


def run_discretization_bias_experiment(
    config: ExperimentConfig,
    results_root: Path,
) -> pd.DataFrame:
    """Quantify spurious near-critical amplification from coarse time steps."""
    rows = []
    rhos = np.array([0.50, 0.70, 0.90, 0.97])
    dts = np.array([0.08, 0.04, 0.02, 0.01, 0.005])
    n_paths = 120 if config.quick else 240
    horizon = 8.0
    mu = np.array([1.0])
    for rho in rhos:
        theoretical_mean = float(horizon * mu[0] / (1.0 - rho))
        for dt in dts:
            params = HawkesParams(
                mu=mu,
                gamma=np.array([[rho]], dtype=float),
                beta=config.beta,
                dt=float(dt),
                horizon=horizon,
            )
            counts = simulate_discrete_hawkes_totals(
                params,
                n_paths=n_paths,
                seed=config.seed + int(10000 * rho) + int(100000 * dt),
            ).sum(axis=1)
            mean_count = float(np.mean(counts))
            rows.append(
                {
                    "rho": rho,
                    "dt": dt,
                    "n_paths": n_paths,
                    "horizon": horizon,
                    "theoretical_mean": theoretical_mean,
                    "mean_count": mean_count,
                    "relative_bias": (mean_count - theoretical_mean) / theoretical_mean,
                }
            )
    df = pd.DataFrame(rows)
    df.to_csv(results_root / "tables" / "discretization_bias.csv", index=False)
    return df


def run_calibration_noise_experiment(
    config: ExperimentConfig,
    results_root: Path,
) -> pd.DataFrame:
    """Estimate rho from finite Hawkes samples to quantify near-critical noise."""
    rng = np.random.default_rng(config.seed + 9000)
    rhos = np.array([0.30, 0.70, 0.90, 0.97])
    horizons = np.array([5.0, 20.0, 80.0])
    reps = 20 if config.quick else 50
    n_paths = 60 if config.quick else 120
    rows = []
    for rho in rhos:
        for horizon in horizons:
            estimates = []
            for rep in range(reps):
                params = HawkesParams(
                    mu=np.array([1.0]),
                    gamma=np.array([[rho]], dtype=float),
                    beta=config.beta,
                    dt=config.dt,
                    horizon=float(horizon),
                )
                seed = int(rng.integers(0, 2**31 - 1))
                counts = simulate_discrete_hawkes_totals(params, n_paths=n_paths, seed=seed).sum(axis=1)
                mean_count = float(np.mean(counts))
                var_count = float(np.var(counts, ddof=1))
                estimates.append(_rho_from_fano(mean_count, var_count))
            est = np.asarray(estimates)
            rows.append(
                {
                    "rho_true": rho,
                    "horizon": horizon,
                    "n_paths": n_paths,
                    "reps": reps,
                    "rho_hat_mean": float(np.mean(est)),
                    "rho_hat_std": float(np.std(est, ddof=1)),
                    "bias": float(np.mean(est) - rho),
                    "rmse": float(np.sqrt(np.mean((est - rho) ** 2))),
                    "q05": float(np.quantile(est, 0.05)),
                    "q95": float(np.quantile(est, 0.95)),
                }
            )
    df = pd.DataFrame(rows)
    df.to_csv(results_root / "tables" / "calibration_noise.csv", index=False)
    return df


def _simulate_policy_paths(
    rho_hat: float,
    rho_true: float,
    epsilon: float,
    policy: str,
    config: ExperimentConfig,
    counts: np.ndarray,
    price_noise: np.ndarray,
    bid_uniform: np.ndarray,
    ask_uniform: np.ndarray,
    scenario_id: str,
) -> pd.DataFrame:
    n_paths = counts.shape[0]
    buy = counts[:, :, 0]
    sell = counts[:, :, 1]

    p = PolicyParams()
    cash = np.zeros(n_paths)
    inventory = np.zeros(n_paths)
    mid = np.full(n_paths, 100.0)
    inv_penalty = np.zeros(n_paths)
    spread_capture = np.zeros(n_paths)
    fills = np.zeros(n_paths)
    adverse = np.zeros(n_paths)

    for t in range(counts.shape[1]):
        imbalance = buy[:, t] - sell[:, t]
        sigma = 0.0025 * np.sqrt(endogenous_variance_proxy(rho_true))
        price_move = 0.08 * imbalance + price_noise[:, t] * sigma * np.sqrt(config.dt)

        bid_offset, ask_offset = quote_offsets(
            inventory,
            rho_hat=rho_hat,
            epsilon=epsilon,
            policy=policy,
            params=p,
            rho_oracle=rho_true,
        )
        bid_fill_prob = 1.0 - np.exp(-sell[:, t] * np.exp(-p.fill_decay * bid_offset))
        ask_fill_prob = 1.0 - np.exp(-buy[:, t] * np.exp(-p.fill_decay * ask_offset))
        bid_fill = bid_uniform[:, t] < bid_fill_prob
        ask_fill = ask_uniform[:, t] < ask_fill_prob

        cash -= bid_fill * (mid - bid_offset)
        cash += ask_fill * (mid + ask_offset)
        inventory += bid_fill.astype(float) - ask_fill.astype(float)
        fills += bid_fill + ask_fill
        spread_capture += bid_fill * bid_offset + ask_fill * ask_offset

        mid_next = mid + price_move
        adverse += bid_fill * np.maximum(mid - mid_next, 0) + ask_fill * np.maximum(mid_next - mid, 0)
        mid = mid_next
        inv_penalty += inventory**2 * config.dt

    terminal_wealth = cash + inventory * mid - 0.05 * inv_penalty
    return pd.DataFrame(
        {
            "scenario_id": scenario_id,
            "path_id": np.arange(n_paths),
            "rho_hat": rho_hat,
            "rho_true": rho_true,
            "epsilon": epsilon,
            "policy": policy,
            "terminal_wealth": terminal_wealth,
            "final_inventory": inventory,
            "abs_inventory": np.abs(inventory),
            "fills": fills,
            "fill_rate": fills / counts.shape[1],
            "spread_capture": spread_capture,
            "adverse_selection": adverse,
            "inventory_penalty": inv_penalty,
        }
    )


def _summarize_policy_paths(path_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["scenario_id", "rho_hat", "rho_true", "epsilon", "policy"]
    for keys, group in path_df.groupby(group_cols, sort=False):
        wealth = group["terminal_wealth"].to_numpy()
        cvar_5 = float(np.mean(np.sort(wealth)[: max(1, int(0.05 * len(wealth)))]))
        rows.append(
            {
                **dict(zip(group_cols, keys, strict=True)),
                "n_paths": len(group),
                "mean_wealth": float(np.mean(wealth)),
                "median_wealth": float(np.median(wealth)),
                "std_wealth": float(np.std(wealth, ddof=1)),
                "cvar_5": cvar_5,
                "certainty_equivalent": certainty_equivalent(wealth),
                "mean_abs_inventory": float(group["abs_inventory"].mean()),
                "inventory_variance": float(group["final_inventory"].var(ddof=1)),
                "fill_rate": float(group["fill_rate"].mean()),
                "spread_capture": float(group["spread_capture"].mean()),
                "adverse_selection": float(group["adverse_selection"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int = 1000) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return np.nan, np.nan
    draws = rng.integers(0, len(values), size=(n_boot, len(values)))
    means = values[draws].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def _write_policy_statistics(path_df: pd.DataFrame, results_root: Path, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed + 7000)
    ci_rows = []
    for policy, group in path_df.groupby("policy", sort=False):
        wealth = group["terminal_wealth"].to_numpy()
        cvar = np.sort(wealth)[: max(1, int(0.05 * len(wealth)))]
        mean_low, mean_high = _bootstrap_ci(wealth, rng)
        cvar_low, cvar_high = _bootstrap_ci(cvar, rng)
        ci_rows.append(
            {
                "policy": policy,
                "n": len(wealth),
                "mean_wealth": float(np.mean(wealth)),
                "mean_wealth_ci_low": mean_low,
                "mean_wealth_ci_high": mean_high,
                "cvar_5": float(np.mean(cvar)),
                "cvar_5_ci_low": cvar_low,
                "cvar_5_ci_high": cvar_high,
                "certainty_equivalent": certainty_equivalent(wealth),
            }
        )

    pivot = path_df.pivot_table(
        index=["scenario_id", "path_id"],
        columns="policy",
        values="terminal_wealth",
        aggfunc="first",
    )
    pair_rows = []
    baseline = "nominal_hawkes"
    for policy in [p for p in pivot.columns if p != baseline]:
        paired = pivot[[baseline, policy]].dropna()
        diff = (paired[policy] - paired[baseline]).to_numpy()
        low, high = _bootstrap_ci(diff, rng)
        t_stat, p_value = stats.ttest_1samp(diff, popmean=0.0)
        pair_rows.append(
            {
                "policy": policy,
                "baseline": baseline,
                "n_pairs": len(diff),
                "mean_wealth_diff": float(np.mean(diff)),
                "diff_ci_low": low,
                "diff_ci_high": high,
                "paired_t_stat": float(t_stat),
                "paired_t_p_value": float(p_value),
            }
        )
    ci_df = pd.DataFrame(ci_rows)
    pair_df = pd.DataFrame(pair_rows)
    ci_df.to_csv(results_root / "tables" / "policy_bootstrap_ci.csv", index=False)
    pair_df.to_csv(results_root / "tables" / "policy_pairwise_tests.csv", index=False)
    return ci_df, pair_df


def _run_policy_scenario(args: tuple[float, float, int, int, ExperimentConfig]) -> pd.DataFrame:
    rho_hat, epsilon, i, j, config = args
    rho_true = min(0.999, rho_hat + max(0.01, 3.0 * epsilon * (1.0 - rho_hat)))
    scenario_id = f"rho{rho_hat:.3f}_eps{epsilon:.4f}"
    n_paths = config.resolved_paths()
    gamma = np.array([[0.48, 0.52], [0.52, 0.48]], dtype=float) * rho_true
    mu = np.array([0.8, 0.8], dtype=float)
    params = HawkesParams(mu=mu, gamma=gamma, beta=config.beta, dt=config.dt, horizon=config.horizon)
    scenario_seed = config.seed + 1000 + 100 * i + 10 * j
    counts = simulate_discrete_hawkes(params, n_paths=n_paths, seed=scenario_seed)["counts"]
    rng = np.random.default_rng(scenario_seed + 999)
    price_noise = rng.standard_normal(size=(n_paths, counts.shape[1]), dtype=np.float32)
    bid_uniform = rng.random(size=(n_paths, counts.shape[1]), dtype=np.float32)
    ask_uniform = rng.random(size=(n_paths, counts.shape[1]), dtype=np.float32)
    frames = []
    for policy in POLICIES:
        frames.append(
            _simulate_policy_paths(
                rho_hat=rho_hat,
                rho_true=rho_true,
                epsilon=epsilon,
                policy=policy,
                config=config,
                counts=counts,
                price_noise=price_noise,
                bid_uniform=bid_uniform,
                ask_uniform=ask_uniform,
                scenario_id=scenario_id,
            )
        )
    return pd.concat(frames, ignore_index=True)


def run_policy_experiment(config: ExperimentConfig, results_root: Path) -> pd.DataFrame:
    """Stress-test robust and nominal quoting policies."""
    rhos = config.resolved_rhos()
    epsilons = np.array([0.005, 0.02]) if config.quick else np.array([0.005, 0.01, 0.02])
    tasks = [
        (float(rho_hat), float(epsilon), i, j, config)
        for i, rho_hat in enumerate(rhos)
        for j, epsilon in enumerate(epsilons)
    ]
    jobs = min(config.resolved_jobs(), len(tasks))
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            path_frames = list(pool.map(_run_policy_scenario, tasks))
    else:
        path_frames = [_run_policy_scenario(task) for task in tasks]
    path_df = pd.concat(path_frames, ignore_index=True)
    path_df.to_csv(results_root / "raw" / "policy_path_wealth.csv", index=False)
    metrics_df = _summarize_policy_paths(path_df)
    metrics_df.to_csv(results_root / "tables" / "policy_stress_metrics.csv", index=False)
    _write_policy_statistics(path_df, results_root, config.seed)
    return metrics_df


def _run_policy_dt_task(args: tuple[float, float, float, int, ExperimentConfig]) -> pd.DataFrame:
    rho_hat, epsilon, dt, task_id, config = args
    audit_config = ExperimentConfig(
        seed=config.seed,
        quick=config.quick,
        dim=config.dim,
        beta=config.beta,
        dt=float(dt),
        horizon=12.0 if config.quick else 16.0,
        n_paths=120 if config.quick else 240,
        n_jobs=1,
    )
    rho_true = min(0.999, rho_hat + max(0.01, 3.0 * epsilon * (1.0 - rho_hat)))
    scenario_id = f"rho{rho_hat:.3f}_eps{epsilon:.4f}_dt{dt:.4f}"
    gamma = np.array([[0.48, 0.52], [0.52, 0.48]], dtype=float) * rho_true
    mu = np.array([0.8, 0.8], dtype=float)
    params = HawkesParams(mu=mu, gamma=gamma, beta=audit_config.beta, dt=float(dt), horizon=audit_config.horizon)
    scenario_seed = config.seed + 17000 + task_id
    counts = simulate_discrete_hawkes(params, n_paths=audit_config.resolved_paths(), seed=scenario_seed)["counts"]
    rng = np.random.default_rng(scenario_seed + 999)
    price_noise = rng.standard_normal(size=(counts.shape[0], counts.shape[1]), dtype=np.float32)
    bid_uniform = rng.random(size=(counts.shape[0], counts.shape[1]), dtype=np.float32)
    ask_uniform = rng.random(size=(counts.shape[0], counts.shape[1]), dtype=np.float32)
    frames = []
    for policy in POLICIES:
        frame = _simulate_policy_paths(
            rho_hat=rho_hat,
            rho_true=rho_true,
            epsilon=epsilon,
            policy=policy,
            config=audit_config,
            counts=counts,
            price_noise=price_noise,
            bid_uniform=bid_uniform,
            ask_uniform=ask_uniform,
            scenario_id=scenario_id,
        )
        frame["dt"] = float(dt)
        frame["steps"] = counts.shape[1]
        frame["audit_horizon"] = audit_config.horizon
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def run_policy_dt_convergence_experiment(config: ExperimentConfig, results_root: Path) -> pd.DataFrame:
    """Audit whether policy ranking survives smaller Hawkes time steps."""
    rhos = np.array([0.92]) if config.quick else np.array([0.92, 0.97])
    dts = np.array([0.04, 0.02, 0.01]) if config.quick else np.array([0.04, 0.02, 0.01, 0.005])
    epsilon = 0.02
    tasks = [
        (float(rho_hat), float(epsilon), float(dt), task_id, config)
        for task_id, (rho_hat, dt) in enumerate((rho, dt) for rho in rhos for dt in dts)
    ]
    jobs = min(config.resolved_jobs(), len(tasks))
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            path_frames = list(pool.map(_run_policy_dt_task, tasks))
    else:
        path_frames = [_run_policy_dt_task(task) for task in tasks]
    path_df = pd.concat(path_frames, ignore_index=True)
    path_df.to_csv(results_root / "raw" / "policy_dt_convergence_path_wealth.csv", index=False)
    metrics = _summarize_policy_paths(path_df)
    dt_meta = (
        path_df.groupby(["scenario_id", "rho_hat", "rho_true", "epsilon", "policy"], as_index=False)
        .agg(dt=("dt", "first"), steps=("steps", "first"), audit_horizon=("audit_horizon", "first"))
    )
    metrics = metrics.merge(dt_meta, on=["scenario_id", "rho_hat", "rho_true", "epsilon", "policy"], how="left")
    pivot = path_df.pivot_table(
        index=["scenario_id", "path_id"],
        columns="policy",
        values="terminal_wealth",
        aggfunc="first",
    )
    baseline = "nominal_hawkes"
    diff_rows = []
    for scenario_id, group in pivot.groupby(level="scenario_id"):
        for policy in [p for p in group.columns if p != baseline]:
            paired = group[[baseline, policy]].dropna()
            diff = (paired[policy] - paired[baseline]).to_numpy()
            diff_rows.append(
                {
                    "scenario_id": scenario_id,
                    "policy": policy,
                    "mean_wealth_diff_vs_nominal": float(np.mean(diff)),
                    "q05_diff_vs_nominal": float(np.quantile(diff, 0.05)),
                    "q95_diff_vs_nominal": float(np.quantile(diff, 0.95)),
                }
            )
    diff_df = pd.DataFrame(diff_rows)
    metrics = metrics.merge(diff_df, on=["scenario_id", "policy"], how="left")
    metrics.to_csv(results_root / "tables" / "policy_dt_convergence.csv", index=False)

    summary = (
        metrics[metrics["policy"].isin(["robust_gamma", "nominal_hawkes", "robust_gamma_abs", "known_true_gamma_no_ambiguity"])]
        .sort_values(["rho_hat", "dt", "policy"])
        .copy()
    )
    summary.to_csv(results_root / "tables" / "policy_dt_convergence_summary.csv", index=False)
    return metrics


def _run_policy_ogata_task(args: tuple[float, float, str, int, ExperimentConfig]) -> pd.DataFrame:
    rho_hat, epsilon, arrival_simulator, task_id, config = args
    audit_config = ExperimentConfig(
        seed=config.seed,
        quick=config.quick,
        dim=config.dim,
        beta=config.beta,
        dt=0.02,
        horizon=8.0 if config.quick else 10.0,
        n_paths=80 if config.quick else 140,
        n_jobs=1,
    )
    rho_true = min(0.999, rho_hat + max(0.01, 3.0 * epsilon * (1.0 - rho_hat)))
    scenario_id = f"rho{rho_hat:.3f}_eps{epsilon:.4f}_{arrival_simulator}"
    gamma = np.array([[0.48, 0.52], [0.52, 0.48]], dtype=float) * rho_true
    mu = np.array([0.8, 0.8], dtype=float)
    params = HawkesParams(mu=mu, gamma=gamma, beta=audit_config.beta, dt=audit_config.dt, horizon=audit_config.horizon)
    scenario_seed = config.seed + 23000 + task_id * 1000
    if arrival_simulator == "discrete":
        counts = simulate_discrete_hawkes(params, n_paths=audit_config.resolved_paths(), seed=scenario_seed)["counts"]
    elif arrival_simulator == "ogata_binned":
        counts = ogata_binned_counts(
            params,
            n_paths=audit_config.resolved_paths(),
            seed=scenario_seed,
            max_events=500_000,
        )
    else:
        raise ValueError(f"unknown arrival simulator: {arrival_simulator}")

    rng = np.random.default_rng(config.seed + 24000 + task_id)
    price_noise = rng.standard_normal(size=(counts.shape[0], counts.shape[1]), dtype=np.float32)
    bid_uniform = rng.random(size=(counts.shape[0], counts.shape[1]), dtype=np.float32)
    ask_uniform = rng.random(size=(counts.shape[0], counts.shape[1]), dtype=np.float32)
    frames = []
    for policy in POLICIES:
        frame = _simulate_policy_paths(
            rho_hat=rho_hat,
            rho_true=rho_true,
            epsilon=epsilon,
            policy=policy,
            config=audit_config,
            counts=counts,
            price_noise=price_noise,
            bid_uniform=bid_uniform,
            ask_uniform=ask_uniform,
            scenario_id=scenario_id,
        )
        frame["arrival_simulator"] = arrival_simulator
        frame["dt"] = audit_config.dt
        frame["steps"] = counts.shape[1]
        frame["audit_horizon"] = audit_config.horizon
        frame["mean_total_events"] = float(counts.sum(axis=(1, 2)).mean())
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def run_policy_ogata_audit_experiment(config: ExperimentConfig, results_root: Path) -> pd.DataFrame:
    """Compare headline policies under binned Ogata arrivals versus fast discrete arrivals."""
    rhos = np.array([0.92]) if config.quick else np.array([0.92, 0.97])
    epsilon = 0.02
    simulators = ("discrete", "ogata_binned")
    tasks = [
        (float(rho_hat), float(epsilon), arrival_simulator, task_id, config)
        for task_id, (rho_hat, arrival_simulator) in enumerate((rho, sim) for rho in rhos for sim in simulators)
    ]
    jobs = min(config.resolved_jobs(), len(tasks))
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            path_frames = list(pool.map(_run_policy_ogata_task, tasks))
    else:
        path_frames = [_run_policy_ogata_task(task) for task in tasks]
    path_df = pd.concat(path_frames, ignore_index=True)
    path_df.to_csv(results_root / "raw" / "policy_ogata_audit_path_wealth.csv", index=False)
    metrics = _summarize_policy_paths(path_df)
    meta = (
        path_df.groupby(["scenario_id", "rho_hat", "rho_true", "epsilon", "policy"], as_index=False)
        .agg(
            arrival_simulator=("arrival_simulator", "first"),
            dt=("dt", "first"),
            steps=("steps", "first"),
            audit_horizon=("audit_horizon", "first"),
            mean_total_events=("mean_total_events", "first"),
        )
    )
    metrics = metrics.merge(meta, on=["scenario_id", "rho_hat", "rho_true", "epsilon", "policy"], how="left")
    pivot = path_df.pivot_table(
        index=["scenario_id", "path_id"],
        columns="policy",
        values="terminal_wealth",
        aggfunc="first",
    )
    baseline = "nominal_hawkes"
    diff_rows = []
    for scenario_id, group in pivot.groupby(level="scenario_id"):
        for policy in [p for p in group.columns if p != baseline]:
            paired = group[[baseline, policy]].dropna()
            diff = (paired[policy] - paired[baseline]).to_numpy()
            diff_rows.append(
                {
                    "scenario_id": scenario_id,
                    "policy": policy,
                    "mean_wealth_diff_vs_nominal": float(np.mean(diff)),
                    "q05_diff_vs_nominal": float(np.quantile(diff, 0.05)),
                    "q95_diff_vs_nominal": float(np.quantile(diff, 0.95)),
                }
            )
    diff_df = pd.DataFrame(diff_rows)
    metrics = metrics.merge(diff_df, on=["scenario_id", "policy"], how="left")
    metrics.to_csv(results_root / "tables" / "policy_ogata_audit.csv", index=False)
    summary = (
        metrics[metrics["policy"].isin(["robust_gamma", "nominal_hawkes", "robust_gamma_abs", "known_true_gamma_no_ambiguity"])]
        .sort_values(["rho_hat", "arrival_simulator", "policy"])
        .copy()
    )
    summary.to_csv(results_root / "tables" / "policy_ogata_audit_summary.csv", index=False)
    return metrics


def _run_event_queue_task(args: tuple[float, float, int, ExperimentConfig]) -> pd.DataFrame:
    rho_hat, epsilon, task_id, config = args
    horizon = 4.0 if config.quick else 6.0
    n_paths = 24 if config.quick else 60
    rho_true = min(0.995, rho_hat + max(0.01, 3.0 * epsilon * (1.0 - rho_hat)))
    gamma = np.array([[0.48, 0.52], [0.52, 0.48]], dtype=float) * rho_true
    mu = np.array([0.8, 0.8], dtype=float)
    hawkes_params = HawkesParams(mu=mu, gamma=gamma, beta=config.beta, dt=config.dt, horizon=horizon)
    queue_cfg = EventQueueConfig(
        horizon=horizon,
        decision_dt=config.dt,
        max_events=200_000,
    )
    frame = run_event_queue_backtest(
        hawkes_params,
        rho_hat=float(rho_hat),
        rho_true=float(rho_true),
        epsilon=float(epsilon),
        policies=EVENT_QUEUE_POLICIES,
        n_paths=n_paths,
        seed=config.seed + 31000 + 100 * task_id,
        cfg=queue_cfg,
    )
    frame["scenario_id"] = f"rho{rho_hat:.3f}_eps{epsilon:.4f}_event_queue"
    return frame


def run_event_queue_backtest_experiment(config: ExperimentConfig, results_root: Path) -> pd.DataFrame:
    """Run a reduced event-time queue backtest for quote/no-quote policies."""
    rhos = np.array([0.92]) if config.quick else np.array([0.92, 0.97])
    epsilon = 0.02
    tasks = [(float(rho_hat), float(epsilon), task_id, config) for task_id, rho_hat in enumerate(rhos)]
    jobs = min(config.resolved_jobs(), len(tasks))
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            path_frames = list(pool.map(_run_event_queue_task, tasks))
    else:
        path_frames = [_run_event_queue_task(task) for task in tasks]
    path_df = pd.concat(path_frames, ignore_index=True)
    path_df.to_csv(results_root / "raw" / "event_queue_backtest_path_wealth.csv", index=False)

    metrics = _summarize_policy_paths(path_df)
    meta = (
        path_df.groupby(["scenario_id", "rho_hat", "rho_true", "epsilon", "policy"], as_index=False)
        .agg(
            horizon=("horizon", "first"),
            decision_dt=("decision_dt", "first"),
            mean_events=("n_events", "mean"),
            mean_quote_updates=("quote_updates", "mean"),
            no_quote_side_time_frac=("no_quote_side_time_frac", "mean"),
            full_no_quote_time_frac=("full_no_quote_time_frac", "mean"),
            bid_fills=("bid_fills", "mean"),
            ask_fills=("ask_fills", "mean"),
        )
    )
    metrics = metrics.merge(meta, on=["scenario_id", "rho_hat", "rho_true", "epsilon", "policy"], how="left")

    pivot = path_df.pivot_table(
        index=["scenario_id", "path_id"],
        columns="policy",
        values="terminal_wealth",
        aggfunc="first",
    )
    baseline = "nominal_hawkes"
    diff_rows = []
    for scenario_id, group in pivot.groupby(level="scenario_id"):
        for policy in [p for p in group.columns if p != baseline]:
            paired = group[[baseline, policy]].dropna()
            diff = (paired[policy] - paired[baseline]).to_numpy()
            diff_rows.append(
                {
                    "scenario_id": scenario_id,
                    "policy": policy,
                    "mean_wealth_diff_vs_nominal": float(np.mean(diff)),
                    "q05_diff_vs_nominal": float(np.quantile(diff, 0.05)),
                    "q95_diff_vs_nominal": float(np.quantile(diff, 0.95)),
                }
            )
    diff_df = pd.DataFrame(diff_rows)
    metrics = metrics.merge(diff_df, on=["scenario_id", "policy"], how="left")
    metrics.to_csv(results_root / "tables" / "event_queue_backtest.csv", index=False)
    summary = metrics.sort_values(["rho_hat", "policy"]).copy()
    summary.to_csv(results_root / "tables" / "event_queue_backtest_summary.csv", index=False)
    return metrics


def _run_dp_task(args: tuple[float, float, str, RobustDPConfig]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rho, epsilon, ambiguity, dp_cfg = args
    return solve_scalar_robust_dp(
        rho_hat=float(rho),
        epsilon=float(epsilon),
        ambiguity=ambiguity,
        config=dp_cfg,
    )


def run_robust_dp_experiment(config: ExperimentConfig, results_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the finite-scenario robust inventory DP on the core rho/epsilon grid."""
    dp_cfg = RobustDPConfig(
        steps=24 if config.quick else 36,
        quote_count=22 if config.quick else 30,
    )
    epsilons = np.array([0.005, 0.02]) if config.quick else np.array([0.005, 0.01, 0.02])
    tasks = [
        (float(rho), float(epsilon), ambiguity, dp_cfg)
        for rho in config.resolved_rhos()
        for epsilon in epsilons
        for ambiguity in ["relative_slack", "absolute_gamma"]
    ]
    jobs = min(config.resolved_jobs(), len(tasks))
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(_run_dp_task, tasks))
    else:
        results = [_run_dp_task(task) for task in tasks]
    policy_frames = [policy for policy, _ in results]
    value_frames = [values for _, values in results]
    policy_df = pd.concat(policy_frames, ignore_index=True)
    value_df = pd.concat(value_frames, ignore_index=True)
    action_summary = (
        policy_df.groupby(["rho_hat", "epsilon", "ambiguity", "rho_worst"], as_index=False)
        .agg(
            no_quote_rate=("is_no_quote", "mean"),
            full_no_quote_rate=("is_full_no_quote", "mean"),
            one_sided_quote_rate=("quoted_sides", lambda x: float((x == 1).mean())),
            quote_cap_hit_rate=("quote_cap_hit", "mean"),
            mean_quoted_sides=("quoted_sides", "mean"),
        )
    )
    summary = (
        policy_df[(policy_df["time_index"] == 0) & (policy_df["inventory"] == 0)]
        .copy()
        .sort_values(["ambiguity", "epsilon", "rho_hat"])
    )
    summary = summary.merge(
        action_summary,
        on=["rho_hat", "epsilon", "ambiguity", "rho_worst"],
        how="left",
        suffixes=("", "_grid"),
    )
    policy_df.to_csv(results_root / "raw" / "robust_dp_policy_grid.csv", index=False)
    value_df.to_csv(results_root / "raw" / "robust_dp_values.csv", index=False)
    summary.to_csv(results_root / "tables" / "robust_dp_quotes.csv", index=False)
    return summary, value_df


def run_ablation_experiment(config: ExperimentConfig, results_root: Path) -> pd.DataFrame:
    """Create ablation table from policy, scaling, DP, and empirical outputs."""
    policy = pd.read_csv(results_root / "tables" / "policy_stress_metrics.csv")
    ci = pd.read_csv(results_root / "tables" / "policy_bootstrap_ci.csv")
    pairs = pd.read_csv(results_root / "tables" / "policy_pairwise_tests.csv")
    scaling = pd.read_csv(results_root / "tables" / "scaling_exponent_fits.csv")
    dp = pd.read_csv(results_root / "tables" / "robust_dp_quotes.csv")

    policy_summary = (
        policy.groupby("policy")
        .agg(
            certainty_equivalent=("certainty_equivalent", "mean"),
            cvar_5=("cvar_5", "mean"),
            fill_rate=("fill_rate", "mean"),
            mean_abs_inventory=("mean_abs_inventory", "mean"),
        )
        .reset_index()
    )
    policy_summary["scenario_mean_certainty_equivalent"] = policy_summary["certainty_equivalent"]
    ci_for_merge = ci[
        [
            "policy",
            "mean_wealth",
            "certainty_equivalent",
            "cvar_5",
            "mean_wealth_ci_low",
            "mean_wealth_ci_high",
            "cvar_5_ci_low",
            "cvar_5_ci_high",
        ]
    ].rename(
        columns={
            "mean_wealth": "pooled_mean_wealth",
            "certainty_equivalent": "pooled_certainty_equivalent",
            "cvar_5": "pooled_cvar_5",
        }
    )
    policy_summary = policy_summary.merge(
        ci_for_merge,
        on="policy",
        how="left",
    )
    policy_summary = policy_summary.merge(
        pairs[["policy", "baseline", "mean_wealth_diff", "diff_ci_low", "diff_ci_high", "paired_t_p_value"]],
        on="policy",
        how="left",
    )
    policy_summary["ablation_family"] = "policy"

    scaling_summary = (
        scaling.groupby(["experiment", "family"])
        .agg(mean_slope=("slope", "mean"), min_r2=("r2", "min"))
        .reset_index()
        .rename(columns={"experiment": "policy", "family": "baseline"})
    )
    scaling_summary["ablation_family"] = "scaling"

    dp_summary = (
        dp.groupby("ambiguity")
        .agg(
            mean_dp_half_spread=("quoted_half_spread", "mean"),
            max_dp_half_spread=("quoted_half_spread", "max"),
            mean_worst_rho=("rho_worst", "mean"),
            mean_no_quote_rate=("no_quote_rate", "mean"),
            max_no_quote_rate=("no_quote_rate", "max"),
            mean_full_no_quote_rate=("full_no_quote_rate", "mean"),
            mean_one_sided_quote_rate=("one_sided_quote_rate", "mean"),
            mean_quote_cap_hit_rate=("quote_cap_hit_rate", "mean"),
        )
        .reset_index()
        .rename(columns={"ambiguity": "policy"})
    )
    dp_summary["ablation_family"] = "robust_dp"

    sota = pd.DataFrame(
        [
            {
                "paper_or_baseline": "Law & Viens 2019/2020",
                "covers_hawkes_mm": True,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Hawkes/point-process MM exists; MESA adds structural Gamma ambiguity.",
            },
            {
                "paper_or_baseline": "Wang, Ventre, Polukarov 2025 quote/no-quote",
                "covers_hawkes_mm": False,
                "covers_robust_mm": True,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Robust/no-quote MM exists; MESA adds spectral Hawkes uncertainty.",
            },
            {
                "paper_or_baseline": "Wang, Ventre, Polukarov 2025 Hawkes ARL",
                "covers_hawkes_mm": True,
                "covers_robust_mm": True,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Closest RL competitor; MESA needs theorem plus Gamma ambiguity.",
            },
            {
                "paper_or_baseline": "Jain et al. 2025 Hawkes impulse control",
                "covers_hawkes_mm": True,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Closest HJB-QVI competitor; no structural robustness law.",
            },
            {
                "paper_or_baseline": "Lalor & Swishchuk 2025 neural Hawkes LOB",
                "covers_hawkes_mm": True,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Strong simulator baseline; MESA adds ambiguity amplification diagnostics.",
            },
            {
                "paper_or_baseline": "Guo, Lin & Huang 2023 Attn-LOB DRL",
                "covers_hawkes_mm": False,
                "covers_robust_mm": True,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "LOB-feature DRL baseline; MESA studies structural Hawkes ambiguity rather than alpha learning.",
            },
            {
                "paper_or_baseline": "Jiang et al. 2025 Relaver latency/inventory RL",
                "covers_hawkes_mm": False,
                "covers_robust_mm": True,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Latency-aware neural MM benchmark; MESA is a reduced-form uncertainty stress test.",
            },
            {
                "paper_or_baseline": "Raffaelli et al. 2026 multivariate Hawkes BTC LOB",
                "covers_hawkes_mm": False,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Current multivariate LOB calibration/forecasting benchmark; MESA adds robust control stress tests.",
            },
            {
                "paper_or_baseline": "El Karmi 2025 deterministic Hawkes LOB simulator",
                "covers_hawkes_mm": False,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Simulator-realism baseline; MESA adds robustness and residual-stress diagnostics.",
            },
            {
                "paper_or_baseline": "Noble, Rosenbaum & Souilmi 2026 realism gap",
                "covers_hawkes_mm": False,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": False,
                "mesa_position": "Strong simulator-realism framing; MESA is a complementary risk layer.",
            },
            {
                "paper_or_baseline": "Kimura 2026 state-dependent Hawkes",
                "covers_hawkes_mm": False,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": True,
                "mesa_position": "Local supercriticality supports structural diagnostics.",
            },
            {
                "paper_or_baseline": "Szymanski & Xu 2025 nearly unstable Hawkes",
                "covers_hawkes_mm": False,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": True,
                "mesa_position": "Near-critical Hawkes limits exist; MESA adds market-making control.",
            },
            {
                "paper_or_baseline": "El Karmi 2026 bivariate nearly unstable Hawkes",
                "covers_hawkes_mm": False,
                "covers_robust_mm": False,
                "covers_gamma_uncertainty": False,
                "covers_critical_exponent": True,
                "mesa_position": "Related limit theory; MESA targets robust market-making premiums.",
            },
            {
                "paper_or_baseline": "MESA reduced-form package",
                "covers_hawkes_mm": True,
                "covers_robust_mm": True,
                "covers_gamma_uncertainty": True,
                "covers_critical_exponent": True,
                "mesa_position": "Reduced-form theorem, policy stress tests, and public-data calibration diagnostics.",
            },
        ]
    )
    source_url = {
        "Law & Viens 2019/2020": "https://arxiv.org/abs/1903.07222",
        "Wang, Ventre, Polukarov 2025 quote/no-quote": "https://arxiv.org/abs/2508.16588",
        "Wang, Ventre, Polukarov 2025 Hawkes ARL": "https://arxiv.org/abs/2508.16589",
        "Jain et al. 2025 Hawkes impulse control": "https://arxiv.org/abs/2510.26438",
        "Lalor & Swishchuk 2025 neural Hawkes LOB": "https://arxiv.org/abs/2502.17417",
        "Guo, Lin & Huang 2023 Attn-LOB DRL": "https://arxiv.org/abs/2305.15821",
        "Jiang et al. 2025 Relaver latency/inventory RL": "https://arxiv.org/abs/2505.12465",
        "Raffaelli et al. 2026 multivariate Hawkes BTC LOB": "https://doi.org/10.1007/s10203-026-00570-z",
        "El Karmi 2025 deterministic Hawkes LOB simulator": "https://arxiv.org/abs/2510.08085",
        "Noble, Rosenbaum & Souilmi 2026 realism gap": "https://arxiv.org/abs/2603.24137",
        "Kimura 2026 state-dependent Hawkes": "https://arxiv.org/abs/2604.23961",
        "Szymanski & Xu 2025 nearly unstable Hawkes": "https://arxiv.org/abs/2501.11648",
        "El Karmi 2026 bivariate nearly unstable Hawkes": "https://arxiv.org/abs/2605.03703",
        "MESA reduced-form package": "local:/Users/goodday/Documents/Projects/16may",
    }
    code_url = {
        "Guo, Lin & Huang 2023 Attn-LOB DRL": "https://github.com/imTurkey/Market-Making-with-Deep-Reinforcement-Learning-from-Limit-Order-Books",
        "Jiang et al. 2025 Relaver latency/inventory RL": "https://anonymous.4open.science/r/Relaver_ijcai-3025/",
        "El Karmi 2025 deterministic Hawkes LOB simulator": "https://github.com/sohaibelkarmi/High-Frequency-Trading-Simulator",
        "MESA reduced-form package": "local:/Users/goodday/Documents/Projects/16may",
    }
    code_reality = {
        "Guo, Lin & Huang 2023 Attn-LOB DRL": "Public demo repository visible with conda_setup.yaml and main.py; license not visible in web audit.",
        "Jiang et al. 2025 Relaver latency/inventory RL": "Paper/rebuttal text points to anonymous 4open code; detailed public post-review repository not verified.",
        "El Karmi 2025 deterministic Hawkes LOB simulator": "Public GitHub repository visible with C++/Python source, configs, docs, tests, Makefile/CMake, and quick-start guidance; license not visible in web audit.",
        "MESA reduced-form package": "Local reproducible package with tests, Makefile, scripts, data fetchers, reports, figures, and PDFs.",
    }
    sota["source_url"] = sota["paper_or_baseline"].map(source_url).fillna("")
    sota["code_url"] = sota["paper_or_baseline"].map(code_url).fillna("")
    sota["code_reality_note"] = sota["paper_or_baseline"].map(code_reality).fillna(
        "No directly usable public code repository verified in the May 16, 2026 web audit."
    )
    sota["web_verified_date"] = "2026-05-16"
    empirical_lob = {
        "Guo, Lin & Huang 2023 Attn-LOB DRL",
        "Jiang et al. 2025 Relaver latency/inventory RL",
        "Lalor & Swishchuk 2025 neural Hawkes LOB",
        "Raffaelli et al. 2026 multivariate Hawkes BTC LOB",
        "El Karmi 2025 deterministic Hawkes LOB simulator",
        "Noble, Rosenbaum & Souilmi 2026 realism gap",
        "MESA reduced-form package",
    }
    queue_latency = {
        "Guo, Lin & Huang 2023 Attn-LOB DRL",
        "Jiang et al. 2025 Relaver latency/inventory RL",
        "El Karmi 2025 deterministic Hawkes LOB simulator",
        "Noble, Rosenbaum & Souilmi 2026 realism gap",
    }
    neural_rl = {
        "Wang, Ventre, Polukarov 2025 Hawkes ARL",
        "Guo, Lin & Huang 2023 Attn-LOB DRL",
        "Jiang et al. 2025 Relaver latency/inventory RL",
        "Lalor & Swishchuk 2025 neural Hawkes LOB",
    }
    sota["empirical_lob_evaluation"] = sota["paper_or_baseline"].isin(empirical_lob)
    sota["queue_or_latency_realism"] = sota["paper_or_baseline"].isin(queue_latency)
    sota["neural_or_rl_policy"] = sota["paper_or_baseline"].isin(neural_rl)
    sota["production_execution_claim"] = False
    sota.to_csv(results_root / "tables" / "sota_comparison.csv", index=False)
    policy_summary.to_csv(results_root / "tables" / "policy_ablation_table.csv", index=False)
    scaling_summary.to_csv(results_root / "tables" / "scaling_ablation_table.csv", index=False)
    dp_summary.to_csv(results_root / "tables" / "dp_ablation_table.csv", index=False)
    return policy_summary


def run_finite_n_experiment(config: ExperimentConfig, results_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Finite-N error proxy using closed-form Gaussian absolute-error moments."""
    n_grid = np.array([25, 50, 100, 250, 500, 1000])
    if config.quick:
        n_grid = n_grid[:4]
    rows = []
    for rho in config.resolved_rhos():
        sigma = np.sqrt(endogenous_variance_proxy(rho))
        for n in n_grid:
            finite_n_scale = sigma / np.sqrt(n)
            rows.append(
                {
                    "rho": rho,
                    "one_minus_rho": 1.0 - rho,
                    "n": n,
                    "mean_error": float(finite_n_scale * np.sqrt(2.0 / np.pi)),
                    "q95_error": float(finite_n_scale * stats.norm.ppf(0.975)),
                }
            )
    df = pd.DataFrame(rows)
    log_n = np.log(df["n"].to_numpy())
    log_gap = np.log(df["one_minus_rho"].to_numpy())
    y = np.log(df["mean_error"].to_numpy())
    design = np.column_stack([np.ones_like(log_n), log_n, log_gap])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    pred = design @ coef
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    fit_df = pd.DataFrame(
        [
            {
                "intercept": coef[0],
                "alpha_N": -coef[1],
                "beta_criticality": -coef[2],
                "r2": 1.0 - ss_res / ss_tot,
            }
        ]
    )
    df.to_csv(results_root / "raw" / "finite_n_error_proxy.csv", index=False)
    fit_df.to_csv(results_root / "tables" / "finite_n_error_fit.csv", index=False)
    return df, fit_df


def write_manifest(config: ExperimentConfig, results_root: Path) -> None:
    row = {
        **asdict(config),
        "resolved_jobs": config.resolved_jobs(),
        "resolved_paths": config.resolved_paths(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }
    manifest = pd.DataFrame([row])
    manifest.to_csv(results_root / "tables" / "run_manifest.csv", index=False)


def run_all(config: ExperimentConfig, results_root: Path = Path("results")) -> dict[str, pd.DataFrame]:
    ensure_dirs(results_root)
    write_manifest(config, results_root)
    scaling, scaling_fits = run_scaling_experiment(config, results_root)
    spectral_gap, spectral_gap_fits = run_spectral_gap_ablation_experiment(config, results_root)
    hawkes_var, hawkes_fits = run_hawkes_variance_experiment(config, results_root)
    simulator_validation = run_simulator_validation_experiment(config, results_root)
    discretization_bias = run_discretization_bias_experiment(config, results_root)
    calibration_noise = run_calibration_noise_experiment(config, results_root)
    policy = run_policy_experiment(config, results_root)
    policy_dt = run_policy_dt_convergence_experiment(config, results_root)
    policy_ogata = run_policy_ogata_audit_experiment(config, results_root)
    event_queue = run_event_queue_backtest_experiment(config, results_root)
    dp_summary, dp_values = run_robust_dp_experiment(config, results_root)
    finite_n, finite_n_fit = run_finite_n_experiment(config, results_root)
    quote_sensitivity, quote_sensitivity_summary = run_quote_sensitivity_diagnostic(config, results_root)
    ablations = run_ablation_experiment(config, results_root)
    return {
        "scaling": scaling,
        "scaling_fits": scaling_fits,
        "spectral_gap": spectral_gap,
        "spectral_gap_fits": spectral_gap_fits,
        "hawkes_variance": hawkes_var,
        "hawkes_variance_fits": hawkes_fits,
        "simulator_validation": simulator_validation,
        "discretization_bias": discretization_bias,
        "calibration_noise": calibration_noise,
        "policy": policy,
        "policy_dt": policy_dt,
        "policy_ogata": policy_ogata,
        "event_queue": event_queue,
        "dp_summary": dp_summary,
        "dp_values": dp_values,
        "finite_n": finite_n,
        "finite_n_fit": finite_n_fit,
        "quote_sensitivity": quote_sensitivity,
        "quote_sensitivity_summary": quote_sensitivity_summary,
        "ablations": ablations,
    }
