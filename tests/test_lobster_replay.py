import pandas as pd

from mesa.control import PolicyParams
from mesa.lobster_replay import (
    LobsterReplayConfig,
    evaluate_lobster_depth_quote_policy,
    evaluate_lobster_l1_quote_policy,
    evaluate_lobster_priority_depth_quote_policy,
    evaluate_lobster_top_of_book_policy,
)


def _toy_message() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [0.0, 0.5, 1.0, 1.5],
            "event_type": [1, 4, 5, 4],
            "order_id": [1, 2, 3, 4],
            "size": [100, 100, 100, 100],
            "price": [1000000, 1000100, 999900, 1000200],
            "direction": [1, 1, -1, 1],
        }
    )


def _toy_book() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ask_price_1": [1000100, 1000200, 1000100, 1000300],
            "ask_size_1": [100, 100, 100, 100],
            "bid_price_1": [999900, 1000000, 999900, 1000100],
            "bid_size_1": [100, 100, 100, 100],
        }
    )


def _wide_toy_book() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ask_price_1": [1000200, 1000200, 1000200, 1000200],
            "ask_size_1": [100, 100, 100, 100],
            "bid_price_1": [999800, 999800, 999800, 999800],
            "bid_size_1": [100, 100, 100, 100],
        }
    )


def _depth_toy_book() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ask_price_1": [1000100, 1000100, 1000100, 1000100],
            "ask_size_1": [100, 100, 100, 100],
            "bid_price_1": [999900, 999900, 999900, 999900],
            "bid_size_1": [100, 100, 100, 100],
            "ask_price_2": [1000200, 1000200, 1000200, 1000200],
            "ask_size_2": [100, 100, 100, 100],
            "bid_price_2": [999800, 999800, 999800, 999800],
            "bid_size_2": [100, 100, 100, 100],
        }
    )


def test_lobster_top_of_book_replay_returns_metrics():
    row = evaluate_lobster_top_of_book_policy(
        _toy_message(),
        _toy_book(),
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(max_events=4, queue_fraction=0.01, decision_interval=0.1),
    )
    assert row["fills"] > 0
    assert row["n_events"] == 4
    assert 0 <= row["no_quote_side_time_frac"] <= 1
    assert "terminal_wealth" in row


def test_lobster_replay_near_critical_guard_withdraws():
    row = evaluate_lobster_top_of_book_policy(
        _toy_message(),
        _toy_book(),
        ticker="TST",
        scenario="toy",
        rho_hat=0.97,
        rho_true=0.97,
        epsilon=0.02,
        policy="liquidity_guard",
        cfg=LobsterReplayConfig(max_events=4, queue_fraction=0.01, decision_interval=0.1),
    )
    assert row["fills"] == 0
    assert row["no_quote_side_time_frac"] > 0.9


def test_l1_quote_join_uses_queue_proxy():
    row = evaluate_lobster_l1_quote_policy(
        _toy_message(),
        _toy_book(),
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(max_events=4, queue_fraction=0.01, decision_interval=10.0),
        params=PolicyParams(base_half_spread=0.01, variance_spread_scale=0.0),
    )
    assert row["fills"] > 0
    assert row["join_side_time_frac"] > 0
    assert row["queue_depletion_from_exec"] > 0


def test_l1_quote_improve_fills_without_queue_ahead():
    row = evaluate_lobster_l1_quote_policy(
        _toy_message(),
        _wide_toy_book(),
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(max_events=4, decision_interval=10.0),
        params=PolicyParams(base_half_spread=0.01, variance_spread_scale=0.0),
    )
    assert row["fills"] > 0
    assert row["improve_side_time_frac"] > 0


def test_l1_quote_away_does_not_assume_hidden_depth_fill():
    row = evaluate_lobster_l1_quote_policy(
        _toy_message(),
        _wide_toy_book(),
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(max_events=4, decision_interval=10.0, max_quote_offset=1.0),
        params=PolicyParams(base_half_spread=0.04, variance_spread_scale=0.0),
    )
    assert row["fills"] == 0
    assert row["away_side_time_frac"] > 0


def test_l1_visible_size_drop_depletes_join_queue():
    msg = _toy_message()
    book = _toy_book()
    book.loc[1, "bid_price_1"] = book.loc[0, "bid_price_1"]
    book.loc[1, "bid_size_1"] = 0
    row = evaluate_lobster_l1_quote_policy(
        msg,
        book,
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(
            max_events=4,
            queue_fraction=0.01,
            decision_interval=10.0,
            visible_cancel_depletion_fraction=0.5,
        ),
        params=PolicyParams(base_half_spread=0.01, variance_spread_scale=0.0),
    )
    assert row["queue_depletion_from_visible_size_drop"] > 0


def test_depth_quote_visible_away_can_fill():
    row = evaluate_lobster_depth_quote_policy(
        _toy_message(),
        _depth_toy_book(),
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(max_events=4, queue_fraction=0.01, decision_interval=10.0),
        params=PolicyParams(base_half_spread=0.02, variance_spread_scale=0.0),
    )
    assert row["depth_visible_side_time_frac"] > 0
    assert row["fills"] > 0
    assert row["mean_visible_depth_rank"] >= 2


def test_depth_quote_requires_multilevel_book():
    try:
        evaluate_lobster_depth_quote_policy(
            _toy_message(),
            _toy_book(),
            ticker="TST",
            scenario="toy",
            rho_hat=0.6,
            rho_true=0.6,
            epsilon=0.02,
            policy="nominal_hawkes",
            cfg=LobsterReplayConfig(max_events=4),
        )
    except ValueError as exc:
        assert "at least two displayed book levels" in str(exc)
    else:
        raise AssertionError("expected multilevel-book ValueError")


