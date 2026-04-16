"""RefinerAgent — strengthens ideas based on critique feedback."""

import logging
from pathlib import Path

from jinja2 import Template

from backend.pipeline.generation.models import Critique, IdeaCandidate, ResearchIdea
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


class RefinerAgent:
    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._prompt_template = (PROMPT_DIR / "refiner_system.md").read_text()

    async def refine_ideas(
        self,
        ideas: list[IdeaCandidate],
        critiques: list[Critique],
        context_papers: list[Paper],
        round_num: int = 1,
    ) -> list[ResearchIdea]:
        """Produce refined, scored research ideas from the ideation-critique cycle."""
        original_ideas = self._format_ideas(ideas)
        critiques_text = self._format_critiques(critiques)
        literature_context = self._format_literature(context_papers)

        prompt = Template(self._prompt_template).render(
            original_ideas=original_ideas,
            critiques=critiques_text,
            literature_context=literature_context,
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are an expert AI/NLP research idea refiner."},
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
                                    "score": {"type": "number"},
                                    "supporting_papers": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": ["title", "problem_statement", "proposed_method"],
                            },
                        }
                    },
                    "required": ["ideas"],
                },
                temperature=0.5,
            )

            refined = []
            for item in result.get("ideas", []):
                refined.append(ResearchIdea(
                    title=item.get("title", "Untitled"),
                    problem_statement=item.get("problem_statement", ""),
                    proposed_method=item.get("proposed_method", ""),
                    expected_contributions=item.get("expected_contributions", ""),
                    novelty_rationale=item.get("novelty_rationale", ""),
                    evaluation_approach=item.get("evaluation_approach", ""),
                    round_generated=round_num,
                    score=min(1.0, max(0.0, item.get("score", 0.5))),
                    supporting_papers=item.get("supporting_papers", []),
                ))
            return sorted(refined, key=lambda r: r.score, reverse=True)

        except Exception as e:
            logger.error("RefinerAgent failed: %s", e)
            # Return unrefined ideas as fallback
            return [
                ResearchIdea(
                    title=idea.title,
                    problem_statement=idea.problem_statement,
                    proposed_method=idea.proposed_method,
                    expected_contributions=idea.expected_contributions,
                    novelty_rationale=idea.novelty_rationale,
                    evaluation_approach=idea.evaluation_approach,
                    round_generated=round_num,
                    score=0.3,
                )
                for idea in ideas
            ]

    @staticmethod
    def _format_ideas(ideas: list[IdeaCandidate]) -> str:
        parts = []
        for i, idea in enumerate(ideas, 1):
            parts.append(
                f"### Idea {i}: {idea.title}\n"
                f"Problem: {idea.problem_statement}\n"
                f"Method: {idea.proposed_method}\n"
                f"Contributions: {idea.expected_contributions}\n"
                f"Novelty: {idea.novelty_rationale}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _format_critiques(critiques: list[Critique]) -> str:
        parts = []
        for c in critiques:
            parts.append(
                f"### Critique of: {c.idea_title}\n"
                f"**Strengths**: {', '.join(c.strengths)}\n"
                f"**Weaknesses**: {', '.join(c.weaknesses)}\n"
                f"**Prior Art**: {', '.join(c.prior_art_concerns)}\n"
                f"**Feasibility**: {', '.join(c.feasibility_concerns)}\n"
                f"**Suggestions**: {', '.join(c.suggestions)}\n"
                f"**Assessment**: {c.overall_assessment}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _format_literature(papers: list[Paper]) -> str:
        lines = []
        for p in papers[:15]:
            lines.append(f"- [{p.id}] ({p.year or 'N/A'}) {p.title}")
        return "\n".join(lines)
