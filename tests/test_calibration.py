import numpy as np
import pandas as pd
from scipy.special import logit

from mesa.calibration import (
    MarkedHawkesFit,
    _lobster_side_marked_state_frame,
    _lobster_side_marked_events,
    _prepare_marked_state_frame,
    _state_residual_event_frame,
    _summarize_state_residual_events,
    compensator_increments,
    exponential_hawkes_neg_loglik,
    fit_fixed_beta_marked_multivariate_hawkes,
    fit_fixed_beta_multiscale_hawkes,
    fit_univariate_exponential_hawkes,
    marked_multivariate_hawkes_neg_loglik_fixed_beta,
    multiscale_hawkes_neg_loglik_fixed_betas,
    validate_marked_hawkes_estimator,
)
from mesa.hawkes import HawkesParams, simulate_ogata_hawkes


def test_hawkes_neg_loglik_is_finite():
    times = np.array([0.1, 0.4, 0.9, 1.7])
    theta = np.array([np.log(1.0), 0.0, np.log(1.0)])
    value = exponential_hawkes_neg_loglik(theta, times, horizon=2.0)
    assert np.isfinite(value)


def test_fit_univariate_hawkes_smoke():
    times = np.linspace(0.1, 5.0, 20)
    fit = fit_univariate_exponential_hawkes(times, max_events=None)
    assert fit.n_events == 20
    assert 0 <= fit.rho < 1
    assert fit.mu > 0
    assert fit.beta > 0


def test_hawkes_likelihood_uses_pre_event_intensity():
    times = np.array([0.0, 100.0])
    theta = np.array([np.log(1.0), logit(0.5 / 0.999), np.log(100.0)])
    baseline = exponential_hawkes_neg_loglik(theta, times, horizon=100.0)
    no_excitation = exponential_hawkes_neg_loglik(
        np.array([np.log(1.0), logit(0.0 / 0.999), np.log(100.0)]),
        times,
        horizon=100.0,
    )
    assert np.isclose(baseline, no_excitation + 0.5, atol=1e-6)


def test_compensator_increments_are_positive_after_first_event():
    increments = compensator_increments(np.array([0.1, 0.4, 0.9]), mu=1.0, rho=0.5, beta=2.0)
    assert increments.shape == (2,)
    assert np.all(increments > 0)


def test_fit_recovers_moderate_synthetic_hawkes():
    params = HawkesParams(
        mu=np.array([0.8]),
        gamma=np.array([[0.4]]),
        beta=2.0,
        dt=0.01,
        horizon=1200.0,
    )
    out = simulate_ogata_hawkes(params, seed=123)
    fit = fit_univariate_exponential_hawkes(out["times"], max_events=None)
    assert abs(fit.rho - 0.4) < 0.15
    assert fit.beta > 0
    assert not fit.hit_beta_upper


def test_multiscale_likelihood_is_finite():
    times = np.array([0.1, 0.4, 0.9, 1.7])
    theta = np.array([np.log(1.0), 0.0, 0.0])
    value = multiscale_hawkes_neg_loglik_fixed_betas(theta, times, horizon=2.0, beta_values=np.array([1.0, 10.0]))
    assert np.isfinite(value)


def test_fixed_beta_multiscale_fit_smoke():
    times = np.linspace(0.1, 10.0, 60)
    fit = fit_fixed_beta_multiscale_hawkes(times, beta_slow=1.0, beta_fast=20.0, max_events=None)
    assert fit.n_events == 60
    assert fit.beta_slow == 1.0
    assert fit.beta_fast == 20.0
    assert 0 <= fit.rho_slow <= fit.rho < 1
    assert 0 <= fit.rho_fast <= fit.rho < 1
    assert np.isclose(fit.rho_slow + fit.rho_fast, fit.rho)


def test_marked_multivariate_likelihood_is_finite():
    times = np.array([0.1, 0.4, 0.9, 1.7, 2.2])
    marks = np.array([0, 1, 0, 1, 0])
    theta = np.r_[np.log([0.8, 0.7]), np.log(np.full((2, 2), 0.05)).ravel()]
    value = marked_multivariate_hawkes_neg_loglik_fixed_beta(
        theta,
        times,
        marks,
        horizon=2.5,
        beta=2.0,
        dim=2,
    )
    assert np.isfinite(value)


