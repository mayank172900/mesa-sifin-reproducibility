# Synthesis Of Subagent Work

At least eight agents were used. The first eight workstreams were:

1. Theory repair: recommended scalar/bivariate theorem first, with Perron
   assumptions and corrected exponent warnings.
2. Literature/novelty: verified that Hawkes market making, robust market
   making, near-critical Hawkes, and graphon MFGs all have strong prior art.
3. Experiment design: proposed scaling, policy, finite-N, ablation, and
   reproducibility suite.
4. Code architecture: recommended scalar/perron/multitype hierarchy and
   Apple Silicon-friendly CPU-first numerics with optional MPS.
5. Robust-control algorithm: proposed Perron-robust inventory dynamic
   programming and full Hawkes evaluation.
6. Paper positioning: recommended SIAM Journal on Financial Mathematics,
   with Quantitative Finance as fallback.
7. Reproducibility: specified tests, run manifests, criticality checks, and
   referee quickstart.
8. Datasets/baselines: identified tick, phawkes, HawkesPyLib, HftBacktest,
   ABIDES, LOBSTER samples, FI-2010, crypto LOB data, and robust/MM baselines.

The consensus is strong: the best publication path is not a broad framework
paper. It is a narrow, rigorous, reproducible paper about structural ambiguity
amplification in near-critical Hawkes market making.

Additional late-stage agents then audited the package:

9. SOTA refresh: added 2025--2026 threats including neural Hawkes LOB
   simulation, Hawkes ARL/no-quote robust market making, impulse control, LOB
   realism-gap simulation, and state-dependent Hawkes local supercriticality.
10. Calibration audit: found and prioritized the pre-event-intensity likelihood
    bug, event-type splits, fixed-beta profiles, timestamp sensitivity, and
    time-rescaling diagnostics.
11. Manuscript referee: identified overclaims around the reduced theorem,
    empirical calibration, SOTA citations, quote-cap/no-quote wording, and
    policy naming.
12. M5 optimization audit: recommended early BLAS thread caps, in-place
    clipping, aggregate-only Hawkes simulation, integer count storage, and
    scaled experiment priorities.
13. Bivariate appendix referee: requested uniform Perron-visibility,
    eigenprojection-conditioning, Perron-coefficient regularity, and cleaner
    asymptotic statements.
14. Manuscript consistency referee: found stale bivariate-bridge wording,
    policy-ranking overclaims, and missing bivariate SOTA table coverage.
15. Artifact auditor: verified key CSV row counts, figures, DP artifacts,
    ablation tables, and the full-run manifest.
16. SOTA/currentness auditor: confirmed SIFIN is plausible only under the
    narrowed structural-Gamma-ambiguity framing and flagged current Hawkes MM,
    robust/no-quote MM, and LOB realism comparators.
