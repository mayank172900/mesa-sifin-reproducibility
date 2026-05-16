# Web-Verified SOTA Audit

Audit date: 2026-05-16.

This note records the current-source check behind `results/tables/sota_comparison.csv`.
It is a claim-control artifact: the goal is not to show that MESA beats every
recent simulator or RL agent, but to identify what each recent paper already
covers and where MESA remains distinct.

## Verified Primary Sources

| Work | Source | Date / venue signal | Code reality checked |
|---|---|---|---|
| Law--Viens weakly consistent LOB market making | [arXiv:1903.07222](https://arxiv.org/abs/1903.07222) | 2019 preprint, revised 2020 | No directly usable public code verified in this audit. |
| Wang--Ventre--Polukarov quote/no-quote robust MM | [arXiv:2508.16588](https://arxiv.org/abs/2508.16588) | 2025-08-07 | No directly usable public code verified in this audit. |
| Wang--Ventre--Polukarov Hawkes ARL | [arXiv:2508.16589](https://arxiv.org/abs/2508.16589) | 2025-08-07 | No directly usable public code verified in this audit. |
| Jain--Firoozye--Kochems--Treleaven Hawkes impulse control MM | [arXiv:2510.26438](https://arxiv.org/abs/2510.26438) | 2025-10-30 | No directly usable public code verified in this audit. |
| Lalor--Swishchuk neural Hawkes LOB simulator | [arXiv:2502.17417](https://arxiv.org/abs/2502.17417) | 2025-02-24 | No directly usable public code verified in this audit. |
| Guo--Lin--Huang Attn-LOB DRL | [arXiv:2305.15821](https://arxiv.org/abs/2305.15821) | 2023 IJCNN paper | Public GitHub demo visible with README, `conda_setup.yaml`, and `main.py`; license not visible in web audit. |
| Jiang et al. Relaver latency/inventory RL | [arXiv:2505.12465](https://arxiv.org/abs/2505.12465) | 2025-05-18 | Paper text points to anonymous 4open code; detailed public post-review repo not verified. |
| Raffaelli--Cestari--Marazzina--Formentin BTC Hawkes LOB | [DOI:10.1007/s10203-026-00570-z](https://doi.org/10.1007/s10203-026-00570-z) | Accepted 2026-03-27, published 2026 | No directly usable public code verified in this audit. |
| El Karmi deterministic Hawkes LOB simulator | [arXiv:2510.08085](https://arxiv.org/abs/2510.08085), [GitHub](https://github.com/sohaibelkarmi/High-Frequency-Trading-Simulator) | 2025-10-09 | Public repository visible with C++/Python source, configs, docs, tests, Makefile/CMake, quick-start guidance, and example outputs; license not visible in web audit. |
| Noble--Rosenbaum--Souilmi LOB simulation realism gap | [arXiv:2603.24137](https://arxiv.org/abs/2603.24137) | 2026-03-25 | No directly usable public code verified in this audit. |
| Kimura extended state-dependent Hawkes LOB | [arXiv:2604.23961](https://arxiv.org/abs/2604.23961) | 2026-04-27 | No directly usable public code verified in this audit; paper includes high-frequency tick-data volatility-signature evidence. |
| Szymanski--Xu nearly unstable Hawkes mean-field limits | [arXiv:2501.11648](https://arxiv.org/abs/2501.11648) | 2025-01-20 | Theory paper; no code expected or verified. |
| El Karmi bivariate nearly unstable Hawkes | [arXiv:2605.03703](https://arxiv.org/abs/2605.03703) | 2026-05-05 | Theory paper; no code expected or verified. |

## Novelty Implications

1. **Hawkes market making is not new.** Law--Viens and Jain et al. already
   establish serious Hawkes/marked-point-process market-making control
   precedents.
2. **Robust/no-quote market making is not new.** Wang--Ventre--Polukarov and
   Relaver make quote refusal, one-sided quoting, latency, and inventory risk
   unavoidable baselines.
3. **Realistic Hawkes LOB simulation is not new.** Lalor--Swishchuk, El Karmi,
   Noble--Rosenbaum--Souilmi, and Kimura make simulator realism, state
   dependence, and local supercriticality active SOTA territory.
4. **Near-critical Hawkes theory is not new.** Szymanski--Xu and El Karmi's
   2026 bivariate limit theorem mean MESA should not claim broad nearly
   unstable Hawkes limit novelty.
5. **The defensible MESA novelty is the intersection:** structural ambiguity
   over the Hawkes branching matrix, Perron/resolvent criticality amplification,
   robust quote/no-quote consequences, and public-data calibration stress
   diagnostics that explicitly avoid production execution claims.

## Code-Reality Consequence

The strongest external reproducibility threat is El Karmi's simulator because
its public repository is materially more complete than most comparison papers.
MESA should therefore avoid claiming simulator primacy. Its SOTA table should
instead state that the simulator line provides realistic data-generation and
execution machinery, while MESA contributes a spectral ambiguity-risk layer and
criticality diagnostics that can be evaluated inside or alongside such
simulators.

The `code_reality_note` field is a lightweight web audit, not a full
reproducibility badge. Rows with anonymous repositories or missing visible
licenses should be treated as partially verified until a final submission
records commit hashes, license status, and exact reproduction commands.
