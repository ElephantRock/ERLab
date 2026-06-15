"""Abandonment tracking — record rejected research directions to avoid re-exploration.

Inspired by DeepScientist's Downgrade and Abandonment Discipline:
"Record what was downgraded, which evidence caused the change, and what
 future evidence would reopen the line."
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AbandonedDirection:
    """A research direction that was rejected or downgraded."""

    direction: str  # gap title or idea title
    reason: str  # why it was abandoned
    evidence: str  # what evidence caused the abandonment
    run_id: str  # which run abandoned it
    reopen_condition: str = ""  # what would be needed to reopen
    created_at: str = ""  # ISO timestamp


def _normalize_title(title: str) -> str:
    """Normalize a title for comparison (lowercase, strip punctuation/whitespace)."""
    if not title:
        return ""
    # Unicode normalize
    title = unicodedata.normalize("NFKD", title)
    # Lowercase
    title = title.lower().strip()
    # Remove non-alphanumeric (keep spaces)
    title = re.sub(r"[^a-z0-9\s]", "", title)
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title)
    return title


class AbandonmentTracker:
    """Track abandoned research directions and exclude them from future runs.

    Storage: JSONL file (one entry per line) at configured path.
    """

    def __init__(self, output_path: str = "./data/abandoned_directions.jsonl") -> None:
        self._path = Path(output_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        direction: str,
        reason: str,
        evidence: str,
        run_id: str,
        reopen_condition: str = "",
    ) -> AbandonedDirection:
        """Record an abandoned direction.

        Args:
            direction: The gap title or idea title that was abandoned.
            reason: Short reason ("low score", "empty proposal", etc.)
            evidence: Detailed evidence ("Score 0.15 on novelty + feasibility")
            run_id: Which run abandoned it.
            reopen_condition: What future evidence would reopen this line.

        Returns:
            The recorded AbandonedDirection.
        """
        entry = AbandonedDirection(
            direction=direction,
            reason=reason,
            evidence=evidence,
            run_id=run_id,
            reopen_condition=reopen_condition,
            created_at=datetime.now().isoformat(),
        )

        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry)) + "\n")
            logger.debug("Recorded abandoned direction: %s (%s)", direction[:50], reason)
        except Exception as e:
            logger.warning("Failed to record abandoned direction: %s", e)

        return entry

    def load_all(self) -> list[AbandonedDirection]:
        """Load all abandoned directions."""
        if not self._path.exists():
            return []

        results: list[AbandonedDirection] = []
        try:
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        results.append(AbandonedDirection(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except Exception as e:
            logger.warning("Failed to load abandoned directions: %s", e)

        return results

    def get_excluded_titles(self) -> set[str]:
        """Get normalized titles of directions to exclude from future gap analysis."""
        return {_normalize_title(a.direction) for a in self.load_all()}

    def is_abandoned(self, title: str) -> bool:
        """Check if a specific title has been abandoned."""
        normalized = _normalize_title(title)
        return normalized in self.get_excluded_titles()

    def count(self) -> int:
        """Return total number of abandoned directions."""
        return len(self.load_all())
