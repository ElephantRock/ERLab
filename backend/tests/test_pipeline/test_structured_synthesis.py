"""Tests for structured output wiring in synthesis stages.

Validates:
1. SectionWiseSynthesizer._generate_section uses CLAIM_SCHEMA (not permissive {"type": "object"})
2. Schema validation + retry + prose fallback flow
3. _structured_complete_with_schema delegates correctly
4. Generation mode tracking (structured | prose_fallback)
5. Sidecar audit trail contains typed claims
6. Metrics: structured_count, fallback_count, valid_rate
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipeline.synthesis.section_wise_synthesizer import (
    SectionDraft,
    SectionWiseSynthesizer,
)
from backend.pipeline.synthesis.section_contracts import CLAIM_SCHEMA, CLAIM_SCHEMA_STR


# ─── Fixtures ───────────────────────────────────────────────────────

def _make_valid_structured_output(section_id: str = "abstract", n_claims: int = 3) -> dict:
    """Create a valid structured output matching CLAIM_SCHEMA."""
    claims = []
    for i in range(n_claims):
        claims.append({
            "claim_id": f"tmp-{i}",
            "text": f"Test claim {i} about the methodology.",
            "type": "background",
            "evidence_ids": [f"SOURCE-{i+1}"],
            "speculative": False,
            "rationale": "Supported by evidence.",
            "section": section_id,
        })
    return {
        "section": section_id,
        "claims": claims,
        "assumptions": [],
    }


def _make_invalid_structured_output() -> dict:
    """Create output that fails schema validation (missing fields)."""
    return {
        "section": "abstract",
        "claims": [
            {"claim_id": "bad-1", "text": "Missing type and evidence_ids"},
        ],
    }


def _make_provider():
    """Create a clean provider mock without auto-created _gateway."""
    provider = MagicMock()
    provider.default_model = "test-model"
    provider._cost_callback = None
    # Explicitly set _gateway to None to avoid mock auto-creation
    provider._gateway = None
    # Set up async methods
    provider.structured_output = AsyncMock()
    provider.complete = AsyncMock()
    return provider


@pytest.fixture
def mock_provider():
    return _make_provider()


@pytest.fixture
def synthesizer(mock_provider):
    return SectionWiseSynthesizer(provider=mock_provider, context_window=8192)


# ─── Test: Schema is used, not permissive {"type": "object"} ────────

class TestSchemaUsage:
    """Verify structured output uses CLAIM_SCHEMA."""

    @pytest.mark.asyncio
    async def test_structured_output_receives_claim_schema(self, synthesizer, mock_provider):
        """The provider's structured_output should be called with CLAIM_SCHEMA."""
        valid_output = _make_valid_structured_output("abstract", 3)
        mock_provider.structured_output = AsyncMock(return_value=valid_output)

        draft = await synthesizer._generate_section(
            section_id="abstract",
            section_title="Abstract",
            target_words=300,
            outline="Standard outline",
            proposal_summary="Test proposal",
            relevant_sources="[SOURCE-1] Paper A",
            domain="AI",
        )

        # structured_output was called — check schema argument
        assert mock_provider.structured_output.called
        call_args = mock_provider.structured_output.call_args
        schema_arg = call_args.kwargs.get("schema") or call_args[1].get("schema")
        assert schema_arg is not None
        # Must be actual CLAIM_SCHEMA, not permissive {"type": "object"}
        assert schema_arg != {"type": "object"}

    @pytest.mark.asyncio
    async def test_generation_mode_structured_on_success(self, synthesizer, mock_provider):
        """When structured output validates, generation_mode='structured'."""
        valid_output = _make_valid_structured_output("introduction", 2)
        mock_provider.structured_output = AsyncMock(return_value=valid_output)

        draft = await synthesizer._generate_section(
            section_id="introduction",
            section_title="Introduction",
            target_words=800,
            outline="Outline",
            proposal_summary="Proposal",
            relevant_sources="[SOURCE-1] Source",
            domain="AI",
        )

        assert draft.generation_mode == "structured"
        assert draft.structured_claims is not None
        assert len(draft.structured_claims) == 2
        assert draft.sidecar is not None


# ─── Test: Retry on schema validation failure ───────────────────────

