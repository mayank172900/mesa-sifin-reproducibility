"""Spectral utilities for Hawkes branching matrices."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PerronData:
    radius: float
    left: np.ndarray
    right: np.ndarray
    gap: float
    condition: float


def spectral_radius(gamma: np.ndarray) -> float:
    """Return the spectral radius of a square matrix."""
    eigvals = np.linalg.eigvals(np.asarray(gamma, dtype=float))
    return float(np.max(np.abs(eigvals)))


def normalize_to_radius(gamma: np.ndarray, rho: float) -> np.ndarray:
    """Scale a nonzero matrix to the requested spectral radius."""
    gamma = np.asarray(gamma, dtype=float)
    current = spectral_radius(gamma)
    if current <= 0:
        raise ValueError("cannot normalize a matrix with zero spectral radius")
    return gamma * (rho / current)


def perron_data(gamma: np.ndarray) -> PerronData:
    """Compute Perron left/right vectors and a simple spectral-gap diagnostic."""
    gamma = np.asarray(gamma, dtype=float)
    vals, vecs = np.linalg.eig(gamma)
    idx = int(np.argmax(np.abs(vals)))
    radius = float(np.real(vals[idx]))
    right = np.real(vecs[:, idx])
    if np.sum(right) < 0:
        right = -right
    right = np.maximum(right, 0)
    right = right / max(np.linalg.norm(right), 1e-12)

    lvals, lvecs = np.linalg.eig(gamma.T)
    lidx = int(np.argmin(np.abs(lvals - vals[idx])))
    left = np.real(lvecs[:, lidx])
    if np.dot(left, right) < 0:
        left = -left
    left = np.maximum(left, 0)
    denom = max(float(np.dot(left, right)), 1e-12)
    left = left / denom

    sorted_abs = np.sort(np.abs(vals))[::-1]
    gap = float(sorted_abs[0] - sorted_abs[1]) if len(sorted_abs) > 1 else float(sorted_abs[0])
    condition = float(np.linalg.norm(left) * np.linalg.norm(right))
    return PerronData(radius=radius, left=left, right=right, gap=gap, condition=condition)


def resolvent(gamma: np.ndarray) -> np.ndarray:
    """Return (I-Gamma)^-1 for a stable branching matrix."""
    gamma = np.asarray(gamma, dtype=float)
    return np.linalg.solve(np.eye(gamma.shape[0]) - gamma, np.eye(gamma.shape[0]))


def variance_amplification(gamma: np.ndarray) -> float:
    """A scalar proxy for Hawkes endogenous variance amplification.

    For nonnegative near-critical matrices, ||(I-Gamma)^-1||_2^2 has the
    leading-order critical exponent two under a simple Perron eigenvalue.
    """
    res = resolvent(gamma)
    return float(np.linalg.norm(res, ord=2) ** 2)


def worst_case_perron_perturbation(
    gamma: np.ndarray,
    epsilon: float,
    rho_max: float = 0.999,
) -> np.ndarray:
    """Move Gamma in the Perron-sensitive Frobenius direction.

    This is the first-order adversarial direction for increasing the Perron
    root when the leading eigenvalue is simple. The result is scaled back if it
    breaches the stability cap.
    """
    data = perron_data(gamma)
    direction = np.outer(data.right, data.left)
    direction = direction / max(np.linalg.norm(direction, ord="fro"), 1e-12)
    candidate = np.maximum(gamma + epsilon * direction, 0.0)
    rho = spectral_radius(candidate)
    if rho > rho_max:
        candidate = candidate * (rho_max / rho)
    return candidate


def make_gamma_family(
    family: str,
    dim: int,
    rho: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Create a nonnegative branching matrix family with prescribed rho."""
    if dim < 2:
        raise ValueError("dim must be at least 2")

    if family == "rank1":
        u = rng.uniform(0.2, 1.0, size=dim)
        v = rng.uniform(0.2, 1.0, size=dim)
        gamma = np.outer(u, v)
    elif family == "block":
        gamma = rng.uniform(0.0, 0.08, size=(dim, dim))
        split = dim // 2
        gamma[:split, :split] += rng.uniform(0.2, 0.8, size=(split, split))
        gamma[split:, split:] += rng.uniform(0.1, 0.5, size=(dim - split, dim - split))
        gamma[:split, split:] += rng.uniform(0.0, 0.2, size=(split, dim - split))
    elif family == "near_degenerate":
        u1 = rng.uniform(0.2, 1.0, size=dim)
        v1 = rng.uniform(0.2, 1.0, size=dim)
        u2 = rng.uniform(0.2, 1.0, size=dim)
        v2 = rng.uniform(0.2, 1.0, size=dim)
        gamma = np.outer(u1, v1) + 0.92 * np.outer(u2, v2)
    elif family == "sparse":
        mask = rng.uniform(size=(dim, dim)) < min(0.35, 4.0 / dim)
        gamma = mask * rng.uniform(0.05, 1.0, size=(dim, dim))
        gamma += 0.02
    else:
        raise ValueError(f"unknown gamma family: {family}")

    return normalize_to_radius(gamma, rho)