def test_fixed_beta_marked_multivariate_fit_smoke():
    params = HawkesParams(
        mu=np.array([0.7, 0.6]),
        gamma=np.array([[0.25, 0.08], [0.04, 0.20]]),
        beta=2.0,
        dt=0.01,
        horizon=500.0,
    )
    out = simulate_ogata_hawkes(params, seed=321)
    fit = fit_fixed_beta_marked_multivariate_hawkes(
        out["times"],
        out["marks"],
        dim=2,
        beta=2.0,
        max_events=None,
    )
    assert fit.n_events == len(out["times"])
    assert fit.mu.shape == (2,)
    assert fit.gamma.shape == (2, 2)
    assert np.all(fit.gamma >= 0)
    assert 0 <= fit.spectral_radius < 1
    assert np.isfinite(fit.mark_log_loss)


def test_lobster_side_mark_mapping():
    msg = pd.DataFrame(
        {
            "time": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            "event_type": [1, 2, 4, 1, 3, 5],
            "order_id": np.arange(6),
            "size": [1, 1, 1, 1, 1, 1],
            "price": [100, 100, 100, 100, 100, 100],
            "direction": [1, 1, 1, -1, -1, -1],
        }
    )
    times, marks, mark_index = _lobster_side_marked_events(msg)
    assert times.tolist() == msg["time"].tolist()
    expected = [
        mark_index["limit_buy"],
        mark_index["cancel_delete_buy"],
        mark_index["execution_buy"],
        mark_index["limit_sell"],
        mark_index["cancel_delete_sell"],
        mark_index["execution_sell"],
    ]
    assert marks.tolist() == expected


def test_lobster_side_marked_state_frame_buckets_are_deterministic():
    msg = pd.DataFrame(
        {
            "time": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            "event_type": [1, 2, 4, 1, 3, 5],
            "order_id": np.arange(6),
            "size": [10, 20, 30, 40, 50, 60],
            "price": [100, 100, 100, 100, 100, 100],
            "direction": [1, 1, 1, -1, -1, -1],
        }
    )
    orderbook = pd.DataFrame(
        {
            "ask_price_1": [10100, 10100, 10200, 10200, 10200, 10300],
            "ask_size_1": [80, 80, 100, 50, 50, 60],
            "bid_price_1": [10000, 10000, 10000, 10000, 10000, 10000],
            "bid_size_1": [120, 120, 80, 100, 100, 200],
        }
    )
    frame, mark_index = _lobster_side_marked_state_frame(msg, orderbook)
    assert len(frame) == 6
    assert frame["mark"].tolist() == [
        mark_index["limit_buy"],
        mark_index["cancel_delete_buy"],
        mark_index["execution_buy"],
        mark_index["limit_sell"],
        mark_index["cancel_delete_sell"],
        mark_index["execution_sell"],
    ]
    assert frame["size_bucket"].tolist() == ["small", "small", "small", "large", "large", "large"]
    assert set(frame["spread_bucket"]) == {"tight", "wide"}
    assert set(frame["imbalance_bucket"]) <= {"bid_heavy", "ask_heavy", "neutral"}


def test_state_residual_alignment_drops_first_event():
    msg = pd.DataFrame(
        {
            "time": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
            "event_type": [1, 2, 4, 1, 3, 5],
            "order_id": np.arange(6),
            "size": [10, 20, 30, 40, 50, 60],
            "price": [100, 100, 100, 100, 100, 100],
            "direction": [1, 1, 1, -1, -1, -1],
        }
    )
    frame, _ = _lobster_side_marked_state_frame(msg)
    prepared = _prepare_marked_state_frame(frame, max_events=None)
    fit = MarkedHawkesFit(
        mu=np.full(6, 0.4),
        gamma=np.eye(6) * 0.05,
        beta=2.0,
        neg_loglik=0.0,
        success=True,
        n_events=len(prepared),
        horizon=1.0,
        spectral_radius=0.05,
        residual_mean=1.0,
        residual_variance=1.0,
        residual_ks_stat=0.0,
        residual_ks_pvalue=1.0,
        mark_log_loss=0.0,
        baseline_mark_log_loss=0.0,
        mark_log_loss_improvement=0.0,
    )
    events = _state_residual_event_frame(prepared, fit)
    assert len(events) == len(prepared) - 1
    assert np.all(np.isfinite(events["residual_increment"]))
    rows = _summarize_state_residual_events(events, ("size_bucket", "side"))
    assert {row["state_variable"] for row in rows} == {"size_bucket", "side"}


def test_marked_hawkes_estimator_validation_smoke(tmp_path):
    summary = validate_marked_hawkes_estimator(
        results_root=tmp_path,
        scenarios=((0.35, 3.0, 250.0),),
        reps=1,
        seed=111,
    )
    assert len(summary) == 1
    assert summary["success_rate"].iloc[0] == 1.0
    assert summary["rho_mae"].iloc[0] < 0.25
    assert (tmp_path / "tables" / "lobster_marked_hawkes_estimator_validation.csv").exists()
