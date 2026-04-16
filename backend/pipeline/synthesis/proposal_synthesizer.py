"""Proposal synthesis — generate structured research proposals."""

import logging

from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """Generate a complete, structured research proposal based on this refined idea.

## Research Idea:
Title: {title}
Problem: {problem}
Method: {method}
Contributions: {contributions}
Evaluation: {evaluation}

## Novelty Assessment:
{novelty_arguments}

## Feasibility:
Timeline: {timeline}
Key risks: {risks}

## Supporting Literature:
{literature}

Generate a research proposal with these sections:
1. **title** - Concise, descriptive title
2. **abstract** - 200-word summary
3. **introduction** - Problem context, motivation, and significance
4. **related_work** - Survey of relevant prior work with citations
5. **proposed_method** - Detailed methodology
6. **expected_contributions** - Specific, measurable contributions
7. **evaluation_plan** - Datasets, baselines, metrics, success criteria
8. **timeline** - 4-phase, 12-week breakdown
9. **references** - Key references as a list"""


class ResearchProposal:
    def __init__(self, idea_id: int | None = None, **sections):
        self.idea_id = idea_id
        self.sections = sections

    @property
    def title(self) -> str:
        return self.sections.get("title", "Untitled Proposal")

    @property
    def abstract(self) -> str:
        return self.sections.get("abstract", "")

    def to_markdown(self) -> str:
        """Convert proposal to Markdown format."""
        md_parts = []
        for key, value in self.sections.items():
            if key == "references":
                md_parts.append(f"## References\n")
                for ref in value if isinstance(value, list) else [value]:
                    md_parts.append(f"- {ref}")
            elif isinstance(value, str):
                header = key.replace("_", " ").title()
                md_parts.append(f"## {header}\n\n{value}")
        return "\n\n".join(md_parts)


class ProposalSynthesizer:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def synthesize(
        self,
        idea: ResearchIdea,
        novelty_report: NoveltyReport | None = None,
        feasibility_report: FeasibilityReport | None = None,
        supporting_papers: list[Paper] | None = None,
    ) -> ResearchProposal:
        """Generate a structured research proposal."""
        literature = self._format_literature(supporting_papers or [])
        prompt = SYNTHESIS_PROMPT.format(
            title=idea.title,
            problem=idea.problem_statement,
            method=idea.proposed_method,
            contributions=idea.expected_contributions,
            evaluation=idea.evaluation_approach,
            novelty_arguments=novelty_report.novelty_arguments if novelty_report else "Not assessed",
            timeline=feasibility_report.estimated_timeline if feasibility_report else "3-6 months",
            risks="; ".join(feasibility_report.key_risks) if feasibility_report else "Not assessed",
            literature=literature,
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You are an expert AI/NLP research proposal writer."},
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "abstract": {"type": "string"},
                        "introduction": {"type": "string"},
                        "related_work": {"type": "string"},
                        "proposed_method": {"type": "string"},
                        "expected_contributions": {"type": "string"},
                        "evaluation_plan": {"type": "string"},
                        "timeline": {"type": "string"},
                        "references": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "abstract", "introduction", "proposed_method"],
                },
                temperature=0.4,
            )
            return ResearchProposal(**result)

        except Exception as e:
            logger.error("Proposal synthesis failed: %s", e)
            return ResearchProposal(
                title=idea.title,
                abstract=idea.problem_statement,
                introduction="Synthesis failed. Manual writing required.",
                proposed_method=idea.proposed_method,
            )

    @staticmethod
    def _format_literature(papers: list[Paper]) -> str:
        if not papers:
            return "No specific supporting papers provided."
        lines = []
        for p in papers[:15]:
            authors = ", ".join(a.name for a in p.authors[:3])
            if len(p.authors) > 3:
                authors += " et al."
            lines.append(f"- {authors} ({p.year or 'n.d.'}). {p.title}. {p.venue or 'Unknown venue'}.")
        return "\n".join(lines)
