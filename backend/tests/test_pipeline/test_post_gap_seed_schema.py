"""Drift test for the typed synthetic post-gap seed.

Asserts the checked-in fixture:
1. validates against the current Paper / ClusterReport / ResearchGap models, and
2. equals the canonical serialized model output.

This runs independently of any pipeline execution and fails immediately when
Paper, ResearchGap, or ClusterReport changes — forcing the fixture to be
regenerated in lockstep. No network access, no pipeline run required.
"""

from __future__ import annotations

import json

from backend.tests.support.post_gap_seed import (
    FIXTURE_PATH,
    SyntheticPostGapSeed,
    build_low_resource_mt_seed,
    serialize_seed,
)


def test_fixture_file_exists():
    assert FIXTURE_PATH.exists(), f"fixture missing at {FIXTURE_PATH}"


def test_fixture_validates_against_current_models():
    seed = SyntheticPostGapSeed.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )
    assert seed.fixture_id == "low_resource_mt_v1"
    assert seed.synthetic is True
    assert seed.schema_version == "erlab.post_gap_seed.v1"


def test_canonical_serialization_matches_checked_in_fixture():
    """The fixture MUST equal the canonical model output byte-for-byte
    (modulo key ordering, which is sorted on both sides)."""
    fixture_data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    canonical = json.loads(serialize_seed())
    assert fixture_data == canonical, (
        "Fixture drift: the checked-in JSON does not match the canonical "
        "serialized model. Regenerate via "
        "post_gap_seed.serialize_seed() after model changes."
    )


def test_seed_structure_contract():
    """The seed carries the agreed downstream inputs: 3 papers, 2 clusters,
    2 valid gaps with clear synthetic provenance."""
    seed = build_low_resource_mt_seed()
    assert len(seed.papers) == 3
    assert len(seed.cluster_report.clusters) == 2
    assert len(seed.gaps) == 2

    # Synthetic provenance on every paper.
    for p in seed.papers:
        assert p.source == "synthetic"
        assert p.id.startswith("SYN-")
        assert p.url and p.url.startswith("urn:erlab:synthetic:")

    # Gaps reference only valid cluster ids from the report.
    valid_ids = {c.cluster_id for c in seed.cluster_report.clusters}
    for g in seed.gaps:
        assert g.title
        assert g.description
        assert 0.0 <= g.confidence <= 1.0
        for cid in g.related_clusters:
            assert cid in valid_ids


def test_serialization_is_deterministic():
    """Serializing twice yields identical output (sort_keys=True)."""
    a = serialize_seed()
    b = serialize_seed()
    assert a == b
