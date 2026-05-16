"""Tests for ContextCompiler, OutputValidator, and DegradedResult."""

import pytest

from backend.pipeline.gateway.token_budget import TokenBudgeter
from backend.pipeline.gateway.context_compiler import ContextCompiler, CompiledPrompt
from backend.pipeline.gateway.validator import OutputValidator
from backend.pipeline.gateway.degraded_result import DegradedResult, degraded_score, degraded_pass


# ── ContextCompiler ──────────────────────────────────────────────────────────

class TestContextCompiler:
    def _make_compiler(self, context=4096):
        return ContextCompiler(TokenBudgeter(default_context=context))

    def test_full_prompt_fits(self):
        compiler = self._make_compiler(8192)
        compiled = compiler.compile(
            instructions="Generate a proposal",
            evidence=["Paper 1 abstract", "Paper 2 abstract"],
            max_output_tokens=2048,
            context_window=8192,
        )
        assert compiled.strategy_used == "full"
        assert compiled.budget.fits
        assert len(compiled.messages) >= 2  # system + at least one user message

    def test_evidence_truncation(self):
        compiler = self._make_compiler(2048)
        # Lots of evidence that won't fit
        evidence = ["x" * 500 for _ in range(20)]  # ~2600 tokens just in evidence
        compiled = compiler.compile(
            instructions="Short task",
            evidence=evidence,
            max_output_tokens=512,
            context_window=2048,
        )
        # Should have truncated
        assert compiled.evidence_dropped > 0
        assert compiled.strategy_used in ("truncated", "truncated+reduced_output", "aggressive_truncate", "emergency")

    def test_no_evidence_fits_easily(self):
        compiler = self._make_compiler(4096)
        compiled = compiler.compile(
            instructions="Simple task",
            evidence=[],
            max_output_tokens=256,
            context_window=4096,
        )
        assert compiled.strategy_used == "full"
        assert compiled.budget.fits

    def test_estimate_evidence_budget(self):
        compiler = self._make_compiler(8192)
        budget = compiler.estimate_evidence_budget(
            instructions="Short instruction",
            current_artifact="",
            max_output_tokens=2048,
            context_window=8192,
        )
        # Should be able to fit several evidence items
        assert budget >= 5

    def test_emergency_mode(self):
        compiler = self._make_compiler(512)
        compiled = compiler.compile(
            instructions="x" * 300,  # Most of the context
            evidence=["y" * 200] * 10,  # Way too much
            max_output_tokens=256,
            context_window=512,
        )
        # Should have dropped most evidence and found some strategy
        assert compiled.evidence_dropped > 0 or compiled.strategy_used == "emergency"
        assert compiled.budget.fits or compiled.strategy_used == "emergency"


# ── OutputValidator ──────────────────────────────────────────────────────────

class TestOutputValidator:
    def test_valid_structured_output(self):
        v = OutputValidator()
        result = v.validate_structured({"field": "value"})
        assert result.valid
        assert result.confidence_penalty == 0.0

    def test_missing_required_field(self):
        v = OutputValidator()
        schema = {"required": ["name", "score"], "properties": {}}
        result = v.validate_structured({"name": "test"}, schema=schema)
        assert not result.valid
        assert any("score" in w for w in result.warnings)

    def test_score_clamping(self):
        v = OutputValidator()
        result = v.validate_structured({"similarity": -0.38})
        assert result.content["similarity"] == 0.0  # clamped
        assert result.was_repaired
        assert result.confidence_penalty > 0

    def test_score_clamping_upper(self):
        v = OutputValidator()
        result = v.validate_structured({"similarity": 3.41})
        assert result.content["similarity"] == 1.0
        assert result.was_repaired

    def test_empty_text_output(self):
        v = OutputValidator()
        result = v.validate_text("")
        assert not result.valid
        assert result.confidence_penalty == 0.5

    def test_valid_text_output(self):
        v = OutputValidator()
        result = v.validate_text("This is a valid response with enough content.")
        assert result.valid

    def test_citation_validation(self):
        v = OutputValidator()
        text = "As shown in [1] and [3], but [5] and (Smith, 2024) are suspicious."
        valid_ids = {"1", "3", "PAPER_014"}
        valid, invalid = v.validate_citations(text, valid_ids)
        assert "[1]" in valid
        assert "[3]" in valid
        assert "[5]" in invalid

    def test_json_repair_code_fence(self):
        v = OutputValidator()
        text = '```json\n{"key": "value"}\n```'
        parsed, repairs = v.repair_json(text)
        assert parsed == {"key": "value"}
        assert "code fence" in repairs[0]

    def test_json_repair_trailing_comma(self):
        v = OutputValidator()
        text = '{"key": "value",}'
        parsed, repairs = v.repair_json(text)
        assert parsed == {"key": "value"}
        assert "trailing" in repairs[0].lower()

    def test_json_repair_missing_bracket(self):
        v = OutputValidator()
        text = '{"key": "value"'
        parsed, repairs = v.repair_json(text)
        assert parsed == {"key": "value"}
        assert "brace" in repairs[0].lower()

    def test_json_repair_unrepairable(self):
        v = OutputValidator()
        text = "this is not json at all"
        parsed, repairs = v.repair_json(text)
        assert parsed is None


# ── DegradedResult ──────────────────────────────────────────────────────────

class TestDegradedResult:
    def test_degraded_score(self):
        result = degraded_score(default=0.5, reason="LLM failed", error="timeout")
        assert result.value == 0.5
        assert result.confidence == 0.0
        assert result.is_degraded
        assert result.requires_review

    def test_degraded_pass(self):
        result = degraded_pass(reason="reflection failed")
        assert result.value is True
        assert result.confidence == 0.0
        assert result.requires_review

    def test_to_dict(self):
        result = degraded_score(reason="test")
        d = result.to_dict()
        assert d["degraded"] is True
        assert d["confidence"] == 0.0
        assert d["reason"] == "test"

    def test_not_fake_perfect(self):
        """Degraded results should never claim high confidence."""
        result = degraded_score()
        assert result.confidence == 0.0
        assert result.value != 1.0  # not fake-perfect
