"""Commissioning remediation: stored failure placeholders fail validation.

A section whose persisted content is a synthesis-failure placeholder
("Synthesis timed out after 300s" / "Timed out") must fail quality
validation as an ERROR — not pass through as merely short prose with a
word-count warning (the 2026-09-12 commissioning-run defect).
"""

from backend.api.quality_checks import (
    compute_quality_checks,
    compute_remediation_hints,
)


def test_timeout_placeholder_fails_validation():
    checks = compute_quality_checks({"abstract": "Synthesis timed out after 300s"})
    abstract = next(c for c in checks if c["section"] == "abstract")
    assert abstract["passed"] is False
    assert any("stored synthesis-failure placeholder" in f for f in abstract["failures"])


def test_bare_timed_out_placeholder_fails_validation():
    checks = compute_quality_checks({"abstract": "Timed out"})
    abstract = next(c for c in checks if c["section"] == "abstract")
    assert abstract["passed"] is False
    assert any("stored synthesis-failure placeholder" in f for f in abstract["failures"])


def test_placeholder_placeholder_hint_is_error_severity():
    sections = {"abstract": "Synthesis timed out after 300s"}
    hints = compute_remediation_hints(sections)
    abstract_hints = [h for h in hints if h["section"] == "abstract"]
    assert abstract_hints, "expected an error hint for the placeholder section"
    assert all(h["severity"] == "error" for h in abstract_hints)
    assert all(
        h["issue_type"] == "synthesis_failure_placeholder" for h in abstract_hints
    )


def test_short_prose_still_reports_word_count_not_placeholder():
    checks = compute_quality_checks({"abstract": "Too short prose."})
    abstract = next(c for c in checks if c["section"] == "abstract")
    assert abstract["passed"] is False
    assert not any("placeholder" in f for f in abstract["failures"])
    assert any(f.startswith("word count") for f in abstract["failures"])


def test_real_prose_passes_without_placeholder_failure():
    sentence = (
        "This abstract describes a memory architecture that keeps task context "
        "bounded while persistent state grows, with explicit invariants for "
        "reconstruction, indexing, placement, publication, and crash recovery. "
    )
    checks = compute_quality_checks({"abstract": sentence * 6})
    abstract = next(c for c in checks if c["section"] == "abstract")
    assert abstract["passed"] is True
