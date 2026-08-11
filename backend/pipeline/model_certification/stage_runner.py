"""Stage evaluation runner — executes eval cases and produces scorecards.

Flow:
    1. Load eval cases for a given stage (or all stages)
    2. Build prompt from case definitions
    3. Call the provider
    4. Capture raw output, parsed output, schema status, tokens, latency
    5. Run stage-specific scorer
    6. Run grounding scorer if requires_grounding
    7. Produce StageEvalResult per case
    8. Aggregate into StageScoreCard per stage
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.model_certification.eval_case import (
    StageEvalCase,
    load_all_suites,
    load_suite,
)
from backend.pipeline.model_certification.scorers.grounding import compute_grounding_metrics
from backend.pipeline.model_certification.stage_report import (
    StageScoreCard,
    compute_latency_percentiles,
)
from backend.pipeline.model_certification.stage_scorer import (
    ScorerRegistry,
    create_default_registry,
)

logger = logging.getLogger(__name__)


@dataclass
class StageEvalResult:
    """Result from a single stage eval case."""

    case_id: str
    stage: str
    model_id: str
    passed_schema: bool = False
    parsed_output: dict | None = None
    raw_output: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    grounding_metrics: dict[str, float] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    token_budget_violation: bool = False
    error: str | None = None


class StageEvalRunner:
    """Runs stage evaluation cases against a model."""

    def __init__(
        self,
        provider: Any,
        model_id: str,
        scorer_registry: ScorerRegistry | None = None,
        eval_dir: str | None = None,
    ) -> None:
        self._provider = provider
        self._model_id = model_id
        self._registry = scorer_registry or create_default_registry()
        self._eval_dir = eval_dir

    async def run_case(self, case: StageEvalCase) -> StageEvalResult:
        """Run a single eval case."""
        result = StageEvalResult(
            case_id=case.case_id,
            stage=case.stage,
            model_id=self._model_id,
        )

        gold = case.gold

        try:
            start = time.monotonic()
            response = await self._provider.complete(
                prompt=case.prompt_template,
                max_tokens=case.output_token_budget,
                temperature=0.3,
            )
            result.latency_seconds = time.monotonic() - start

            # Extract raw output
            if hasattr(response, "text"):
                result.raw_output = response.text
            elif isinstance(response, str):
                result.raw_output = response
            elif isinstance(response, dict):
                result.raw_output = response.get("text", str(response))
            else:
                result.raw_output = str(response)

            # Token estimation
            result.output_tokens = int(len(result.raw_output.split()) * 1.3)
            result.input_tokens = int(len(case.prompt_template.split()) * 1.3)

            # Token budget violation check
            if result.output_tokens > case.output_token_budget:
                result.token_budget_violation = True
                result.failures.append("Token budget violated")

            # Try parsing as JSON
            text = result.raw_output.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines:
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    result.parsed_output = parsed
                    result.passed_schema = True
            except json.JSONDecodeError:
                result.passed_schema = False

            # Run stage-specific scorer
            result.scores = self._registry.score(
                case.stage,
                result.raw_output,
                result.parsed_output,
                case,
                gold,
            )
            stage_failures = self._registry.failures(
                case.stage,
                result.raw_output,
                result.parsed_output,
                case,
                gold,
            )
            result.failures.extend(stage_failures)

            # Run grounding scorer if required
            if case.requires_grounding:
                result.grounding_metrics = compute_grounding_metrics(
                    result.raw_output, result.parsed_output, case, gold,
                )

        except Exception as e:
            result.error = str(e)[:200]

        return result

    async def run_stage(self, stage: str) -> list[StageEvalResult]:
        """Run all cases for a given stage."""
        if not self._eval_dir:
            return []
        cases = load_suite(stage, self._eval_dir)
        results = []
        for case in cases:
            result = await self.run_case(case)
            results.append(result)
        return results

    async def run_all(self) -> dict[str, list[StageEvalResult]]:
        """Run all available stage eval suites."""
        if not self._eval_dir:
            return {}
        suites = load_all_suites(self._eval_dir)
        all_results: dict[str, list[StageEvalResult]] = {}
        for stage, cases in suites.items():
            results = []
            for case in cases:
                result = await self.run_case(case)
                results.append(result)
            all_results[stage] = results
        return all_results


def aggregate_scorecards(
    results_by_stage: dict[str, list[StageEvalResult]],
) -> dict[str, StageScoreCard]:
    """Aggregate per-case results into per-stage scorecards."""
    cards = {}
    for stage, results in results_by_stage.items():
        if not results:
            continue

        cases_run = len(results)
        cases_passed = sum(1 for r in results if not r.error and not r.failures)

        # Schema valid rate
        schema_valid = sum(1 for r in results if r.passed_schema) / max(cases_run, 1)

        # Latency percentiles
        latencies = [r.latency_seconds for r in results if r.latency_seconds > 0]
        p50, p95 = compute_latency_percentiles(latencies)

        # Token budget violations
        budget_violations = sum(1 for r in results if r.token_budget_violation)
        budget_violation_rate = budget_violations / max(cases_run, 1)

        # Aggregate metrics (average across cases)
        all_metrics: dict[str, list[float]] = {}
        for r in results:
            for k, v in r.scores.items():
                all_metrics.setdefault(k, []).append(v)

        avg_metrics = {
            k: round(sum(vals) / len(vals), 3)
            for k, vals in all_metrics.items()
        }

        # Aggregate grounding metrics
        grounding_metrics: dict[str, list[float]] = {}
        for r in results:
            if r.grounding_metrics:
                for k, v in r.grounding_metrics.items():
                    grounding_metrics.setdefault(k, []).append(v)

        avg_grounding = {
            k: round(sum(vals) / len(vals), 3)
            for k, vals in grounding_metrics.items()
        }

        # Aggregate score
        all_scores = [v for r in results for v in r.scores.values()]
        aggregate = round(sum(all_scores) / max(len(all_scores), 1), 3)

        # Known failure modes (deduplicated)
        all_failures = list({f for r in results for f in r.failures})

        cards[stage] = StageScoreCard(
            stage=stage,
            cases_run=cases_run,
            cases_passed=cases_passed,
            aggregate_score=aggregate,
            schema_valid_rate=round(schema_valid, 3),
            latency_p50=round(p50, 3),
            latency_p95=round(p95, 3),
            token_budget_violation_rate=round(budget_violation_rate, 3),
            metrics=avg_metrics,
            grounding_metrics=avg_grounding,
            known_failure_modes=all_failures,
        )

    return cards
