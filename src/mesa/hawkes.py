"""Vectorized discrete-time Hawkes simulators.

The simulator uses the standard exponential-kernel Markov recursion

    lambda_{t+dt} = mu + exp(-beta dt)(lambda_t-mu) + beta Gamma dN_t

where Gamma is the branching matrix, i.e. the integral of the kernel.
The Poisson discretization is intentionally simple, fast, and stable enough
for the scaling experiments in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mesa.spectral import spectral_radius


@dataclass(frozen=True)
class HawkesParams:
    mu: np.ndarray
    gamma: np.ndarray
    beta: float = 4.0
    dt: float = 0.02
    horizon: float = 20.0

    @property
    def steps(self) -> int:
        if self.dt <= 0:
            raise ValueError("dt must be positive")
        steps = int(round(self.horizon / self.dt))
        if not np.isclose(steps * self.dt, self.horizon, rtol=0.0, atol=1e-10):
            raise ValueError("horizon must be an integer multiple of dt for discrete simulation")
        return steps

    @property
    def dim(self) -> int:
        return int(np.asarray(self.mu).shape[0])


def stationary_intensity(mu: np.ndarray, gamma: np.ndarray) -> np.ndarray:
    """Return the stationary intensity for a stable Hawkes process."""
    mu = np.asarray(mu, dtype=float)
    gamma = np.asarray(gamma, dtype=float)
    rho = spectral_radius(gamma)
    if rho >= 1.0:
        raise ValueError(f"unstable Hawkes branching matrix with spectral radius {rho:.6g}")
    return np.linalg.solve(np.eye(gamma.shape[0]) - gamma, mu)


def _excitation_from_counts(counts: np.ndarray, gamma: np.ndarray) -> np.ndarray:
    """Return Hawkes excitation increments for path-by-type count arrays."""
    return np.einsum("pj,ij->pi", counts, gamma, optimize=True)


def simulate_discrete_hawkes(
    params: HawkesParams,
    n_paths: int,
    seed: int = 0,
    keep_intensity: bool = False,
    counts_dtype: np.dtype | type = np.int16,
) -> dict[str, np.ndarray]:
    """Simulate count paths and optionally intensities."""
    rng = np.random.default_rng(seed)
    mu = np.asarray(params.mu, dtype=float)
    gamma = np.asarray(params.gamma, dtype=float)
    dim = params.dim
    steps = params.steps
    decay = float(np.exp(-params.beta * params.dt))
    dtype = np.dtype(counts_dtype)
    dtype_max = np.iinfo(dtype).max

    lam = np.broadcast_to(stationary_intensity(mu, gamma), (n_paths, dim)).copy()
    counts = np.empty((n_paths, steps, dim), dtype=dtype)
    intensities = np.empty((n_paths, steps, dim), dtype=np.float32) if keep_intensity else None
    overflow_count = 0

    for t in range(steps):
        np.clip(lam, 1e-8, 1e6, out=lam)
        inc = rng.poisson(lam * params.dt)
        overflow_count += int(np.count_nonzero(inc > dtype_max))
        counts[:, t, :] = np.minimum(inc, dtype_max)
        if keep_intensity:
            intensities[:, t, :] = lam
        lam = mu + decay * (lam - mu) + params.beta * _excitation_from_counts(inc, gamma)

    out = {"counts": counts, "overflow_count": np.asarray(overflow_count, dtype=np.int64)}
    if keep_intensity:
        out["intensity"] = intensities
    return out


def simulate_discrete_hawkes_totals(
    params: HawkesParams,
    n_paths: int,
    seed: int = 0,
) -> np.ndarray:
    """Simulate Hawkes paths while storing only total counts per path/type."""
    rng = np.random.default_rng(seed)
    mu = np.asarray(params.mu, dtype=float)
    gamma = np.asarray(params.gamma, dtype=float)
    dim = params.dim
    steps = params.steps
    decay = float(np.exp(-params.beta * params.dt))

    lam = np.broadcast_to(stationary_intensity(mu, gamma), (n_paths, dim)).copy()
    totals = np.zeros((n_paths, dim), dtype=np.int64)
    for _ in range(steps):
        np.clip(lam, 1e-8, 1e6, out=lam)
        inc = rng.poisson(lam * params.dt)
        totals += inc
        lam = mu + decay * (lam - mu) + params.beta * _excitation_from_counts(inc, gamma)
    return totals


def simulate_ogata_hawkes(
    params: HawkesParams,
    seed: int = 0,
    initial_intensity: np.ndarray | None = None,
    max_events: int = 1_000_000,
) -> dict[str, np.ndarray]:
    """Simulate one multivariate exponential Hawkes path with Ogata thinning.

    The kernel is consistent with ``simulate_discrete_hawkes``:
    an event of type ``j`` increases intensity ``i`` by
    ``beta * gamma[i, j]``.
    """
    rng = np.random.default_rng(seed)
    mu = np.asarray(params.mu, dtype=float)
    gamma = np.asarray(params.gamma, dtype=float)
    beta = float(params.beta)
    horizon = float(params.horizon)
    dim = params.dim
    lam = (
        np.asarray(initial_intensity, dtype=float).copy()
        if initial_intensity is not None
        else stationary_intensity(mu, gamma)
    )
    if lam.shape != (dim,):
        raise ValueError(f"initial_intensity must have shape {(dim,)}")

    t = 0.0
    times: list[float] = []
    marks: list[int] = []
    intensities_before: list[np.ndarray] = []

    while t < horizon and len(times) < max_events:
        lam = np.maximum(lam, 1e-12)
        total_bound = float(lam.sum())
        if total_bound <= 0:
            break
        t_candidate = t + rng.exponential(1.0 / total_bound)
        if t_candidate > horizon:
            break
        decay = np.exp(-beta * (t_candidate - t))
        lam_candidate = mu + decay * (lam - mu)
        total_candidate = float(lam_candidate.sum())
        if rng.uniform() * total_bound <= total_candidate:
            probs = lam_candidate / total_candidate
            mark = int(rng.choice(dim, p=probs))
            times.append(t_candidate)
            marks.append(mark)
            intensities_before.append(lam_candidate.copy())
            lam = lam_candidate + beta * gamma[:, mark]
        else:
            lam = lam_candidate
        t = t_candidate

    return {
        "times": np.asarray(times, dtype=float),
        "marks": np.asarray(marks, dtype=np.int16),
        "intensity_before": np.asarray(intensities_before, dtype=float),
    }


def ogata_counts(
    params: HawkesParams,
    n_paths: int,
    seed: int = 0,
) -> np.ndarray:
    """Return total event counts per path/type from Ogata simulation."""
    counts = np.zeros((n_paths, params.dim), dtype=int)
    for path in range(n_paths):
        out = simulate_ogata_hawkes(params, seed=seed + path)
        if len(out["marks"]):
            counts[path] = np.bincount(out["marks"], minlength=params.dim)
    return counts


def ogata_binned_counts(
    params: HawkesParams,
    n_paths: int,
    seed: int = 0,
    max_events: int = 1_000_000,
    counts_dtype: np.dtype | type = np.int32,
) -> np.ndarray:
    """Return binned event counts from Ogata paths on the params dt grid."""
    steps = params.steps
    dim = params.dim
    counts = np.zeros((n_paths, steps, dim), dtype=counts_dtype)
    for path in range(n_paths):
        out = simulate_ogata_hawkes(params, seed=seed + path, max_events=max_events)
        times = out["times"]
        marks = out["marks"]
        if len(times) == 0:
            continue
        bins = np.floor(times / params.dt).astype(int)
        valid = (bins >= 0) & (bins < steps)
        if np.any(valid):
            np.add.at(counts[path], (bins[valid], marks[valid]), 1)
    return counts


def count_summary(counts: np.ndarray) -> dict[str, np.ndarray]:
    """Summarize aggregate path counts."""
    totals = np.asarray(counts).sum(axis=1)
    return {
        "path_totals": totals,
        "mean": totals.mean(axis=0),
        "var": totals.var(axis=0, ddof=1),
        "total_mean": totals.sum(axis=1).mean(),
        "total_var": totals.sum(axis=1).var(ddof=1),
    }