def test_priority_depth_quote_tracks_behind_order_ids():
    msg = pd.DataFrame(
        {
            "time": [0.0, 0.25, 0.5, 0.75, 1.0],
            "event_type": [1, 1, 2, 4, 4],
            "order_id": [1, 99, 99, 2, 3],
            "size": [100, 100, 100, 100, 100],
            "price": [1000000, 1000200, 1000200, 1000100, 1000200],
            "direction": [1, -1, -1, 1, 1],
        }
    )
    book = _depth_toy_book().iloc[[0, 0, 0, 0, 0]].reset_index(drop=True)
    row = evaluate_lobster_priority_depth_quote_policy(
        msg,
        book,
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(
            max_events=5,
            decision_interval=10.0,
            priority_initial_queue_fraction=1.0,
            priority_queue_stress_multiplier=1.0,
        ),
        params=PolicyParams(base_half_spread=0.02, variance_spread_scale=0.0),
    )
    assert row["priority_behind_additions"] > 0
    assert row["priority_behind_depletion_ignored"] > 0
    assert row["priority_initial_queue_fraction"] == 1.0
    assert row["priority_queue_stress_multiplier"] == 1.0
    assert "priority_hidden_queue_multiplier" not in row
    assert row["priority_visible_levels_used"] == 2
    assert row["priority_max_visible_depth_rank"] >= 2
    assert row["fills"] == 0
    assert row["priority_zero_residual_fill_prevented"] == 1


def test_priority_depth_quote_requires_queue_depletion_before_fill():
    msg = pd.DataFrame(
        {
            "time": [0.0, 0.25, 0.5, 0.75],
            "event_type": [1, 4, 4, 4],
            "order_id": [1, 10, 11, 12],
            "size": [100, 100, 100, 100],
            "price": [1000200, 1000200, 1000200, 1000200],
            "direction": [-1, 1, 1, 1],
        }
    )
    book = _depth_toy_book().iloc[[0, 0, 0, 0]].reset_index(drop=True)
    row = evaluate_lobster_priority_depth_quote_policy(
        msg,
        book,
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(
            max_events=4,
            decision_interval=10.0,
            priority_initial_queue_fraction=1.0,
            priority_queue_stress_multiplier=1.0,
        ),
        params=PolicyParams(base_half_spread=0.02, variance_spread_scale=0.0, inventory_skew=0.0),
    )
    assert row["fills"] == 1
    assert row["priority_queue_fills"] == 1
    assert row["priority_improve_fills"] == 0
    assert row["priority_queue_violation_count"] == 0
    assert row["priority_zero_residual_fill_prevented"] == 1
    assert row["priority_mean_initial_ahead_lots"] >= 2.0
    assert row["priority_visible_levels_used"] == 2
    assert row["priority_max_visible_depth_rank"] >= 2


def test_priority_depth_quote_exact_queue_exhaustion_needs_residual_volume():
    msg = pd.DataFrame(
        {
            "time": [0.0, 0.25, 0.5],
            "event_type": [1, 4, 4],
            "order_id": [1, 10, 11],
            "size": [100, 100, 100],
            "price": [1000200, 1000200, 1000200],
            "direction": [-1, 1, 1],
        }
    )
    book = _depth_toy_book().iloc[[0, 0, 0]].reset_index(drop=True)
    row = evaluate_lobster_priority_depth_quote_policy(
        msg,
        book,
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(
            max_events=3,
            decision_interval=10.0,
            priority_initial_queue_fraction=1.0,
            priority_queue_stress_multiplier=1.0,
        ),
        params=PolicyParams(base_half_spread=0.02, variance_spread_scale=0.0, inventory_skew=0.0),
    )
    assert row["fills"] == 0
    assert row["priority_queue_fills"] == 0
    assert row["priority_residual_fill_lots"] == 0.0
    assert row["priority_zero_residual_fill_prevented"] == 1


def test_priority_depth_quote_partial_fill_uses_residual_volume():
    msg = pd.DataFrame(
        {
            "time": [0.0, 0.25, 0.5, 0.75],
            "event_type": [1, 4, 4, 4],
            "order_id": [1, 10, 11, 12],
            "size": [100, 100, 100, 50],
            "price": [1000200, 1000200, 1000200, 1000200],
            "direction": [-1, 1, 1, 1],
        }
    )
    book = _depth_toy_book().iloc[[0, 0, 0, 0]].reset_index(drop=True)
    row = evaluate_lobster_priority_depth_quote_policy(
        msg,
        book,
        ticker="TST",
        scenario="toy",
        rho_hat=0.6,
        rho_true=0.6,
        epsilon=0.02,
        policy="nominal_hawkes",
        cfg=LobsterReplayConfig(
            max_events=4,
            decision_interval=10.0,
            priority_initial_queue_fraction=1.0,
            priority_queue_stress_multiplier=1.0,
        ),
        params=PolicyParams(base_half_spread=0.02, variance_spread_scale=0.0, inventory_skew=0.0),
    )
    assert row["fills"] == 1
    assert row["priority_queue_fills"] == 1
    assert row["priority_partial_fill_events"] == 1
    assert row["priority_residual_fill_lots"] == 0.5
    assert row["total_fill_lots"] == 0.5
