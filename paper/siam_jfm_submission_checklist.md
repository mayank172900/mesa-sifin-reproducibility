# SIAM Journal on Financial Mathematics Submission Checklist

Date checked: 2026-05-16.

Target journal: SIAM Journal on Financial Mathematics (SIFIN).

Official sources checked:

- SIFIN Instructions for Authors:
  https://epubs.siam.org/journal/sifin/instructions-for-authors
- SIAM Information for Journal Authors:
  https://epubs.siam.org/journal-authors
- SIAM Editorial Policy on Artificial Intelligence:
  https://epubs.siam.org/artificial-intelligence

## Current Package Status

| Requirement | Official basis | Package evidence | Status |
|---|---|---|---|
| Submit through SIAM Journal Submission and Tracking System | SIFIN instructions say manuscripts are entered through the journal tracking system | External action by corresponding author; not a local artifact | external |
| Manuscript PDF required | SIFIN instructions request manuscript PDF | `paper/mesa_sifin_manuscript.pdf`; author metadata remains a human finalization item | ready-draft |
| Cover letter PDF required | SIFIN instructions request cover letter PDF | `paper/siam_jfm_cover_letter.pdf` | ready-draft |
| Figures embedded inline | SIFIN instructions require inline figures | manuscript includes figures through `\includegraphics` and compiled PDF embeds them | ready |
| Abstract no more than 250 words | SIAM author instructions specify one-paragraph abstract under 250 words | validator checks `paper/mesa_sifin_manuscript.tex`; current count is under 250 | ready |
| Keywords and MSC codes accompany article | SIAM author instructions require keywords and mathematics subject classifications | manuscript includes `Keywords` and `MSC` immediately after abstract | ready |
| Abbreviated title available | SIAM author instructions require a running head under 50 characters | `paper/siam_jfm_submission_metadata.md` gives `Structural Hawkes Ambiguity` | ready |
| SIAM/SIFIN macros considered | SIAM encourages SIAM multimedia macros for SIFIN | `paper/mesa_sifin_manuscript_siam.tex` and `paper/siam_macro_conversion_note.md` prepare the `siamonline250211.cls` source handoff; official class/style files must be downloaded or requested by the corresponding author before compiling that source | source-prepared |
| No simultaneous publication statement | SIAM submission policy requires originality/no simultaneous submission | draft cover letter includes representation for human author confirmation | ready-draft |
| AI/LLM use documented where applicable | SIAM AI policy requires documentation beyond spelling/style polishing | manuscript acknowledgments, `paper/siam_jfm_ai_disclosure.md`, and draft cover letter include a disclosure block for human author review | ready-draft |

## Final Human Actions Before Upload

- Replace placeholder author, affiliation, ORCID, funding, and corresponding
  author fields in the cover letter and manuscript.
- Confirm no simultaneous submission and no prior publication conflict.
- Download or request SIAM's official `siamonline250211.cls` macro package,
  fill final author metadata in `paper/mesa_sifin_manuscript_siam.tex`, and
  compile the SIAM source if the corresponding author wants the upload PDF in
  SIAM format.
- Confirm whether the AI disclosure wording is acceptable to all human authors.
- Upload `paper/mesa_sifin_manuscript.pdf` and
  `paper/siam_jfm_cover_letter.pdf` through the SIAM submission system.
