# Paper-Code Novelty Scout For MESA

Assumptions used: topic is Hawkes criticality, robust market making, structural
uncertainty over the branching matrix `Gamma`, and near-critical market
microstructure. Time window was expanded beyond 30 days because the local draft
depends on 2019-2026 prior art. Compute budget is one Apple Silicon workstation.
Publishing target is SIAM Journal on Financial Mathematics first, with
Quantitative Finance / Market Microstructure and Liquidity as fallback.

## Live Web Update, 2026-05-16

I rechecked the comparison set against current primary pages and recorded the
audit in `paper/web_sota_audit.md`. The key update is reproducibility:
El Karmi's 2025 deterministic Hawkes LOB simulator now has a visible public
repository with C++/Python source, configs, docs, tests, Makefile/CMake, and
quick-start guidance. That makes simulator realism a strong external baseline,
not a novelty claim for MESA. Attn-LOB also has a visible public demo
repository with environment setup, while Relaver points to anonymous 4open code
but the detailed public post-review repository was not verified in this pass.

The latest theory/calibration threats are also sharper: Kimura's April 2026
state-dependent Hawkes LOB paper uses local supercriticality to reproduce
volatility signature plots, Noble--Rosenbaum--Souilmi's March 2026 paper makes
LOB simulator realism and execution sensitivity central, and El Karmi's May
2026 bivariate nearly unstable Hawkes theorem narrows any broad claim about
near-critical Hawkes limits. These papers reinforce the MESA positioning:
spectral branching-matrix ambiguity and robust quote consequences, not first
Hawkes control, not first robust market making, and not first realistic Hawkes
LOB simulator.

## A) Top Picks (3 Papers)

### 1. Jain, Firoozye, Kochems, Treleaven (2025)

