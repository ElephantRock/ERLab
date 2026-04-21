"""Lesson extraction from pipeline failures and underperforming runs."""

import logging

from backend.pipeline.result import PipelineResult
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

LESSON_PROMPT = """Analyze this pipeline run and extract lessons learned.

## Parameters used:
{params}

## Results:
- Total ideas: {total_ideas}
- Average score: {avg_score:.3f}
- Top idea score: {top_score:.3f}

## Identified Gaps:
{gaps_text}

## Top Ideas:
{ideas_text}

Extract 1-3 actionable lessons about what went wrong or could be improved.
Each lesson should be specific and prescriptive.

Respond with JSON: {{"lessons": [{{"lesson": "...", "category": "param_tuning|prompt_engineering|pipeline_structure|domain_strategy"}}]}}
"""


class LessonExtractor:
    """Extract lessons from failed or underperforming runs (AutoResearchClaw pattern)."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def extract(
        self,
        result: PipelineResult,
        params: dict,
    ) -> list[str]:
        """Extract lessons from a pipeline run. Returns list of lesson strings."""
        if not result.ideas:
            return ["No ideas generated — consider expanding search queries or reducing max_gaps."]

        avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
        top_score = max(i.score for i in result.ideas) if result.ideas else 0.0

        # Only extract lessons if performance is below average
        if avg_score > 0.7:
            return []

        gaps_text = "\n".join(f"- {g.title}: {g.description[:150]}" for g in result.gaps[:5])
        ideas_text = "\n".join(
            f"- {i.title} (score: {i.score:.2f})"
            for i in sorted(result.ideas, key=lambda x: x.score, reverse=True)[:5]
        )

        prompt = LESSON_PROMPT.format(
            params=params,
            total_ideas=len(result.ideas),
            avg_score=avg_score,
            top_score=top_score,
            gaps_text=gaps_text,
            ideas_text=ideas_text,
        )

        try:
            raw = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research pipeline improvement advisor.",
                    },
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "lessons": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "lesson": {"type": "string"},
                                    "category": {"type": "string"},
                                },
                                "required": ["lesson"],
                            },
                        }
                    },
                    "required": ["lessons"],
                },
            )

            return [lesson.get("lesson", "") for lesson in raw.get("lessons", []) if lesson.get("lesson")]

        except Exception as e:
            logger.error("Lesson extraction failed: %s", e)
            return []
