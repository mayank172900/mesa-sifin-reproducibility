#!/usr/bin/env python3
"""Validate the MESA submission package and write an artifact manifest."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys


IMPORTANT_FILES = [
    "README.md",
    "README_REPRODUCE.md",
    "REFEREE_QUICKSTART.md",
    "Makefile",
    "pyproject.toml",
    "requirements.txt",
    "notes/subagents_synthesis.md",
    "paper/mesa_sifin_manuscript.tex",
    "paper/mesa_sifin_manuscript.pdf",
    "paper/mesa_sifin_manuscript_siam.tex",
    "paper/mesa_scalar_theory_appendix.tex",
    "paper/mesa_scalar_theory_appendix.pdf",
    "paper/novelty_scout.md",
    "paper/web_sota_audit.md",
    "paper/reference_audit.md",
    "paper/theory_repair.md",
    "paper/experiment_report.md",
    "paper/ablation_sota_report.md",
    "paper/datasets_and_empirical_scope.md",
    "paper/journal_readiness_audit.md",
    "paper/mesa_sifin_draft.md",
    "paper/control_proof_completion_map.md",
    "paper/queue_position_replay_completeness.md",
    "paper/m_series_optimization_report.md",
    "paper/siam_macro_conversion_note.md",
    "paper/siam_jfm_submission_checklist.md",
    "paper/siam_jfm_submission_metadata.md",
    "paper/siam_jfm_ai_disclosure.md",
    "paper/siam_jfm_cover_letter.tex",
    "paper/siam_jfm_cover_letter.pdf",
]

TEX_LOGS = [
    "paper/mesa_sifin_manuscript.log",
    "paper/mesa_scalar_theory_appendix.log",
    "paper/siam_jfm_cover_letter.log",
]

GENERATED_OUTPUTS = {
    "results/tables/submission_artifact_manifest.csv",
    "paper/submission_readiness_check.md",
}

LOG_WARNING_RE = re.compile(
    r"Overfull|Underfull|Undefined|undefined|Citation|Reference|"
    r"LaTeX Warning|Emergency stop|Fatal|Error"
)

SOTA_REQUIRED_COLUMNS = {
    "paper_or_baseline",
    "covers_hawkes_mm",
    "covers_robust_mm",
    "covers_gamma_uncertainty",
    "covers_critical_exponent",
    "mesa_position",
    "source_url",
    "code_url",
    "code_reality_note",
    "web_verified_date",
}


@dataclass(frozen=True)
class ArtifactRow:
    category: str
    relative_path: str
    status: str
    bytes: int
    sha256: str
    mtime_utc: str


def extract_promised_artifacts(root: Path) -> list[str]:
    """Extract result and paper paths promised by the two referee docs."""
    promised: set[str] = set(IMPORTANT_FILES)
    promised.update(TEX_LOGS)
    for base, patterns in {
        "src": ("*.py",),
        "scripts": ("*.py",),
        "tests": ("*.py",),
        "configs": ("*.json",),
    }.items():
        base_path = root / base
        if not base_path.exists():
            continue
        for pattern in patterns:
            for path in base_path.rglob(pattern):
                if "__pycache__" in path.parts:
                    continue
                promised.add(path.relative_to(root).as_posix())
    for doc in ["README_REPRODUCE.md", "REFEREE_QUICKSTART.md"]:
        text = (root / doc).read_text(encoding="utf-8")
        for match in re.finditer(r"`((?:results|paper|notes|src|scripts|tests)/[^`]+)`", text):
            path = match.group(1).strip()
            if "*" in path or path in GENERATED_OUTPUTS:
                continue
            promised.add(path)
    for tex_rel in ["paper/mesa_sifin_manuscript.tex", "paper/mesa_scalar_theory_appendix.tex"]:
        tex_path = root / tex_rel
        if not tex_path.exists():
            continue
        text = tex_path.read_text(encoding="utf-8")
        for match in re.finditer(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", text):
            image_path = (tex_path.parent / match.group(1)).resolve()
            try:
                promised.add(image_path.relative_to(root).as_posix())
            except ValueError:
                continue
    return sorted(promised)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def category_for(path: str) -> str:
    if path.endswith(".pdf") or path.startswith("paper/"):
        return "paper"
    if path.startswith("results/raw/"):
        return "raw"
    if path.startswith("results/tables/"):
        return "table"
    if path.startswith("results/figures/"):
        return "figure"
    if path.startswith("src/") or path.startswith("scripts/") or path.startswith("tests/"):
        return "code"
    return "metadata"


def build_manifest(root: Path, promised: list[str]) -> list[ArtifactRow]:
    rows: list[ArtifactRow] = []
    for rel in promised:
        path = root / rel
        if path.exists() and path.is_file():
            stat = path.stat()
            rows.append(
                ArtifactRow(
                    category=category_for(rel),
                    relative_path=rel,
                    status="present",
                    bytes=stat.st_size,
                    sha256=sha256_file(path),
                    mtime_utc=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                )
            )
        else:
            rows.append(
                ArtifactRow(
                    category=category_for(rel),
                    relative_path=rel,
                    status="missing",
                    bytes=0,
                    sha256="",
                    mtime_utc="",
                )
            )
    return rows


def scan_tex_logs(root: Path) -> list[str]:
    hits: list[str] = []
    for rel in TEX_LOGS:
        path = root / rel
        if not path.exists():
            hits.append(f"{rel}: missing log file")
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if LOG_WARNING_RE.search(line):
                hits.append(f"{rel}:{line_no}: {line.strip()}")
    return hits


def citation_integrity(root: Path) -> tuple[list[str], dict[str, int]]:
    text = (root / "paper/mesa_sifin_manuscript.tex").read_text(encoding="utf-8")
    bibitems = re.findall(r"\\bibitem\{([^}]+)\}", text)
    cites = sorted({key.strip() for group in re.findall(r"\\cite\{([^}]+)\}", text) for key in group.split(",")})
    missing = sorted(set(cites) - set(bibitems))
    uncited = sorted(set(bibitems) - set(cites))
    problems = [f"missing bibitem for cite key {key}" for key in missing]
    problems.extend(f"uncited bibitem {key}" for key in uncited)
    return problems, {"bibitems": len(bibitems), "unique_cites": len(cites)}


def sota_integrity(root: Path) -> list[str]:
    path = root / "results/tables/sota_comparison.csv"
    if not path.exists():
        return ["results/tables/sota_comparison.csv missing"]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(SOTA_REQUIRED_COLUMNS - columns)
        rows = list(reader)
    problems = [f"sota_comparison.csv missing required column {col}" for col in missing]
    if not rows:
        problems.append("sota_comparison.csv has no rows")
    else:
        if "MESA reduced-form package" not in {row.get("paper_or_baseline", "") for row in rows}:
            problems.append("sota_comparison.csv missing MESA reduced-form package row")
        blank_sources = [
            row.get("paper_or_baseline", "")
            for row in rows
            if not row.get("source_url", "").strip()
        ]
        if blank_sources:
            problems.append(f"sota_comparison.csv has blank source_url rows: {', '.join(blank_sources)}")
    return problems


def _read_csv_dicts(root: Path, rel: str) -> tuple[list[dict[str, str]], list[str]]:
    path = root / rel
    if not path.exists():
        return [], [f"{rel} missing"]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), []


def _float_value(row: dict[str, str], column: str, rel: str) -> tuple[float | None, str | None]:
    raw = row.get(column, "")
    try:
        return float(raw), None
    except (TypeError, ValueError):
        return None, f"{rel} has nonnumeric {column}: {raw!r}"


def queue_replay_integrity(root: Path) -> list[str]:
    """Check that displayed-depth priority replay artifacts satisfy diagnostics."""
    problems: list[str] = []
    raw_rel = "results/raw/lobster_priority_depth_quote_replay.csv"
    summary_rel = "results/tables/lobster_priority_depth_quote_replay_summary.csv"
    sensitivity_rel = "results/tables/lobster_priority_depth_sensitivity_summary.csv"
    deepest_raw_rel = "results/raw/lobster_deepest_public_priority_replay.csv"
    deepest_summary_rel = "results/tables/lobster_deepest_public_priority_replay_summary.csv"
    raw_rows, raw_errors = _read_csv_dicts(root, raw_rel)
    summary_rows, summary_errors = _read_csv_dicts(root, summary_rel)
    sensitivity_rows, sensitivity_errors = _read_csv_dicts(root, sensitivity_rel)
    deepest_raw_rows, deepest_raw_errors = _read_csv_dicts(root, deepest_raw_rel)
    deepest_summary_rows, deepest_summary_errors = _read_csv_dicts(root, deepest_summary_rel)
    problems.extend(raw_errors + summary_errors + sensitivity_errors + deepest_raw_errors + deepest_summary_errors)

    raw_required = {
        "fills",
        "priority_initial_ahead_lots",
        "priority_visible_quote_resets",
        "priority_mean_initial_ahead_lots",
        "priority_visible_levels_used",
        "priority_min_visible_depth_rank",
        "priority_max_visible_depth_rank",
        "priority_queue_fills",
        "priority_improve_fills",
        "priority_queue_violation_count",
        "priority_partial_fill_events",
        "priority_residual_fill_lots",
        "priority_zero_residual_fill_prevented",
        "total_fill_lots",
    }
    summary_required = {
        "mean_priority_initial_ahead_lots",
        "mean_priority_visible_quote_resets",
        "mean_priority_mean_initial_ahead_lots",
        "max_priority_visible_levels_used",
        "min_priority_visible_depth_rank",
        "max_priority_visible_depth_rank",
        "mean_priority_queue_fills",
        "mean_priority_improve_fills",
        "max_priority_queue_violation_count",
        "mean_priority_partial_fill_events",
        "mean_priority_residual_fill_lots",
        "max_priority_zero_residual_fill_prevented",
        "mean_total_fill_lots",
    }
    for rel, rows in [(raw_rel, raw_rows), (deepest_raw_rel, deepest_raw_rows)]:
        if rows and not raw_required.issubset(rows[0]):
            problems.append(f"{rel} missing queue columns: {sorted(raw_required - set(rows[0]))}")
    for rel, rows in [
        (summary_rel, summary_rows),
        (sensitivity_rel, sensitivity_rows),
        (deepest_summary_rel, deepest_summary_rows),
    ]:
        if rows and not summary_required.issubset(rows[0]):
            problems.append(f"{rel} missing queue summary columns: {sorted(summary_required - set(rows[0]))}")

    queued_fill_seen = False
    improve_fill_seen = False
    for rel, rows in [(raw_rel, raw_rows), (deepest_raw_rel, deepest_raw_rows)]:
        for idx, row in enumerate(rows, start=2):
            values: dict[str, float] = {}
            for column in raw_required:
                value, error = _float_value(row, column, rel)
                if error:
                    problems.append(error)
                    continue
                values[column] = float(value)
            if len(values) != len(raw_required):
                continue
            if values["priority_queue_violation_count"] != 0.0:
                problems.append(f"{rel}:{idx} has priority_queue_violation_count={values['priority_queue_violation_count']}")
            if abs((values["priority_queue_fills"] + values["priority_improve_fills"]) - values["fills"]) > 1e-9:
                problems.append(f"{rel}:{idx} queue/improve fills do not sum to fills")
            if values["priority_residual_fill_lots"] - values["total_fill_lots"] > 1e-9:
                problems.append(f"{rel}:{idx} residual fill lots exceed total fill lots")
            if values["fills"] > 0 and values["total_fill_lots"] <= 0:
                problems.append(f"{rel}:{idx} has fill events but no filled lots")
            if values["priority_partial_fill_events"] > values["fills"]:
                problems.append(f"{rel}:{idx} has more partial fill events than fill events")
            if values["priority_visible_quote_resets"] > 0 and values["priority_mean_initial_ahead_lots"] <= 0:
                problems.append(f"{rel}:{idx} has visible quote resets but nonpositive mean initial queue ahead")
            if values["priority_visible_levels_used"] < 2:
                problems.append(f"{rel}:{idx} did not load a multilevel displayed book")
            if values["priority_visible_quote_resets"] > 0 and values["priority_max_visible_depth_rank"] < 1:
                problems.append(f"{rel}:{idx} has visible quote resets but no positive depth rank")
            if values["priority_max_visible_depth_rank"] > values["priority_visible_levels_used"]:
                problems.append(f"{rel}:{idx} depth rank exceeds loaded displayed levels")
            queued_fill_seen = queued_fill_seen or values["priority_queue_fills"] > 0
            improve_fill_seen = improve_fill_seen or values["priority_improve_fills"] > 0

    if raw_rows and not queued_fill_seen:
        problems.append(f"{raw_rel} has no queued fills, so queued-fill invariant is unexercised")
    if raw_rows and not improve_fill_seen:
        problems.append(f"{raw_rel} has no improve fills, so improve-fill path is unexercised")

    for rel, rows in [
        (summary_rel, summary_rows),
        (sensitivity_rel, sensitivity_rows),
        (deepest_summary_rel, deepest_summary_rows),
    ]:
        for idx, row in enumerate(rows, start=2):
            value, error = _float_value(row, "max_priority_queue_violation_count", rel)
            if error:
                problems.append(error)
            elif value != 0.0:
                problems.append(f"{rel}:{idx} has max_priority_queue_violation_count={value}")
            levels_value, levels_error = _float_value(row, "max_priority_visible_levels_used", rel)
            rank_value, rank_error = _float_value(row, "max_priority_visible_depth_rank", rel)
            if levels_error:
                problems.append(levels_error)
            elif levels_value < 2:
                problems.append(f"{rel}:{idx} did not summarize a multilevel displayed book")
            if rank_error:
                problems.append(rank_error)
            elif not levels_error and rank_value > levels_value:
                problems.append(f"{rel}:{idx} depth rank exceeds loaded displayed levels")
    return problems


def benchmark_integrity(root: Path) -> list[str]:
    """Check local M-series benchmark artifacts and oversubscription controls."""
    problems: list[str] = []
    result_rel = "results/tables/m_series_benchmark.csv"
    env_rel = "results/tables/m_series_benchmark_environment.csv"
    rows, result_errors = _read_csv_dicts(root, result_rel)
    env_rows, env_errors = _read_csv_dicts(root, env_rel)
    problems.extend(result_errors + env_errors)
    if not rows or not env_rows:
        return problems

    required_columns = {
        "benchmark",
        "workers",
        "seconds",
        "work_units",
        "throughput_units_per_second",
        "checksum",
        "speedup_vs_single_worker",
        "parallel_efficiency",
    }
    missing = required_columns - set(rows[0])
    if missing:
        problems.append(f"{result_rel} missing columns: {sorted(missing)}")
        return problems

    benchmark_names = {row.get("benchmark", "") for row in rows}
    required_benchmarks = {
        "spectral_resolvent",
        "quote_vectorization",
        "hawkes_totals",
        "parallel_spectral_resolvent",
    }
    missing_benchmarks = required_benchmarks - benchmark_names
    if missing_benchmarks:
        problems.append(f"{result_rel} missing benchmarks: {sorted(missing_benchmarks)}")

    parallel_workers: set[int] = set()
    for idx, row in enumerate(rows, start=2):
        for column in ["workers", "seconds", "work_units", "throughput_units_per_second", "checksum"]:
            value, error = _float_value(row, column, result_rel)
            if error:
                problems.append(error)
                continue
            if column in {"workers", "seconds", "work_units", "throughput_units_per_second"} and value <= 0:
                problems.append(f"{result_rel}:{idx} has nonpositive {column}: {value}")
        if row.get("benchmark") == "parallel_spectral_resolvent":
            workers_value, error = _float_value(row, "workers", result_rel)
            if error:
                problems.append(error)
                continue
            workers = int(workers_value)
            parallel_workers.add(workers)
            for column in ["speedup_vs_single_worker", "parallel_efficiency"]:
                value, error = _float_value(row, column, result_rel)
                if error:
                    problems.append(error)
                elif value <= 0:
                    problems.append(f"{result_rel}:{idx} has nonpositive {column}: {value}")

    required_workers = {1, 2, 4, 8, 16}
    if not required_workers.issubset(parallel_workers):
        problems.append(f"{result_rel} missing parallel worker rows: {sorted(required_workers - parallel_workers)}")

    env = {row.get("key", ""): row.get("value", "") for row in env_rows}
    for key in ["VECLIB_MAXIMUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        if env.get(key) != "1":
            problems.append(f"{env_rel} expected {key}=1, found {env.get(key)!r}")
    try:
        if int(env.get("max_workers_tested", "0")) < 16:
            problems.append(f"{env_rel} max_workers_tested is below documented 16-worker run")
    except ValueError:
        problems.append(f"{env_rel} has noninteger max_workers_tested={env.get('max_workers_tested')!r}")
    return problems


def proof_scope_integrity(root: Path) -> list[str]:
    """Check that proof and queue scope notes contain the expected audit anchors."""
    anchors = {
        "paper/control_proof_completion_map.md": [
            "Conditional theorem chain",
            "Compact continuous-intensity HJBI verification",
            "Weighted comparison and global untruncated HJBI",
            "End-to-end multitype Hawkes HJBI/control result",
            "Remaining proof obligations for a stronger theorem",
            "Not claimed",
        ],
        "paper/queue_position_replay_completeness.md": [
            "Completed public-data replay",
            "priority_visible_levels_used",
            "priority_queue_violation_count == 0",
            "priority_residual_fill_lots",
            "deepest-public supplement",
            "Honest boundary",
        ],
    }
    problems: list[str] = []
    for rel, required in anchors.items():
        path = root / rel
        if not path.exists():
            problems.append(f"{rel} missing")
            continue
        text = path.read_text(encoding="utf-8")
        for anchor in required:
            if anchor not in text:
                problems.append(f"{rel} missing audit anchor {anchor!r}")
    return problems


def _extract_environment(text: str, name: str) -> str:
    pattern = re.compile(rf"\\begin\{{{re.escape(name)}\}}(.*?)\\end\{{{re.escape(name)}\}}", re.S)
    match = pattern.search(text)
    return match.group(1) if match else ""


def _strip_tex_commands(text: str) -> str:
    text = re.sub(r"%.*", " ", text)
    text = re.sub(r"\\cite\{[^}]*\}", " ", text)
    text = re.sub(r"\\[A-Za-z]+(?:\[[^]]*\])?(?:\{[^}]*\})?", " ", text)
    text = re.sub(r"[{}$]", " ", text)
    return text


def siam_submission_integrity(root: Path) -> list[str]:
    """Check SIFIN-specific submission-readiness requirements."""
    problems: list[str] = []
    manuscript = root / "paper/mesa_sifin_manuscript.tex"
    if not manuscript.exists():
        return ["paper/mesa_sifin_manuscript.tex missing"]
    text = manuscript.read_text(encoding="utf-8")
    abstract = _extract_environment(text, "abstract")
    if not abstract:
        problems.append("manuscript missing abstract environment")
    else:
        words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", _strip_tex_commands(abstract))
        if len(words) > 250:
            problems.append(f"abstract has {len(words)} words, exceeding SIAM 250-word limit")
    if "\\textbf{Keywords.}" not in text:
        problems.append("manuscript missing Keywords block")
    if "\\textbf{MSC.}" not in text:
        problems.append("manuscript missing MSC block")
    if "\\section*{Acknowledgments}" not in text:
        problems.append("manuscript missing acknowledgments/disclosure section")
    normalized_text = re.sub(r"\s+", " ", text)
    if "OpenAI Codex" not in text or "human authors are responsible" not in normalized_text:
        problems.append("manuscript missing SIAM AI disclosure/accountability language")

    siam_source = root / "paper/mesa_sifin_manuscript_siam.tex"
    if siam_source.exists():
        siam_text = siam_source.read_text(encoding="utf-8")
        for anchor in [
            r"\documentclass[review]{siamonline250211}",
            r"\headers{Structural Hawkes Ambiguity}{MESA Working Manuscript}",
            r"\begin{abstract}",
            r"\begin{keywords}",
            r"\begin{AMS}",
            "OpenAI Codex",
        ]:
            if anchor not in siam_text:
                problems.append(f"mesa_sifin_manuscript_siam.tex missing anchor {anchor!r}")
    else:
        problems.append("paper/mesa_sifin_manuscript_siam.tex missing")

    conversion_note = root / "paper/siam_macro_conversion_note.md"
    if conversion_note.exists():
        note_text = conversion_note.read_text(encoding="utf-8")
        for anchor in ["siamonline250211.cls", "https://epubs.siam.org/journal-authors", "mesa_sifin_manuscript_siam.tex"]:
            if anchor not in note_text:
                problems.append(f"siam_macro_conversion_note.md missing anchor {anchor!r}")
    else:
        problems.append("paper/siam_macro_conversion_note.md missing")

    metadata = root / "paper/siam_jfm_submission_metadata.md"
    if metadata.exists():
        metadata_text = metadata.read_text(encoding="utf-8")
        match = re.search(r"^Abbreviated title:\s*(.+?)\.\s*$", metadata_text, re.M)
        if not match:
            problems.append("siam_jfm_submission_metadata.md missing abbreviated title")
        else:
            running_head = match.group(1).strip()
            if len(running_head) > 50:
                problems.append(f"abbreviated title exceeds 50 characters: {running_head!r}")
    else:
        problems.append("paper/siam_jfm_submission_metadata.md missing")

    checklist = root / "paper/siam_jfm_submission_checklist.md"
    if checklist.exists():
        checklist_text = checklist.read_text(encoding="utf-8")
        for anchor in [
            "https://epubs.siam.org/journal/sifin/instructions-for-authors",
            "https://epubs.siam.org/journal-authors",
            "https://epubs.siam.org/artificial-intelligence",
            "Cover letter PDF required",
            "Keywords and MSC codes accompany article",
        ]:
            if anchor not in checklist_text:
                problems.append(f"siam_jfm_submission_checklist.md missing anchor {anchor!r}")
    else:
        problems.append("paper/siam_jfm_submission_checklist.md missing")

    ai_disclosure = root / "paper/siam_jfm_ai_disclosure.md"
    if ai_disclosure.exists():
        disclosure_text = ai_disclosure.read_text(encoding="utf-8")
        if "OpenAI Codex" not in disclosure_text or "human authors are responsible" not in disclosure_text:
            problems.append("siam_jfm_ai_disclosure.md missing required AI accountability language")
    else:
        problems.append("paper/siam_jfm_ai_disclosure.md missing")

    cover_tex = root / "paper/siam_jfm_cover_letter.tex"
    cover_pdf = root / "paper/siam_jfm_cover_letter.pdf"
    if not cover_tex.exists():
        problems.append("paper/siam_jfm_cover_letter.tex missing")
    else:
        cover_text = cover_tex.read_text(encoding="utf-8")
        normalized_cover = re.sub(r"\s+", " ", cover_text)
        for phrase in ["not under review elsewhere", "OpenAI Codex", "SIAM Journal on Financial Mathematics"]:
            if phrase not in normalized_cover:
                problems.append(f"siam_jfm_cover_letter.tex missing phrase {phrase!r}")
    if not cover_pdf.exists():
        problems.append("paper/siam_jfm_cover_letter.pdf missing")
    return problems


def siam_external_submission_items(root: Path) -> list[str]:
    """Report human/external upload items that local automation cannot complete."""
    items: list[str] = []
    manuscript = root / "paper/mesa_sifin_manuscript.tex"
    if manuscript.exists() and "MESA Working Manuscript" in manuscript.read_text(encoding="utf-8"):
        items.append("replace manuscript working-author placeholder with final author metadata")
    cover_tex = root / "paper/siam_jfm_cover_letter.tex"
    if cover_tex.exists():
        cover_text = cover_tex.read_text(encoding="utf-8")
        if "Corresponding author" in cover_text:
            items.append("replace cover-letter corresponding-author placeholders")
        if "TODO before submission" in cover_text:
            items.append("confirm whether conference/preprint/repository history must be disclosed")
    metadata = root / "paper/siam_jfm_submission_metadata.md"
    if metadata.exists():
        metadata_text = metadata.read_text(encoding="utf-8")
        if "[fill before submission]" in metadata_text:
            items.append("fill submission metadata placeholders for author, affiliation, funding, and conflicts")
        if "archive/provide DOI later" in metadata_text:
            items.append("archive code/data package and record public DOI or repository URL")
    siam_source = root / "paper/mesa_sifin_manuscript_siam.tex"
    if siam_source.exists() and not (root / "paper/siam_macros/siamonline250211.cls").exists():
        items.append("download or request SIAM's official siamonline250211.cls package before compiling SIAM source")
    return items


def write_manifest(rows: list[ArtifactRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ArtifactRow.__dataclass_fields__))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def write_report(
    root: Path,
    rows: list[ArtifactRow],
    tex_hits: list[str],
    citation_problems: list[str],
    citation_counts: dict[str, int],
    sota_problems: list[str],
    queue_problems: list[str],
    benchmark_problems: list[str],
    proof_scope_problems: list[str],
    siam_problems: list[str],
    siam_external_items: list[str],
    out_path: Path,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    missing = [row for row in rows if row.status != "present"]
    present = [row for row in rows if row.status == "present"]
    generated_at = datetime.now(timezone.utc).isoformat()
    total_bytes = sum(row.bytes for row in present)
    category_counts: dict[str, int] = {}
    for row in present:
        category_counts[row.category] = category_counts.get(row.category, 0) + 1
    domain_problems = queue_problems + benchmark_problems + proof_scope_problems + siam_problems
    failures = len(missing) + len(tex_hits) + len(citation_problems) + len(sota_problems) + len(domain_problems)

    lines = [
        "# Submission Package Validation",
        "",
        f"Generated at: {generated_at}.",
        "",
        "## Summary",
        "",
        f"- Status: {'PASS_WITH_EXTERNAL_ACTIONS' if failures == 0 and siam_external_items else ('PASS' if failures == 0 else 'FAIL')}",
        f"- Present promised artifacts: {len(present)}",
        f"- Missing promised artifacts: {len(missing)}",
        f"- Total promised artifact bytes: {total_bytes}",
        f"- Citation keys: {citation_counts['unique_cites']} unique cites, {citation_counts['bibitems']} bibitems",
        f"- TeX log warning hits: {len(tex_hits)}",
        f"- SOTA table problems: {len(sota_problems)}",
        f"- Queue replay diagnostic problems: {len(queue_problems)}",
        f"- M-series benchmark problems: {len(benchmark_problems)}",
        f"- Proof/scope audit problems: {len(proof_scope_problems)}",
        f"- SIFIN technical-readiness problems: {len(siam_problems)}",
        f"- SIFIN human/external upload items: {len(siam_external_items)}",
        "",
        "## Present Artifacts By Category",
        "",
    ]
    for category in sorted(category_counts):
        lines.append(f"- {category}: {category_counts[category]}")

    lines.extend(["", "## Missing Artifacts", ""])
    if missing:
        lines.extend(f"- `{row.relative_path}`" for row in missing)
    else:
        lines.append("- none")

    lines.extend(["", "## TeX Log Scan", ""])
    if tex_hits:
        lines.extend(f"- `{hit}`" for hit in tex_hits[:50])
        if len(tex_hits) > 50:
            lines.append(f"- ... {len(tex_hits) - 50} additional hits omitted")
    else:
        lines.append("- no warning/error hits under the configured scan")

    lines.extend(["", "## Citation Integrity", ""])
    if citation_problems:
        lines.extend(f"- {problem}" for problem in citation_problems)
    else:
        lines.append("- all in-text citation keys map to bibliography entries, with no uncited bibitems")

    lines.extend(["", "## SOTA Integrity", ""])
    if sota_problems:
        lines.extend(f"- {problem}" for problem in sota_problems)
    else:
        lines.append("- `results/tables/sota_comparison.csv` has source/code audit columns and a MESA row")

    lines.extend(["", "## Domain Integrity", ""])
    if domain_problems:
        if queue_problems:
            lines.append("Queue replay:")
            lines.extend(f"- {problem}" for problem in queue_problems)
        if benchmark_problems:
            lines.append("M-series benchmark:")
            lines.extend(f"- {problem}" for problem in benchmark_problems)
        if proof_scope_problems:
            lines.append("Proof/scope notes:")
            lines.extend(f"- {problem}" for problem in proof_scope_problems)
        if siam_problems:
            lines.append("SIFIN submission readiness:")
            lines.extend(f"- {problem}" for problem in siam_problems)
    else:
        lines.append(
            "- queue replay diagnostics, M-series benchmark controls, proof/scope audit anchors, and SIFIN submission checks pass"
        )

    lines.extend(["", "## Human/External Upload Items", ""])
    if siam_external_items:
        lines.extend(f"- {item}" for item in siam_external_items)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Manifest",
            "",
            "- CSV manifest: `results/tables/submission_artifact_manifest.csv`",
        ]
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the current MESA submission package.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--manifest",
        default="results/tables/submission_artifact_manifest.csv",
        help="CSV manifest path relative to root.",
    )
    parser.add_argument(
        "--report",
        default="paper/submission_readiness_check.md",
        help="Markdown report path relative to root.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on missing artifacts or integrity problems.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    promised = extract_promised_artifacts(root)
    rows = build_manifest(root, promised)
    tex_hits = scan_tex_logs(root)
    citation_problems, citation_counts = citation_integrity(root)
    sota_problems = sota_integrity(root)
    queue_problems = queue_replay_integrity(root)
    benchmark_problems = benchmark_integrity(root)
    proof_scope_problems = proof_scope_integrity(root)
    siam_problems = siam_submission_integrity(root)
    siam_external_items = siam_external_submission_items(root)

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = root / report_path

    write_manifest(rows, manifest_path)
    write_report(
        root,
        rows,
        tex_hits,
        citation_problems,
        citation_counts,
        sota_problems,
        queue_problems,
        benchmark_problems,
        proof_scope_problems,
        siam_problems,
        siam_external_items,
        report_path,
    )

    failures = sum(row.status != "present" for row in rows)
    failures += (
        len(tex_hits)
        + len(citation_problems)
        + len(sota_problems)
        + len(queue_problems)
        + len(benchmark_problems)
        + len(proof_scope_problems)
        + len(siam_problems)
    )
    status = "PASS_WITH_EXTERNAL_ACTIONS" if failures == 0 and siam_external_items else ("PASS" if failures == 0 else "FAIL")
    print(f"submission validation {status}")
    print(f"manifest: {_display_path(manifest_path, root)}")
    print(f"report: {_display_path(report_path, root)}")
    print(f"failures: {failures}")
    if args.strict and failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
