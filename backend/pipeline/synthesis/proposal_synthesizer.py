"""Proposal synthesis — generate full-length research proposals via free-text LLM generation."""

import logging
import re
from pathlib import Path

from jinja2 import Template

from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.literature.models import Paper
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"

# Section markers the LLM must produce — used for parsing free-text output
REQUIRED_SECTIONS = [
    "Title",
    "Abstract",
    "Introduction",
    "Related Work",
    "Proposed Method",
    "Expected Contributions",
    "Evaluation Plan",
    "Timeline",
    "References",
    "Risk Mitigation",
]

# Minimum word counts per section — enforced on generation
MIN_WORDS = {
    "abstract": 150,
    "introduction": 400,
    "related_work": 300,
    "proposed_method": 500,
    "expected_contributions": 150,
    "evaluation_plan": 300,
    "timeline": 100,
    "risk_mitigation": 150,
}

# Per-section quality checklist — each check is a (pattern, description) tuple.
# A section FAILS a check if the pattern is NOT found. The refinement pass
# re-generates sections that fail any check, plus the word-count check.
SECTION_CHECKLIST: dict[str, list[tuple[str, str]]] = {
    "proposed_method": [
        (r"\$.*\$", "mathematical notation ($...$)"),
    ],
    "related_work": [
        (r"\[\d+\]|\(\w+,\s*\d{4}\)", "citation markers ([1] or Author, Year)"),
    ],
    "introduction": [
        (r"contribut|novelt|our ", "contributions statement"),
    ],
    "evaluation_plan": [
        (r"baseline|metric|dataset|benchmark", "evaluation specifics (baseline/metric/dataset)"),
    ],
}


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
                if isinstance(value, list):
                    for i, ref in enumerate(value, 1):
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
                elif isinstance(value, str):
                    # Free-text references — emit as-is
                    md_parts.append(value)
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

    def word_count(self) -> int:
        """Total word count across all sections."""
        total = 0
        for v in self.sections.values():
            if isinstance(v, str):
                total += len(v.split())
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        total += len(item.split())
                    elif isinstance(item, dict):
                        total += sum(len(str(x).split()) for x in item.values())
            elif isinstance(v, dict):
                total += sum(len(str(x).split()) for x in v.values())
        return total


