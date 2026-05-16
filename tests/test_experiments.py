from pathlib import Path

import numpy as np

from mesa.experiments import ExperimentConfig, run_spectral_gap_ablation_experiment


def test_spectral_gap_ablation_recovers_visibility_caveat(tmp_path: Path):
    _, fits = run_spectral_gap_ablation_experiment(ExperimentConfig(quick=True), tmp_path)
    visible = fits[
        (fits["gap_multiple"] == 2.0)
        & (fits["loading"] == "perron_visible")
        & (fits["adversary"] == "perron_aligned")
    ].iloc[0]
    orthogonal = fits[
        (fits["gap_multiple"] == 2.0)
        & (fits["loading"] == "perron_orthogonal")
        & (fits["adversary"] == "perron_aligned")
    ].iloc[0]
    second_mode = fits[
        (fits["gap_multiple"] == 2.0)
        & (fits["loading"] == "perron_orthogonal")
        & (fits["adversary"] == "second_mode")
    ].iloc[0]
    assert np.isclose(visible["slope"], -2.0, atol=0.15)
    assert orthogonal["n_positive"] == 0
    assert np.isclose(second_mode["slope"], -2.0, atol=0.15)
