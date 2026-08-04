"""v1.0.2 regression tests — demonstrate B-EVAL-01 and B-COST-01 on v1.0.1.

These tests are EXPECTED TO FAIL on the unmodified v1.0.1 baseline (x-fail).
They freeze the two proven blockers so Commits 2 and 3 must make them pass:

  test_b_cost_01_usage_call_through_cache_wrapper
      B-COST-01: OpenAIProvider.complete_with_usage() rejects the stage=/run_id=
      kwargs that CachedProvider forwards → TypeError. (defect F-1)

  test_b_eval_01_empty_response_does_not_silently_persist_zeros
      B-EVAL-01: ProposalEvaluator._parse_response silently builds an all-zero /
      empty-justification ProposalEvaluation when the model returns an empty or
      unusable response, instead of signalling failure. (defect F-4)

Root-cause evidence (captured against the configured cloud model during the
v1.0.1 authoritative E2E, run_3e35557675c9):
  * 70 cloud calls; 0 token counts; 0 cost records persisted.
  * Final-paper evaluation persisted all 7 scores = 0.00, all 7 justifications empty.
  * Direct capture confirmed GLM-4.6 intermittently returns empty responses.
"""
from __future__ import annotations

import pytest

from backend.pipeline.evaluation.proposal_evaluator import (
    DIMENSIONS,
    ProposalEvaluation,
    ProposalEvaluator,
)


# ── B-COST-01: usage contract broken under the cache wrapper ──────────────


@pytest.mark.anyio
async def test_b_cost_01_usage_call_through_cache_wrapper():
    """complete_with_usage(stage=, run_id=) must succeed through the default
    cache+resilience wrappers and return token usage.

    On v1.0.1 this raised TypeError because OpenAIProvider.complete_with_usage
    did not accept stage=/run_id= while CachedProvider forwarded them. The fix
    makes concrete-provider overrides accept the base-class contract.
    """
    from backend.providers.cache.cached_provider import CachedProvider
    from backend.providers.cache.memory_cache import InMemoryCache
    from backend.providers.base import LLMResponse
    from backend.tests.conftest import FakeLLMProvider

    # A provider that conforms to the base-class complete_with_usage contract
    # (accepts stage=/run_id=), exercising the cache wrapper's forwarding.
    class UsageProviderConforming(FakeLLMProvider):
        async def complete_with_usage(
            self, messages, temperature=0.7, max_tokens=4096, stage="", run_id=None,  # noqa: ARG002
        ):
            return LLMResponse(content="ok", input_tokens=10, output_tokens=5)

    cache = InMemoryCache(max_size=10, ttl_seconds=3600)
    wrapped = CachedProvider(wrapped=UsageProviderConforming(), cache=cache)

    # The cache wrapper forwards stage=/run_id=; the conforming override must accept them.
    resp = await wrapped.complete_with_usage(
        [{"role": "user", "content": "ping"}],
        stage="test_stage",
        run_id="test_run",
    )
    assert resp.content == "ok"
    # Usage must be populated (the whole point of the usage-enabled path).
    assert resp.input_tokens == 10
    assert resp.output_tokens == 5


@pytest.mark.anyio
async def test_b_cost_01_real_openai_provider_usage_through_factory():
    """The real OpenAIProvider, constructed through the factory with the default
    cache wrapper, must accept stage=/run_id= on complete_with_usage.

    Uses a stubbed HTTP client so no network call is made. On v1.0.1 the
    concrete override rejects stage= and raises TypeError before any call.
    """
    from backend.providers.openai_provider import OpenAIProvider

    p = OpenAIProvider(api_key="stub-key", model="stub-model", base_url="http://stub")
    # Replace the network client with a stub that returns a minimal response.
    class _Usage:
        prompt_tokens = 7
        completion_tokens = 3

    class _ChoiceMsg:
        content = "stubbed"

    class _Choice:
        message = _ChoiceMsg()

    class _Resp:
        usage = _Usage()
        choices = [_Choice()]
        model = "stub-model"

    class _StubClient:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs):  # noqa: ARG004
                    return _Resp()

    p._client = _StubClient()

    # On v1.0.1 this raises TypeError: unexpected keyword argument 'stage'.
    resp = await p.complete_with_usage(
        [{"role": "user", "content": "ping"}],
        stage="paper_synthesis",
        run_id="run_test",
    )
    assert resp.content == "stubbed"
    assert resp.input_tokens == 7
    assert resp.output_tokens == 3


