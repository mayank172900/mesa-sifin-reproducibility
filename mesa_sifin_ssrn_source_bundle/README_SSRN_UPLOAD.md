# SSRN-ready MESA paper package

Full combined SSRN PDF:
- `mesa_sifin_ssrn_full.pdf`

Component PDFs used to build the combined PDF:
- `mesa_sifin_ssrn.pdf`
- `mesa_scalar_theory_appendix_ssrn.pdf`

Recommended SSRN use:
1. Upload `mesa_sifin_ssrn_full.pdf` as the full-text PDF. It contains the main paper followed by the theory appendix.
2. Do not upload `mesa_scalar_theory_appendix_ssrn.pdf` as a separate supplemental manuscript when using the combined full-text PDF.
3. Use content format: Paper; content type: Preprint / working paper.
4. Confirm the author metadata and AI disclosure before final submission.
5. Answer funding/competing-interest fields in the SSRN form only if prompted.
6. Add a public GitHub/Zenodo/OSF URL for the companion code/data artifacts if available.

Data note:
- Large raw market-data files are intentionally not included in this source bundle.
- The submission metadata file includes a data/code note for the SSRN form or supplemental-material description if needed.
- The included `figures/` directory is enough to compile the TeX files.

Validation performed:
- LaTeX builds completed with no unresolved references reported in the final logs.
- The combined full-text PDF and its component PDFs were rendered to page images for visual inspection.
- The uploaded codebase test suite passed: 54 tests passed.
- The repository submission validator returned PASS_WITH_EXTERNAL_ACTIONS; remaining actions are human/external metadata/repository decisions.
