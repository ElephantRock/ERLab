"""CurationEngine — rule-based paper filtering and ranking.

AIV v5.3 — BATCH-124
HB-01: Returns [] on empty input. HB-02: Invalid rules skipped with warning.
"""

from __future__ import annotations

import logging

from backend.pipeline.curation.models import CurationRule

logger = logging.getLogger(__name__)


class CurationEngine:
    """Filter and rank papers based on user-defined curation rules."""

    def __init__(self, rules: list[CurationRule], embedding_service=None) -> None:
        self._rules = [r for r in rules if r.enabled]
        self._embedding_service = embedding_service

    def filter(self, papers: list[dict]) -> list[dict]:
        """Apply all rules to filter papers.

        Returns empty list on empty input (HB-01).
        Invalid rules are skipped with warning (HB-02).
        """
        if not papers:
            return []  # HB-01

        result = list(papers)
        max_papers = len(result)

        for rule in self._rules:
            try:
                if rule.rule_type == "max_papers":
                    max_papers = min(max_papers, int(rule.value))
                elif rule.rule_type == "must_include":
                    result = [p for p in result if self._includes(p, rule)]
                elif rule.rule_type == "must_exclude":
                    result = [p for p in result if not self._includes(p, rule)]
                elif rule.rule_type == "semantic_threshold":
                    result = self._semantic_filter(result, rule)
                else:
                    logger.warning("Unknown rule_type '%s' in rule %s (HB-02)", rule.rule_type, rule.rule_id)
            except Exception as e:
                logger.warning("Rule %s failed: %s (HB-02)", rule.rule_id, e)

        # Sort by score and limit
        scored = [(p, self.score(p)) for p in result]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored[:max_papers]]

    def score(self, paper: dict) -> float:
        """Score a paper based on how many include rules it matches."""
        if not self._rules:
            return 0.5
        include_rules = [r for r in self._rules if r.rule_type == "must_include"]
        if not include_rules:
            return 0.5
        matched = sum(1 for r in include_rules if self._includes(paper, r))
        return matched / len(include_rules)

    @staticmethod
    def _includes(paper: dict, rule: CurationRule) -> bool:
        """Check if paper includes the rule's value in the specified field."""
        search_val = str(rule.value).lower()
        if rule.field == "keyword":
            # Search in title + abstract
            text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
            return search_val in text
        elif rule.field == "author":
            authors = str(paper.get("authors", "")).lower()
            return search_val in authors
        elif rule.field == "venue":
            venue = str(paper.get("venue", "")).lower()
            return search_val in venue
        elif rule.field == "abstract":
            abstract = str(paper.get("abstract", "")).lower()
            return search_val in abstract
        else:
            logger.warning("Unknown field '%s' in rule %s", rule.field, rule.rule_id)
            return False

    def _semantic_filter(self, papers: list[dict], rule: CurationRule) -> list[dict]:
        """Filter by semantic similarity (placeholder — returns all if no embedding service)."""
        if self._embedding_service is None:
            return papers  # No filtering without embeddings
        # Full semantic search would use embedding service here
        return papers