class ProposalSynthesizer:
    def __init__(self, provider: LLMProvider, ensemble_reviewer=None, verify_references: bool = True):
        self._provider = provider
        self._ensemble_reviewer = ensemble_reviewer
        self._verify_references = verify_references
        self._prompt_template = (PROMPT_DIR / "synthesis_system.md").read_text()

    async def synthesize(
        self,
        idea: ResearchIdea,
        novelty_report: NoveltyReport | None = None,
        feasibility_report: FeasibilityReport | None = None,
        supporting_papers: list[Paper] | None = None,
        gaps: list | None = None,
    ) -> ResearchProposal:
        """Generate a full-length research proposal section by section."""
        literature = self._format_literature(supporting_papers or [])
        context = self._build_context(idea, novelty_report, feasibility_report, literature, gaps)

        sections: dict[str, str | list] = {}

        # Pass 1: Generate all sections in one call (efficient)
        try:
            raw_text = await self._provider.complete(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior researcher writing a full research proposal for a "
                            "competitive conference (ACL, EMNLP, NeurIPS). You MUST "
                            "produce ALL sections with substantial content. Do NOT write stubs, "
                            "summaries, or placeholder text. Each section must be detailed and "
                            "technically precise.\n\n"
                            "CRITICAL: This is a CLOSED-BOOK EXAM. You may ONLY cite sources "
                            "labeled [SOURCE-X] in the Supporting Literature. If a claim cannot "
                            "be backed by a [SOURCE-X] paper, write 'internal reasoning' — do NOT "
                            "invent citations. Do NOT use author names from your training data that "
                            "are not listed below.\n\n"
                            "OUTPUT FORMAT: Write each section with a markdown header like:\n"
                            "## Title\n...\n## Abstract\n...\n## Introduction\n...\n"
                            "## Related Work\n...\n## Proposed Method\n...\n"
                            "## Expected Contributions\n...\n## Evaluation Plan\n...\n"
                            "## Timeline\n...\n## References\n...\n## Risk Mitigation\n...\n\n"
                            "You MUST include ALL 10 sections. Each prose section must be at least "
                            "200 words. The Proposed Method must be at least 500 words with "
                            "mathematical notation ($...$). The Introduction must be at least 400 words.\n\n"
                            "MANDATORY PRE-COMPUTATION: Before writing prose, internally: (1) list each "
                            "[SOURCE-X] and its key claim, (2) map claims to sources, (3) assign sources "
                            "to sections. Map first, write second."
                        ),
                    },
                    {"role": "user", "content": context},
                ],
                temperature=0.4,
                max_tokens=8192,
            )
            parsed = self._parse_sections(raw_text)
            sections = dict(parsed.sections)
        except Exception as e:
            logger.error("Full generation failed: %s — falling back to section-by-section", e)
            sections = {}

        # Pass 2: Fill in any missing or short sections individually
        for section_name in REQUIRED_SECTIONS:
            key = section_name.lower().replace(" ", "_")
            content = sections.get(key, "")
            if not content or (isinstance(content, str) and len(content.split()) < MIN_WORDS.get(key, 50)):
                try:
                    section_text = await self._generate_single_section(
                        section_name, idea, novelty_report, feasibility_report, literature, gaps
                    )
                    if section_text and len(section_text.split()) > len(content.split() if isinstance(content, str) else ""):
                        sections[key] = section_text
                except Exception as se:
                    logger.warning("Section %s generation failed: %s", section_name, se)
                    if key not in sections:
                        sections[key] = ""

        proposal = ResearchProposal(idea_id=None, **sections)

        # Pass 3: Refinement — check each section against quality checklist
        proposal = await self._refine_sections(
            proposal, idea, novelty_report, feasibility_report, literature, gaps,
            supporting_papers=supporting_papers,
        )

        # Ensemble review
        if self._ensemble_reviewer:
            try:
                review_result = await self._ensemble_reviewer.review(proposal, idea)
                if review_result is not None:
                    proposal.sections["ensemble_review"] = review_result.model_dump()
            except Exception as e:
                logger.warning("Ensemble review failed: %s", e)

        return proposal

    async def _generate_single_section(
        self,
        section_name: str,
        idea: ResearchIdea,
        novelty_report: NoveltyReport | None,
        feasibility_report: FeasibilityReport | None,
        literature: str,
        gaps: list | None,
    ) -> str:
        """Generate a single section independently."""
        min_words = MIN_WORDS.get(section_name.lower().replace(" ", "_"), 100)
        tips = {
            "Abstract": "150-250 words. State problem, approach, expected result. No first person.",
            "Introduction": "400+ words. 3-4 paragraphs: context, limitations, approach, contributions.",
            "Related Work": "300+ words. Organized by themes, not chronologically. Cite specific papers.",
            "Proposed Method": "500+ words. Formal problem definition, algorithmic steps, math notation.",
            "Expected Contributions": "3-5 numbered contributions, each stating WHAT and WHY.",
            "Evaluation Plan": "300+ words. Datasets, baselines, metrics, ablation design.",
            "Timeline": "100+ words. 12-week breakdown in 4 phases.",
            "References": "List all cited works with author-year-title-venue.",
            "Risk Mitigation": "Top 3 risks with mitigation strategies.",
            "Title": "Concise title under 15 words.",
        }
        tip = tips.get(section_name, "Write a detailed, technically precise section.")

        prompt = (
            f"Research Idea: {idea.title}\n"
            f"Problem: {idea.problem_statement}\n"
            f"Method: {idea.proposed_method}\n"
            f"Contributions: {idea.expected_contributions}\n\n"
            f"Write ONLY the \"{section_name}\" section.\n"
            f"Tips: {tip}\n"
            f"Minimum {min_words} words.\n"
        )
        if novelty_report:
            prompt += f"\nNovelty arguments: {novelty_report.novelty_arguments[:300]}\n"
        if feasibility_report:
            prompt += f"\nFeasibility: {feasibility_report.reasoning[:300]}\n"

        return await self._provider.complete(
            messages=[
                {"role": "system", "content": f"You are writing the {section_name} section of a research proposal. Produce full-length, publication-quality prose."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=4096,
        )

    async def _refine_sections(
        self,
        proposal: ResearchProposal,
        idea: ResearchIdea,
        novelty_report: NoveltyReport | None = None,
        feasibility_report: FeasibilityReport | None = None,
        literature: str = "",
        gaps: list | None = None,
        supporting_papers: list | None = None,
    ) -> ResearchProposal:
        """Check each section against a quality checklist and re-generate failures.

        For each section, two types of checks run:
          1. Word-count check: does the section meet its MIN_WORDS threshold?
          2. Pattern check: does the section contain required patterns from SECTION_CHECKLIST?

        Sections that fail any check are re-generated via `_generate_single_section`.
        The re-generated version replaces the original only if it passes the same checks
        or is at least longer than the original.

        Returns the proposal with refined sections.
        """
        sections_to_refine: list[tuple[str, str, list[str]]] = []  # (key, section_name, failures)

        for section_name in REQUIRED_SECTIONS:
            key = section_name.lower().replace(" ", "_")
            content = proposal.sections.get(key, "")
            if not isinstance(content, str) or not content:
                continue

            failures: list[str] = []

            # Check 1: word count
            min_words = MIN_WORDS.get(key, 50)
            word_count = len(content.split())
            if word_count < min_words:
                failures.append(f"word count {word_count} < {min_words}")

            # Check 2: pattern checklist
            checklist = SECTION_CHECKLIST.get(key, [])
            for pattern, description in checklist:
                if not re.search(pattern, content, re.IGNORECASE):
                    failures.append(f"missing {description}")

            if failures:
                sections_to_refine.append((key, section_name, failures))

        if not sections_to_refine:
            logger.info("Refinement pass: all sections passed quality checks")
            return proposal

        logger.info(
            "Refinement pass: %d sections need re-generation: %s",
            len(sections_to_refine),
            ", ".join(f"{name} ({'; '.join(fails)})" for _, name, fails in sections_to_refine),
        )

        for key, section_name, failures in sections_to_refine:
            try:
                old_content = proposal.sections.get(key, "")
                old_word_count = len(old_content.split()) if isinstance(old_content, str) else 0

                new_content = await self._generate_single_section(
                    section_name, idea, novelty_report, feasibility_report, literature, gaps
                )

                if not new_content:
                    logger.warning("Refinement of %s produced empty output — keeping original", section_name)
                    continue

                # Verify the replacement is an improvement
                new_word_count = len(new_content.split())
                new_failures = self._check_section(key, new_content)

                if new_word_count >= old_word_count and len(new_failures) <= len(failures):
                    # Accept: same or fewer failures, same or longer
                    proposal.sections[key] = new_content
                    logger.info(
                        "Refined %s: %d→%d words, %d→%d failures",
                        section_name, old_word_count, new_word_count,
                        len(failures), len(new_failures),
                    )
                elif new_word_count > old_word_count:
                    # Accept: longer even if failures remain — at least more content
                    proposal.sections[key] = new_content
                    logger.info(
                        "Refined %s: %d→%d words (accepted despite %d remaining failures)",
                        section_name, old_word_count, new_word_count, len(new_failures),
                    )
                else:
                    logger.warning(
                        "Refinement of %s did not improve — keeping original", section_name
                    )
            except Exception as e:
                logger.warning("Refinement of %s failed: %s", section_name, e)

        # Reference verification pass
        if self._verify_references:
            proposal = self._verify_proposal_references(proposal, supporting_papers or [])

        return proposal

    def _verify_proposal_references(self, proposal: ResearchProposal, corpus_papers: list[Paper]) -> ResearchProposal:
        """Verify references in proposal against actual corpus."""
        # Step 1: Sanitize — strip any citation not in the provided source list
        proposal = self._sanitize_citations(proposal, corpus_papers)
        
        # Step 2: Verify — run reference verifier for trust scoring
        try:
            from backend.pipeline.verification.reference_verifier import ReferenceVerifier
            verifier = ReferenceVerifier()
            full_text = "\n".join(str(v) for v in proposal.sections.values())
            corpus_dicts = [{"title": p.title, "authors": p.authors or [], "year": str(p.year) if p.year else ""} for p in corpus_papers]
            report = verifier.verify(full_text, corpus_dicts)
            if report.trust_score < 0.7:
                logger.warning("Reference trust score: %.1f — %d unverifiable citations",
                             report.trust_score, report.potentially_hallucinated)
                for key in proposal.sections:
                    if isinstance(proposal.sections[key], str):
                        proposal.sections[key] = verifier.strip_unverified_citations(
                            proposal.sections[key], report
                        )
            else:
                logger.info("Reference verification passed: %.1f trust score", report.trust_score)
        except Exception as e:
            logger.warning("Reference verification failed (non-fatal): %s", e)
        return proposal

    @staticmethod
    def _sanitize_citations(proposal: ResearchProposal, corpus_papers: list[Paper]) -> ResearchProposal:
        """Strip citations that don't match any provided source paper.
        
        Uses regex to find author-year citation patterns and checks each
        against the actual author surnames in the provided corpus.
        Non-matching citations are replaced with 'internal reasoning'.
        """
        import re
        
        if not corpus_papers:
            return proposal
        
        # Build allowed surname set from corpus
        allowed_surnames = set()
        for p in corpus_papers:
            for author in (p.authors or []):
                name = getattr(author, 'name', str(author))
                if name:
                    # surname = last word
                    allowed_surnames.add(name.strip().split()[-1].lower())
        
        # Four citation patterns to match:
        # 1. (Author et al., Year)  — parenthesized multi-author
        # 2. (Author, Year)         — parenthesized single author  
        # 3. Author et al. (Year)   — narrative multi-author
        # 4. Author (Year)          — narrative single author
        patterns = [
            re.compile(r'\(([A-Z][a-z]+)\s+et\s+al\.,?\s*(\d{4})\)'),
            re.compile(r'\(([A-Z][a-z]+),?\s*(\d{4})\)'),
            re.compile(r'([A-Z][a-z]+)\s+et\s+al\.\s+\((\d{4})\)'),
            re.compile(r'([A-Z][a-z]+)\s+\((\d{4})\)'),
        ]
        
        stripped_count = 0
        for key in proposal.sections:
            if not isinstance(proposal.sections[key], str):
                continue
            text = proposal.sections[key]
            
            for pat in patterns:
                def _check(m):
                    nonlocal stripped_count
                    surname = m.group(1).lower()
                    if surname in allowed_surnames:
                        return m.group(0)  # Keep
                    stripped_count += 1
                    return "internal reasoning"
                text = pat.sub(_check, text)
            
            proposal.sections[key] = text
        
        if stripped_count > 0:
            logger.warning(
                "Sanitized %d non-corpus citations (replaced with 'internal reasoning')",
                stripped_count,
            )
        return proposal

    @staticmethod
    def _check_section(key: str, content: str) -> list[str]:
        """Run the quality checklist on a section. Returns list of failure descriptions."""
        failures: list[str] = []
        min_words = MIN_WORDS.get(key, 50)
        if len(content.split()) < min_words:
            failures.append(f"word count {len(content.split())} < {min_words}")
        for pattern, description in SECTION_CHECKLIST.get(key, []):
            if not re.search(pattern, content, re.IGNORECASE):
                failures.append(f"missing {description}")
        return failures

    def _build_context(
        self,
        idea: ResearchIdea,
        novelty_report: NoveltyReport | None,
        feasibility_report: FeasibilityReport | None,
        literature: str,
        gaps: list | None,
    ) -> str:
        """Build the full context string for the LLM prompt."""
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
        key_risks = feasibility_report.key_risks if feasibility_report else []
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

        return Template(self._prompt_template).render(
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

    @staticmethod
    def _parse_sections(raw_text: str, idea_id: int | None = None) -> ResearchProposal:
        """Parse free-text markdown output into a ResearchProposal with keyed sections."""
        sections: dict[str, str | list] = {}

        # Split on ## headers
        pattern = r"##\s+(" + "|".join(REQUIRED_SECTIONS) + r")\s*\n"
        parts = re.split(pattern, raw_text)

        # parts alternates: [preamble, section_name, content, section_name, content, ...]
        i = 1
        while i < len(parts) - 1:
            section_name = parts[i].strip()
            content = parts[i + 1].strip()
            key = section_name.lower().replace(" ", "_")

            # Try to parse references as list
            if key == "references":
                sections[key] = ProposalSynthesizer._parse_references(content)
            else:
                sections[key] = content

            i += 2

        # If there's preamble text before first ## header, check for title
        if parts[0].strip() and "title" not in sections:
            first_line = parts[0].strip().split("\n")[0]
            if first_line and not first_line.startswith("#"):
                sections["title"] = first_line

        return ResearchProposal(idea_id=idea_id, **sections)

    @staticmethod
    def _parse_references(text: str) -> str | list[dict]:
        """Try to parse references into structured dicts; fall back to raw text."""
        refs = []
        # Match patterns like [1] Author (Year). Title. Venue.
        for m in re.finditer(
            r"\[\d+\]\s*(.+?)(?:\n|$)",
            text,
        ):
            line = m.group(1).strip()
            refs.append({"raw": line})

        if refs:
            return refs
        return text  # Return raw text if parsing fails

    @staticmethod
    def _find_short_sections(proposal: ResearchProposal) -> list[str]:
        """Return list of section keys that don't meet minimum word counts."""
        short = []
        for key, minimum in MIN_WORDS.items():
            content = proposal.sections.get(key, "")
            if isinstance(content, str) and len(content.split()) < minimum:
                short.append(key)
        return short

    async def _expand_sections(
        self,
        proposal: ResearchProposal,
        short_sections: list[str],
        idea: ResearchIdea,
    ) -> ResearchProposal:
        """Expand sections that are too short via a follow-up LLM call."""
        expand_prompt = (
            f"The following research proposal has sections that are too short. "
            f"Expand ONLY these sections: {', '.join(short_sections)}.\n\n"
            f"Research idea: {idea.title}\n"
            f"Problem: {idea.problem_statement}\n"
            f"Method: {idea.proposed_method}\n\n"
        )
        for key in short_sections:
            current = proposal.sections.get(key, "")
            if isinstance(current, str):
                expand_prompt += f"## {key.replace('_', ' ').title()}\n{current}\n\n"

        expand_prompt += (
            "\nRewrite ONLY the sections above. Each must be detailed and technically precise. "
            "Use markdown ## headers. The Introduction must be 400+ words. "
            "The Proposed Method must be 500+ words with math notation. "
            "Related Work must be 300+ words citing specific papers."
        )

        try:
            expansion = await self._provider.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior researcher expanding thin sections of a research proposal. Produce full-length, publication-quality prose.",
                    },
                    {"role": "user", "content": expand_prompt},
                ],
                temperature=0.4,
                max_tokens=6144,
            )

            expanded = self._parse_sections(expansion, idea_id=proposal.idea_id)
            # Merge expanded sections back in
            for key in short_sections:
                if key in expanded.sections:
                    new_content = expanded.sections[key]
                    if isinstance(new_content, str) and len(new_content.split()) > len(
                        str(proposal.sections.get(key, "")).split()
                    ):
                        proposal.sections[key] = new_content

        except Exception as e:
            logger.warning("Section expansion failed: %s", e)

        return proposal

    @staticmethod
    def _format_literature(papers: list[Paper]) -> str:
        if not papers:
            return "No specific supporting papers provided."
        lines = []
        for idx, p in enumerate(papers[:30], 1):
            authors = ", ".join(a.name for a in p.authors[:3])
            if len(p.authors) > 3:
                authors += " et al."
            line = f"[SOURCE-{idx}] {authors} ({p.year or 'n.d.'}). {p.title}. {p.venue or 'Unknown venue'}."
            if p.doi:
                line += f" DOI: {p.doi}."
            elif p.url:
                line += f" URL: {p.url}."
            if p.arxiv_id:
                line += f" arXiv: {p.arxiv_id}."
            if p.abstract:
                line += f"\n  Abstract: {p.abstract[:800]}"
            lines.append(line)
        return "\n".join(lines)
