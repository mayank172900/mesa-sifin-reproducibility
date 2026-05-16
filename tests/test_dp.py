from mesa.dp import RobustDPConfig, solve_scalar_robust_dp, worst_case_rho


def test_worst_case_rho_conventions():
    assert worst_case_rho(0.9, 0.1, "relative_slack") == 0.91
    assert worst_case_rho(0.9, 0.1, "absolute_gamma") == 0.999


def test_scalar_robust_dp_returns_policy_grid():
    cfg = RobustDPConfig(q_max=2, steps=3, quote_count=4)
    policy, values = solve_scalar_robust_dp(0.8, 0.01, config=cfg)
    assert set(["time_index", "inventory", "bid_offset", "ask_offset", "half_spread"]).issubset(policy.columns)
    assert len(policy) == cfg.steps * len(cfg.inventory_grid)
    assert len(values) == (cfg.steps + 1) * len(cfg.inventory_grid)
    active_half_spreads = policy["half_spread"].dropna()
    assert (active_half_spreads >= cfg.quote_min).all()


def test_scalar_robust_dp_exposes_no_quote_actions():
    cfg = RobustDPConfig(q_max=2, steps=3, quote_count=4)
    policy, _ = solve_scalar_robust_dp(0.8, 0.01, config=cfg)
    expected = {
        "bid_active",
        "ask_active",
        "bid_action",
        "ask_action",
        "quoted_sides",
        "action",
        "no_quote_action",
        "is_no_quote",
        "is_full_no_quote",
        "quoted_half_spread",
        "quote_cap_hit",
    }
    assert expected.issubset(policy.columns)
    assert set(policy["bid_action"]).issubset({"quote", "no_quote"})
    assert set(policy["ask_action"]).issubset({"quote", "no_quote"})
    assert policy["quoted_sides"].between(0, 2).all()
    assert (policy["is_no_quote"] == (policy["quoted_sides"] < 2)).all()
    assert (policy["is_full_no_quote"] == (policy["quoted_sides"] == 0)).all()


def test_no_quote_offsets_are_nan_when_inactive():
    cfg = RobustDPConfig(q_max=1, steps=2, quote_count=3)
    policy, _ = solve_scalar_robust_dp(0.8, 0.01, config=cfg)
    assert policy.loc[~policy["bid_active"], "bid_offset"].isna().all()
    assert policy.loc[~policy["ask_active"], "ask_offset"].isna().all()
    assert policy.loc[policy["bid_active"], "bid_offset"].notna().all()
    assert policy.loc[policy["ask_active"], "ask_offset"].notna().all()


def test_no_quote_can_be_optimal_when_fills_are_unattractive():
    cfg = RobustDPConfig(
        q_max=1,
        steps=3,
        quote_min=0.01,
        quote_max=0.05,
        quote_count=3,
        base_arrival=50.0,
        fill_decay=0.1,
        inventory_penalty=20.0,
        risk_aversion=80.0,
        terminal_penalty=80.0,
        max_fill_prob=0.45,
    )
    policy, _ = solve_scalar_robust_dp(0.98, 0.02, ambiguity="absolute_gamma", config=cfg)
    assert policy["is_no_quote"].any()
