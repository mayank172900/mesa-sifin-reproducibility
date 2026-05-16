#!/usr/bin/env python3
"""Build a deterministic handoff bundle for the MESA/SIFIN package."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import zipfile

try:
    from validate_submission_package import extract_promised_artifacts, sha256_file
except ModuleNotFoundError:  # Imported as scripts.build_submission_bundle in tests.
    from scripts.validate_submission_package import extract_promised_artifacts, sha256_file


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUNDLE_NAME = "mesa_sifin_submission_bundle.zip"
BUNDLE_PATH = DIST / BUNDLE_NAME
BUNDLE_MANIFEST = DIST / "mesa_sifin_submission_bundle_manifest.csv"
BUNDLE_SHA256 = DIST / "mesa_sifin_submission_bundle.sha256"
HANDOFF_NOTE = ROOT / "paper" / "submission_handoff_note.md"
FIXED_ZIP_DATE = (2026, 5, 16, 0, 0, 0)


@dataclass(frozen=True)
class BundleRow:
    relative_path: str
    bytes: int
    sha256: str


def write_handoff_note() -> None:
    HANDOFF_NOTE.write_text(
        "\n".join(
            [
                "# Submission Handoff Note",
                "",
                "Date: 2026-05-16.",
                "",
                "This note describes the deterministic local handoff bundle built by",
                "`scripts/build_submission_bundle.py`.",
                "",
                "## Bundle Files",
                "",
                "- `dist/mesa_sifin_submission_bundle.zip`",
                "- `dist/mesa_sifin_submission_bundle_manifest.csv`",
                "- `dist/mesa_sifin_submission_bundle.sha256`",
                "",
                "The zip contains the validated manuscript sources/PDFs, SIAM-source",
                "handoff, cover-letter draft, reports, code, tests, configs, selected",
                "results tables/figures/raw experiment artifacts, and validation outputs.",
                "It intentionally does not include `data/raw/` because raw external data",
                "should be fetched from source or redistributed only under the relevant",
                "data-provider terms.",
                "",
                "## Required Human/External Actions",
                "",
                "- Replace working author placeholders with final author, affiliation,",
                "  ORCID, funding, conflict, and corresponding-author metadata.",
                "- Confirm originality, no simultaneous submission, and prior",
                "  dissemination/preprint history.",
                "- Archive the code/data manifest in a public repository or DOI service",
                "  if required by the journal or authors.",
                "- Download or request SIAM's official `siamonline250211.cls` package",
                "  before compiling the generated SIAM source.",
                "",
                "The local validator reports `PASS_WITH_EXTERNAL_ACTIONS` until those",
                "human/external tasks are complete.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def collect_bundle_paths(root: Path = ROOT) -> list[Path]:
    """Return sorted paths for the handoff zip, excluding raw data and dist."""
    rels = set(extract_promised_artifacts(root))
    rels.update(
        {
            "results/tables/submission_artifact_manifest.csv",
            "paper/submission_readiness_check.md",
            "paper/submission_handoff_note.md",
        }
    )
    paths: list[Path] = []
    for rel in sorted(rels):
        if rel.startswith(("data/", "dist/")) or "__pycache__" in rel:
            continue
        path = root / rel
        if path.is_file():
            paths.append(path)
    return paths


def build_rows(paths: list[Path], root: Path = ROOT) -> list[BundleRow]:
    rows: list[BundleRow] = []
    for path in paths:
        rows.append(
            BundleRow(
                relative_path=path.relative_to(root).as_posix(),
                bytes=path.stat().st_size,
                sha256=sha256_file(path),
            )
        )
    return rows


def write_bundle_manifest(rows: list[BundleRow]) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    with BUNDLE_MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(BundleRow.__dataclass_fields__))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_zip(paths: list[Path], root: Path = ROOT) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BUNDLE_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in paths:
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(rel, FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def write_bundle_sha() -> str:
    digest = hashlib.sha256(BUNDLE_PATH.read_bytes()).hexdigest()
    BUNDLE_SHA256.write_text(f"{digest}  {BUNDLE_NAME}\n", encoding="utf-8")
    return digest


def main() -> None:
    write_handoff_note()
    paths = collect_bundle_paths(ROOT)
    rows = build_rows(paths, ROOT)
    write_bundle_manifest(rows)
    write_zip(paths, ROOT)
    digest = write_bundle_sha()
    total_bytes = sum(row.bytes for row in rows)
    generated_at = datetime.now(timezone.utc).isoformat()
    print(f"generated_at: {generated_at}")
    print(f"bundle: {BUNDLE_PATH.relative_to(ROOT)}")
    print(f"bundle_manifest: {BUNDLE_MANIFEST.relative_to(ROOT)}")
    print(f"bundle_sha256: {digest}")
    print(f"files: {len(rows)}")
    print(f"payload_bytes: {total_bytes}")


if __name__ == "__main__":
    main()
