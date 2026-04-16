"""Feasibility scoring — evaluate practical viability of research ideas."""

import logging

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

FEASIBILITY_PROMPT = """You are a research feasibility evaluator. Assess the practical viability of this research idea.

## Research Idea:
Title: {title}
Problem: {problem}
Method: {method}
Contributions: {contributions}
Evaluation: {evaluation}

## Novelty Assessment:
Overall novelty: {novelty_score:.2f}
{novelty_arguments}

Score each dimension from 0 to 10:
1. **data_availability** (0-10): Are the required datasets publicly available or obtainable?
2. **computational_requirements** (0-10): Can this be done with reasonable compute (1-4 GPUs for <1 month)?
3. **methodological_complexity** (0-10): Can the methods be implemented in ~3 months by a small team?
4. **evaluation_plan** (0-10): Are the baselines and metrics well-defined and achievable?
5. **novelty_grounding** (0-10): Is the novelty claim defensible against existing work?
6. **impact_potential** (0-10): Expected citation potential and community interest?

Also provide:
- **overall_score**: Weighted average (data 20%, compute 15%, methods 20%, eval 20%, novelty 10%, impact 15%)
- **reasoning**: A paragraph explaining the scores
- **estimated_timeline**: Realistic timeline estimate (e.g., "3-6 months")
- **key_risks**: Top 2-3 risks that could prevent success"""


class FeasibilityReport:
    def __init__(
        self,
        overall_score: float,
        data_availability: float,
        computational_requirements: float,
        methodological_complexity: float,
        evaluation_plan: float,
        novelty_grounding: float,
        impact_potential: float,
        reasoning: str,
        estimated_timeline: str,
        key_risks: list[str],
    ):
        self.overall_score = overall_score
        self.data_availability = data_availability
        self.computational_requirements = computational_requirements
        self.methodological_complexity = methodological_complexity
        self.evaluation_plan = evaluation_plan
        self.novelty_grounding = novelty_grounding
        self.impact_potential = impact_potential
        self.reasoning = reasoning
        self.estimated_timeline = estimated_timeline
        self.key_risks = key_risks


class FeasibilityScorer:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def score_feasibility(
        self,
        idea: ResearchIdea,
        novelty_report: NoveltyReport | None = None,
    ) -> FeasibilityReport:
        """Evaluate idea feasibility across 6 dimensions."""
        prompt = FEASIBILITY_PROMPT.format(
            title=idea.title,
            problem=idea.problem_statement,
            method=idea.proposed_method,
            contributions=idea.expected_contributions,
            evaluation=idea.evaluation_approach,
            novelty_score=novelty_report.overall_score if novelty_report else 0.5,
            novelty_arguments=novelty_report.novelty_arguments if novelty_report else "Not assessed",
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are an expert research feasibility evaluator for AI/NLP projects."},
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "data_availability": {"type": "number"},
                        "computational_requirements": {"type": "number"},
                        "methodological_complexity": {"type": "number"},
                        "evaluation_plan": {"type": "number"},
                        "novelty_grounding": {"type": "number"},
                        "impact_potential": {"type": "number"},
                        "overall_score": {"type": "number"},
                        "reasoning": {"type": "string"},
                        "estimated_timeline": {"type": "string"},
                        "key_risks": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["overall_score", "reasoning"],
                },
                temperature=0.2,
            )

            return FeasibilityReport(
                overall_score=min(10, max(0, result.get("overall_score", 5.0))),
                data_availability=min(10, max(0, result.get("data_availability", 5.0))),
                computational_requirements=min(10, max(0, result.get("computational_requirements", 5.0))),
                methodological_complexity=min(10, max(0, result.get("methodological_complexity", 5.0))),
                evaluation_plan=min(10, max(0, result.get("evaluation_plan", 5.0))),
                novelty_grounding=min(10, max(0, result.get("novelty_grounding", 5.0))),
                impact_potential=min(10, max(0, result.get("impact_potential", 5.0))),
                reasoning=result.get("reasoning", ""),
                estimated_timeline=result.get("estimated_timeline", "Unknown"),
                key_risks=result.get("key_risks", []),
            )

        except Exception as e:
            logger.error("Feasibility scoring failed: %s", e)
            return FeasibilityReport(
                overall_score=5.0,
                data_availability=5.0,
                computational_requirements=5.0,
                methodological_complexity=5.0,
                evaluation_plan=5.0,
                novelty_grounding=5.0,
                impact_potential=5.0,
                reasoning=f"Scoring failed: {e}",
                estimated_timeline="Unknown",
                key_risks=["Scoring evaluation failed"],
            )
