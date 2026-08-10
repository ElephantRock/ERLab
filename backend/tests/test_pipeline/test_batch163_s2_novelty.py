"""BATCH-163: Semantic Scholar Novelty Verification.

TASK-01: S2NoveltyVerifier (6 tests)
TASK-02: NoveltyChecker S2 augmentation (4 tests)
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock


class TestS2NoveltyVerifier:

    def test_01_no_s2_returns_unknown(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
        verifier = S2NoveltyVerifier(s2_source=None)
        result = asyncio.run(verifier.verify("Test idea"))
        assert result.llm_verdict == "unknown"

    def test_02_no_papers_means_novel(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
        mock_s2 = MagicMock()
        mock_s2.search = AsyncMock(return_value=[])
        verifier = S2NoveltyVerifier(s2_source=mock_s2, cooldown=0)
        result = asyncio.run(verifier.verify("Novel idea"))
        assert result.llm_verdict == "novel"
        assert result.novelty_score == 1.0

    def test_03_papers_without_llm_uses_heuristic(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
        mock_s2 = MagicMock()
        paper = MagicMock(title="Similar Paper")
        mock_s2.search = AsyncMock(return_value=[paper])
        verifier = S2NoveltyVerifier(s2_source=mock_s2, llm_provider=None, cooldown=0)
        result = asyncio.run(verifier.verify("Test idea"))
        assert result.s2_papers_found == 1
        assert result.novelty_score < 1.0

    def test_04_llm_verdict_novel(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
        mock_s2 = MagicMock()
        paper = MagicMock(title="Old Paper")
        mock_s2.search = AsyncMock(return_value=[paper])
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="VERDICT: novel\nJUSTIFICATION: Different approach")
        verifier = S2NoveltyVerifier(s2_source=mock_s2, llm_provider=mock_llm, cooldown=0)
        result = asyncio.run(verifier.verify("New idea"))
        assert result.llm_verdict == "novel"
        assert result.novelty_score == 0.9

    def test_05_llm_verdict_not_novel(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
        mock_s2 = MagicMock()
        paper = MagicMock(title="Existing Paper")
        mock_s2.search = AsyncMock(return_value=[paper])
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="VERDICT: not_novel\nJUSTIFICATION: Already done")
        verifier = S2NoveltyVerifier(s2_source=mock_s2, llm_provider=mock_llm, cooldown=0)
        result = asyncio.run(verifier.verify("Old idea"))
        assert result.llm_verdict == "not_novel"
        assert result.novelty_score == 0.1

    def test_06_parse_verdict_fallback(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
        assert S2NoveltyVerifier._parse_verdict("gibberish response") == "unknown"
        assert S2NoveltyVerifier._parse_verdict("VERDICT: novel") == "novel"
        assert S2NoveltyVerifier._parse_verdict("VERDICT: partially_novel") == "partially_novel"
        assert S2NoveltyVerifier._parse_verdict("VERDICT: not_novel") == "not_novel"

    def test_07_s2_search_failure_graceful(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
        mock_s2 = MagicMock()
        mock_s2.search = AsyncMock(side_effect=Exception("API down"))
        verifier = S2NoveltyVerifier(s2_source=mock_s2)
        result = asyncio.run(verifier.verify("Test idea"))
        assert "error" in result.justification.lower() or result.llm_verdict == "unknown"

    def test_08_verdict_to_score_mapping(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyVerifier
        assert S2NoveltyVerifier._verdict_to_score("novel") == 0.9
        assert S2NoveltyVerifier._verdict_to_score("partially_novel") == 0.5
        assert S2NoveltyVerifier._verdict_to_score("not_novel") == 0.1
        assert S2NoveltyVerifier._verdict_to_score("unknown") == 0.5

    def test_09_s2_verifier_in_novelty_package(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyResult, S2NoveltyVerifier
        assert S2NoveltyVerifier is not None
        assert S2NoveltyResult is not None

    def test_10_s2_result_dataclass_fields(self):
        from backend.pipeline.novelty.s2_verifier import S2NoveltyResult
        r = S2NoveltyResult(idea_title="Test", s2_papers_found=3)
        assert r.idea_title == "Test"
        assert r.s2_papers_found == 3
        assert r.prior_art_titles == []
        assert r.llm_verdict == "unknown"
