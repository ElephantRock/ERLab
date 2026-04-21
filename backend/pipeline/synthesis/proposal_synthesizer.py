"""Proposal synthesis — generate structured research proposals."""

import logging
from pathlib import Path

from jinja2 import Template

from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.literature.models import Paper
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


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
                md_parts.append("## References\n")
                for i, ref in enumerate(value if isinstance(value, list) else [value], 1):
                    if isinstance(ref, dict):
                        authors = ref.get("authors", "Unknown")
                        year = ref.get("year", "n.d.")
                        title = ref.get("title", "Untitled")
                        venue = ref.get("venue", "")
                        doi = ref.get("doi", "")
                        url = ref.get("url", "")
                        line = f"[{i}] {authors} ({year}). {title}."
                        if venue:
                            line += f" {venue}."
                        if doi:
                            line += f" DOI: {doi}"
                        elif url:
                            line += f" URL: {url}"
                        md_parts.append(line)
                    else:
                        md_parts.append(f"- {ref}")
            elif key == "evaluation_plan" and isinstance(value, dict):
                header = key.replace("_", " ").title()
                md_parts.append(f"## {header}\n")
                for sub_key, sub_val in value.items():
                    sub_header = sub_key.replace("_", " ").title()
                    if isinstance(sub_val, list):
                        md_parts.append(f"**{sub_header}**: " + ", ".join(str(v) for v in sub_val))
                    else:
                        md_parts.append(f"**{sub_header}**: {sub_val}")
            elif isinstance(value, str):
                header = key.replace("_", " ").title()
                md_parts.append(f"## {header}\n\n{value}")
            elif isinstance(value, dict):
                header = key.replace("_", " ").title()
                md_parts.append(f"## {header}\n")
                for sub_key, sub_val in value.items():
                    sub_header = sub_key.replace("_", " ").title()
                    md_parts.append(f"**{sub_header}**: {sub_val}")
        return "\n\n".join(md_parts)