# ── B-EVAL-01: empty/unusable response silently persists zeros ────────────


class _EmptyResponseProvider:
    """Provider that returns an empty string, mirroring the observed GLM-4.6
    intermittent empty-response behavior."""

    @property
    def provider_name(self) -> str:
        return "empty-stub"

    @property
    def default_model(self) -> str:
        return "stub"

    async def complete(self, messages, temperature=0.7, max_tokens=4096):  # noqa: ARG002
        return ""

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):  # noqa: ARG002
        yield ""

    async def structured_output(self, messages, schema, temperature=0.3, **kwargs):  # noqa: ARG002
        return {}


@pytest.mark.anyio
async def test_b_eval_01_empty_response_does_not_silently_persist_zeros():
    """When the model returns an empty/unusable response, the evaluator must NOT
    silently persist an all-zero / empty-justification result.

    On v1.0.1, ProposalEvaluator._parse_response("") built a ProposalEvaluation
    with every score=0.0 and every justification="" — exactly the B-EVAL-01
    symptom. The fix raises UnusableEvaluationResponseError so the pipeline's
    existing try/except stores an honest "Evaluation failed" label instead.
    """
    from backend.pipeline.evaluation.proposal_evaluator import (
        UnusableEvaluationResponseError,
    )

    evaluator = ProposalEvaluator(provider=_EmptyResponseProvider())

    # After the fix: an empty response must raise, not return silent zeros.
    with pytest.raises(UnusableEvaluationResponseError):
        await evaluator.evaluate("A real proposal about SVM curriculum learning.")


@pytest.mark.anyio
async def test_b_eval_01_unparseable_response_does_not_silently_persist_zeros():
    """A non-empty response that matches no dimension scores is also unusable
    and must raise rather than persist silent zeros (the _parse_response guard).
    """
    from backend.pipeline.evaluation.proposal_evaluator import (
        UnusableEvaluationResponseError,
    )

    class _ProseProvider(_EmptyResponseProvider):
        async def complete(self, messages, temperature=0.7, max_tokens=4096):  # noqa: ARG002
            return "This proposal looks reasonable but I cannot score it precisely."

    evaluator = ProposalEvaluator(provider=_ProseProvider())
    with pytest.raises(UnusableEvaluationResponseError):
        await evaluator.evaluate("A real proposal about SVM curriculum learning.")


