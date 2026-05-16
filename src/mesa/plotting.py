"""Figure generation for MESA experiments."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def save_scaling_plot(results_root: Path) -> None:
    df = pd.read_csv(results_root / "raw" / "scaling_premiums.csv")
    fig, ax = plt.subplots(figsize=(7, 4.8))
    plot_df = df[(df["experiment"] == "minimal_relative_slack") & (df["epsilon"] == df["epsilon"].min())]
    ax.loglog(plot_df["one_minus_rho"], plot_df["premium"], marker="o", label="relative slack")
    abs_df = df[(df["experiment"] == "absolute_gamma_derivative") & (df["epsilon"] == df["epsilon"].min())]
    ax.loglog(abs_df["one_minus_rho"], abs_df["premium"], marker="s", label="absolute Gamma")
    for family in ["rank1", "block", "near_degenerate", "sparse"]:
        sub = df[(df["experiment"] == "matrix_resolvent") & (df["family"] == family) & (df["epsilon"] == df["epsilon"].min())]
        ax.loglog(sub["one_minus_rho"], sub["premium"], marker=".", alpha=0.75, label=family)
    ax.invert_xaxis()
    ax.set_xlabel("1 - rho")
    ax.set_ylabel("robustness premium proxy")
    ax.set_title("Criticality amplification")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "criticality_scaling.png", dpi=220)
    plt.close(fig)


def save_spectral_gap_ablation_plot(results_root: Path) -> None:
    table = results_root / "raw" / "spectral_gap_ablation.csv"
    fits_table = results_root / "tables" / "spectral_gap_ablation_fits.csv"
    if not table.exists() or not fits_table.exists():
        return
    df = pd.read_csv(table)
    fits = pd.read_csv(fits_table)
    if df.empty or fits.empty:
        return
    gap = 2.0
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.2))
    colors = {
        "perron_visible": "#3b6ea8",
        "weak_perron_visible": "#8a5a2b",
        "perron_orthogonal": "#8d4766",
    }
    for loading, sub in df[(df["gap_multiple"] == gap) & (df["adversary"] == "perron_aligned")].groupby("loading"):
        axes[0].loglog(
            sub["one_minus_rho"],
            sub["premium"],
            marker="o",
            label=loading,
            color=colors.get(loading),
        )
    axes[0].invert_xaxis()
    axes[0].set_xlabel("1 - rho")
    axes[0].set_ylabel("directional premium")
    axes[0].set_title("Perron visibility ablation")
    axes[0].legend(frameon=False, fontsize=7)

    second = fits[(fits["adversary"] == "second_mode") & (fits["loading"] == "perron_orthogonal")].copy()
    perron = fits[(fits["adversary"] == "perron_aligned") & (fits["loading"] == "perron_visible")].copy()
    axes[1].plot(second["gap_multiple"], -second["slope"], marker="s", label="second-mode loading")
    axes[1].plot(perron["gap_multiple"], -perron["slope"], marker="o", label="Perron-visible")
    axes[1].axhline(2.0, color="black", linewidth=0.8, linestyle="--")
    axes[1].set_xlabel("second-mode gap multiple")
    axes[1].set_ylabel("estimated critical exponent")
    axes[1].set_title("Mode choice and lower-bound caveat")
    axes[1].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "spectral_gap_ablation.png", dpi=220)
    plt.close(fig)


def save_hawkes_variance_plot(results_root: Path) -> None:
    df = pd.read_csv(results_root / "raw" / "hawkes_variance.csv")
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.loglog(df["one_minus_rho"], df["fano_factor"], marker="o")
    ax.invert_xaxis()
    ax.set_xlabel("1 - rho")
    ax.set_ylabel("Fano factor")
    ax.set_title("Hawkes count variance near criticality")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "hawkes_variance.png", dpi=220)
    plt.close(fig)


def save_policy_plot(results_root: Path) -> None:
    df = pd.read_csv(results_root / "tables" / "policy_stress_metrics.csv")
    pivot = df.pivot_table(
        index="rho_hat",
        columns="policy",
        values="certainty_equivalent",
        aggfunc="mean",
    )
    fig, ax = plt.subplots(figsize=(7, 4.8))
    pivot.plot(ax=ax, marker="o")
    ax.set_xlabel("estimated rho")
    ax.set_ylabel("certainty equivalent")
    ax.set_title("Policy performance under adversarial rho stress")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "policy_stress.png", dpi=220)
    plt.close(fig)


def save_policy_dt_convergence_plot(results_root: Path) -> None:
    table = results_root / "tables" / "policy_dt_convergence_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    plot_policies = ["robust_gamma", "robust_gamma_abs", "known_true_gamma_no_ambiguity"]
    colors = {
        "robust_gamma": "#3b6ea8",
        "robust_gamma_abs": "#8a5a2b",
        "known_true_gamma_no_ambiguity": "#8d4766",
    }
    rhos = sorted(df["rho_hat"].unique())
    fig, axes = plt.subplots(1, len(rhos), figsize=(4.9 * len(rhos), 4.0), squeeze=False)
    for ax, rho in zip(axes[0], rhos, strict=True):
        sub_rho = df[df["rho_hat"] == rho]
        for policy in plot_policies:
            sub = sub_rho[sub_rho["policy"] == policy].sort_values("dt")
            if sub.empty:
                continue
            ax.plot(
                sub["dt"],
                sub["mean_wealth_diff_vs_nominal"],
                marker="o",
                label=policy,
                color=colors[policy],
            )
        ax.axhline(0.0, color="black", linewidth=0.8)
        ax.set_xscale("log")
        ax.invert_xaxis()
        ax.set_xlabel("Hawkes time step")
        ax.set_title(f"rho_hat={rho:g}")
        ax.set_ylabel("mean wealth diff vs nominal")
    axes[0, 0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "policy_dt_convergence.png", dpi=220)
    plt.close(fig)


def save_policy_ogata_audit_plot(results_root: Path) -> None:
    table = results_root / "tables" / "policy_ogata_audit_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    plot_policies = ["robust_gamma", "robust_gamma_abs", "known_true_gamma_no_ambiguity"]
    sub = df[df["policy"].isin(plot_policies)].copy()
    if sub.empty:
        return
    sub["label"] = sub["arrival_simulator"] + "\nrho=" + sub["rho_hat"].map(lambda x: f"{x:g}")
    labels = list(dict.fromkeys(sub["label"]))
    x = np.arange(len(labels))
    width = 0.24
    colors = {
        "robust_gamma": "#3b6ea8",
        "robust_gamma_abs": "#8a5a2b",
        "known_true_gamma_no_ambiguity": "#8d4766",
    }
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    for idx, policy in enumerate(plot_policies):
        vals = []
        for label in labels:
            row = sub[(sub["label"] == label) & (sub["policy"] == policy)]
            vals.append(float(row["mean_wealth_diff_vs_nominal"].iloc[0]) if len(row) else np.nan)
        ax.bar(x + (idx - 1) * width, vals, width=width, label=policy, color=colors[policy])
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("mean wealth diff vs nominal")
    ax.set_title("Discrete vs Ogata-binned policy audit")
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "policy_ogata_audit.png", dpi=220)
    plt.close(fig)


def save_event_queue_backtest_plot(results_root: Path) -> None:
    table = results_root / "tables" / "event_queue_backtest_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    plot_policies = ["robust_gamma", "robust_gamma_abs", "liquidity_guard"]
    sub = df[df["policy"].isin(plot_policies)].copy()
    if sub.empty:
        return
    rhos = sorted(sub["rho_hat"].unique())
    x = np.arange(len(rhos))
    width = 0.24
    colors = {
        "robust_gamma": "#3b6ea8",
        "robust_gamma_abs": "#8a5a2b",
        "liquidity_guard": "#3c7d63",
    }
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    for idx, policy in enumerate(plot_policies):
        vals = []
        nq = []
        for rho in rhos:
            row = sub[(sub["rho_hat"] == rho) & (sub["policy"] == policy)]
            vals.append(float(row["mean_wealth_diff_vs_nominal"].iloc[0]) if len(row) else np.nan)
            nq.append(float(row["no_quote_side_time_frac"].iloc[0]) if len(row) else np.nan)
        axes[0].bar(x + (idx - 1) * width, vals, width=width, label=policy, color=colors[policy])
        axes[1].plot(rhos, nq, marker="o", label=policy, color=colors[policy])
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([f"{rho:g}" for rho in rhos])
    axes[0].set_xlabel("estimated rho")
    axes[0].set_ylabel("mean wealth diff vs nominal")
    axes[0].set_title("Event-queue policy performance")
    axes[1].set_xlabel("estimated rho")
    axes[1].set_ylabel("side-time no-quote fraction")
    axes[1].set_title("Event-queue quote withdrawal")
    axes[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "event_queue_backtest.png", dpi=220)
    plt.close(fig)


def save_lobster_top_of_book_replay_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_top_of_book_replay_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    plot_policies = ["robust_gamma", "robust_gamma_abs", "liquidity_guard"]
    sub = df[df["policy"].isin(plot_policies)].copy()
    if sub.empty:
        return
    scenarios = list(sub["scenario"].drop_duplicates())
    colors = {
        "robust_gamma": "#3b6ea8",
        "robust_gamma_abs": "#8a5a2b",
        "liquidity_guard": "#3c7d63",
    }
    x = np.arange(len(scenarios))
    width = 0.24
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.2))
    for idx, policy in enumerate(plot_policies):
        wealth = []
        no_quote = []
        for scenario in scenarios:
            row = sub[(sub["scenario"] == scenario) & (sub["policy"] == policy)]
            wealth.append(float(row["mean_wealth_diff_vs_nominal"].iloc[0]) if len(row) else np.nan)
            no_quote.append(float(row["mean_no_quote_side_time_frac"].iloc[0]) if len(row) else np.nan)
        axes[0].bar(x + (idx - 1) * width, wealth, width=width, label=policy, color=colors[policy])
        axes[1].bar(x + (idx - 1) * width, no_quote, width=width, label=policy, color=colors[policy])
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    labels = [s.replace("_", "\n") for s in scenarios]
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
    axes[0].set_ylabel("mean wealth diff vs nominal")
    axes[0].set_title("Public LOBSTER replay wealth")
    axes[1].set_ylabel("mean side-time no-quote fraction")
    axes[1].set_title("Public LOBSTER replay quote withdrawal")
    axes[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_top_of_book_replay.png", dpi=220)
    plt.close(fig)


def save_lobster_l1_quote_replay_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_l1_quote_replay_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    plot_policies = ["nominal_hawkes", "robust_gamma", "robust_gamma_abs", "liquidity_guard"]
    sub = df[df["policy"].isin(plot_policies)].copy()
    if sub.empty:
        return
    scenario = "calibrated_side_gamma" if "calibrated_side_gamma" in set(sub["scenario"]) else sub["scenario"].iloc[0]
    cal = sub[sub["scenario"] == scenario].set_index("policy").reindex(plot_policies)
    stress = sub[sub["scenario"] == "near_critical_stress"].set_index("policy").reindex(plot_policies)
    x = np.arange(len(plot_policies))
    labels = [p.replace("_", "\n") for p in plot_policies]
    colors = {
        "join": "#3b6ea8",
        "improve": "#3c7d63",
        "away": "#8a5a2b",
        "withdraw": "#8d4766",
    }
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2), gridspec_kw={"width_ratios": [1.0, 1.15, 1.0]})
    axes[0].bar(x, cal["mean_wealth_diff_vs_nominal"], color="#3b6ea8")
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, fontsize=7)
    axes[0].set_ylabel("wealth diff vs nominal")
    axes[0].set_title("Calibrated L1 replay")

    bottom = np.zeros(len(cal))
    for state, col in [
        ("join", "mean_join_side_time_frac"),
        ("improve", "mean_improve_side_time_frac"),
        ("away", "mean_away_side_time_frac"),
        ("withdraw", "mean_no_quote_side_time_frac"),
    ]:
        vals = cal[col].to_numpy(dtype=float)
        axes[1].bar(x, vals, bottom=bottom, label=state, color=colors[state])
        bottom += vals
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=7)
    axes[1].set_ylabel("side-time fraction")
    axes[1].set_ylim(0.0, 1.02)
    axes[1].set_title("Join / improve / away / withdraw")
    axes[1].legend(frameon=False, fontsize=7)

    if not stress.empty:
        axes[2].bar(x, stress["mean_wealth_diff_vs_nominal"], color="#8a5a2b")
        axes[2].axhline(0.0, color="black", linewidth=0.8)
        axes[2].set_xticks(x)
        axes[2].set_xticklabels(labels, fontsize=7)
        axes[2].set_ylabel("wealth diff vs nominal")
        axes[2].set_title("Near-critical L1 stress")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_l1_quote_replay.png", dpi=220)
    plt.close(fig)


def save_lobster_depth_quote_replay_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_depth_quote_replay_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    plot_policies = ["nominal_hawkes", "robust_gamma", "robust_gamma_abs", "liquidity_guard"]
    sub = df[df["policy"].isin(plot_policies)].copy()
    if sub.empty:
        return
    scenario = "calibrated_side_gamma" if "calibrated_side_gamma" in set(sub["scenario"]) else sub["scenario"].iloc[0]
    cal = sub[sub["scenario"] == scenario].set_index("policy").reindex(plot_policies)
    stress = sub[sub["scenario"] == "near_critical_stress"].set_index("policy").reindex(plot_policies)
    x = np.arange(len(plot_policies))
    labels = [p.replace("_", "\n") for p in plot_policies]
    colors = {
        "join L1": "#3b6ea8",
        "improve": "#3c7d63",
        "visible depth": "#8a5a2b",
        "outside depth": "#6b6f76",
        "withdraw": "#8d4766",
    }
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2), gridspec_kw={"width_ratios": [1.0, 1.25, 1.0]})
    axes[0].bar(x, cal["mean_wealth_diff_vs_nominal"], color="#3b6ea8")
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, fontsize=7)
    axes[0].set_ylabel("wealth diff vs nominal")
    axes[0].set_title("Calibrated depth replay")

    bottom = np.zeros(len(cal))
    for label, col in [
        ("join L1", "mean_join_l1_side_time_frac"),
        ("improve", "mean_improve_side_time_frac"),
        ("visible depth", "mean_depth_visible_side_time_frac"),
        ("outside depth", "mean_outside_depth_side_time_frac"),
        ("withdraw", "mean_no_quote_side_time_frac"),
    ]:
        vals = cal[col].to_numpy(dtype=float)
        axes[1].bar(x, vals, bottom=bottom, label=label, color=colors[label])
        bottom += vals
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=7)
    axes[1].set_ylabel("side-time fraction")
    axes[1].set_ylim(0.0, 1.02)
    axes[1].set_title("Displayed-depth quote states")
    axes[1].legend(frameon=False, fontsize=7)

    if not stress.empty:
        axes[2].bar(x, stress["mean_wealth_diff_vs_nominal"], color="#8a5a2b")
        axes[2].axhline(0.0, color="black", linewidth=0.8)
        axes[2].set_xticks(x)
        axes[2].set_xticklabels(labels, fontsize=7)
        axes[2].set_ylabel("wealth diff vs nominal")
        axes[2].set_title("Near-critical depth stress")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_depth_quote_replay.png", dpi=220)
    plt.close(fig)


def save_lobster_priority_depth_quote_replay_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_priority_depth_quote_replay_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    plot_policies = ["nominal_hawkes", "robust_gamma", "robust_gamma_abs", "liquidity_guard"]
    sub = df[df["policy"].isin(plot_policies)].copy()
    if sub.empty:
        return
    scenario = "calibrated_side_gamma" if "calibrated_side_gamma" in set(sub["scenario"]) else sub["scenario"].iloc[0]
    cal = sub[sub["scenario"] == scenario].set_index("policy").reindex(plot_policies)
    stress = sub[sub["scenario"] == "near_critical_stress"].set_index("policy").reindex(plot_policies)
    x = np.arange(len(plot_policies))
    labels = [p.replace("_", "\n") for p in plot_policies]
    colors = {
        "join L1": "#3b6ea8",
        "improve": "#3c7d63",
        "visible depth": "#8a5a2b",
        "outside depth": "#6b6f76",
        "withdraw": "#8d4766",
    }
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.2), gridspec_kw={"width_ratios": [1.0, 1.25, 1.0]})
    axes[0].bar(x, cal["mean_wealth_diff_vs_nominal"], color="#3b6ea8")
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, fontsize=7)
    axes[0].set_ylabel("wealth diff vs nominal")
    axes[0].set_title("Priority depth replay")

    bottom = np.zeros(len(cal))
    for label, col in [
        ("join L1", "mean_join_l1_side_time_frac"),
        ("improve", "mean_improve_side_time_frac"),
        ("visible depth", "mean_depth_visible_side_time_frac"),
        ("outside depth", "mean_outside_depth_side_time_frac"),
        ("withdraw", "mean_no_quote_side_time_frac"),
    ]:
        vals = cal[col].to_numpy(dtype=float)
        axes[1].bar(x, vals, bottom=bottom, label=label, color=colors[label])
        bottom += vals
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=7)
    axes[1].set_ylabel("side-time fraction")
    axes[1].set_ylim(0.0, 1.02)
    axes[1].set_title("Message-priority quote states")
    axes[1].legend(frameon=False, fontsize=7)

    if not stress.empty:
        axes[2].bar(x, stress["mean_wealth_diff_vs_nominal"], color="#8a5a2b")
        axes[2].axhline(0.0, color="black", linewidth=0.8)
        axes[2].set_xticks(x)
        axes[2].set_xticklabels(labels, fontsize=7)
        axes[2].set_ylabel("wealth diff vs nominal")
        axes[2].set_title("Near-critical priority stress")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_priority_depth_quote_replay.png", dpi=220)
    plt.close(fig)


def save_lobster_priority_depth_sensitivity_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_priority_depth_sensitivity_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    scenario = "calibrated_side_gamma" if "calibrated_side_gamma" in set(df["scenario"]) else df["scenario"].iloc[0]
    sub = df[(df["scenario"] == scenario) & (df["policy"] == "nominal_hawkes")].copy()
    if sub.empty:
        return
    fractions = sorted(sub["priority_initial_queue_fraction"].unique())
    stress_column = "priority_queue_stress_multiplier"
    multipliers = sorted(sub[stress_column].unique())
    fill_grid = sub.pivot_table(
        index=stress_column,
        columns="priority_initial_queue_fraction",
        values="mean_total_fill_lots",
        aggfunc="mean",
    ).reindex(index=multipliers, columns=fractions)
    wealth_grid = sub.pivot_table(
        index=stress_column,
        columns="priority_initial_queue_fraction",
        values="mean_terminal_wealth",
        aggfunc="mean",
    ).reindex(index=multipliers, columns=fractions)
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.1))
    for ax, grid, title, label in [
        (axes[0], fill_grid, "Filled-lot sensitivity", "mean filled lots"),
        (axes[1], wealth_grid, "Wealth sensitivity", "mean terminal wealth"),
    ]:
        image = ax.imshow(grid.to_numpy(dtype=float), aspect="auto", origin="lower", cmap="viridis")
        ax.set_xticks(range(len(fractions)))
        ax.set_xticklabels([f"{v:g}" for v in fractions])
        ax.set_yticks(range(len(multipliers)))
        ax.set_yticklabels([f"{v:g}" for v in multipliers])
        ax.set_xlabel("initial same-price queue fraction")
        ax.set_ylabel("displayed queue-stress multiplier")
        ax.set_title(title)
        fig.colorbar(image, ax=ax, label=label)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_priority_depth_sensitivity.png", dpi=220)
    plt.close(fig)


def save_lobster_orderbook_reconstruction_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_orderbook_reconstruction_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    sub = df[df["ticker"] != "PANEL"].copy()
    if sub.empty:
        return
    x = np.arange(len(sub))
    labels = sub["ticker"].tolist()
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2))
    axes[0].bar(x - 0.18, sub["bid_top1_price_match_rate"], width=0.36, label="bid", color="#3b6ea8")
    axes[0].bar(x + 0.18, sub["ask_top1_price_match_rate"], width=0.36, label="ask", color="#8a5a2b")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylim(0.0, 1.02)
    axes[0].set_ylabel("top-1 price match rate")
    axes[0].set_title("Observable reconstruction price match")
    axes[0].legend(frameon=False, fontsize=8)

    axes[1].bar(x - 0.18, sub["bid_top1_size_mae"], width=0.36, label="bid", color="#3b6ea8")
    axes[1].bar(x + 0.18, sub["ask_top1_size_mae"], width=0.36, label="ask", color="#8a5a2b")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel("top-1 size MAE")
    axes[1].set_title("Observable reconstruction size drift")
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_orderbook_reconstruction.png", dpi=220)
    plt.close(fig)


def save_finite_n_plot(results_root: Path) -> None:
    df = pd.read_csv(results_root / "raw" / "finite_n_error_proxy.csv")
    pivot = df.pivot_table(index="rho", columns="n", values="mean_error")
    fig, ax = plt.subplots(figsize=(7, 4.8))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", origin="lower")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{v:.3f}" for v in pivot.index])
    ax.set_xlabel("N")
    ax.set_ylabel("rho")
    ax.set_title("Finite-N mean-field error proxy")
    fig.colorbar(image, ax=ax, label="mean absolute error")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "finite_n_heatmap.png", dpi=220)
    plt.close(fig)


def save_quote_sensitivity_diagnostic_plot(results_root: Path) -> None:
    table = results_root / "raw" / "quote_sensitivity_diagnostic.csv"
    summary_table = results_root / "tables" / "quote_sensitivity_diagnostic_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    summary = pd.read_csv(summary_table) if summary_table.exists() else pd.DataFrame()
    if df.empty:
        return
    epsilon = df["epsilon"].max()
    sub = df[(df["epsilon"] == epsilon) & (df["smooth_region"])].copy()
    if sub.empty:
        return
    colors = {
        "nominal_hawkes": "#3b6ea8",
        "robust_gamma": "#8a5a2b",
        "robust_gamma_abs": "#8d4766",
    }
    fig, ax = plt.subplots(figsize=(7, 4.8))
    for policy, policy_df in sub.groupby("policy"):
        policy_df = policy_df.sort_values("one_minus_rho")
        label = policy
        if not summary.empty:
            fit = summary[(summary["policy"] == policy) & (summary["epsilon"] == epsilon)]
            if not fit.empty:
                label = f"{policy} (slope {fit['estimated_critical_exponent'].iloc[0]:.2f})"
        ax.loglog(
            policy_df["one_minus_rho"],
            policy_df["analytic_uncapped_d_half_drho"],
            marker="o",
            label=label,
            color=colors.get(policy),
        )
    capped = df[(df["epsilon"] == epsilon) & (~df["smooth_region"])]
    if not capped.empty:
        ax.scatter(
            capped["one_minus_rho"],
            np.maximum(capped["analytic_uncapped_d_half_drho"], 1e-12),
            marker="x",
            color="black",
            s=45,
            label="capped/nonsmooth",
        )
    ax.invert_xaxis()
    ax.set_xlabel("1 - rho")
    ax.set_ylabel("d half-spread / d rho")
    ax.set_title("Interior quote-map sensitivity")
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "quote_sensitivity_diagnostic.png", dpi=220)
    plt.close(fig)


def save_robust_dp_plot(results_root: Path) -> None:
    table = results_root / "tables" / "robust_dp_quotes.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    quote_col = "quoted_half_spread" if "quoted_half_spread" in df.columns else "half_spread"
    fig, ax = plt.subplots(figsize=(7, 4.8))
    for (ambiguity, epsilon), sub in df.groupby(["ambiguity", "epsilon"]):
        label = f"{ambiguity}, eps={epsilon:g}"
        sub = sub.sort_values("rho_hat")
        ax.plot(sub["rho_hat"], sub[quote_col], marker="o", label=label)
        if "is_no_quote" in sub.columns and sub["is_no_quote"].any():
            no_quote = sub[sub["is_no_quote"]]
            ax.scatter(
                no_quote["rho_hat"],
                np.full(len(no_quote), df[quote_col].max(skipna=True)),
                marker="x",
                s=55,
                color="black",
                linewidths=1.2,
            )
    ax.set_xlabel("estimated rho")
    ax.set_ylabel("q=0 quoted half-spread")
    ax.set_title("Finite-scenario robust DP quote/no-quote policy")
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "robust_dp_quotes.png", dpi=220)
    plt.close(fig)


def save_lobster_panel_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_panel_sanity_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.8))
    axes[0].bar(df["ticker"], df["event_count_fano"], color="#3b6ea8")
    axes[0].set_ylabel("event-count Fano factor")
    axes[0].set_title("LOBSTER event clustering")
    axes[1].bar(df["ticker"], df["mean_spread"], color="#8a5a2b")
    axes[1].set_ylabel("mean spread")
    axes[1].set_title("L1 spread by name")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_panel_sanity.png", dpi=220)
    plt.close(fig)


def save_crypto_panel_plot(results_root: Path) -> None:
    table = results_root / "tables" / "crypto_l2_sanity_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.8))
    axes[0].bar(df["symbol"], df["relative_spread_bps"], color="#3c7d63")
    axes[0].set_ylabel("relative spread (bps)")
    axes[0].set_title("Crypto L2 spreads")
    axes[1].bar(df["symbol"], df["total_depth_fano"], color="#8d4766")
    axes[1].set_ylabel("depth Fano factor")
    axes[1].set_title("Depth overdispersion")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "crypto_l2_sanity.png", dpi=220)
    plt.close(fig)


def save_binance_aggtrade_hawkes_plot(results_root: Path) -> None:
    sanity_table = results_root / "tables" / "binance_aggtrades_sanity_summary.csv"
    hawkes_table = results_root / "tables" / "binance_aggtrades_hawkes_best.csv"
    if not sanity_table.exists() or not hawkes_table.exists():
        return
    sanity = pd.read_csv(sanity_table)
    hawkes = pd.read_csv(hawkes_table)
    if sanity.empty or hawkes.empty:
        return
    all_hawkes = hawkes[hawkes["event_group"] == "all"].set_index("symbol").reindex(sanity["symbol"])
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 3.8))
    axes[0].bar(sanity["symbol"], sanity["event_count_fano"], color="#3b6ea8")
    axes[0].set_ylabel("1s count Fano")
    axes[0].set_title("Binance trade clustering")
    axes[1].bar(sanity["symbol"], sanity["event_count_acf1"], color="#3c7d63")
    axes[1].set_ylabel("1s count lag-1 corr")
    axes[1].set_title("Count persistence")
    axes[2].bar(all_hawkes.index, all_hawkes["rho"], color="#8a5a2b")
    axes[2].set_ylim(0.0, 1.0)
    axes[2].set_ylabel("best fixed-beta rho")
    axes[2].set_title("AggTrade Hawkes fit")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "binance_aggtrades_hawkes.png", dpi=220)
    plt.close(fig)


def save_binance_aggtrade_cross_date_plot(results_root: Path) -> None:
    sanity_table = results_root / "tables" / "binance_aggtrades_cross_date_sanity_summary.csv"
    hawkes_table = results_root / "tables" / "binance_aggtrades_hawkes_cross_date_best.csv"
    if not sanity_table.exists() or not hawkes_table.exists():
        return
    sanity = pd.read_csv(sanity_table)
    hawkes = pd.read_csv(hawkes_table)
    if sanity.empty or hawkes.empty:
        return
    all_hawkes = hawkes[hawkes["event_group"] == "all"].copy()
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.9))
    for symbol, sub in sanity.groupby("symbol"):
        sub = sub.sort_values("date")
        axes[0].plot(sub["date"], sub["event_count_fano"], marker="o", label=symbol)
        axes[1].plot(sub["date"], sub["event_count_acf1"], marker="o", label=symbol)
    for symbol, sub in all_hawkes.groupby("symbol"):
        sub = sub.sort_values("date")
        axes[2].plot(sub["date"], sub["rho"], marker="o", label=symbol)
    axes[0].set_ylabel("1s count Fano")
    axes[0].set_title("Cross-date trade clustering")
    axes[1].set_ylabel("1s count lag-1 corr")
    axes[1].set_title("Cross-date persistence")
    axes[2].set_ylabel("best fixed-beta rho")
    axes[2].set_ylim(0.0, 1.0)
    axes[2].set_title("Cross-date Hawkes rho")
    for ax in axes:
        ax.tick_params(axis="x", rotation=30, labelsize=7)
    axes[2].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "binance_aggtrades_cross_date_hawkes.png", dpi=220)
    plt.close(fig)


def save_calibration_noise_plot(results_root: Path) -> None:
    table = results_root / "tables" / "calibration_noise.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    fig, ax = plt.subplots(figsize=(7, 4.8))
    for rho, sub in df.groupby("rho_true"):
        ax.errorbar(
            sub["horizon"],
            sub["rho_hat_mean"],
            yerr=sub["rho_hat_std"],
            marker="o",
            capsize=3,
            label=f"rho={rho:g}",
        )
    ax.plot(df["horizon"], df["horizon"] * 0 + df["rho_true"].mean(), alpha=0)
    ax.set_xscale("log")
    ax.set_xlabel("sample horizon")
    ax.set_ylabel("Fano-based rho estimate")
    ax.set_title("Calibration noise near criticality")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "calibration_noise.png", dpi=220)
    plt.close(fig)


def save_simulator_validation_plot(results_root: Path) -> None:
    table = results_root / "tables" / "simulator_validation.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    pivot = df.pivot(index="rho", columns="method", values="mean_count")
    fig, ax = plt.subplots(figsize=(6, 4.2))
    pivot.plot(ax=ax, marker="o")
    ax.set_xlabel("rho")
    ax.set_ylabel("mean count")
    ax.set_title("Discrete vs Ogata simulator validation")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "simulator_validation.png", dpi=220)
    plt.close(fig)


def save_discretization_bias_plot(results_root: Path) -> None:
    table = results_root / "tables" / "discretization_bias.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    fig, ax = plt.subplots(figsize=(7, 4.8))
    for rho, sub in df.groupby("rho"):
        sub = sub.sort_values("dt")
        ax.plot(sub["dt"], sub["relative_bias"], marker="o", label=f"rho={rho:g}")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("discrete time step")
    ax.set_ylabel("relative mean-count bias")
    ax.set_title("Discretization bias near criticality")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "discretization_bias.png", dpi=220)
    plt.close(fig)


def save_lobster_hawkes_event_type_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_hawkes_fit_by_event_type.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    order = ["all", "limit", "cancel_delete", "execution"]
    colors = {
        "all": "#3b6ea8",
        "limit": "#3c7d63",
        "cancel_delete": "#8a5a2b",
        "execution": "#8d4766",
    }
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.1))
    for event_group in order:
        sub = df[df["event_group"] == event_group]
        if sub.empty:
            continue
        axes[0].scatter(
            sub["event_rate_fit"],
            sub["rho"],
            label=event_group,
            color=colors[event_group],
            s=np.where(sub["hit_beta_upper"], 72, 42),
            alpha=0.82,
            edgecolor="black",
            linewidth=0.4,
        )
        axes[1].scatter(
            sub["rho"],
            sub["beta"],
            label=event_group,
            color=colors[event_group],
            s=np.where(sub["hit_beta_upper"], 72, 42),
            alpha=0.82,
            edgecolor="black",
            linewidth=0.4,
        )
    axes[0].set_xscale("log")
    axes[0].set_xlabel("fitted event rate")
    axes[0].set_ylabel("branching ratio rho")
    axes[0].set_title("Event-type Hawkes branching")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("branching ratio rho")
    axes[1].set_ylabel("decay beta")
    axes[1].set_title("Single-scale decay diagnostics")
    axes[1].axhline(np.exp(5.0), color="black", linewidth=0.8, linestyle="--")
    axes[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_hawkes_event_type_rho_beta.png", dpi=220)
    plt.close(fig)


def save_lobster_fixed_beta_profile_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_hawkes_fixed_beta_sensitivity.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    df["delta_neg_loglik"] = df.groupby(["ticker", "event_group"])["neg_loglik"].transform(lambda x: x - x.min())
    profile = (
        df.groupby(["event_group", "beta_fixed"], as_index=False)
        .agg(median_delta_nll=("delta_neg_loglik", "median"), median_rho=("rho", "median"))
        .sort_values("beta_fixed")
    )
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.1))
    for event_group, sub in profile.groupby("event_group"):
        axes[0].plot(sub["beta_fixed"], sub["median_delta_nll"], marker="o", label=event_group)
        axes[1].plot(sub["beta_fixed"], sub["median_rho"], marker="o", label=event_group)
    axes[0].set_xscale("log")
    axes[0].set_xlabel("fixed beta")
    axes[0].set_ylabel("median delta NLL")
    axes[0].set_title("Fixed-beta likelihood profile")
    axes[1].set_xscale("log")
    axes[1].set_xlabel("fixed beta")
    axes[1].set_ylabel("median fitted rho")
    axes[1].set_title("Branching sensitivity")
    axes[0].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_beta_profile_likelihood.png", dpi=220)
    plt.close(fig)


def save_lobster_timestamp_sensitivity_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_timestamp_resolution_sensitivity.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    summary = (
        df.groupby("resolution_seconds", as_index=False)
        .agg(median_rho=("rho", "median"), median_beta=("beta", "median"), median_retained=("retained_share", "median"))
        .sort_values("resolution_seconds")
    )
    labels = ["raw" if v == 0 else f"{v:g}s" for v in summary["resolution_seconds"]]
    x = np.arange(len(summary))
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.8))
    axes[0].plot(x, summary["median_rho"], marker="o", color="#3b6ea8")
    axes[0].set_ylabel("median rho")
    axes[0].set_title("Timestamp rho sensitivity")
    axes[1].plot(x, summary["median_beta"], marker="o", color="#8a5a2b")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("median beta")
    axes[1].set_title("Timestamp beta sensitivity")
    axes[2].plot(x, summary["median_retained"], marker="o", color="#3c7d63")
    axes[2].set_ylabel("retained event share")
    axes[2].set_title("Burst aggregation")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, ha="right")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_timestamp_resolution_sensitivity.png", dpi=220)
    plt.close(fig)


def save_lobster_multiscale_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_hawkes_multiscale_best.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    order = ["all", "limit", "cancel_delete", "execution"]
    df["event_group"] = pd.Categorical(df["event_group"], categories=order, ordered=True)
    df = df.sort_values(["event_group", "ticker"])
    summary = (
        df.groupby("event_group", observed=False, as_index=False)
        .agg(
            rho_slow=("rho_slow", "median"),
            rho_fast=("rho_fast", "median"),
            fast_share=("fast_share", "median"),
            residual_ks=("residual_ks_stat", "median"),
        )
        .dropna(subset=["event_group"])
    )
    x = np.arange(len(summary))
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.1))
    axes[0].bar(x, summary["rho_slow"], label="slow", color="#3b6ea8")
    axes[0].bar(x, summary["rho_fast"], bottom=summary["rho_slow"], label="fast", color="#8a5a2b")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(summary["event_group"].astype(str), rotation=25, ha="right")
    axes[0].set_ylabel("median branching contribution")
    axes[0].set_title("Two-scale Hawkes branching allocation")
    axes[0].legend(frameon=False, fontsize=7)
    axes[1].plot(x, summary["fast_share"], marker="o", color="#3c7d63", label="fast share")
    axes[1].plot(x, summary["residual_ks"], marker="s", color="#8d4766", label="KS stat")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(summary["event_group"].astype(str), rotation=25, ha="right")
    axes[1].set_ylim(0, max(1.0, float(summary[["fast_share", "residual_ks"]].max().max()) * 1.1))
    axes[1].set_title("Fast-scale weight and residual lack-of-fit")
    axes[1].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_hawkes_multiscale.png", dpi=220)
    plt.close(fig)


def save_lobster_marked_multivariate_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_marked_hawkes_multivariate_best.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    groups = ["limit", "cancel_delete", "execution"]
    gamma_cols = [[f"gamma_{target}_from_{source}" for source in groups] for target in groups]
    gamma = np.array([[df[col].median() for col in row] for row in gamma_cols], dtype=float)
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.1))
    im = axes[0].imshow(gamma, cmap="viridis", vmin=0.0)
    axes[0].set_xticks(np.arange(len(groups)))
    axes[0].set_yticks(np.arange(len(groups)))
    axes[0].set_xticklabels(groups, rotation=30, ha="right")
    axes[0].set_yticklabels(groups)
    axes[0].set_xlabel("source event group")
    axes[0].set_ylabel("target intensity")
    axes[0].set_title("Median marked Hawkes branching matrix")
    for i in range(len(groups)):
        for j in range(len(groups)):
            axes[0].text(j, i, f"{gamma[i, j]:.2f}", ha="center", va="center", color="white", fontsize=7)
    fig.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04)

    x = np.arange(len(df))
    axes[1].bar(x, df["spectral_radius"], color="#3b6ea8", label="spectral radius")
    axes[1].plot(x, df["mark_log_loss_improvement"], marker="o", color="#8a5a2b", label="mark log-loss gain")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(df["ticker"], rotation=25, ha="right")
    axes[1].set_ylim(0, max(1.0, float(df[["spectral_radius", "mark_log_loss_improvement"]].max().max()) * 1.1))
    axes[1].set_title("Stability and mark prediction")
    axes[1].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_marked_hawkes_multivariate.png", dpi=220)
    plt.close(fig)


def save_lobster_side_marked_multivariate_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_side_marked_hawkes_multivariate_best.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    groups = [
        "limit_buy",
        "cancel_delete_buy",
        "execution_buy",
        "limit_sell",
        "cancel_delete_sell",
        "execution_sell",
    ]
    labels = ["L buy", "C/D buy", "E buy", "L sell", "C/D sell", "E sell"]
    gamma_cols = [[f"gamma_{target}_from_{source}" for source in groups] for target in groups]
    gamma = np.array([[df[col].median() for col in row] for row in gamma_cols], dtype=float)
    side_gamma = np.array(
        [
            [df["gamma_side_buy_from_buy"].median(), df["gamma_side_buy_from_sell"].median()],
            [df["gamma_side_sell_from_buy"].median(), df["gamma_side_sell_from_sell"].median()],
        ],
        dtype=float,
    )
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 4.1), gridspec_kw={"width_ratios": [1.35, 0.8, 1.0]})
    im = axes[0].imshow(gamma, cmap="magma", vmin=0.0)
    axes[0].set_xticks(np.arange(len(groups)))
    axes[0].set_yticks(np.arange(len(groups)))
    axes[0].set_xticklabels(labels, rotation=35, ha="right")
    axes[0].set_yticklabels(labels)
    axes[0].set_xlabel("source mark")
    axes[0].set_ylabel("target intensity")
    axes[0].set_title("Median six-mark Gamma")
    fig.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04)

    im2 = axes[1].imshow(side_gamma, cmap="viridis", vmin=0.0)
    axes[1].set_xticks([0, 1])
    axes[1].set_yticks([0, 1])
    axes[1].set_xticklabels(["buy", "sell"])
    axes[1].set_yticklabels(["buy", "sell"])
    axes[1].set_xlabel("source side")
    axes[1].set_ylabel("target side")
    axes[1].set_title("Side aggregate")
    for i in range(2):
        for j in range(2):
            axes[1].text(j, i, f"{side_gamma[i, j]:.2f}", ha="center", va="center", color="white", fontsize=8)
    fig.colorbar(im2, ax=axes[1], fraction=0.046, pad=0.04)

    x = np.arange(len(df))
    axes[2].bar(x, df["spectral_radius"], color="#3b6ea8", label="spectral radius")
    axes[2].plot(x, df["mark_log_loss_improvement"], marker="o", color="#8a5a2b", label="mark log-loss gain")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(df["ticker"], rotation=25, ha="right")
    axes[2].set_ylim(0, max(1.0, float(df[["spectral_radius", "mark_log_loss_improvement"]].max().max()) * 1.1))
    axes[2].set_title("Stability and mark prediction")
    axes[2].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_side_marked_hawkes_multivariate.png", dpi=220)
    plt.close(fig)


def save_lobster_side_marked_state_residuals_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_side_marked_state_residuals_summary.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    df = df.copy().sort_values(["state_variable", "state_bucket"]).reset_index(drop=True)
    df["label"] = df["state_variable"] + "\n" + df["state_bucket"]
    x = np.arange(len(df))
    colors = {
        "event_group": "#3b6ea8",
        "side": "#8a5a2b",
        "size_bucket": "#3c7d63",
        "spread_bucket": "#8d4766",
        "imbalance_bucket": "#6d6a2e",
        "depth_bucket": "#5a5a5a",
    }
    bar_colors = [colors.get(v, "#666666") for v in df["state_variable"]]
    fig, axes = plt.subplots(2, 1, figsize=(10.8, 6.8), sharex=True)
    axes[0].bar(x, df["median_residual_ks_stat"], color=bar_colors)
    axes[0].set_ylabel("median KS statistic")
    axes[0].set_title("State-conditioned side-aware Hawkes residuals")
    axes[1].bar(x, df["median_mark_log_loss_improvement"], color=bar_colors)
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_ylabel("median mark log-loss gain")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(df["label"], rotation=45, ha="right", fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_side_marked_state_residuals.png", dpi=220)
    plt.close(fig)


def save_lobster_size_side_marked_multivariate_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_size_side_marked_hawkes_multivariate_best.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    size_gamma = np.array(
        [
            [df["gamma_size_small_from_small"].median(), df["gamma_size_small_from_large"].median()],
            [df["gamma_size_large_from_small"].median(), df["gamma_size_large_from_large"].median()],
        ],
        dtype=float,
    )
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.0))
    im = axes[0].imshow(size_gamma, cmap="viridis", vmin=0.0)
    axes[0].set_xticks([0, 1])
    axes[0].set_yticks([0, 1])
    axes[0].set_xticklabels(["small", "large"])
    axes[0].set_yticklabels(["small", "large"])
    axes[0].set_xlabel("source size")
    axes[0].set_ylabel("target size")
    axes[0].set_title("Median size aggregate Gamma")
    for i in range(2):
        for j in range(2):
            axes[0].text(j, i, f"{size_gamma[i, j]:.2f}", ha="center", va="center", color="white", fontsize=8)
    fig.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04)

    x = np.arange(len(df))
    axes[1].bar(x, df["spectral_radius"], color="#3b6ea8", label="spectral radius")
    axes[1].plot(x, df["mark_log_loss_improvement"], marker="o", color="#8a5a2b", label="mark log-loss gain")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(df["ticker"], rotation=25, ha="right")
    axes[1].set_ylim(0, max(1.0, float(df[["spectral_radius", "mark_log_loss_improvement"]].max().max()) * 1.1))
    axes[1].set_title("12-mark robustness")
    axes[1].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_size_side_marked_multivariate.png", dpi=220)
    plt.close(fig)


def save_hawkes_estimator_validation_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_hawkes_estimator_validation.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    labels = [f"rho={r:g}\nbeta={b:g}" for r, b in zip(df["rho_true"], df["beta_true"])]
    x = np.arange(len(df))
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.8))
    axes[0].bar(x, df["rho_mae"], color="#3b6ea8")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylabel("rho MAE")
    axes[0].set_title("Estimator branching recovery")
    axes[1].bar(x, df["beta_mape"], color="#8a5a2b")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel("beta MAPE")
    axes[1].set_title("Estimator decay recovery")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_hawkes_estimator_validation.png", dpi=220)
    plt.close(fig)


def save_marked_hawkes_estimator_validation_plot(results_root: Path) -> None:
    table = results_root / "tables" / "lobster_marked_hawkes_estimator_validation.csv"
    if not table.exists():
        return
    df = pd.read_csv(table)
    if df.empty:
        return
    labels = [f"rho={r:g}" for r in df["rho_true"]]
    x = np.arange(len(df))
    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.8))
    axes[0].bar(x, df["rho_mae"], color="#3b6ea8")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylabel("rho MAE")
    axes[0].set_title("Spectral radius recovery")
    axes[1].bar(x, df["gamma_relative_frobenius_mean"], color="#8a5a2b")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel("relative Frobenius error")
    axes[1].set_title("Branching matrix recovery")
    axes[2].bar(x, df["mark_log_loss_gain_mean"], color="#3c7d63")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels)
    axes[2].set_ylabel("log-loss gain")
    axes[2].set_title("Mark prediction gain")
    fig.tight_layout()
    fig.savefig(results_root / "figures" / "lobster_marked_hawkes_estimator_validation.png", dpi=220)
    plt.close(fig)


def save_all_figures(results_root: Path = Path("results")) -> None:
    save_scaling_plot(results_root)
    save_spectral_gap_ablation_plot(results_root)
    save_hawkes_variance_plot(results_root)
    save_policy_plot(results_root)
    save_policy_dt_convergence_plot(results_root)
    save_policy_ogata_audit_plot(results_root)
    save_event_queue_backtest_plot(results_root)
    save_lobster_top_of_book_replay_plot(results_root)
    save_lobster_l1_quote_replay_plot(results_root)
    save_lobster_depth_quote_replay_plot(results_root)
    save_lobster_priority_depth_quote_replay_plot(results_root)
    save_lobster_priority_depth_sensitivity_plot(results_root)
    save_lobster_orderbook_reconstruction_plot(results_root)
    save_finite_n_plot(results_root)
    save_quote_sensitivity_diagnostic_plot(results_root)
    save_robust_dp_plot(results_root)
    save_lobster_panel_plot(results_root)
    save_crypto_panel_plot(results_root)
    save_binance_aggtrade_hawkes_plot(results_root)
    save_binance_aggtrade_cross_date_plot(results_root)
    save_calibration_noise_plot(results_root)
    save_simulator_validation_plot(results_root)
    save_discretization_bias_plot(results_root)
    save_hawkes_estimator_validation_plot(results_root)
    save_marked_hawkes_estimator_validation_plot(results_root)
    save_lobster_hawkes_event_type_plot(results_root)
    save_lobster_fixed_beta_profile_plot(results_root)
    save_lobster_multiscale_plot(results_root)
    save_lobster_marked_multivariate_plot(results_root)
    save_lobster_side_marked_multivariate_plot(results_root)
    save_lobster_side_marked_state_residuals_plot(results_root)
    save_lobster_size_side_marked_multivariate_plot(results_root)
    save_lobster_timestamp_sensitivity_plot(results_root)