class ProposalSynthesizer:
    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._prompt_template = (PROMPT_DIR / "synthesis_system.md").read_text()

    async def synthesize(
        self,
        idea: ResearchIdea,
        novelty_report: NoveltyReport | None = None,
        feasibility_report: FeasibilityReport | None = None,
        supporting_papers: list[Paper] | None = None,
        gaps: list | None = None,
    ) -> ResearchProposal:
        """Generate a structured research proposal."""
        literature = self._format_literature(supporting_papers or [])
        key_risks = feasibility_report.key_risks if feasibility_report else []

        gap_descriptions = ""
        if gaps:
            gap_lines = []
            for g in gaps[:8]:
                gap_lines.append(
                    f"- **{g.title}** (confidence: {g.confidence:.2f}, type: {g.gap_type}): "
                    f"{g.description}"
                )
            gap_descriptions = "\n".join(gap_lines)

        closest_matches = ""
        if novelty_report and novelty_report.closest_matches:
            match_lines = []
            for m in novelty_report.closest_matches[:5]:
                title = m.get("title", "Unknown")
                dist = m.get("distance", "N/A")
                abstract = m.get("abstract", "")
                line = f"- **{title}** (distance: {dist})"
                if abstract:
                    line += f"\n  Abstract: {abstract}"
                match_lines.append(line)
            closest_matches = "\n".join(match_lines)

        feasibility_reasoning = ""
        if feasibility_report:
            feasibility_reasoning = (
                f"Overall feasibility: {feasibility_report.overall_score:.1f}/10\n"
                f"Reasoning: {feasibility_report.reasoning}\n"
                f"Sub-scores: data={feasibility_report.data_availability:.1f}, "
                f"compute={feasibility_report.computational_requirements:.1f}, "
                f"methods={feasibility_report.methodological_complexity:.1f}, "
                f"eval={feasibility_report.evaluation_plan:.1f}, "
                f"novelty_grounding={feasibility_report.novelty_grounding:.1f}, "
                f"impact={feasibility_report.impact_potential:.1f}"
            )

        prompt = Template(self._prompt_template).render(
            title=idea.title,
            problem=idea.problem_statement,
            method=idea.proposed_method,
            contributions=idea.expected_contributions,
            evaluation=idea.evaluation_approach,
            novelty_arguments=novelty_report.novelty_arguments
            if novelty_report
            else "Not assessed",
            timeline=feasibility_report.estimated_timeline if feasibility_report else "3-6 months",
            risks="; ".join(key_risks) if key_risks else "Not assessed",
            key_risks=key_risks,
            literature=literature,
            gap_descriptions=gap_descriptions,
            closest_matches=closest_matches,
            feasibility_reasoning=feasibility_reasoning,
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert AI/NLP research proposal writer.",
                    },
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
                        "evaluation_plan": {
                            "type": "object",
                            "properties": {
                                "datasets": {"type": "array", "items": {"type": "string"}},
                                "baselines": {"type": "array", "items": {"type": "string"}},
                                "metrics": {"type": "array", "items": {"type": "string"}},
                                "ablation_design": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                        },
                        "timeline": {"type": "string"},
                        "references": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "authors": {"type": "string"},
                                    "year": {"type": "integer"},
                                    "title": {"type": "string"},
                                    "venue": {"type": "string"},
                                    "doi": {"type": "string"},
                                    "url": {"type": "string"},
                                },
                            },
                        },
                        "risk_mitigation": {"type": "string"},
                    },
                    "required": ["title", "abstract", "introduction", "proposed_method"],
                },
                temperature=0.4,
            )
            proposal = ResearchProposal(**result)

            # Quality gate — retry once if sections are too short
            if not self._check_quality(proposal)[0]:
                augmented_prompt = prompt + (
                    "\n\nIMPORTANT: Your previous attempt had sections that were too short. "
                    "Ensure abstract is at least 150 words, introduction at least 100 words, "
                    "and proposed_method at least 100 words."
                )
                try:
                    result2 = await self._provider.structured_output(
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert AI/NLP research proposal writer.",
                            },
                            {"role": "user", "content": augmented_prompt},
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
                                "evaluation_plan": {
                                    "type": "object",
                                    "properties": {
                                        "datasets": {"type": "array", "items": {"type": "string"}},
                                        "baselines": {"type": "array", "items": {"type": "string"}},
                                        "metrics": {"type": "array", "items": {"type": "string"}},
                                        "ablation_design": {"type": "string"},
                                        "summary": {"type": "string"},
                                    },
                                },
                                "timeline": {"type": "string"},
                                "references": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "authors": {"type": "string"},
                                            "year": {"type": "integer"},
                                            "title": {"type": "string"},
                                            "venue": {"type": "string"},
                                            "doi": {"type": "string"},
                                            "url": {"type": "string"},
                                        },
                                    },
                                },
                                "risk_mitigation": {"type": "string"},
                            },
                            "required": ["title", "abstract", "introduction", "proposed_method"],
                        },
                        temperature=0.4,
                    )
                    proposal2 = ResearchProposal(**result2)
                    if self._check_quality(proposal2)[0]:
                        return proposal2
                except Exception:
                    pass

            return proposal

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
            line = f"- {authors} ({p.year or 'n.d.'}). {p.title}. {p.venue or 'Unknown venue'}."
            if p.doi:
                line += f" DOI: {p.doi}."
            elif p.url:
                line += f" URL: {p.url}."
            if p.arxiv_id:
                line += f" arXiv: {p.arxiv_id}."
            if p.abstract:
                line += f"\n  Abstract: {p.abstract[:200]}"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _check_quality(proposal: ResearchProposal) -> tuple[bool, list[str]]:
        """Validate proposal section lengths. Returns (pass, issues)."""
        issues = []
        min_words = {"abstract": 50, "introduction": 100, "proposed_method": 100}
        for section, threshold in min_words.items():
            text = proposal.sections.get(section, "")
            if len(text.split()) < threshold:
                issues.append(f"{section} has fewer than {threshold} words")
        return len(issues) == 0, issues
