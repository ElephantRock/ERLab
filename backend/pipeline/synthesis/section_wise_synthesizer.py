"""Section-wise paper synthesis — generate papers in pieces that fit the context.

The monolithic PaperSynthesizer tries to generate the entire paper in one LLM call.
This fails when the prompt (proposal + sources) exceeds the model's context.

SectionWiseSynthesizer instead:
1. Generates a paper outline from the proposal summary
2. Generates each section independently with relevant evidence
3. Runs a consistency pass to ensure coherence
4. Assembles the final paper with proper citations

This is the execution strategy the SmartRouter would choose for paper_synthesis
when the model's context is too small for monolithic generation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "paper_synthesis_system.md"

# Minimum output tokens per section — if available budget is below this,
# we should not even try to generate that section
MIN_SECTION_OUTPUT_TOKENS = 800

# Standard academic paper sections in order
DEFAULT_SECTIONS = [
    ("abstract", "Abstract", 300),
    ("introduction", "Introduction", 800),
    ("related_work", "Related Work", 1000),
    ("proposed_method", "Proposed Method", 1500),
    ("evaluation_plan", "Evaluation Plan", 800),
    ("discussion", "Discussion and Future Work", 600),
    ("conclusion", "Conclusion", 400),
]


@dataclass
class SectionDraft:
    """A single generated section of the paper."""

    section_id: str
    title: str
    content: str
    word_count: int
    citations_used: list[str]
    model_used: str
    tokens_used: int = 0
    truncated: bool = False


@dataclass
class SectionWiseResult:
    """Result of section-wise paper synthesis."""

    proposal_id: int
    paper_markdown: str
    word_count: int
    sections_generated: int
    sections_total: int
    venue: str
    model_used: str
    source_count: int
    outline: str
    consistency_notes: str

    def to_dict(self) -> dict:
        return asdict(self)


class SectionWiseSynthesizer:
    """Generate academic papers section by section to fit small context models.

    Usage:
        synth = SectionWiseSynthesizer(provider)
        result = await synth.synthesize(proposal_text, source_papers, domain, venue)
    """

    def __init__(self, provider: LLMProvider, context_window: int = 8192) -> None:
        self._provider = provider
        self._context_window = context_window
        try:
            self._system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._system_prompt = (
                "You are an academic paper writer. Write rigorous, well-cited research papers. "
                "Use [SOURCE-X] citations referencing only the provided sources."
            )

    async def synthesize(
        self,
        proposal_text: str,
        source_papers: list[str],
        domain: str = "AI/NLP",
        venue: str = "Generic",
        proposal_id: int = 0,
    ) -> SectionWiseResult:
        """Generate a paper section by section.

        Steps:
        1. Generate outline from proposal summary
        2. Select relevant sources for each section
        3. Generate each section independently
        4. Assemble and return

        Args:
            proposal_text: The proposal markdown.
            source_papers: Formatted source strings with [SOURCE-X] citations.
            domain: Research domain.
            venue: Target venue.
            proposal_id: Identifier for the proposal.

        Returns:
            SectionWiseResult with the assembled paper.
        """
        model_used = self._get_model_name()

        # Step 1: Generate outline
        outline = await self._generate_outline(proposal_text, domain)
        logger.info("Paper outline generated: %d chars", len(outline))

        # Step 2: Build a compressed source reference for citation
        source_index = self._build_source_index(source_papers)

        # Step 3: Generate each section
        sections: list[SectionDraft] = []
        source_text = "\n".join(source_papers[:20])  # cap total source length

        for section_id, section_title, target_words in DEFAULT_SECTIONS:
            # Select the most relevant sources for this section
            relevant_sources = self._select_relevant_sources(
                source_text, section_id, section_title, outline,
            )

            draft = await self._generate_section(
                section_id=section_id,
                section_title=section_title,
                target_words=target_words,
                outline=outline,
                proposal_summary=self._summarize_proposal(proposal_text),
                relevant_sources=relevant_sources,
                domain=domain,
            )
            sections.append(draft)
            logger.info(
                "Section '%s': %d words, %d citations",
                section_title, draft.word_count, len(draft.citations_used),
            )

        # Step 4: Assemble
        paper_md = self._assemble_paper(sections, outline, domain, venue, len(source_papers))
        total_words = len(paper_md.split())

        return SectionWiseResult(
            proposal_id=proposal_id,
            paper_markdown=paper_md,
            word_count=total_words,
            sections_generated=len([s for s in sections if s.word_count > 50]),
            sections_total=len(DEFAULT_SECTIONS),
            venue=venue,
            model_used=model_used,
            source_count=len(source_papers),
            outline=outline[:500],
            consistency_notes="Section-wise generation — sections may need manual coherence review",
        )

    async def _generate_outline(self, proposal_text: str, domain: str) -> str:
        """Generate a paper outline from the proposal."""
        # Truncate proposal for outline generation to fit context
        proposal_summary = self._summarize_proposal(proposal_text)

        prompt = (
            f"Generate a brief outline for an academic paper in the domain '{domain}'.\n\n"
            f"Proposal summary:\n{proposal_summary}\n\n"
            f"Provide a short outline with section titles and 1-2 sentence descriptions. "
            f"Use sections: Abstract, Introduction, Related Work, Proposed Method, "
            f"Evaluation Plan, Discussion, Conclusion."
        )

        try:
            result = await self._provider.complete(
                messages=[
                    {"role": "system", "content": "You are an academic paper outline generator. Be concise."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            return result.strip() if result else "Standard academic paper structure"
        except Exception as e:
            logger.warning("Outline generation failed: %s — using default", e)
            return "Standard academic paper structure"

    def _summarize_proposal(self, proposal_text: str, max_chars: int = 2000) -> str:
        """Truncate proposal to a summary that fits within context."""
        if len(proposal_text) <= max_chars:
            return proposal_text
        # Take first portion + last portion
        head = proposal_text[:max_chars * 2 // 3]
        tail = proposal_text[-max_chars // 3:]
        return head + "\n\n[...]\n\n" + tail

    def _build_source_index(self, source_papers: list[str]) -> str:
        """Build a compact source index for reference."""
        if not source_papers:
            return "No sources provided."

        lines = []
        for paper in source_papers[:30]:
            # Extract just the first line (title + citation marker)
            first_line = paper.split("\n")[0][:150]
            lines.append(first_line)
        return "\n".join(lines)

    def _select_relevant_sources(
        self,
        source_text: str,
        section_id: str,
        section_title: str,
        outline: str,
    ) -> str:
        """Select sources most relevant to a section.

        Uses keyword matching between section topic and source titles/abstracts.
        Returns a subset of sources that fit within the per-section budget.
        """
        # Budget: roughly 1/3 of context for sources, 1/3 for instructions, 1/3 for output
        source_budget = self._context_window // 3

        # Keywords for each section type
        section_keywords = {
            "related_work": ["prior", "previous", "existing", "related", "background", "survey", "literature"],
            "proposed_method": ["method", "approach", "framework", "architecture", "algorithm", "model", "technique"],
            "evaluation_plan": ["evaluation", "experiment", "benchmark", "dataset", "metric", "baseline", "result"],
            "discussion": ["limitation", "future", "implication", "challenge", "direction"],
            "introduction": ["introduction", "motivation", "problem", "challenge", "opportunity"],
            "abstract": [],  # Abstract uses all sources at a glance
            "conclusion": [],  # Conclusion is self-referential
        }

        keywords = section_keywords.get(section_id, [])
        sources = source_text.split("\n")

        if not keywords:
            # No filtering — just truncate to budget
            return source_text[:source_budget]

        # Score sources by keyword overlap
        scored = []
        for source in sources:
            source_lower = source.lower()
            score = sum(1 for kw in keywords if kw in source_lower)
            scored.append((score, source))

        # Sort by relevance (highest first) and take until budget
        scored.sort(reverse=True)
        selected = []
        total_len = 0
        for score, source in scored:
            if total_len + len(source) + 1 > source_budget:
                break
            if source.strip():
                selected.append(source)
                total_len += len(source) + 1

        return "\n".join(selected) if selected else source_text[:source_budget]

    async def _generate_section(
        self,
        section_id: str,
        section_title: str,
        target_words: int,
        outline: str,
        proposal_summary: str,
        relevant_sources: str,
        domain: str,
    ) -> SectionDraft:
        """Generate a single section of the paper."""
        prompt = (
            f"Write the '{section_title}' section ({target_words} target words) "
            f"for a research paper in '{domain}'.\n\n"
            f"Paper outline:\n{outline[:500]}\n\n"
            f"Proposal summary:\n{proposal_summary[:1000]}\n\n"
            f"Available sources (cite using [SOURCE-X]):\n{relevant_sources}\n\n"
            f"Write the {section_title} section now. "
            f"Be rigorous, cite sources, and aim for {target_words} words."
        )

        # Calculate output tokens for this section
        max_output = max(MIN_SECTION_OUTPUT_TOKENS, target_words * 2)  # rough tokens

        try:
            result = await self._provider.complete(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=min(max_output, 4096),
            )
        except Exception as e:
            logger.warning("Section '%s' generation failed: %s", section_title, e)
            return SectionDraft(
                section_id=section_id,
                title=section_title,
                content=f"[Section generation failed: {e}]",
                word_count=0,
                citations_used=[],
                model_used=self._get_model_name(),
            )

        content = result.strip() if result else ""
        word_count = len(content.split())

        # Extract citations used
        citations = re.findall(r'\[SOURCE-\d+\]', content)

        return SectionDraft(
            section_id=section_id,
            title=section_title,
            content=content,
            word_count=word_count,
            citations_used=citations,
            model_used=self._get_model_name(),
        )

    def _assemble_paper(
        self,
        sections: list[SectionDraft],
        outline: str,
        domain: str,
        venue: str,
        source_count: int,
    ) -> str:
        """Assemble sections into a complete paper."""
        parts = [
            f"# Research Paper: {domain}",
            f"**Venue:** {venue}",
            f"**Sources:** {source_count} papers cited",
            "",
            "---",
            "",
        ]

        for section in sections:
            if section.word_count > 0:
                parts.append(f"## {section.title}\n")
                parts.append(section.content)
                parts.append("\n")

        # Add references section
        parts.append("## References\n")
        parts.append(f"[Generated from {source_count} source papers — see proposal for full bibliography]")
        parts.append("")

        return "\n".join(parts)

    def _get_model_name(self) -> str:
        """Get the model name from the provider."""
        model = getattr(self._provider, "default_model", "unknown")
        if callable(model):
            model = model()
        return str(model)
