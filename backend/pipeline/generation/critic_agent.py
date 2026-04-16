"""CriticAgent — evaluates ideas for weaknesses and prior art overlap."""

import logging
from pathlib import Path

from jinja2 import Template

from backend.pipeline.generation.error_taxonomy import ErrorTaxonomy
from backend.pipeline.generation.models import Critique, IdeaCandidate
from backend.pipeline.generation.strategies import CriticStrategy
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


class CriticAgent:
    def __init__(self, provider: LLMProvider, error_taxonomy: ErrorTaxonomy | None = None):
        self._provider = provider
        self._prompt_template = (PROMPT_DIR / "critic_system.md").read_text()
        self._error_taxonomy = error_taxonomy or ErrorTaxonomy()

    async def critique_ideas(
        self,
        ideas: list[IdeaCandidate],
        context_papers: list[Paper],
        strategy: CriticStrategy | None = None,
    ) -> list[Critique]:
        """Evaluate each idea for weaknesses and prior art overlap."""
        ideas_text = self._format_ideas(ideas)
        literature_context = self._format_literature(context_papers)
        error_focus = self._error_taxonomy.format_prompt_section()

        prompt = Template(self._prompt_template).render(
            ideas_text=ideas_text,
            literature_context=literature_context,
            strategy=strategy.value if strategy else None,
            error_focus=error_focus,
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are a rigorous AI/NLP research critic."},
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "critiques": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "idea_title": {"type": "string"},
                                    "strengths": {"type": "array", "items": {"type": "string"}},
                                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                                    "prior_art_concerns": {"type": "array", "items": {"type": "string"}},
                                    "feasibility_concerns": {"type": "array", "items": {"type": "string"}},
                                    "suggestions": {"type": "array", "items": {"type": "string"}},
                                    "overall_assessment": {"type": "string"},
                                },
                                "required": ["idea_title", "weaknesses", "suggestions"],
                            },
                        }
                    },
                    "required": ["critiques"],
                },
                temperature=0.3,
            )

            critiques = []
            for c in result.get("critiques", []):
                critique = Critique(
                    idea_title=c.get("idea_title", "Unknown"),
                    strengths=c.get("strengths", []),
                    weaknesses=c.get("weaknesses", []),
                    prior_art_concerns=c.get("prior_art_concerns", []),
                    feasibility_concerns=c.get("feasibility_concerns", []),
                    suggestions=c.get("suggestions", []),
                    overall_assessment=c.get("overall_assessment", ""),
                )
                critiques.append(critique)
                # Record error categories for future run weighting
                for weakness in critique.weaknesses:
                    category = self._error_taxonomy.classify(weakness)
                    if category:
                        self._error_taxonomy.record(category, weakness)
            return critiques

        except Exception as e:
            logger.error("CriticAgent failed: %s", e)
            return [Critique(idea_title=idea.title, overall_assessment=f"Critique failed: {e}") for idea in ideas]

    @staticmethod
    def _format_ideas(ideas: list[IdeaCandidate]) -> str:
        parts = []
        for i, idea in enumerate(ideas, 1):
            parts.append(
                f"### Idea {i}: {idea.title}\n"
                f"**Problem**: {idea.problem_statement}\n"
                f"**Method**: {idea.proposed_method}\n"
                f"**Contributions**: {idea.expected_contributions}\n"
                f"**Novelty**: {idea.novelty_rationale}\n"
                f"**Evaluation**: {idea.evaluation_approach}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _format_literature(papers: list[Paper]) -> str:
        lines = []
        for p in papers[:15]:
            abstract = (p.abstract or "")[:150]
            lines.append(f"- [{p.year or 'N/A'}] {p.title}: {abstract}...")
        return "\n".join(lines)