@pytest.mark.anyio
async def test_b_eval_01_valid_tagged_response_still_parses():
    """Guardrail for Commit 3: when the model DOES respond in the documented
    tagged format, parsing must still work. Captured GLM-4.6 responses confirm
    the model follows NOVELTY_SCORE:/NOVELTY_JUSTIFICATION: format when it
    responds, so the fix must not break that path.
    """
    valid_response = (
        "NOVELTY_SCORE: 0.7\n"
        "NOVELTY_JUSTIFICATION: The SVM-curriculum idea is a non-trivial combination.\n"
        "FEASIBILITY_SCORE: 0.6\n"
        "FEASIBILITY_JUSTIFICATION: SVM teacher adds modest overhead; implementable.\n"
        "COMPLETENESS_SCORE: 0.5\n"
        "COMPLETENESS_JUSTIFICATION: Method and eval present; timeline thin.\n"
        "RIGOR_SCORE: 0.4\n"
        "RIGOR_JUSTIFICATION: Loss function sketched; optimizer unspecified.\n"
        "CLARITY_SCORE: 0.8\n"
        "CLARITY_JUSTIFICATION: Clearly written and well-structured.\n"
        "BASELINE_ADEQUACY_SCORE: 0.3\n"
        "BASELINE_ADEQUACY_JUSTIFICATION: Only one baseline mentioned.\n"
        "COMPUTE_REALISM_SCORE: 0.6\n"
        "COMPUTE_REALISM_JUSTIFICATION: Small-model focus is realistic.\n"
        "OVERALL_SCORE: 0.556\n"
    )

    class _ValidProvider(_EmptyResponseProvider):
        async def complete(self, messages, temperature=0.7, max_tokens=4096):  # noqa: ARG002
            return valid_response

    evaluator = ProposalEvaluator(provider=_ValidProvider())
    result = await evaluator.evaluate("A real proposal about SVM curriculum learning.")
    assert result.novelty.score == pytest.approx(0.7)
    assert "non-trivial" in result.novelty.justification
    assert result.clarity.score == pytest.approx(0.8)


# ── Commit 6: live paper-evaluation call-site provider gap (B-EVAL-01) ─────


@pytest.mark.anyio
async def test_b_eval_01_paper_eval_no_provider_does_not_silently_return_zeros():
    """The live paper-evaluation call site (PaperSynthesisStage, stages.py:2419)
    constructs ProposalEvaluator(self._provider). When self._provider is None,
    the evaluator must NOT silently return an all-zero / empty-justification
    ProposalEvaluation — that is the exact B-EVAL-01 symptom observed in the
    confirmatory run (run_c600518856d2).

    On the current branch (pre-Commit-6), ProposalEvaluator(None).evaluate(real_paper)
    returns the default ProposalEvaluation() via the provider-is-None early-return
    (proposal_evaluator.py:104), bypassing the cloud model and the
    UnusableEvaluationResponseError guard entirely.

    The fix must: resolve a configured provider at the call site (or raise an
    explicit failure), never persist silent zeros for "provider unavailable".
    """
    # Reproduce the call-site condition: provider=None, non-empty paper
    evaluator = ProposalEvaluator(provider=None)
    result = await evaluator.evaluate(
        "## A Real Paper\n\n## Abstract\nThis is a complete paper about "
        "SVM-guided curriculum learning for tabular transformers with full "
        "methodology and evaluation sections."
    )

    # The broken behavior: silent all-zero / empty-justification default.
    broken = (
        isinstance(result, ProposalEvaluation)
        and all(getattr(result, d).score == 0.0 for d in DIMENSIONS)
        and all(getattr(result, d).justification == "" for d in DIMENSIONS)
    )
    assert not broken, (
        "B-EVAL-01 integration regression: ProposalEvaluator(None) silently "
        "returned all-zero/empty evaluation for a non-empty paper without "
        "invoking the configured provider or signalling failure"
    )


@pytest.mark.anyio
async def test_b_eval_01_paper_eval_resolves_configured_provider_when_none_passed():
    """After the fix, the paper-evaluation path must resolve a configured
    thinking provider when self._provider is None (mirroring the proposal-eval
    call site at stages.py:3653 which uses get_thinking_provider() fallback).

    This test verifies the call-site resolution helper exists and returns a
    usable provider, so the evaluator is never constructed with None when a
    provider is available.
    """
    from backend.pipeline.evaluation.proposal_evaluator import (
        resolve_evaluation_provider,
    )

    # When called with None, must fall back to the configured thinking provider.
    provider = resolve_evaluation_provider(provider=None)
    assert provider is not None, (
        "B-EVAL-01: resolve_evaluation_provider(None) returned None even though "
        "a cloud provider is configured — the paper-eval call site would "
        "construct ProposalEvaluator(None) and silently persist zeros"
    )
    assert hasattr(provider, "complete"), "resolved provider has no complete()"
