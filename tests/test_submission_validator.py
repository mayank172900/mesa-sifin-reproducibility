from pathlib import Path

from scripts.build_submission_bundle import collect_bundle_paths, write_handoff_note
from scripts.validate_submission_package import (
    benchmark_integrity,
    citation_integrity,
    extract_promised_artifacts,
    proof_scope_integrity,
    queue_replay_integrity,
    siam_external_submission_items,
    siam_submission_integrity,
    sota_integrity,
)


def test_submission_validator_extracts_promised_artifacts():
    root = Path(__file__).resolve().parents[1]
    promised = set(extract_promised_artifacts(root))
    assert "paper/mesa_sifin_manuscript.pdf" in promised
    assert "paper/mesa_sifin_manuscript_siam.tex" in promised
    assert "paper/mesa_sifin_manuscript.log" in promised
    assert "results/figures/lobster_panel_sanity.png" in promised
    assert "results/figures/crypto_l2_sanity.png" in promised
    assert "results/tables/sota_comparison.csv" in promised
    assert "results/figures/quote_sensitivity_diagnostic.png" in promised
    assert "paper/control_proof_completion_map.md" in promised
    assert "paper/queue_position_replay_completeness.md" in promised
    assert "results/tables/m_series_benchmark.csv" in promised
    assert "paper/siam_jfm_submission_checklist.md" in promised
    assert "paper/siam_macro_conversion_note.md" in promised
    assert "paper/siam_jfm_cover_letter.pdf" in promised
    assert "results/raw/lobster_deepest_public_priority_replay.csv" in promised
    assert "results/tables/lobster_deepest_public_priority_replay_summary.csv" in promised


def test_submission_validator_integrity_checks_pass_current_package():
    root = Path(__file__).resolve().parents[1]
    citation_problems, counts = citation_integrity(root)
    assert citation_problems == []
    assert counts["bibitems"] == counts["unique_cites"] == 18
    assert sota_integrity(root) == []


def test_submission_validator_domain_integrity_checks_pass_current_package():
    root = Path(__file__).resolve().parents[1]
    assert queue_replay_integrity(root) == []
    assert benchmark_integrity(root) == []
    assert proof_scope_integrity(root) == []
    assert siam_submission_integrity(root) == []
    assert siam_external_submission_items(root) != []


def test_submission_bundle_collects_handoff_without_raw_data_or_dist():
    root = Path(__file__).resolve().parents[1]
    write_handoff_note()
    rels = {path.relative_to(root).as_posix() for path in collect_bundle_paths(root)}
    assert "paper/mesa_sifin_manuscript.pdf" in rels
    assert "paper/submission_readiness_check.md" in rels
    assert "paper/submission_handoff_note.md" in rels
    assert "results/raw/lobster_deepest_public_priority_replay.csv" in rels
    assert not any(rel.startswith("data/") for rel in rels)
    assert not any(rel.startswith("dist/") for rel in rels)
