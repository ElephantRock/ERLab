"""3-Tier Token Profiler — measures reasoning vs content token splits.

Profiles how a model divides its token budget between reasoning (thinking)
and content (actual output) across three difficulty tiers. This catches
the "thinking model emptiness" problem where a model burns all its tokens
in reasoning and produces zero content.

Metrics captured per tier:
  - pre_content_tokens: tokens spent reasoning before first content byte
  - content_tokens: tokens in the actual output
  - efficiency_ratio: content_tokens / total_tokens
  - finish_reason: "stop" (complete) or "length" (truncated)

The profiler also computes:
  - min_safe_max_tokens: minimum max_tokens to avoid truncation
  - peak_reasoning_observed: worst-case reasoning budget seen
  - recommended_buffer: extra tokens beyond peak for safety
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ── Prompts ───────────────────────────────────────────────────────

TIER1_PROMPT = (
    "Return exactly this JSON with no other text or explanation: "
    '{"status": "ok"}'
)

TIER1_SYSTEM = "You are a test harness. Follow instructions precisely."

TIER2_ABSTRACT = """We present a novel framework for retrieval-augmented generation
(RAG) that addresses the semantic gap between user queries and document chunks.
Our approach introduces a dynamic chunking mechanism that adjusts segment
boundaries based on query complexity, measured by token entropy and entity
density. We evaluate on three benchmarks: Natural Questions, TriviaQA, and a
custom scientific literature dataset of 10,000 papers. Results show that
adaptive chunking improves retrieval precision by 15.3% over fixed-size
chunking (p < 0.01) while reducing latency by 22%. We also find that
multi-hop queries benefit disproportionately from smaller, semantically
coherent chunks, with a 31% improvement in answer accuracy. The framework
integrates with existing RAG pipelines via a drop-in replacement for the
retriever component, requiring no retraining of the language model.
Our analysis reveals that the optimal chunk size varies by domain:
scientific abstracts perform best at 256 tokens, while legal documents
require 512-token segments for adequate context preservation."""

TIER2_PROMPT = (
    "Read the following academic abstract and extract the primary methodology "
    "as a 3-item JSON list of strings. Each string should be one key methodological step.\n\n"
    f"Abstract:\n{TIER2_ABSTRACT}\n\n"
    'Output format: ["step 1", "step 2", "step 3"]'
)

TIER3_PROMPT = (
    "Design a novel 4-step experimental framework to test the hypothesis that "
    "dynamic chunk sizing based on query complexity improves RAG retrieval "
    "accuracy. For each step, outline: (a) the objective, (b) the method, "
    "(c) at least one edge case to handle. Be specific and technical."
)


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class TierResult:
    """Result of a single tier test."""

    tier: int
    name: str
    prompt_description: str
    max_tokens_requested: int

    # Raw API metrics
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    prompt_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""

    # Derived metrics
    content_tokens: int = 0  # completion_tokens minus reasoning_tokens
    pre_content_tokens: int = 0  # alias for reasoning_tokens
    efficiency_ratio: float = 0.0  # content / total
    elapsed_seconds: float = 0.0

    # Output
    content: str = ""
    reasoning_content: str = ""

    # Diagnosis
    is_truncated: bool = False
    is_empty: bool = False

    @property
    def passed(self) -> bool:
        """A tier passes if it produced non-empty content and wasn't truncated."""
        return not self.is_empty and not self.is_truncated

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("content", None)  # Don't store full content in report
        d.pop("reasoning_content", None)
        return d


@dataclass
class TokenProfile:
    """Aggregated token profile across all tiers."""

    model_id: str
    profiled_at: str = ""
    engine: str = ""

    # Per-tier results
    tiers: list[TierResult] = field(default_factory=list)

    # Aggregated metrics
    avg_reasoning_overhead: int = 0
    peak_reasoning_observed: int = 0
    recommended_buffer: int = 200
    min_safe_max_tokens: int = 0

    # Capability flags
    supports_structured_json: bool = False
    requires_reasoning_budget: bool = False
    is_thinking_model: bool = False

    # Pipeline routing recommendations
    suitable_for_smoke_test: bool = False
    suitable_for_idea_generation: bool = False
    suitable_for_synthesis: bool = False

    @property
    def efficiency_ratio(self) -> float:
        """Overall efficiency: content tokens / total tokens across all tiers."""
        total_content = sum(t.content_tokens for t in self.tiers)
        total_all = sum(t.total_tokens for t in self.tiers)
        return total_content / total_all if total_all > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "profiled_at": self.profiled_at,
            "engine": self.engine,
            "capabilities": {
                "supports_structured_json": self.supports_structured_json,
                "requires_reasoning_budget": self.requires_reasoning_budget,
                "is_thinking_model": self.is_thinking_model,
            },
            "token_profile": {
                "avg_reasoning_overhead": self.avg_reasoning_overhead,
                "peak_reasoning_observed": self.peak_reasoning_observed,
                "recommended_buffer": self.recommended_buffer,
                "efficiency_ratio": round(self.efficiency_ratio, 3),
            },
            "pipeline_routing": {
                "suitable_for_smoke_test": self.suitable_for_smoke_test,
                "suitable_for_idea_generation": self.suitable_for_idea_generation,
                "suitable_for_synthesis": self.suitable_for_synthesis,
                "min_pipeline_max_tokens": self.min_safe_max_tokens,
            },
            "tier_details": [t.to_dict() for t in self.tiers],
        }


