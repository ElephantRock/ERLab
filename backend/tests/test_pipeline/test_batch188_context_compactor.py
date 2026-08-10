"""Tests for BATCH-188: Context Auto-Compaction.

AIV §13: Tests verify behavior (proposal under budget, sections preserved).
"""


from backend.pipeline.synthesis.context_compactor import (
    compact_proposal,
    estimate_tokens,
    truncate_oversized,
)


class TestCompactProposal:
    """compact_proposal reduces oversized proposals."""

    def test_01_under_budget_unchanged(self):
        """Proposals under budget pass through unchanged."""
        text = "Short proposal content"
        result = compact_proposal(text, max_tokens=100_000)
        assert result == text

    def test_02_dict_under_budget_unchanged(self):
        """Dict proposals under budget pass through."""
        proposal = {"content": "Short", "title": "Test"}
        result = compact_proposal(proposal, max_tokens=100_000)
        assert result["content"] == "Short"

    def test_03_oversized_gets_compacted(self):
        """Oversized proposal gets compacted."""
        # Create a proposal over budget
        long_proposal = "# Title\n\n## Methodology\n" + "A" * 200_000
        result = compact_proposal(long_proposal, max_tokens=10_000)
        assert estimate_tokens(str(result)) <= 10_500  # some overhead

    def test_04_methodology_preserved(self):
        """Methodology section is preserved in full."""
        proposal = (
            "# Title\n\n"
            "## Background\n" + "X" * 50_000 + "\n\n"
            "## Methodology\nCore approach: transformer-based architecture with attention.\n\n"
            "## Evaluation\nBenchmark results.\n"
        )
        result = compact_proposal(proposal, max_tokens=5_000)
        assert "transformer-based" in str(result)

    def test_05_dict_oversized_compacted(self):
        """Dict proposal content gets compacted."""
        proposal = {"content": "A" * 200_000, "title": "Big Proposal"}
        result = compact_proposal(proposal, max_tokens=10_000)
        assert len(result["content"]) < 200_000

    def test_06_empty_proposal(self):
        """Empty proposal returns empty."""
        result = compact_proposal("", max_tokens=10_000)
        assert result == ""


class TestTruncateOversized:
    """truncate_oversized handles lists with large items."""

    def test_07_small_items_unchanged(self):
        items = ["small text", "another small text"]
        result = truncate_oversized(items, max_chars=1000)
        assert result == items

    def test_08_large_item_truncated(self):
        items = ["A" * 500_000]
        result = truncate_oversized(items, max_chars=100_000)
        assert len(result[0]) <= 100_100  # truncation marker overhead
        assert "truncated" in result[0]

    def test_09_dict_item_truncated(self):
        items = [{"content": "B" * 500_000, "title": "Big"}]
        result = truncate_oversized(items, max_chars=100_000)
        assert len(result[0]["content"]) <= 100_100
        assert result[0]["title"] == "Big"
