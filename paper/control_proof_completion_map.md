# Multitype HJBI/control proof completion map

Date: 2026-05-16

This note records the conditional theorem chain, and the remaining proof
obligations, for the multitype Hawkes control component of MESA.

## Conditional theorem chain

1. Finite-state robust Bellman verification
   - Location: `paper/mesa_sifin_manuscript.tex`, Numerical Method section.
   - Role: verifies the implemented finite-scenario quote/no-quote DP on a
     finite inventory/action/regime grid.

2. Compact continuous-intensity HJBI verification
   - Location: `paper/mesa_scalar_theory_appendix.tex`, Compact
     Continuous-Intensity HJBI Bridge.
   - Role: gives viscosity identification for the truncated multitype Hawkes
     PDMP on compact intensity domains under the stated compact-PDMP
     dynamic-programming and comparison hypotheses.

3. Untruncated Lyapunov bridge
   - Location: `paper/mesa_scalar_theory_appendix.tex`, Untruncated Lyapunov
     Bridge.
   - Role: proves nonexplosion, finite `p>1` weighted maximal moments,
     truncation-tail control, and compact approximation under common Lyapunov
     subcriticality.

4. Weighted comparison and global untruncated HJBI
   - Location: `paper/mesa_scalar_theory_appendix.tex`, Weighted Comparison
     And Global Untruncated HJBI.
   - Role: proves pairwise comparison and uniqueness of the untruncated
     viscosity solution in any weighted subclass with a fixed boundary
     condition at infinity, plus local uniform convergence of compact
     truncations to that fixed-boundary solution.

5. Interior robust quote optimizer sensitivity
   - Location: `paper/mesa_scalar_theory_appendix.tex`, Interior Quote
     Optimizer Sensitivity.
   - Role: connects the HJBI Hamiltonian to differentiable quote changes under
     unique smooth active worst-case selectors and inactive quote constraints.

6. End-to-end multitype Hawkes HJBI/control result
   - Location: `paper/mesa_scalar_theory_appendix.tex`, Consolidated Multitype
     Control Theorem.
   - Role: assembles nonexplosion, weighted value finiteness, untruncated
     HJBI uniqueness, compact-truncation convergence, classical selector
     verification when smooth, and interior quote differentiability into one
     theorem statement.

## Exact scope

The current proof chain is complete only conditional on the stated exponential
Hawkes model class plus:

- finite inventory;
- compact controls and compact rectangular ambiguity;
- compact-PDMP dynamic-programming and bounded-comparison hypotheses for the
  truncated game;
- common Lyapunov subcriticality for the ambiguity set;
- a `p>1` Lyapunov maximal-moment/tail-integrability condition;
- controlled mark rates bounded by the Hawkes intensity state;
- linearly growing rewards/payoffs;
- a fixed weighted boundary condition at infinity for the subclass in which
  uniqueness is claimed.

## Remaining proof obligations for a stronger theorem

The appendix no longer treats the following as proven:

- removal of the compact-PDMP DPP/comparison hypothesis by a fully self-contained
  compact-game proof;
- uniqueness across every linearly growing weighted solution without a shared
  boundary condition at infinity;
- untruncated convergence for linearly growing payoffs without the `p>1` tail
  bound;
- classical differentiability through no-quote, spread-cap, or active-adversary
  switching boundaries;
- state-dependent, learned, multiscale, or power-law Hawkes kernels unless the
  same Lyapunov/comparison assumptions are re-established;
- exchange-grade hidden-liquidity and anonymous-priority reconstruction.

## Not claimed

The manuscript should present the result as a conditional theorem chain rather
than an unconditional full multitype HJBI/control proof.