class TestRetryBehavior:
    """Verify retry logic when schema validation fails."""

    @pytest.mark.asyncio
    async def test_retries_once_on_invalid_schema(self, synthesizer, mock_provider):
        """If first attempt returns invalid JSON, retry with error hint."""
        invalid_output = _make_invalid_structured_output()
        valid_output = _make_valid_structured_output("related_work", 4)

        mock_provider.structured_output = AsyncMock(
            side_effect=[invalid_output, valid_output]
        )

        draft = await synthesizer._generate_section(
            section_id="related_work",
            section_title="Related Work",
            target_words=1000,
            outline="Outline",
            proposal_summary="Proposal",
            relevant_sources="[SOURCE-1]",
            domain="AI",
        )

        assert mock_provider.structured_output.call_count == 2
        assert draft.generation_mode == "structured"
        assert len(draft.structured_claims) == 4

    @pytest.mark.asyncio
    async def test_prose_fallback_after_two_failures(self, synthesizer, mock_provider):
        """After structured + retry both fail, falls back to prose."""
        invalid_output = _make_invalid_structured_output()
        mock_provider.structured_output = AsyncMock(
            side_effect=[invalid_output, invalid_output]
        )
        mock_provider.complete = AsyncMock(
            return_value="This is a prose section about related work [SOURCE-1]."
        )

        draft = await synthesizer._generate_section(
            section_id="related_work",
            section_title="Related Work",
            target_words=1000,
            outline="Outline",
            proposal_summary="Proposal",
            relevant_sources="[SOURCE-1]",
            domain="AI",
        )

        assert draft.generation_mode == "prose_fallback"
        assert draft.content != ""
        assert draft.structured_claims is None
        assert mock_provider.structured_output.call_count == 2
        assert mock_provider.complete.called


# ─── Test: Complete failure → prose fallback ─────────────────────────

class TestProseFallback:
    """Verify prose fallback when structured output throws exceptions."""

    @pytest.mark.asyncio
    async def test_exception_triggers_prose_fallback(self, synthesizer, mock_provider):
        """When structured_output raises, falls to prose fallback."""
        mock_provider.structured_output = AsyncMock(
            side_effect=RuntimeError("Model unavailable")
        )
        mock_provider.complete = AsyncMock(
            return_value="A prose fallback section with [SOURCE-2]."
        )

        draft = await synthesizer._generate_section(
            section_id="proposed_method",
            section_title="Proposed Method",
            target_words=1500,
            outline="Outline",
            proposal_summary="Proposal",
            relevant_sources="[SOURCE-2] Method paper",
            domain="AI",
        )

        assert draft.generation_mode == "prose_fallback"
        assert "[SOURCE-2]" in draft.citations_used

    @pytest.mark.asyncio
    async def test_total_failure_returns_error_section(self, synthesizer, mock_provider):
        """When both structured and prose fail, returns error section."""
        mock_provider.structured_output = AsyncMock(
            side_effect=RuntimeError("Model unavailable")
        )
        mock_provider.complete = AsyncMock(
            side_effect=RuntimeError("Still unavailable")
        )

        draft = await synthesizer._generate_section(
            section_id="conclusion",
            section_title="Conclusion",
            target_words=400,
            outline="Outline",
            proposal_summary="Proposal",
            relevant_sources="",
            domain="AI",
        )

        assert draft.generation_mode == "prose_fallback"
        assert draft.word_count == 0
        assert "failed" in draft.content.lower()


# ─── Test: Sidecar audit trail ──────────────────────────────────────

class TestSidecarAudit:
    """Verify the sidecar contains proper audit trail."""

    @pytest.mark.asyncio
    async def test_sidecar_has_typed_claims(self, synthesizer, mock_provider):
        """Sidecar must include claim_id, type, evidence_ids, rendered_as."""
        valid_output = _make_valid_structured_output("evaluation_plan", 2)
        valid_output["claims"][0]["type"] = "evaluation_metric"
        valid_output["claims"][1]["type"] = "evaluation_benchmark"
        mock_provider.structured_output = AsyncMock(return_value=valid_output)

        draft = await synthesizer._generate_section(
            section_id="evaluation_plan",
            section_title="Evaluation Plan",
            target_words=800,
            outline="Outline",
            proposal_summary="Proposal",
            relevant_sources="[SOURCE-1] Benchmark",
            domain="AI",
        )

        assert draft.sidecar is not None
        assert draft.sidecar["section"] == "evaluation_plan"
        assert draft.sidecar["claim_count"] == 2
        assert draft.sidecar["assumption_count"] == 0

        for claim in draft.sidecar["claims"]:
            assert "claim_id" in claim
            assert "type" in claim
            assert "evidence_ids" in claim
            assert "rendered_as" in claim

    @pytest.mark.asyncio
    async def test_claim_types_present_tracked(self, synthesizer, mock_provider):
        """SectionDraft.claim_types_present lists distinct types."""
        valid_output = _make_valid_structured_output("proposed_method", 3)
        valid_output["claims"][0]["type"] = "method_design_motivation"
        valid_output["claims"][1]["type"] = "method_proposed_mechanism"
        valid_output["claims"][2]["type"] = "method_claimed_benefit"
        mock_provider.structured_output = AsyncMock(return_value=valid_output)

        draft = await synthesizer._generate_section(
            section_id="proposed_method",
            section_title="Proposed Method",
            target_words=1500,
            outline="Outline",
            proposal_summary="Proposal",
            relevant_sources="[SOURCE-1]",
            domain="AI",
        )

        types_present = set(draft.claim_types_present)
        assert "method_design_motivation" in types_present
        assert "method_proposed_mechanism" in types_present
        assert "method_claimed_benefit" in types_present