- Paper: [An Impulse Control Approach to Market Making in a Hawkes LOB Market](https://arxiv.org/abs/2510.26438)
- Date: submitted October 30, 2025; revised October 31, 2025.
- Repository: no direct verified usable repository found on the arXiv page.
- License: arXiv page provides a license link; no code license verified.
- Reproducibility score: 2/5.

Contribution summary: This is the nearest Hawkes-control competitor. It studies
market making in a high-fidelity mutually exciting Hawkes LOB, formulates an
impulse-control HJB-QVI, and uses deep RL / deep PDE approximation because the
full problem is high-dimensional and nonlocal.

Novelty gaps for MESA:

- No structural ambiguity set over `Gamma`.
- No theorem or experiment about resolvent amplification as `rho(Gamma) -> 1`.
- No market-making premium tied to a spectral branching matrix.
- No Perron/spectral-gap condition for robust quoting.

Best extension ideas:

- Prove a minimal robust Hawkes market-making theorem where the uncertain object
  is the branching ratio/matrix, then compare numerically with impulse-control
  Hawkes baselines.
- Add a finite-scenario robust Bellman approximation using Perron worst-case
  perturbations, and evaluate under full Hawkes simulation.

Minimal experiment checklist:

- Scalar/bivariate Hawkes robust premium sweep over `rho` and `epsilon`.
- Perron perturbation ablation versus random Frobenius perturbations.
- Robust vs nominal policy evaluation under matched Hawkes paths.

Publishability potential: 4/5.

### 2. Wang, Ventre, Polukarov (2025)

- Paper: [Robust Market Making: To Quote, or not To Quote](https://arxiv.org/abs/2508.16588)
- Related Hawkes extension: [ARL-Based Multi-Action Market Making with Hawkes Processes and Variable Volatility](https://arxiv.org/abs/2508.16589)
- Date: August 7, 2025.
- Repository: no complete reproducibility repository verified during this pass.
- License: no code license verified.
- Reproducibility score: 2/5.

Contribution summary: This cluster covers robust/adversarial market making,
quote/no-quote action spaces, and a Hawkes-process market simulation variant.
It is a serious novelty threat to any generic "robust market making" claim.

Novelty gaps for MESA:

- Robustness is adversarial or volatility/environmental, not structural
  uncertainty over a Hawkes branching matrix.
- No spectral criticality theorem.
- No proof that ambiguity costs scale through `(I-Gamma)^(-1)`.

Best extension ideas:

- Make no-quote thresholds a corollary of structural ambiguity amplification.
- Compare robust-Gamma quoting with quote/no-quote baselines under the same
  near-critical Hawkes stress grid.

Minimal experiment checklist:

- Include `as_poisson`, `nominal_hawkes`, `robust_vol_only`, `robust_gamma`, and
  `known_true_gamma_no_ambiguity` policies.
- Report certainty equivalent, tail PnL, inventory variance, fill rate, and
  adverse-selection loss.

Publishability potential: 4/5.

### 3. Szymanski and Xu (2025)

- Paper: [Mean-Field Limits for Nearly Unstable Hawkes Processes](https://arxiv.org/abs/2501.11648)
- Date: January 20, 2025.
- Repository: no code repository verified.
- License: no code license verified.
- Reproducibility score: 1/5, theory paper.

Contribution summary: This paper establishes scaling limits and propagation of
chaos for nearly unstable Hawkes systems, including regimes depending on
`n(1-||phi||_1)^2`. It is the strongest warning against overclaiming the
mean-field/propagation-of-chaos novelty.

Novelty gaps for MESA:

- No market-making control problem.
- No robust ambiguity set over `Gamma`.
- No trading policy or spread/no-quote implication.

Best extension ideas:

- Use their near-critical mean-field regimes as the mathematical backdrop, then
  specialize to a controlled market-maker facing structural estimation error.
- Treat finite-N degradation as an implication/experiment, not the main theorem.

Minimal experiment checklist:

- Fit `error_N,rho = C N^{-alpha}(1-rho)^{-beta}`.
- Keep graphon/mean-field material secondary unless a new control-specific
  theorem is proven.

Publishability potential: 3.5/5 as a supporting lane, not the first paper core.

## B) Other Viable (2-5 Papers)

- Law and Viens (2019/2020), [Market Making under a Weakly Consistent LOB Model](https://arxiv.org/abs/1903.07222). Hawkes/marked-point-process market making and HJB-QVI already exist. Reproducibility score 2/5; publishability threat high for generic Hawkes-control claims.
- El Karmi (2025), [A Deterministic Limit Order Book Simulator with Hawkes-Driven Order Flow](https://arxiv.org/abs/2510.08085) and [public repository](https://github.com/sohaibelkarmi/High-Frequency-Trading-Simulator). Strongest code-reality competitor: visible source, configs, docs, tests, and quick-start guidance. Reproducibility score 4/5, with license not verified in the web audit.
- Lalor and Swishchuk (2025), [Event-Based Limit Order Book Simulation under a Neural Hawkes Process](https://arxiv.org/abs/2502.17417). Neural Hawkes LOB simulation and DRL market making. Reproducibility score 2/5; threat to simulator novelty.
- Kimura (2026), [Extended State-dependent Hawkes Process for Limit Order Books](https://arxiv.org/abs/2604.23961). State-dependent Hawkes with local supercriticality and volatility-signature evidence. Reproducibility score 1/5; threat to claims that fixed exponential Hawkes calibration is enough.
- Noble, Rosenbaum, and Souilmi (2026), [Bridging the Reality Gap in Limit Order Book Simulation](https://arxiv.org/abs/2603.24137). Strong simulator-realism and execution-sensitivity framing. Reproducibility score 1/5 in this audit; threat to production-execution claims.
- El Karmi (2026), [Scaling Limits of Bivariate Nearly-Unstable Hawkes Processes](https://arxiv.org/abs/2605.03703). Very current bivariate near-critical Hawkes/rough-volatility theory. Reproducibility score 1/5; threat to any broad near-critical Hawkes-limit claim.

## C) Two-Week Execution Plan For Best Pick

Day 1: Freeze the first paper thesis as structural ambiguity amplification in
scalar and finite-dimensional Perron-visible Hawkes market making.

Day 2: Rewrite related work honestly: Hawkes control exists; robust market
making exists; the missing piece is uncertain `Gamma` near criticality.

Day 3: Formalize the minimal model, admissible controls, inventory grid, and
static or rectangular ambiguity interpretation.

Day 4: Prove Hawkes stationarity/resolvent lemmas and specify the exact
normalization under which the premium exponent is two.

Day 5: Prove upper bound for the ambiguity premium.

Day 6: Prove lower bound under simple Perron root, spectral gap, and
price-impact alignment.

Day 7: Add the corrected warning: absolute `Gamma` perturbations may yield
exponent three or four depending on variance normalization.

Day 8: Extend the code from scalar to finite-dimensional Perron scenarios and
add criticality sentinel tests.

Day 9: Run full scaling sweeps and bootstrap confidence intervals.

Day 10: Run robust-vs-nominal market-making stress tests with common random
numbers.

Day 11: Run finite-N error and spectral-gap ablations.

Day 12: Draft SIAM-style paper sections: introduction, related work, model,
theorem, numerics.

Day 13: Draft appendix: proof details, Perron projection, CIR caveat, data
pipeline limitations.

Day 14: Referee audit: remove overclaims, label approximations, regenerate all
figures/tables from a clean manifest.

## D) Don't-Do List To Avoid Plagiarism And Non-Novelty

- Do not claim first Hawkes market-making control paper.
- Do not claim robust market making is new.
- Do not claim near-critical Hawkes limits are new.
- Do not claim graphon mean-field games are new.
- Do not state unconditional `Theta(epsilon/(1-rho)^2)` for absolute `Gamma`
  balls unless the proof supports that normalization.
- Separate replication, approximation, and contribution.
- Avoid dataset leakage and hidden tuning; use common random numbers for policy
  comparisons.
- Document negative or corrected-exponent results rather than hiding them.
