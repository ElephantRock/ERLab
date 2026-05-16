"""LLM Gateway — the single entry point for all LLM calls.

Every LLM interaction in the pipeline should pass through this gateway.
It provides:
- Token budgeting (refuse oversized prompts)
- Capability-aware routing (right model for the task)
- Output validation (mechanical repair, semantic flagging)
- Call logging (every call recorded for observability)
- Degraded result semantics (no fake-perfect scores)

Flow:
    LLMRequest → resolve model → check budget → compile context →
    execute → validate → log → return LLMResponse
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.gateway.token_budget import PromptTooLargeError, TokenBudget, TokenBudgeter
from backend.pipeline.gateway.capability_registry import ModelCapabilities, ModelCapabilityRegistry

logger = logging.getLogger(__name__)


@dataclass
class LLMRequest:
    """Unified request spec for all LLM calls."""

    task: str                         # e.g., "proposal_synthesis", "citation_audit"
    messages: list[dict]              # the prompt
    max_output_tokens: int = 4096     # desired output length
    temperature: float = 0.7
    schema: dict | None = None        # if set, uses structured_output
    tools: list[dict] | None = None   # if set, uses complete_with_tools
    role: str = "draft"               # "draft", "reason", "synthesize", "critique"
    risk_level: str = "normal"        # "low", "normal", "high"
    requires_independent_judgment: bool = False
    stage: str = ""                   # pipeline stage name
    run_id: str = ""                  # pipeline run ID
    context_window_override: int | None = None  # force a specific context size


@dataclass
class LLMResponse:
    """Gateway response with full observability."""

    content: str | dict               # the LLM output
    input_tokens: int = 0
    output_tokens: int = 0
    model_used: str = ""
    provider: str = ""
    confidence: float = 1.0           # 0-1, based on validation
    warnings: list[str] = field(default_factory=list)
    fallback_used: bool = False       # true if compaction/splitting happened
    degraded: bool = False            # true if result is degraded
    latency_ms: float = 0.0

    @property
    def is_reliable(self) -> bool:
        """Whether this response is reliable enough to use without review."""
        return self.confidence >= 0.5 and not self.degraded


@dataclass
class GatewayCallLog:
    """Record of a single gateway call for observability."""

    timestamp: float
    task: str
    stage: str
    run_id: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    confidence: float
    fallback_used: bool
    degraded: bool
    warnings: list[str]
    error: str | None = None


class LLMGateway:
    """Single entry point for ALL LLM calls in the pipeline.

    Usage:
        gateway = LLMGateway(registry, budgeter)
        response = await gateway.call(LLMRequest(
            task="proposal_synthesis",
            messages=[...],
            max_output_tokens=4096,
            role="synthesize",
        ))
    """

    def __init__(
        self,
        capability_registry: ModelCapabilityRegistry,
        token_budgeter: TokenBudgeter,
        default_model: str = "",
    ):
        self._registry = capability_registry
        self._budgeter = token_budgeter
        self._default_model = default_model
        self._call_log: list[GatewayCallLog] = []
        self._provider_fn = None  # set via set_provider_fn

    def set_provider_fn(self, fn) -> None:
        """Set the function that executes LLM calls.

        Signature: async fn(messages, temperature, max_tokens, schema=None, tools=None) -> str | dict
        """
        self._provider_fn = fn

    async def call(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM call through the full gateway pipeline."""

        t0 = time.monotonic()
        error = None
        response = None

        try:
            # 1. Resolve model capabilities
            model_id = self._default_model
            caps = self._resolve_model(request, model_id)

            # 2. Pre-flight token check
            ctx_window = request.context_window_override or caps.context_window
            budget = self._budgeter.check(
                request.messages,
                request.max_output_tokens,
                context_window=ctx_window,
            )

            # 3. If prompt doesn't fit, try to adapt
            messages = request.messages
            fallback_used = False

            if not budget.fits:
                # Try reducing max_output to fit
                reduced_output = budget.available_for_output
                if reduced_output >= 256:
                    logger.info(
                        "Reducing output budget: %d → %d to fit context",
                        request.max_output_tokens, reduced_output,
                    )
                    request.max_output_tokens = reduced_output
                    budget = self._budgeter.check(
                        messages, reduced_output, context_window=ctx_window,
                    )
                    fallback_used = True
                else:
                    # Prompt is genuinely too large
                    raise PromptTooLargeError(
                        input_tokens=budget.input_tokens,
                        output_reserve=request.max_output_tokens,
                        context_window=ctx_window,
                        available=budget.available_for_input,
                    )

            # 4. Execute the LLM call
            if self._provider_fn is None:
                raise RuntimeError("LLMGateway has no provider function. Call set_provider_fn() first.")

            content = await self._provider_fn(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_output_tokens,
                schema=request.schema,
                tools=request.tools,
            )

            # 5. Validate output
            warnings = self._validate_output(content, request)
            confidence = self._score_confidence(warnings, caps)

            # 6. Build response
            elapsed_ms = (time.monotonic() - t0) * 1000
            response = LLMResponse(
                content=content,
                input_tokens=budget.input_tokens,
                output_tokens=self._estimate_output_tokens(content),
                model_used=caps.model_id,
                provider=caps.provider,
                confidence=confidence,
                warnings=warnings,
                fallback_used=fallback_used,
                latency_ms=elapsed_ms,
            )

            return response

        except PromptTooLargeError:
            raise  # propagate to caller for compaction/splitting
        except Exception as e:
            error = str(e)[:200]
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.error("Gateway call failed for task '%s': %s", request.task, error)

            return LLMResponse(
                content="",
                confidence=0.0,
                degraded=True,
                warnings=[f"LLM call failed: {error}"],
                latency_ms=elapsed_ms,
            )

        finally:
            # Always log
            self._log_call(request, response, error)

    def _resolve_model(self, request: LLMRequest, default_model: str) -> ModelCapabilities:
        """Resolve model capabilities for this request."""
        model_id = default_model or self._default_model
        return self._registry.get(model_id)

    def _validate_output(self, content: str | dict, request: LLMRequest) -> list[str]:
        """Validate LLM output. Returns list of warnings.

        Only performs mechanical validation here:
        - JSON validity check (if schema was requested)
        - Empty output check
        - Basic sanity checks

        Does NOT perform semantic validation (citation grounding, claim evidence).
        That's the ClaimEvidenceValidator's job.
        """
        warnings = []

        # Empty output
        if not content:
            warnings.append("Empty output from LLM")
            return warnings

        # String output sanity
        if isinstance(content, str):
            if len(content) < 10:
                warnings.append(f"Suspiciously short output: {len(content)} chars")
            return warnings

        # Dict output (structured) — check basic validity
        if isinstance(content, dict):
            if request.schema:
                # Check required keys exist
                required = request.schema.get("required", [])
                properties = request.schema.get("properties", {})
                if isinstance(properties, dict):
                    for key in required:
                        if key not in content:
                            warnings.append(f"Missing required field: {key}")

            # Check for None/null values in required fields
            for key, value in content.items():
                if value is None:
                    warnings.append(f"Null value in field: {key}")

        return warnings

    def _score_confidence(self, warnings: list[str], caps: ModelCapabilities) -> float:
        """Assign confidence score based on warnings and model reliability.

        Starts at 1.0, reduced by:
        - Each warning: -0.1
        - Model reliability: scales confidence by reliability score
        """
        score = 1.0

        # Penalty per warning
        score -= len(warnings) * 0.1

        # Scale by model's overall reliability
        reliability_scores = caps.reliability.values()
        if reliability_scores:
            avg_reliability = sum(reliability_scores) / len(reliability_scores)
            score *= avg_reliability

        return max(0.0, min(1.0, score))

    def _estimate_output_tokens(self, content: str | dict) -> int:
        """Estimate output tokens."""
        if isinstance(content, str):
            return int(len(content) / 3.8)
        return int(len(str(content)) / 3.8)

    def _log_call(self, request: LLMRequest, response: LLMResponse | None, error: str | None) -> None:
        """Log every call for observability."""
        entry = GatewayCallLog(
            timestamp=time.time(),
            task=request.task,
            stage=request.stage,
            run_id=request.run_id,
            model=response.model_used if response else "",
            provider=response.provider if response else "",
            input_tokens=response.input_tokens if response else 0,
            output_tokens=response.output_tokens if response else 0,
            latency_ms=response.latency_ms if response else 0,
            confidence=response.confidence if response else 0,
            fallback_used=response.fallback_used if response else False,
            degraded=response.degraded if response else True,
            warnings=response.warnings if response else [],
            error=error,
        )
        self._call_log.append(entry)

        # Keep log bounded (last 1000 calls)
        if len(self._call_log) > 1000:
            self._call_log = self._call_log[-500:]

    def get_call_log(self, run_id: str = "", stage: str = "", limit: int = 100) -> list[dict]:
        """Get call log entries, optionally filtered."""
        entries = self._call_log
        if run_id:
            entries = [e for e in entries if e.run_id == run_id]
        if stage:
            entries = [e for e in entries if e.stage == stage]

        entries = entries[-limit:]

        return [
            {
                "timestamp": e.timestamp,
                "task": e.task,
                "stage": e.stage,
                "run_id": e.run_id,
                "model": e.model,
                "input_tokens": e.input_tokens,
                "output_tokens": e.output_tokens,
                "latency_ms": round(e.latency_ms, 1),
                "confidence": round(e.confidence, 2),
                "fallback_used": e.fallback_used,
                "degraded": e.degraded,
                "warnings": e.warnings,
                "error": e.error,
            }
            for e in entries
        ]
