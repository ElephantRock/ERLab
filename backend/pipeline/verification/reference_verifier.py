"""Reference Verifier: Checks that cited papers actually exist.

Scans proposal text for citation patterns (Author et al., YEAR),
cross-references against the papers actually retrieved during the
pipeline run, and flags hallucinated references.

This addresses the reviewer concern: "verifying the existence of
every reference is essential for a paper that champions verifiable AI."
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Match patterns like "Besta et al., 2024" or "(Wei et al., 2022)"
_CITATION_PATTERN = re.compile(
    r'([A-Z][a-z]+(?:\s+et\s+al\.?)?)\s*[\(\[,]\s*(\d{4})\s*[\)\]\)]?',
    re.MULTILINE,
)

# Match patterns like "[1]", "[2]" numbered references
_NUMBERED_REF_PATTERN = re.compile(r'\[(\d+)\]')

# Match patterns like "[SOURCE-1]", "[SOURCE-2]"
_SOURCE_X_PATTERN = re.compile(r'\[SOURCE-(\d+)\]')


class VerificationState(Enum):
    """5-state verification for citations and claims (B159).

    Replaces binary found/not-found with nuanced assessment.
    """
    SUPPORTED = "supported"                    # Citation found, context matches
    PARTIALLY_SUPPORTED = "partially_supported"  # Citation found, context unclear
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # Citation exists but can't verify context
    CONTRADICTED = "contradicted"              # Citation found but claim contradicts source
    UNVERIFIED = "unverified"                  # Citation not found in corpus at all


@dataclass
class CitationCheck:
    """Result of verifying a single citation."""
    citation_text: str
    author: str
    year: str
    found_in_corpus: bool = False
    matched_paper_title: str = ""
    confidence: float = 0.0  # 0.0 = unverifiable, 1.0 = confirmed
    verification_state: VerificationState = VerificationState.UNVERIFIED
    decayed_confidence: float = 0.0  # After temporal decay (B159-TASK-03)


@dataclass
class VerificationReport:
    """Full verification report for a proposal."""
    total_citations: int = 0
    verified: int = 0
    unverifiable: int = 0
    potentially_hallucinated: int = 0
    citations: list[CitationCheck] = field(default_factory=list)
    coverage_rate: float = 0.0  # fraction of citations found in corpus

    @property
    def trust_score(self) -> float:
        """0.0–1.0 score: how trustworthy are the references."""
        if self.total_citations == 0:
            return 1.0
        return self.verified / self.total_citations


class ReferenceVerifier:
    """Verifies that citations in generated proposals match retrieved papers.

    Usage:
        verifier = ReferenceVerifier()
        report = verifier.verify(proposal_text, retrieved_papers)
        if report.trust_score < 0.5:
            logger.warning("Low reference trust score: %.1f", report.trust_score)
    """

    def __init__(self, similarity_threshold: float = 0.6) -> None:
        self._threshold = similarity_threshold

    def verify(self, proposal_text: str, corpus_papers: list[dict]) -> VerificationReport:
        """Verify all citations in a proposal against the retrieved paper corpus.

        Args:
            proposal_text: The full proposal markdown text.
            corpus_papers: List of dicts with at least 'title', 'authors', 'year' keys.

        Returns:
            VerificationReport with per-citation results and aggregate trust score.
        """
        citations = self._extract_citations(proposal_text)
        source_x_checks = self.verify_source_x(proposal_text, len(corpus_papers))

        report = VerificationReport(total_citations=len(citations) + len(source_x_checks))

        # Build lookup indices from corpus
        author_year_index = self._build_author_year_index(corpus_papers)

        for cit in citations:
            # Check if author+year matches any paper in corpus
            key = (cit.author.lower().replace(" et al", "").replace(" et al.", "").strip(), cit.year)
            matches = author_year_index.get(key, [])

            if matches:
                cit.found_in_corpus = True
                cit.matched_paper_title = matches[0].get("title", "")
                cit.confidence = 1.0
                cit.verification_state = VerificationState.SUPPORTED
                report.verified += 1
            else:
                # Try fuzzy matching on author name
                fuzzy_found = False
                for (a, y), papers in author_year_index.items():
                    if y == cit.year and self._fuzzy_author_match(cit.author, a):
                        cit.found_in_corpus = True
                        cit.matched_paper_title = papers[0].get("title", "")
                        cit.confidence = 0.7
                        cit.verification_state = VerificationState.PARTIALLY_SUPPORTED
                        report.verified += 1
                        fuzzy_found = True
                        break

                if not fuzzy_found:
                    cit.found_in_corpus = False
                    cit.confidence = 0.0
                    cit.verification_state = VerificationState.UNVERIFIED
                    report.potentially_hallucinated += 1

            report.citations.append(cit)

        # Add [SOURCE-X] checks to report
        for check in source_x_checks:
            report.citations.append(check)
            if check.found_in_corpus:
                report.verified += 1
            else:
                report.potentially_hallucinated += 1

        report.unverifiable = report.total_citations - report.verified
        report.coverage_rate = report.verified / max(report.total_citations, 1)

        # B159: Apply temporal decay to each citation's confidence
        try:
            from backend.pipeline.verification.temporal_decay import apply_decay
            for cit in report.citations:
                year_int = int(cit.year) if cit.year and cit.year.isdigit() else None
                cit.decayed_confidence = apply_decay(cit.confidence, year_int)
        except Exception:
            for cit in report.citations:
                cit.decayed_confidence = cit.confidence

        return report

    def verify_source_x(self, proposal_text: str, source_count: int) -> list[CitationCheck]:
        """Verify [SOURCE-X] references in proposal text.

        Args:
            proposal_text: The full proposal markdown text.
            source_count: Number of available source papers.

        Returns:
            List of CitationCheck for each [SOURCE-X] reference found.
        """
        checks: list[CitationCheck] = []
        seen: set[int] = set()

        for match in _SOURCE_X_PATTERN.finditer(proposal_text):
            idx = int(match.group(1))
            if idx in seen:
                continue
            seen.add(idx)

            found = 1 <= idx <= source_count
            checks.append(CitationCheck(
                citation_text=match.group(0),
                author=f"SOURCE-{idx}",
                year="",
                found_in_corpus=found,
                matched_paper_title=f"Source paper {idx}" if found else "",
                confidence=1.0 if found else 0.0,
            ))

        return checks

    def _extract_citations(self, text: str) -> list[CitationCheck]:
        """Extract author-year citations from text."""
        citations = []
        seen = set()
        for match in _CITATION_PATTERN.finditer(text):
            author = match.group(1).strip()
            year = match.group(2)
            key = (author, year)
            if key not in seen:
                seen.add(key)
                citations.append(CitationCheck(
                    citation_text=match.group(0),
                    author=author,
                    year=year,
                ))
        return citations

    def _build_author_year_index(self, papers: list[dict]) -> dict[tuple[str, str], list[dict]]:
        """Build (author_lastname, year) → [papers] index."""
        from backend.pipeline.verification.surname_utils import extract_surname

        index: dict[tuple[str, str], list[dict]] = {}
        for paper in papers:
            authors = paper.get("authors", [])
            year = str(paper.get("year", ""))
            title = paper.get("title", "")

            if not year or not authors:
                # Use title as fallback
                continue

            # Index by each author's surname
            if isinstance(authors, list):
                for author_entry in authors:
                    last_name = extract_surname(author_entry)
                    if last_name and year:
                        key = (last_name, year)
                        index.setdefault(key, []).append(paper)
            elif isinstance(authors, str):
                last_name = extract_surname(authors)
                if last_name and year:
                    key = (last_name, year)
                    index.setdefault(key, []).append(paper)

        return index

    def _fuzzy_author_match(self, cite_author: str, index_author: str) -> bool:
        """Fuzzy match author names (handles 'et al.' variations)."""
        cite_clean = cite_author.lower().replace("et al", "").replace(".", "").strip()
        index_clean = index_author.lower().strip()
        return cite_clean == index_clean or cite_clean.startswith(index_clean) or index_clean.startswith(cite_clean)

    def strip_unverified_citations(self, proposal_text: str, report: VerificationReport) -> str:
        """Remove or flag citations that couldn't be verified.

        Replaces hallucinated citations with [Citation needed] markers.
        """
        text = proposal_text
        for cit in report.citations:
            if not cit.found_in_corpus and cit.confidence == 0.0:
                # Replace the citation with a flag
                text = text.replace(cit.citation_text, f"[Citation needed: {cit.author}, {cit.year}]")
        return text