# ── Profiler ──────────────────────────────────────────────────────

class TokenProfiler:
    """Run 3-tier token profiling on a model via OpenAI-compatible API.

    Works with LM Studio, vLLM, and any OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        api_key: str = "lm-studio",
        timeout: float = 180.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def profile_model(self, model_id: str) -> TokenProfile:
        """Run all 3 tiers and return an aggregated profile.

        Args:
            model_id: Model identifier (e.g., "google/gemma-4-12b").

        Returns:
            TokenProfile with all metrics computed.
        """
        logger.info("Starting 3-tier token profiling for %s", model_id)
        profile = TokenProfile(
            model_id=model_id,
            profiled_at=datetime.now(UTC).isoformat(),
            engine=self._detect_engine(),
        )

        # Tier 1: Structure test (zero-reasoning)
        t1 = await self._run_tier(
            model_id=model_id,
            tier=1,
            name="structure_test",
            prompt_description="Return exact JSON, no reasoning",
            system=TIER1_SYSTEM,
            user_prompt=TIER1_PROMPT,
            max_tokens=2000,
            temperature=0.0,
        )
        profile.tiers.append(t1)
        logger.info(
            "Tier 1 (structure): reasoning=%d, content=%d, truncated=%s, empty=%s",
            t1.reasoning_tokens, t1.content_tokens, t1.is_truncated, t1.is_empty,
        )

        # Tier 2: Constrained extraction (low-reasoning)
        t2 = await self._run_tier(
            model_id=model_id,
            tier=2,
            name="constrained_extraction",
            prompt_description="Extract methodology from abstract into JSON list",
            system="You are a precise information extraction system.",
            user_prompt=TIER2_PROMPT,
            max_tokens=2000,
            temperature=0.1,
        )
        profile.tiers.append(t2)
        logger.info(
            "Tier 2 (extraction): reasoning=%d, content=%d, truncated=%s, empty=%s",
            t2.reasoning_tokens, t2.content_tokens, t2.is_truncated, t2.is_empty,
        )

        # Tier 3: Stress test (high-reasoning / synthesis)
        t3 = await self._run_tier(
            model_id=model_id,
            tier=3,
            name="synthesis_stress",
            prompt_description="Design 4-step experimental framework with edge cases",
            system="You are an expert research methodologist.",
            user_prompt=TIER3_PROMPT,
            max_tokens=4000,
            temperature=0.7,
        )
        profile.tiers.append(t3)
        logger.info(
            "Tier 3 (synthesis): reasoning=%d, content=%d, truncated=%s, empty=%s",
            t3.reasoning_tokens, t3.content_tokens, t3.is_truncated, t3.is_empty,
        )

        # Compute aggregated metrics
        self._compute_aggregates(profile)

        return profile

    async def _run_tier(
        self,
        model_id: str,
        tier: int,
        name: str,
        prompt_description: str,
        system: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> TierResult:
        """Run a single tier test."""
        result = TierResult(
            tier=tier,
            name=name,
            prompt_description=prompt_description,
            max_tokens_requested=max_tokens,
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json={
                        "model": model_id,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()

            result.elapsed_seconds = round(time.monotonic() - t0, 2)

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            usage = data.get("usage", {})

            # Parse token usage
            result.completion_tokens = usage.get("completion_tokens", 0)
            result.prompt_tokens = usage.get("prompt_tokens", 0)
            result.total_tokens = usage.get("total_tokens", 0)

            # Parse reasoning tokens (multiple detection strategies)
            completion_details = usage.get("completion_tokens_details", {})
            result.reasoning_tokens = completion_details.get("reasoning_tokens", 0)

            # Parse content
            result.content = message.get("content", "") or ""
            result.reasoning_content = message.get("reasoning_content", "") or ""
            result.finish_reason = choice.get("finish_reason", "")

            # If reasoning_tokens not in usage, try to infer
            if result.reasoning_tokens == 0:
                # Strategy 1: reasoning_content present (LIM after fix)
                if result.reasoning_content:
                    result.reasoning_tokens = len(result.reasoning_content) // 4
                # Strategy 2: completion_tokens >> content length suggests hidden reasoning
                elif result.content and result.completion_tokens > 0:
                    estimated_content_tokens = len(result.content) // 4
                    if result.completion_tokens > estimated_content_tokens * 2:
                        result.reasoning_tokens = result.completion_tokens - estimated_content_tokens

            # Compute derived metrics
            result.content_tokens = result.completion_tokens - result.reasoning_tokens
            result.pre_content_tokens = result.reasoning_tokens
            result.efficiency_ratio = (
                result.content_tokens / result.completion_tokens
                if result.completion_tokens > 0
                else 0.0
            )
            result.is_truncated = result.finish_reason == "length"
            result.is_empty = len(result.content.strip()) == 0

        except Exception as e:
            result.elapsed_seconds = round(time.monotonic() - t0, 2)
            result.finish_reason = f"error: {e}"
            result.is_empty = True
            logger.error("Tier %d failed: %s", tier, e)

        return result

    def _compute_aggregates(self, profile: TokenProfile) -> None:
        """Compute aggregated metrics from tier results."""
        tiers = profile.tiers
        if not tiers:
            return

        # Reasoning overhead
        reasoning_values = [t.reasoning_tokens for t in tiers if t.reasoning_tokens > 0]
        if reasoning_values:
            profile.avg_reasoning_overhead = int(sum(reasoning_values) / len(reasoning_values))
            profile.peak_reasoning_observed = max(reasoning_values)
        else:
            profile.avg_reasoning_overhead = 0
            profile.peak_reasoning_observed = 0

        # Determine if this is a thinking model
        profile.is_thinking_model = profile.peak_reasoning_observed > 100

        # Structured JSON support: Tier 1 or 2 must produce valid content
        t1, t2, t3 = tiers[0], tiers[1], tiers[2]
        profile.supports_structured_json = (
            (not t1.is_empty and "{" in t1.content)
            or (not t2.is_empty and "[" in t2.content)
        )

        # Min safe max_tokens: peak_reasoning + recommended_buffer + typical content
        # Typical content per pipeline stage: ~500-1000 tokens
        # Use Tier 3's content as the worst case content requirement
        tier3_content = t3.content_tokens if t3.content_tokens > 0 else 1000
        profile.min_safe_max_tokens = (
            profile.peak_reasoning_observed
            + profile.recommended_buffer
            + tier3_content
        )

        # If Tier 3 was truncated, we don't know the true peak.
        # Extrapolate: if it used all tokens and was truncated, estimate higher.
        if t3.is_truncated:
            profile.min_safe_max_tokens = max(
                profile.min_safe_max_tokens,
                t3.max_tokens_requested + 1000,
            )
            logger.warning(
                "Tier 3 was truncated at %d tokens — true reasoning peak unknown. "
                "min_safe_max_tokens set conservatively to %d",
                t3.max_tokens_requested,
                profile.min_safe_max_tokens,
            )

        # Stage suitability
        profile.requires_reasoning_budget = profile.is_thinking_model
        profile.suitable_for_smoke_test = not t1.is_empty
        profile.suitable_for_idea_generation = not t3.is_empty
        profile.suitable_for_synthesis = not t3.is_truncated and not t3.is_empty

    def _detect_engine(self) -> str:
        """Detect which engine we're talking to."""
        if "1234" in self._base_url:
            return "lmstudio"
        if "vllm" in self._base_url:
            return "vllm"
        return "openai-compatible"


