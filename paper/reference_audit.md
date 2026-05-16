# Manuscript Reference Audit

Audit date: 2026-05-16.

Scope: `mesa_sifin_ssrn_source_bundle/mesa_sifin_ssrn.tex`, `thebibliography`
environment. After the SSRN claim-audit fixes, the SSRN source has 17
bibliography entries, 17 unique in-text citation keys, no uncited bibliography
items, and no missing bibliography keys.
The helper script from `paper-reference-audit` was attempted but stalled on
network/API lookup, so the final audit below is a manual source-of-record pass.

## Citation-Key Integrity

| Check | Result |
|---|---:|
| `\bibitem{...}` entries | 17 |
| unique `\cite{...}` keys | 17 |
| cited keys missing from bibliography | 0 |
| bibliography keys not cited | 0 |

## Entry-by-Entry Verification

| Key | Manuscript entry | Source used | Mismatch / action | Judgment |
|---|---|---|---|---|
| `BacryMuzy2015` | Bacry, Mastromatteo, Muzy, *Hawkes processes in finance*, arXiv:1502.04592, 2015 | [arXiv:1502.04592](https://arxiv.org/abs/1502.04592) | Authors, title, year, arXiv ID match. Journal details could be added later if desired. | verified |
| `LawViens2019` | Law and Viens, *Market making under a weakly consistent limit order book model*, arXiv:1903.07222, 2019 | [arXiv:1903.07222](https://arxiv.org/abs/1903.07222) | Authors, title, arXiv ID match. Entry says 2019; source also records later revision, but 2019 is acceptable for arXiv first posting. | verified |
| `Kumar2024` | Kumar, *Deep Hawkes Process for High-Frequency Market Making*, Journal of Banking and Financial Technology, 2024 | [arXiv:2109.15110](https://arxiv.org/abs/2109.15110); DOI `10.1007/s42786-024-00049-8` | Added arXiv ID and DOI; normalized title capitalization. | corrected and verified |
| `Raffaelli2026` | Raffaelli, Cestari, Marazzina, Formentin, *Forecasting Bitcoin price movements using multivariate Hawkes processes and limit order book data*, Decisions in Economics and Finance, 2026, DOI | [Springer DOI](https://doi.org/10.1007/s10203-026-00570-z) | Authors, title, journal, year, DOI match. | verified |
| `WangNoQuote2025` | Wang, Ventre, Polukarov, *Robust Market Making: To Quote, or not To Quote*, ICAIF 2023, arXiv:2508.16588, 2025 | [arXiv:2508.16588](https://arxiv.org/abs/2508.16588); DOI `10.1145/3604237.3626858` | Authors, title, proceedings identity, DOI, and arXiv ID match the source audit. | verified |
| `WangHawkesARL2025` | Wang, Ventre, Polukarov, *ARL-Based Multi-Action Market Making with Hawkes Processes and Variable Volatility*, ICAIF 2024, arXiv:2508.16589, 2025 | [arXiv:2508.16589](https://arxiv.org/abs/2508.16589); DOI `10.1145/3677052.3698695` | Authors, title, proceedings identity, DOI, and arXiv ID match the source audit. | verified |
| `LalorSwishchuk2025` | Lalor and Swishchuk, *Event-Based Limit Order Book Simulation under a Neural Hawkes Process: Application in Market-Making*, arXiv:2502.17417, 2025 | [arXiv:2502.17417](https://arxiv.org/abs/2502.17417) | Authors, title, year, arXiv ID match. | verified |
| `GuoAttnLOB2023` | Guo, Lin, Huang, *Market Making with Deep Reinforcement Learning from Limit Order Books*, IJCNN 2023, arXiv:2305.15821 | [arXiv:2305.15821](https://arxiv.org/abs/2305.15821); DOI `10.1109/IJCNN54540.2023.10191123`; [repository](https://github.com/imTurkey/Market-Making-with-Deep-Reinforcement-Learning-from-Limit-Order-Books) | Corrected initials to H. Guo, J. Lin, and F. Huang; public demo repository exists and is separately audited in `web_sota_audit.md`. | corrected and verified |
| `Jiang2025` | Jiang, Yang, Wang, Li, Huang, Li, *Resolving Latency and Inventory Risk in Market Making with Reinforcement Learning*, arXiv:2505.12465, 2025 | [arXiv:2505.12465](https://arxiv.org/abs/2505.12465) | Author list and title match the arXiv record visible in the audit. | verified |
| `Jain2025` | Jain, Firoozye, Kochems, Treleaven, *An Impulse Control Approach to Market Making in a Hawkes LOB Market*, arXiv:2510.26438, 2025 | [arXiv:2510.26438](https://arxiv.org/abs/2510.26438) | Corrected first author initial to K. Jain; title, year, and arXiv ID match. | corrected and verified |
| `ElKarmiSimulator2025` | El Karmi, *A Deterministic Limit Order Book Simulator with Hawkes-Driven Order Flow*, arXiv:2510.08085, 2025 | [arXiv:2510.08085](https://arxiv.org/abs/2510.08085); [repository](https://github.com/sohaibelkarmi/High-Frequency-Trading-Simulator) | Title, author, year, arXiv ID match; public repository exists and is separately audited in `web_sota_audit.md`. | verified |
| `Noble2026` | Noble, Rosenbaum, Souilmi, *Bridging the Reality Gap in Limit Order Book Simulation*, arXiv:2603.24137, 2026 | [arXiv:2603.24137](https://arxiv.org/abs/2603.24137) | Authors, title, year, arXiv ID match. | verified |
| `Kimura2026` | Kimura, *Extended State-dependent Hawkes Process for Limit Order Books: Mathematical Foundation and the Reproduction of Volatility Signature Plots*, arXiv:2604.23961, 2026 | [arXiv:2604.23961](https://arxiv.org/abs/2604.23961) | Author, title, year, arXiv ID match. | verified |
| `SzymanskiXu2025` | Szymanski and Xu, *Mean-Field Limits for Nearly Unstable Hawkes Processes*, arXiv:2501.11648, 2025 | [arXiv:2501.11648](https://arxiv.org/abs/2501.11648) | Corrected Xu initial to W.; title, year, and arXiv ID match. | corrected and verified |
| `ElKarmi2026` | El Karmi, *Scaling Limits of Bivariate Nearly-Unstable Hawkes Processes and Applications to Rough Volatility*, arXiv:2605.03703, 2026 | [arXiv:2605.03703](https://arxiv.org/abs/2605.03703) | Author, title, year, arXiv ID match. | verified |
| `Hardiman2013` | Hardiman, Bercot, Bouchaud, *Critical reflexivity in financial markets: a Hawkes process analysis*, arXiv:1302.1405, 2013 | [arXiv:1302.1405](https://arxiv.org/abs/1302.1405) | Expanded title and corrected first author initials to S. J. Hardiman. | corrected and verified |
| `Ogata1988` | Ogata, *Statistical models for earthquake occurrences and residual analysis for point processes*, JASA 83(401):9--27, 1988 | [Taylor & Francis DOI](https://www.tandfonline.com/doi/abs/10.1080/01621459.1988.10478560) | Added DOI; author, title, venue, issue, pages, and year match. | corrected and verified |

## Remaining Style Notes

- The bibliography is source-correct for the current SSRN source bundle.
- `Kang2026` was removed from the SSRN bibliography because no SSRN
  abstract/introduction/related-work/SOTA claim depends on it.
- Most 2025--2026 SOTA entries are arXiv-only as of this audit; this is normal
  for the current related-work frontier but should be rechecked before
  submission.
