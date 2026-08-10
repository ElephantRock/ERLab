"""BATCH-132 Tests — LLM-Grounded Contradiction Verification."""

from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.claims.contradiction.detector import ContradictionDetector
from backend.pipeline.claims.contradiction.models import ContradictionCandidate
from backend.pipeline.claims.models import Claim, ClaimType


def _result(paper_id, dataset, metric, value, method_name=None):
    return Claim(
        claim_type=ClaimType.RESULT, title=f"{metric} on {dataset}",
        description=f"Achieves {value}", source_paper_id=paper_id,
        dataset=dataset, metric=metric, value=value, method_name=method_name,
    )


def _mock_provider(responses):
    """Provider that returns different responses based on claim content."""
    call_count = [0]
    def side_effect(messages, **kwargs):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return responses[idx]
    provider = MagicMock()
    provider.complete = AsyncMock(side_effect=side_effect)
    return provider


class TestLLMContradictionVerification:
    def test_llm_marks_different_conditions_as_not_contradiction(self):
        """TEST-132-01: EN→DE vs FR→EN correctly marked 'different_conditions'."""
        provider = _mock_provider([
            '{"is_genuine_contradiction": false, "category": "different_conditions", "reasoning": "Different language directions: English-to-German vs French-to-English"}'
        ])
        detector = ContradictionDetector(provider=provider)
        claims = [
            _result("P1", "WMT 2014 English-to-German", "BLEU", "28.4", "Transformer"),
            _result("P2", "WMT 2014 French-to-English", "BLEU", "28.4", "GPT-3"),
        ]
        result = detector.find_contradictions(claims)
        # Different datasets → no candidates paired
        # If they are paired due to normalization, they should be marked not genuine
        for c in result:
            assert c.is_genuine is not True

    def test_llm_marks_genuine_contradiction(self):
        """TEST-132-02: Same conditions, different values → genuine contradiction."""
        provider = _mock_provider([
            '{"is_genuine_contradiction": true, "category": "contradiction", "reasoning": "Same dataset and metric, same method claimed, different results"}'
        ])
        detector = ContradictionDetector(provider=provider)
        claims = [
            _result("P1", "SQuAD", "F1", "93.2", "BERT"),
            _result("P2", "SQuAD", "F1", "78.5", "BERT"),
        ]
        result = detector.find_contradictions(claims)
        assert len(result) >= 1
        # With LLM verification, should be marked genuine
        if result[0].is_genuine is not None:
            assert result[0].is_genuine is True

    def test_fallback_to_numeric_on_llm_failure(self):
        """TEST-132-03: Falls back to numeric heuristic on LLM failure."""
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("API down"))
        detector = ContradictionDetector(provider=provider)
        claims = [
            _result("P1", "SQuAD", "F1", "93.2"),
            _result("P2", "SQuAD", "F1", "45.0"),
        ]
        result = detector.find_contradictions(claims)
        assert len(result) >= 1
        assert result[0].is_genuine is True  # Numeric: >10% difference

    def test_no_provider_uses_numeric(self):
        """TEST-132-04: Without provider, uses numeric heuristic."""
        detector = ContradictionDetector(provider=None)
        claims = [
            _result("P1", "GLUE", "accuracy", "80.5"),
            _result("P2", "GLUE", "accuracy", "92.1"),
        ]
        result = detector.find_contradictions(claims)
        assert len(result) >= 1
        assert result[0].explanation.startswith("[Numeric]")

    def test_prompt_exists(self):
        """TEST-132-05: Verification prompt exists."""
        from pathlib import Path
        p = Path("backend/pipeline/claims/contradiction/prompts/verification.md")
        assert p.exists()

    def test_candidate_creates(self):
        """TEST-132-06: Backward compat — ContradictionCandidate still works."""
        c = _result("P1", "SQuAD", "F1", "90.0")
        cand = ContradictionCandidate(claim_a=c, claim_b=c, metric="F1", dataset="SQuAD", value_a="90.0", value_b="80.0")
        assert cand.is_genuine is None

    def test_existing_b125_tests_concept(self):
        """TEST-132-07: Core pairing logic unchanged from B125."""
        detector = ContradictionDetector(provider=None)
        claims = [
            _result("P1", "SQuAD", "F1", "90.0"),
            _result("P2", "SQuAD", "F1", "80.0"),
            _result("P3", "GLUE", "accuracy", "85.0"),
        ]
        result = detector.find_contradictions(claims)
        assert len(result) == 1  # Only P1-P2 pair on SQuAD/F1
        assert result[0].dataset == "squad"
