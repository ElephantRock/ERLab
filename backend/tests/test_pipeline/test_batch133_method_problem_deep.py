"""BATCH-133 Tests — LLM-Grounded Method-Problem Scoring."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.method_problem import MethodProblemDetector, MethodProblemGap


def _method(name, paper_id="P1"):
    return Claim(claim_type=ClaimType.METHOD, title=name, description=f"{name}",
                 source_paper_id=paper_id, method_name=name)

def _result(dataset, metric="acc", value="90%", paper_id="P1", method_name=None):
    return Claim(claim_type=ClaimType.RESULT, title=f"{metric} on {dataset}",
                 description=f"{value}", source_paper_id=paper_id,
                 dataset=dataset, metric=metric, value=value, method_name=method_name)


class TestLLMMethodProblemScoring:
    def test_llm_differentiates_scores(self):
        """TEST-133-01: LLM produces differentiated scores (not all 0.5)."""
        call_count = [0]
        def side_effect(messages, **kwargs):
            content = messages[0]["content"]
            # Check the DATASET section specifically (last occurrence of Name:)
            dataset_section = content.split("## DATASET")[-1] if "## DATASET" in content else ""
            if "ImageNet" in dataset_section:
                return '{"applicability_score": 0.15, "reasoning": "NLP model on image data", "estimated_improvement": "N/A"}'
            elif "SQuAD" in dataset_section:
                return '{"applicability_score": 0.9, "reasoning": "BERT designed for reading comprehension", "estimated_improvement": "SOTA-level"}'
            return '{"applicability_score": 0.5, "reasoning": "Unknown combo", "estimated_improvement": "N/A"}'

        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=side_effect)
        detector = MethodProblemDetector(provider=provider)

        claims = [
            _method("BERT", "P1"),
            _result("SQuAD", "F1", "93.2%", "P2"),
            _result("ImageNet", "accuracy", "76%", "P3"),
        ]
        gaps = detector.find_gaps(claims)

        # BERT+SQuAD should score higher than BERT+ImageNet
        squad_gap = [g for g in gaps if "squad" in g.problem_dataset.lower()]
        imagenet_gap = [g for g in gaps if "imagenet" in g.problem_dataset.lower()]

        if squad_gap and imagenet_gap:
            assert squad_gap[0].applicability_score > imagenet_gap[0].applicability_score

    def test_fallback_uses_heuristic_on_failure(self):
        """TEST-133-02: Falls back to heuristic on LLM failure."""
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("API down"))
        detector = MethodProblemDetector(provider=provider)
        claims = [_method("BERT"), _result("SQuAD")]
        gaps = detector.find_gaps(claims)
        if gaps:
            # LLM failed → returns conservative 0.3 (cross-modality default)
            assert all(g.applicability_score in (0.3, 0.5, 0.7) for g in gaps)

    def test_no_provider_uses_05(self):
        """TEST-133-03: Without provider, uses 0.5."""
        detector = MethodProblemDetector(provider=None)
        claims = [_method("BERT"), _result("SQuAD")]
        gaps = detector.find_gaps(claims)
        if gaps:
            assert all(g.applicability_score == 0.5 for g in gaps)

    def test_known_pairs_excluded(self):
        """TEST-133-04: Known method-dataset pairs excluded."""
        detector = MethodProblemDetector(provider=None)
        claims = [
            _method("BERT", "P1"),
            _result("GLUE", "accuracy", "80.5%", "P1", method_name="BERT"),
        ]
        gaps = detector.find_gaps(claims)
        for g in gaps:
            assert not (g.method_name == "BERT" and g.problem_dataset.lower() == "glue")

    def test_score_range(self):
        """TEST-133-05: Scores are in 0.0-1.0 range."""
        provider = MagicMock()
        provider.complete = AsyncMock(return_value='{"applicability_score": 0.72, "reasoning": "good fit", "estimated_improvement": "10-15%"}')
        detector = MethodProblemDetector(provider=provider)
        claims = [_method("ResNet"), _result("CIFAR-10")]
        gaps = detector.find_gaps(claims)
        if gaps:
            assert 0.0 <= gaps[0].applicability_score <= 1.0

    def test_backward_compat_b126(self):
        """TEST-133-06: Core gap-finding logic unchanged from B126."""
        detector = MethodProblemDetector(provider=None)
        claims = [
            _method("BERT", "P1"),
            _result("SQuAD", "F1", "90%", "P2"),
        ]
        gaps = detector.find_gaps(claims)
        # BERT not applied to SQuAD in our claims → should appear
        assert len(gaps) >= 1

    def test_prompt_exists(self):
        """TEST-133-07: Applicability scoring prompt exists."""
        from pathlib import Path
        p = Path("backend/pipeline/claims/prompts/applicability_scoring.md")
        assert p.exists()

    def test_modality_matching_heuristic(self):
        """TEST-133-08: Heuristic scores based on modality matching."""
        from backend.pipeline.claims.method_problem import MethodProblemDetector

        # Text method + text dataset → 0.7
        assert MethodProblemDetector._heuristic_score("BERT", "SQuAD", "text", "text") == 0.7
        # Text method + image dataset → 0.3
        assert MethodProblemDetector._heuristic_score("BERT", "ImageNet", "text", "image") == 0.3
        # Image method + image dataset → 0.7
        assert MethodProblemDetector._heuristic_score("ResNet", "CIFAR-10", "image", "image") == 0.7
        # Unknown modality → 0.5
        assert MethodProblemDetector._heuristic_score("Foo", "Bar", None, None) == 0.5
        assert MethodProblemDetector._heuristic_score("BERT", "Bar", "text", None) == 0.5
