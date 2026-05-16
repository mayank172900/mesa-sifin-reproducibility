# MESA Theory Repair Memo

## Safe First-Paper Thesis

MESA should become:

> Structural ambiguity in near-critical Hawkes order flow produces a spectral
> robustness premium for market making. The premium is controlled by the
> Hawkes resolvent `(I-Gamma)^(-1)` and becomes large as `rho(Gamma) -> 1`.

The proof appendix now states this for scalar and bivariate exponential Hawkes
order flow at the reduced risk-premium level. It also verifies the finite-state
Bellman layer, proves a compact truncated continuous-intensity HJBI bridge, and
adds an untruncated Lyapunov stability/truncation bridge under a common
subcriticality vector, plus weighted comparison for the corresponding
untruncated HJBI.

## Assumptions To Add

- Exponential Hawkes kernels, so the intensity state is Markov.
- Irreducible nonnegative `Gamma`.
- Uniform subcriticality: `rho(Gamma) <= rho_max < 1`.
- For untruncated uniform stability, common Lyapunov subcriticality:
  `Gamma.T v <= (1-kappa) v` for one `v > 0` across the ambiguity set.
- Simple Perron root with spectral gap bounded below.
- Positive left/right Perron vectors `ell`, `r`, normalized by `ell^T r = 1`.
- Price-impact/fill-risk direction has nonzero alignment with the Perron mode.
- Compact quote controls and finite inventory grid.
- Relaxed or finite-scenario ambiguity unless pointwise Isaacs is proved.

## Repaired Theorem 1: Value And HJBI

Under compact controls, finite inventory, exponential Hawkes dynamics, and a
compact convex rectangular ambiguity set, the robust control problem has a value
in relaxed controls. The value is the unique viscosity solution of a coupled
finite-inventory nonlocal integro-HJBI system with polynomial growth.

Proof route:

- Treat the controlled Hawkes inventory process as a PDMP with jumps.
- Use dynamic programming for the finite-inventory coupled system.
- Use relaxed controls to recover Hamiltonian minimax equality.
- Apply comparison for nonlocal integro-PDEs under Lipschitz coefficients and
  Lyapunov growth bounds.
- Only claim pure feedback saddle when measurable pure selectors satisfy Isaacs.

## Repaired Theorem 2: Policy Perturbation

The zero-ambiguity base policy is not Avellaneda-Stoikov. It is a known-Hawkes
market-making policy:

```text
delta^{0,*} = delta^{H,*}(t, q, lambda; Gamma_hat)
```

If the known-Hawkes Hamiltonian has a unique strictly concave quote optimizer
and the value/Hamiltonian is directionally differentiable in `Gamma`, then:

```text
delta^{epsilon,*} = delta^{H,*} + epsilon psi_1 + o(epsilon)
```

The sign `psi_1 >= 0` requires an adverse-selection monotonicity condition. In
general, only the robust half-spread is guaranteed to widen.

## Repaired Theorem 3: Criticality Amplification

Resolvent expansion for irreducible nonnegative `Gamma` with simple Perron root:

```text
(I-Gamma)^(-1) = (1-rho)^(-1) r ell^T + O(1/gap)
```

Perron root perturbation:

```text
rho(Gamma + E) - rho(Gamma) = ell^T E r + O(||E||_F^2 / gap)
```

Worst first-order Frobenius perturbation is aligned with `ell r^T`; the
resolvent projection itself is `r ell^T`.

Important correction: if `epsilon` is an absolute perturbation radius in
`Gamma`, and if the spread is linear in the effective variance
`sigma_eff^2 ~ (1-rho)^(-2)`, then perturbing `rho` directly can produce
`epsilon (1-rho)^(-3)` behavior. If stationary intensity also diverges inside
the price-risk term, the exponent can be still steeper.

The draft's `epsilon/(1-rho)^2` theorem is safest when `epsilon` is defined as
uncertainty at the structural/resolvent risk level or as relative uncertainty
scaled with the stability slack. Otherwise state a bound family rather than a
single unconditional exponent.

## Journal-Risk Flags

- Static ambiguity and pointwise HJBI are inconsistent unless carefully
  formulated.
- The spectral-radius sublevel set is compact but nonconvex.
- The HJBI is nonlocal and coupled across inventory states, not a standard PDE.
- The full multitype theorem needs Perron/eigengap assumptions.
- The strongest publishable path is the rigorous scalar and finite-dimensional
  Perron-visible reduced-form theorem now in the appendix, plus finite-state
  Bellman, compact HJBI, untruncated Lyapunov, weighted comparison, and smooth
  interior optimizer-sensitivity bridges. The remaining future-theory items
  are no-quote/boundary active-set differentiability and extending the same
  conditions to richer state-dependent or learned Hawkes kernels.