def profile_to_capability_report(
    profile: TokenProfile,
    safe_context_window: int = 0,
) -> dict[str, Any]:
    """Convert a TokenProfile into a capability report dict.

    This extends the existing CapabilityReport schema with token profiling data
    that the CertifiedLookup system can read.
    """
    return {
        "model_id": profile.model_id,
        "profiled_at": profile.profiled_at,
        "eval_version": "0.3",
        "capabilities": {
            "supports_structured_json": profile.supports_structured_json,
            "requires_reasoning_budget": profile.requires_reasoning_budget,
            "is_thinking_model": profile.is_thinking_model,
        },
        "token_profile": {
            "avg_reasoning_overhead": profile.avg_reasoning_overhead,
            "peak_reasoning_observed": profile.peak_reasoning_observed,
            "recommended_buffer": profile.recommended_buffer,
            "efficiency_ratio": round(profile.efficiency_ratio, 3),
            "min_safe_max_tokens": profile.min_safe_max_tokens,
        },
        "pipeline_routing": {
            "suitable_for_smoke_test": profile.suitable_for_smoke_test,
            "suitable_for_idea_generation": profile.suitable_for_idea_generation,
            "suitable_for_synthesis": profile.suitable_for_synthesis,
            "min_pipeline_max_tokens": profile.min_safe_max_tokens,
        },
        "safe_context_window": safe_context_window,
        "safe_output_tokens": profile.min_safe_max_tokens,
        "tier_details": [t.to_dict() for t in profile.tiers],
    }
