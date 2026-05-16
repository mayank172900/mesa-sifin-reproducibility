# SSRN Submission Metadata

Title: Structural Hawkes Ambiguity in Near-Critical Market Making

Author: Mayank Sharma
Affiliation: Indian Institute of Technology Jodhpur, Department of Engineering Science
Email: may1729int@gmail.com

Content format: Paper
Content type: Preprint / working paper

Manuscript/full-text file: `mesa_sifin_ssrn_full.pdf`
Source/compilation archive: `mesa_sifin_ssrn_source_bundle.zip`
Reproducibility/code repository: https://github.com/mayank172900/mesa-sifin-reproducibility

Suggested keywords:
- Hawkes processes
- robust market making
- structural ambiguity
- near-critical order flow
- limit order books
- viscosity solutions
- queue-position risk

Suggested JEL codes:
- C58
- G12
- G14
- G17

Suggested abstract:
This paper studies a narrow source of model risk in market making: uncertainty about the self-excitation structure of Hawkes order flow. The structure is encoded by a branching matrix Gamma, while the distance to instability is measured by the Perron root rho(Gamma). In a reduced robust inventory model, ambiguity in Gamma is amplified through the Hawkes resolvent (I-Gamma)^(-1), so near-critical calibration error can become an economic risk premium. The critical exponent depends on normalization: relative critical-slack ambiguity gives a square-law reduced premium, while absolute branching-matrix ambiguity contributes one additional derivative factor when epsilon is smaller than the remaining critical slack. The paper gives a reduced-form spectral theorem and conditional robust-control bridges under stated compact-PDMP, Lyapunov, weighted-comparison, and smooth-interior assumptions. It then evaluates robust and nominal quoting policies under common random numbers, Ogata event times, public LOBSTER sample replays, Binance aggregate trades, and crypto order-book samples. The empirical claim is deliberately limited: structural Hawkes ambiguity is visible in these near-critical stress tests, but public Hawkes calibrations remain diagnostic inputs rather than complete execution models.

AI disclosure:
Generative AI tools were used for language editing, LaTeX cleanup, code scaffolding, experiment automation, validation-script review, and reproducibility-package organization. The author reviewed the outputs and remains responsible for all mathematical claims, proofs, citations, code, data processing, numerical experiments, and final text.

Data/code note:
Large raw market-data files are not attached to the SSRN full-text PDF or source archive. The combined full-text PDF contains the main paper followed by the theory appendix. The TeX source bundle includes the main-paper source, appendix source, and figures needed for compilation. The companion code/artifact package can be posted separately as SSRN supplemental material, GitHub, Zenodo, or OSF.
