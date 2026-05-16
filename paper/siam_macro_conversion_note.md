# SIAM Online Macro Source Handoff

Date: 2026-05-16.

SIFIN is an online-only SIAM journal. SIAM's author instructions say authors
are highly encouraged to use SIAM LaTeX2e macros, and the SIAM journal-author
page lists the online-only multimedia macro package for JUQ, SIADS, SIAGA,
SIFIN, SIIMS, and SIMODS. The class file named there is
`siamonline250211.cls`.

Official source:

- https://epubs.siam.org/journal-authors
- https://epubs.siam.org/journal/sifin/instructions-for-authors

Local package status:

- `paper/mesa_sifin_manuscript.tex` remains the stable article-class source
  used for local PDF builds.
- `paper/mesa_sifin_manuscript_siam.tex` is the generated SIAM-source handoff
  created by `scripts/build_siam_source.py`.
- The generated SIAM source uses
  `\documentclass[review]{siamonline250211}`, SIAM `keywords` and `AMS`
  environments, and the running head
  `\headers{Structural Hawkes Ambiguity}{MESA Working Manuscript}`.
- The generated source is not compiled by `make paper` because SIAM's
  `siamonline250211.cls` and `siamplain.bst` are not vendored in this research
  package. Before final upload, download the official macro zip from SIAM or
  request it by email, place the class/style files on TeX's search path, fill
  author metadata, and compile the SIAM source.

This artifact turns the macro task into a concrete handoff while preserving the
locally reproducible article-class PDF build.