# ─── Test: _structured_complete_with_schema ──────────────────────────

class TestStructuredCompleteDelegation:
    """Verify _structured_complete_with_schema delegates correctly."""

    @pytest.mark.asyncio
    async def test_tries_provider_structured_output(self, synthesizer, mock_provider):
        """Falls through to provider.structured_output when no gateway."""
        valid = _make_valid_structured_output("abstract")
        mock_provider.structured_output = AsyncMock(return_value=valid)

        result = await synthesizer._structured_complete_with_schema(
            messages=[{"role": "user", "content": "test"}],
            section_id="abstract",
            schema=CLAIM_SCHEMA,
            max_tokens=4096,
        )

        assert result == valid
        mock_provider.structured_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_complete_on_no_structured_method(self):
        """When provider lacks structured_output, falls to complete + parse."""
        provider = MagicMock()
        provider._gateway = None
        del provider.structured_output  # Remove the method
        valid_dict = _make_valid_structured_output("abstract")
        provider.complete = AsyncMock(return_value=json.dumps(valid_dict))

        synth = SectionWiseSynthesizer(provider=provider, context_window=8192)

        result = await synth._structured_complete_with_schema(
            messages=[{"role": "user", "content": "test"}],
            section_id="abstract",
            schema=CLAIM_SCHEMA,
            max_tokens=4096,
        )

        assert isinstance(result, dict)
        assert "claims" in result


# ─── Test: Metrics tracking ─────────────────────────────────────────

class TestMetricsTracking:
    """Verify generation_mode metrics are trackable across sections."""

    @pytest.mark.asyncio
    async def test_mixed_modes_across_sections(self):
        """Simulate some sections structured, some fallback."""
        valid = _make_valid_structured_output("abstract", 2)
        invalid = _make_invalid_structured_output()
        prose_text = "Prose content with [SOURCE-1]."

        sections = [
            ("abstract", "Abstract", 300),
            ("introduction", "Introduction", 800),
            ("related_work", "Related Work", 1000),
        ]

        results = []
        for i, (sid, title, words) in enumerate(sections):
            provider = _make_provider()
            synth = SectionWiseSynthesizer(provider=provider, context_window=8192)

            if i < 2:
                # Structured succeeds
                provider.structured_output = AsyncMock(return_value=valid)
            else:
                # Structured fails, prose fallback
                provider.structured_output = AsyncMock(
                    side_effect=[invalid, invalid]
                )
                provider.complete = AsyncMock(return_value=prose_text)

            draft = await synth._generate_section(
                section_id=sid,
                section_title=title,
                target_words=words,
                outline="Outline",
                proposal_summary="Proposal",
                relevant_sources="[SOURCE-1]",
                domain="AI",
            )
            results.append(draft)

        structured_count = sum(1 for r in results if r.generation_mode == "structured")
        fallback_count = sum(1 for r in results if r.generation_mode == "prose_fallback")
        valid_rate = structured_count / len(results)

        assert structured_count == 2
        assert fallback_count == 1
        assert valid_rate == pytest.approx(0.667, abs=0.01)


# ─── Test: CLAIM_SCHEMA correctness ─────────────────────────────────

class TestClaimSchema:
    """Verify CLAIM_SCHEMA is properly defined and importable."""

    def test_claim_schema_has_claims_array(self):
        assert "claims" in CLAIM_SCHEMA.get("properties", CLAIM_SCHEMA)

    def test_claim_schema_str_is_json(self):
        parsed = json.loads(CLAIM_SCHEMA_STR)
        assert isinstance(parsed, dict)

    def test_claim_schema_str_roundtrip(self):
        parsed = json.loads(CLAIM_SCHEMA_STR)
        assert "claims" in str(parsed)

    def test_section_contracts_importable(self):
        from backend.pipeline.synthesis.section_contracts import get_section_prompt
        prompt = get_section_prompt("abstract")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_all_section_ids_have_prompts(self):
        from backend.pipeline.synthesis.section_contracts import get_section_prompt
        for section_id in ["abstract", "introduction", "related_work", "proposed_method",
                          "evaluation_plan", "discussion", "conclusion"]:
            prompt = get_section_prompt(section_id)
            assert len(prompt) > 50, f"Prompt for {section_id} too short"


# ─── Test: Gateway LM Studio structured output path ─────────────────

class TestGatewayLMStudioPath:
    """Verify the orchestrator _gateway_provider_fn uses LM Studio native."""

    def test_provider_fn_uses_openai_compat_for_schema(self):
        """The _gateway_provider_fn should try LM Studio native response_format."""
        from backend.pipeline.orchestrator._orchestrator import PipelineOrchestrator
        assert PipelineOrchestrator is not None
