"""IdeatorAgent — generates raw research ideas from gaps and literature."""

import json
import logging
from pathlib import Path

from jinja2 import Template

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.models import IdeaCandidate
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


class IdeatorAgent:
    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._prompt_template = (PROMPT_DIR / "ideator_system.md").read_text()

    async def generate_ideas(
        self,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        prior_critique: list[str] | None = None,
        n_ideas: int = 3,
    ) -> list[IdeaCandidate]:
        """Generate raw research ideas informed by gaps and literature."""
        context = self._build_context(gaps, context_papers)
        critique_text = "\n\n".join(prior_critique) if prior_critique else None

        prompt = Template(self._prompt_template).render(
            n_ideas=n_ideas,
            context=context,
            prior_critique=critique_text,
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are an expert AI/NLP research ideation agent."},
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "ideas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "problem_statement": {"type": "string"},
                                    "proposed_method": {"type": "string"},
                                    "expected_contributions": {"type": "string"},
                                    "novelty_rationale": {"type": "string"},
                                    "evaluation_approach": {"type": "string"},
                                },
                                "required": ["title", "problem_statement", "proposed_method"],
                            },
                        }
                    },
                    "required": ["ideas"],
                },
                temperature=0.8,
            )

            ideas = []
            for item in result.get("ideas", []):
                ideas.append(IdeaCandidate(
                    title=item.get("title", "Untitled"),
                    problem_statement=item.get("problem_statement", ""),
                    proposed_method=item.get("proposed_method", ""),
                    expected_contributions=item.get("expected_contributions", ""),
                    novelty_rationale=item.get("novelty_rationale", ""),
                    evaluation_approach=item.get("evaluation_approach", ""),
                ))
            return ideas

        except Exception as e:
            logger.error("IdeatorAgent failed: %s", e)
            return []

    @staticmethod
    def _build_context(gaps: list[ResearchGap], papers: list[Paper]) -> str:
        parts = ["### Identified Research Gaps:"]
        for i, gap in enumerate(gaps, 1):
            parts.append(f"{i}. **{gap.title}** ({gap.gap_type})\n   {gap.description}\n   Impact: {gap.potential_impact}")

        parts.append("\n### Key Literature:")
        for p in papers[:20]:
            abstract = (p.abstract or "")[:150]
            parts.append(f"- [{p.year or 'N/A'}] {p.title}: {abstract}...")

        return "\n".join(parts)
