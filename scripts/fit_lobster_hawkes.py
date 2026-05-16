#!/usr/bin/env python3
"""Fit univariate Hawkes models to public LOBSTER samples."""

from __future__ import annotations

import argparse
from pathlib import Path

from mesa.calibration import (
    fit_lobster_fixed_beta_sensitivity,
    fit_lobster_marked_multivariate_hawkes,
    fit_lobster_multiscale_hawkes_sensitivity,
    fit_lobster_panel_hawkes,
    fit_lobster_panel_hawkes_by_event_type,
    fit_lobster_side_marked_multivariate_hawkes,
    fit_lobster_side_marked_state_residual_diagnostics,
    fit_lobster_size_side_marked_multivariate_hawkes,
    fit_lobster_timestamp_sensitivity,
    validate_hawkes_estimator,
    validate_marked_hawkes_estimator,
)
from mesa.plotting import (
    save_hawkes_estimator_validation_plot,
    save_marked_hawkes_estimator_validation_plot,
    save_lobster_fixed_beta_profile_plot,
    save_lobster_hawkes_event_type_plot,
    save_lobster_marked_multivariate_plot,
    save_lobster_multiscale_plot,
    save_lobster_side_marked_multivariate_plot,
    save_lobster_side_marked_state_residuals_plot,
    save_lobster_size_side_marked_multivariate_plot,
    save_lobster_timestamp_sensitivity_plot,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/raw/lobster")
    parser.add_argument("--results", default="results")
    parser.add_argument("--max-events", type=int, default=150_000)
    parser.add_argument("--diagnostic-max-events", type=int, default=30_000)
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Run event-type, fixed-beta, multiscale, grouped/side-aware marked, state-residual, and timestamp diagnostics.",
    )
    parser.add_argument(
        "--size-side-robustness",
        action="store_true",
        help="Also run the heavier 12-mark size/side/event Hawkes robustness fit.",
    )
    parser.add_argument("--validate-estimator", action="store_true", help="Validate MLE on synthetic Ogata Hawkes samples.")
    parser.add_argument("--skip-panel", action="store_true", help="Skip all-event panel refit and only run requested diagnostics.")
    args = parser.parse_args()
    max_events = None if args.max_events <= 0 else args.max_events
    diagnostic_max_events = None if args.diagnostic_max_events <= 0 else args.diagnostic_max_events
    results = Path(args.results)
    if args.validate_estimator:
        validation = validate_hawkes_estimator(results_root=results)
        print("\nEstimator validation")
        print(validation.round(6).to_string(index=False))
        marked_validation = validate_marked_hawkes_estimator(results_root=results)
        print("\nMarked estimator validation")
        print(marked_validation.round(6).to_string(index=False))
        save_hawkes_estimator_validation_plot(results)
        save_marked_hawkes_estimator_validation_plot(results)

    if not args.skip_panel:
        fits = fit_lobster_panel_hawkes(
            data_root=Path(args.data_root),
            results_root=results,
            max_events=max_events,
        )
        print("\nAll-event fits")
        print(fits.round(6).to_string(index=False))
    if args.diagnostics:
        event_fits = fit_lobster_panel_hawkes_by_event_type(
            data_root=Path(args.data_root),
            results_root=results,
            max_events=diagnostic_max_events,
        )
        fixed_beta = fit_lobster_fixed_beta_sensitivity(
            data_root=Path(args.data_root),
            results_root=results,
            max_events=diagnostic_max_events,
        )
        timestamp = fit_lobster_timestamp_sensitivity(
            data_root=Path(args.data_root),
            results_root=results,
            max_events=diagnostic_max_events,
        )
        multiscale = fit_lobster_multiscale_hawkes_sensitivity(
            data_root=Path(args.data_root),
            results_root=results,
            max_events=diagnostic_max_events,
        )
        marked = fit_lobster_marked_multivariate_hawkes(
            data_root=Path(args.data_root),
            results_root=results,
            max_events=diagnostic_max_events,
        )
        side_marked = fit_lobster_side_marked_multivariate_hawkes(
            data_root=Path(args.data_root),
            results_root=results,
            max_events=diagnostic_max_events,
        )
        state_residuals = fit_lobster_side_marked_state_residual_diagnostics(
            data_root=Path(args.data_root),
            results_root=results,
            max_events=diagnostic_max_events,
        )
        size_side = None
        if args.size_side_robustness:
            size_side = fit_lobster_size_side_marked_multivariate_hawkes(
                data_root=Path(args.data_root),
                results_root=results,
                max_events=diagnostic_max_events,
            )
        save_lobster_hawkes_event_type_plot(results)
        save_lobster_fixed_beta_profile_plot(results)
        save_lobster_multiscale_plot(results)
        save_lobster_marked_multivariate_plot(results)
        save_lobster_side_marked_multivariate_plot(results)
        save_lobster_side_marked_state_residuals_plot(results)
        if size_side is not None:
            save_lobster_size_side_marked_multivariate_plot(results)
        save_lobster_timestamp_sensitivity_plot(results)
        print("\nEvent-type fits")
        print(event_fits.round(6).to_string(index=False))
        print("\nFixed-beta sensitivity summary")
        print(
            fixed_beta.groupby(["event_group", "beta_fixed"])["rho"]
            .median()
            .reset_index()
            .round(6)
            .to_string(index=False)
        )
        print("\nTimestamp sensitivity")
        print(
            timestamp.groupby("resolution_seconds")[["rho", "beta", "retained_share"]]
            .median()
            .reset_index()
            .round(6)
            .to_string(index=False)
        )
        print("\nMultiscale Hawkes best fixed beta-pair fits")
        print(
            multiscale.sort_values(["ticker", "event_group", "aic"])
            .groupby(["ticker", "event_group"], as_index=False)
            .first()[["ticker", "event_group", "beta_pair", "rho", "rho_slow", "rho_fast", "fast_share", "residual_ks_stat"]]
            .round(6)
            .to_string(index=False)
        )
        print("\nMarked multivariate Hawkes best fixed-beta fits")
        print(
            marked.sort_values(["ticker", "aic"])
            .groupby("ticker", as_index=False)
            .first()[["ticker", "beta_fixed", "spectral_radius", "mark_log_loss_improvement", "residual_ks_stat"]]
            .round(6)
            .to_string(index=False)
        )
        print("\nSide-aware marked multivariate Hawkes best fixed-beta fits")
        print(
            side_marked.sort_values(["ticker", "aic"])
            .groupby("ticker", as_index=False)
            .first()[["ticker", "beta_fixed", "spectral_radius", "mark_log_loss_improvement", "residual_ks_stat"]]
            .round(6)
            .to_string(index=False)
        )
        print("\nSide-aware state-conditioned residual diagnostics")
        print(
            state_residuals.groupby(["state_variable", "state_bucket"])[
                ["residual_mean", "residual_ks_stat", "mark_log_loss_improvement"]
            ]
            .median()
            .reset_index()
            .round(6)
            .to_string(index=False)
        )
        if size_side is not None:
            print("\nSize/side/event marked Hawkes robustness fits")
            print(
                size_side.sort_values(["ticker", "aic"])
                .groupby("ticker", as_index=False)
                .first()[["ticker", "beta_fixed", "spectral_radius", "mark_log_loss_improvement", "residual_ks_stat"]]
                .round(6)
                .to_string(index=False)
            )


if __name__ == "__main__":
    main()
