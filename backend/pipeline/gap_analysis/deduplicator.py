"""Gap Deduplicator: Merges near-duplicate gaps across pipeline runs.

Uses word-overlap similarity to identify gaps that are essentially
the same finding across different runs. Merges them with metadata
tracking which runs contributed.

Addresses the concern: "Cross-run gap deduplication using semantic similarity."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MergedGap:
    """A gap that may have been seen in multiple runs."""
    canonical_title: str
    description: str
    gap_type: str
    confidence: float
    source_run_ids: list[str] = field(default_factory=list)
    occurrence_count: int = 1
    merged: bool = False

    def to_dict(self) -> dict:
        return {
            "canonical_title": self.canonical_title,
            "description": self.description,
            "gap_type": self.gap_type,
            "confidence": self.confidence,
            "source_run_ids": self.source_run_ids,
            "occurrence_count": self.occurrence_count,
            "merged": self.merged,
        }


class GapDeduplicator:
    """Merges near-duplicate gaps using word-overlap similarity.

    Threshold: gaps with >0.6 word overlap are considered duplicates.
    The first occurrence becomes the canonical version.
    """

    def __init__(self, threshold: float = 0.6) -> None:
        self._threshold = threshold

    def deduplicate(
        self,
        gaps: list[dict],
        run_id: str = "",
    ) -> list[MergedGap]:
        """Deduplicate a list of gaps.

        Args:
            gaps: List of dicts with 'title', 'description', 'gap_type', 'confidence'.
            run_id: The run ID to associate with these gaps.

        Returns:
            List of MergedGap objects with deduplication metadata.
        """
        if not gaps:
            return []

        merged: list[MergedGap] = []

        for gap in gaps:
            title = gap.get("title", "")
            best_match: MergedGap | None = None
            best_sim = 0.0

            for existing in merged:
                sim = self._title_similarity(title, existing.canonical_title)
                if sim > best_sim and sim >= self._threshold:
                    best_sim = sim
                    best_match = existing

            if best_match:
                # Merge into existing
                best_match.occurrence_count += 1
                best_match.merged = True
                if run_id and run_id not in best_match.source_run_ids:
                    best_match.source_run_ids.append(run_id)
                # Keep higher confidence
                new_conf = gap.get("confidence", 0.5)
                if new_conf > best_match.confidence:
                    best_match.confidence = new_conf
                    best_match.description = gap.get("description", best_match.description)
            else:
                # New unique gap
                mg = MergedGap(
                    canonical_title=title,
                    description=gap.get("description", ""),
                    gap_type=gap.get("gap_type", "unknown"),
                    confidence=gap.get("confidence", 0.5),
                    source_run_ids=[run_id] if run_id else [],
                    occurrence_count=1,
                    merged=False,
                )
                merged.append(mg)

        logger.info(
            "Deduplication: %d input gaps → %d unique (%d merged)",
            len(gaps), len(merged), sum(1 for m in merged if m.merged),
        )
        return merged

    def deduplicate_multi_run(
        self,
        run_gaps: dict[str, list[dict]],
    ) -> list[MergedGap]:
        """Deduplicate gaps from multiple runs.

        Args:
            run_gaps: Dict mapping run_id → list of gap dicts.

        Returns:
            Deduplicated list of MergedGap objects.
        """
        all_merged: list[MergedGap] = []

        for run_id, gaps in run_gaps.items():
            for gap in gaps:
                title = gap.get("title", "")
                best_match: MergedGap | None = None
                best_sim = 0.0

                for existing in all_merged:
                    sim = self._title_similarity(title, existing.canonical_title)
                    if sim > best_sim and sim >= self._threshold:
                        best_sim = sim
                        best_match = existing

                if best_match:
                    best_match.occurrence_count += 1
                    best_match.merged = True
                    if run_id not in best_match.source_run_ids:
                        best_match.source_run_ids.append(run_id)
                    new_conf = gap.get("confidence", 0.5)
                    if new_conf > best_match.confidence:
                        best_match.confidence = new_conf
                else:
                    mg = MergedGap(
                        canonical_title=title,
                        description=gap.get("description", ""),
                        gap_type=gap.get("gap_type", "unknown"),
                        confidence=gap.get("confidence", 0.5),
                        source_run_ids=[run_id],
                        occurrence_count=1,
                        merged=False,
                    )
                    all_merged.append(mg)

        logger.info(
            "Multi-run dedup: %d runs, %d total gaps → %d unique",
            len(run_gaps),
            sum(len(g) for g in run_gaps.values()),
            len(all_merged),
        )
        return all_merged

    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """Word-overlap similarity between two titles."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)
