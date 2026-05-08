"""Curation models — rule definitions for paper filtering.

AIV v5.3 — BATCH-124
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CurationRule:
    """A single curation rule for filtering papers.

    Rule types:
      - must_include: Paper MUST contain the value in the specified field
      - must_exclude: Paper MUST NOT contain the value
      - semantic_threshold: Paper abstract must be semantically similar to value
      - max_papers: Limit output to N top-scored papers
    """
    rule_id: str
    rule_type: str       # must_include | must_exclude | semantic_threshold | max_papers
    field: str           # keyword | author | venue | abstract
    value: str | float
    enabled: bool = True
