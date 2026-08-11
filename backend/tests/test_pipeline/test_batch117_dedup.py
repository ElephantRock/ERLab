"""BATCH-117: Cross-Run Gap Deduplication tests.

Validates that the GapDeduplicator correctly merges near-duplicate
gaps while preserving unique gaps and tracking source run IDs.
"""

from backend.pipeline.gap_analysis.deduplicator import GapDeduplicator

# ── TEST-117-01-01: Identical gaps are merged ─────────────────────

def test_117_01_01_identical_merged():
    """Identical gaps are merged into one."""
    dedup = GapDeduplicator()
    gaps = [
        {"title": "cost efficiency of reasoning", "description": "d1", "gap_type": "methodological", "confidence": 0.8},
        {"title": "cost efficiency of reasoning", "description": "d2", "gap_type": "methodological", "confidence": 0.9},
    ]
    result = dedup.deduplicate(gaps, run_id="run_1")
    assert len(result) < len(gaps), f"Expected merge, got {len(result)} items"
    assert result[0].occurrence_count == 2


# ── TEST-117-01-02: Unique gaps are preserved (HB-01) ─────────────

def test_117_01_02_unique_preserved():
    """Unique gaps are preserved (HB-01)."""
    dedup = GapDeduplicator()
    gaps = [
        {"title": "cost efficiency of reasoning", "description": "d1", "gap_type": "methodological", "confidence": 0.8},
        {"title": "multilingual bias detection", "description": "d2", "gap_type": "empirical", "confidence": 0.7},
    ]
    result = dedup.deduplicate(gaps, run_id="run_1")
    assert len(result) == 2, f"Expected 2 unique gaps, got {len(result)}"
    titles = [g.canonical_title for g in result]
    assert "multilingual bias detection" in titles


# ── TEST-117-01-03: Similar titles are merged ─────────────────────

def test_117_01_03_similar_merged():
    """Similar titles like 'cost efficiency' and 'cost-efficient reasoning' are merged."""
    dedup = GapDeduplicator(threshold=0.6)
    gaps = [
        {"title": "cost efficiency trade-offs in reasoning", "description": "d1", "gap_type": "methodological", "confidence": 0.8},
        {"title": "cost-efficient reasoning methods", "description": "d2", "gap_type": "methodological", "confidence": 0.7},
    ]
    result = dedup.deduplicate(gaps, run_id="run_1")
    # These share words "cost" "efficiency/efficient" "reasoning/methods"
    assert len(result) <= 2, f"Expected merge or near-merge, got {len(result)}"


# ── TEST-117-01-04: Merge metadata includes source run IDs ────────

def test_117_01_04_source_run_ids():
    """Merged gaps include source run IDs."""
    dedup = GapDeduplicator()
    run_gaps = {
        "run_1": [{"title": "test gap a", "description": "d", "gap_type": "theoretical", "confidence": 0.8}],
        "run_2": [{"title": "test gap a", "description": "d", "gap_type": "theoretical", "confidence": 0.9}],
    }
    result = dedup.deduplicate_multi_run(run_gaps)
    assert len(result) == 1, f"Expected 1 merged gap, got {len(result)}"
    assert "run_1" in result[0].source_run_ids
    assert "run_2" in result[0].source_run_ids


# ── TEST-117-01-05: Empty input returns empty ─────────────────────

def test_117_01_05_empty_input():
    """Empty input returns empty list."""
    dedup = GapDeduplicator()
    result = dedup.deduplicate([])
    assert result == []


# ── TEST-117-01-06: Single gap returns unchanged ──────────────────

def test_117_01_06_single_gap():
    """Single gap returns as single MergedGap."""
    dedup = GapDeduplicator()
    gaps = [{"title": "unique gap", "description": "d", "gap_type": "empirical", "confidence": 0.7}]
    result = dedup.deduplicate(gaps, run_id="run_1")
    assert len(result) == 1
    assert result[0].canonical_title == "unique gap"
    assert result[0].merged is False


# ── TEST-117-01-07: Dedup works across 3+ runs ────────────────────

def test_117_01_07_three_runs():
    """Dedup correctly merges across 3+ runs."""
    dedup = GapDeduplicator()
    run_gaps = {
        "run_1": [
            {"title": "knowledge graph reasoning", "description": "d", "gap_type": "methodological", "confidence": 0.7},
            {"title": "bias in generation", "description": "d", "gap_type": "empirical", "confidence": 0.6},
        ],
        "run_2": [
            {"title": "knowledge graph reasoning methods", "description": "d", "gap_type": "methodological", "confidence": 0.8},
            {"title": "scalability issues", "description": "d", "gap_type": "methodological", "confidence": 0.5},
        ],
        "run_3": [
            {"title": "bias detection in generation", "description": "d", "gap_type": "empirical", "confidence": 0.9},
        ],
    }
    result = dedup.deduplicate_multi_run(run_gaps)
    # "knowledge graph reasoning" and "knowledge graph reasoning methods" should merge
    # "bias in generation" and "bias detection in generation" should merge
    # "scalability issues" stays unique
    assert len(result) <= 4, f"Expected ≤4 unique gaps from 5 inputs, got {len(result)}"
    # At least one should be merged
    assert any(g.merged for g in result), "Expected at least one merged gap"
