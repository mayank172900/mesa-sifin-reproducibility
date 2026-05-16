# Submission Handoff Note

Date: 2026-05-16.

This note describes the deterministic local handoff bundle built by
`scripts/build_submission_bundle.py`.

## Bundle Files

- `dist/mesa_sifin_submission_bundle.zip`
- `dist/mesa_sifin_submission_bundle_manifest.csv`
- `dist/mesa_sifin_submission_bundle.sha256`

The zip contains the validated manuscript sources/PDFs, SIAM-source
handoff, cover-letter draft, reports, code, tests, configs, selected
results tables/figures/raw experiment artifacts, and validation outputs.
It intentionally does not include `data/raw/` because raw external data
should be fetched from source or redistributed only under the relevant
data-provider terms.

## Required Human/External Actions

- Replace working author placeholders with final author, affiliation,
  ORCID, funding, conflict, and corresponding-author metadata.
- Confirm originality, no simultaneous submission, and prior
  dissemination/preprint history.
- Archive the code/data manifest in a public repository or DOI service
  if required by the journal or authors.
- Download or request SIAM's official `siamonline250211.cls` package
  before compiling the generated SIAM source.

The local validator reports `PASS_WITH_EXTERNAL_ACTIONS` until those
human/external tasks are complete.
