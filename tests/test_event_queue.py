import numpy as np

from mesa.event_queue import EventQueueConfig, evaluate_event_queue_policy, run_event_queue_backtest
from mesa.hawkes import HawkesParams


def test_event_queue_evaluator_returns_no_quote_metrics():
    cfg = EventQueueConfig(horizon=1.0, decision_dt=0.1, no_quote_threshold=0.03)
    row = evaluate_event_queue_policy(
        np.array([0.1, 0.2, 0.4]),
        np.array([0, 1, 0]),
        np.array([1.0, 1.0, 1.0]),
        np.zeros(3),
        rho_hat=0.99,
        rho_true=0.995,
        epsilon=0.02,
        policy="robust_gamma_abs",
        cfg=cfg,
    )
    assert row["policy"] == "robust_gamma_abs"
    assert row["n_events"] == 3
    assert row["no_quote_side_time_frac"] > 0
    assert row["full_no_quote_time_frac"] >= 0


def test_event_queue_backtest_reuses_paths_across_policies():
    params = HawkesParams(
        mu=np.array([0.4, 0.4]),
        gamma=np.array([[0.1, 0.05], [0.05, 0.1]]),
        beta=2.0,
        dt=0.05,
        horizon=1.5,
    )
    cfg = EventQueueConfig(horizon=1.5, decision_dt=0.1, max_events=5000)
    df = run_event_queue_backtest(
        params,
        rho_hat=0.7,
        rho_true=0.75,
        epsilon=0.02,
        policies=["nominal_hawkes", "robust_gamma"],
        n_paths=3,
        seed=22,
        cfg=cfg,
    )
    assert len(df) == 6
    assert set(df["policy"]) == {"nominal_hawkes", "robust_gamma"}
    assert df.groupby("path_id")["n_events"].nunique().max() == 1
    assert {"terminal_wealth", "no_quote_side_time_frac", "full_no_quote_time_frac"}.issubset(df.columns)
