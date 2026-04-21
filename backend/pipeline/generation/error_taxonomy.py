"""Error taxonomy for CriticAgent learning.

Tracks error categories across pipeline runs so the Critic can focus
attention on historically common failure modes. Adopted from RAG-Critic's
error-aware criticism pattern.
"""

import json
from collections import Counter
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class ErrorCategory(str, Enum):
    METHODOLOGICAL = "methodological"  # Flawed experimental design
    NOVELTY = "novelty"  # Overlap with existing work
    FEASIBILITY = "feasibility"  # Impractical resource requirements
    SCOPE = "scope"  # Too broad or too narrow
    CITATION = "citation"  # Missing or incorrect references


# Keyword mapping for classifying critique weaknesses into error categories
_KEYWORD_MAP: dict[ErrorCategory, list[str]] = {
    ErrorCategory.METHODOLOGICAL: [
        "method",
        "evaluation",
        "experiment",
        "baseline",
        "metric",
        "ablation",
        "validation",
        "protocol",
        "reproducib",
    ],
    ErrorCategory.NOVELTY: [
        "novel",
        "existing",
        "prior",
        "overlap",
        "incremental",
        "similar",
        "already",
        "previous work",
        "state-of-the-art",
    ],
    ErrorCategory.FEASIBILITY: [
        "feasib",
        "resource",
        "compute",
        "data",
        "cost",
        "practical",
        "implement",
        "scalab",
        "hardware",
    ],
    ErrorCategory.SCOPE: [
        "scope",
        "broad",
        "narrow",
        "ambitious",
        "focused",
        "realistic",
        "manageable",
        "direction",
    ],
    ErrorCategory.CITATION: [
        "citation",
        "reference",
        "cite",
        "missing reference",
        "related work",
        "bibliography",
    ],
}


class ErrorObservation(BaseModel):
    category: ErrorCategory
    description: str
    count: int = 1


class ErrorTaxonomy:
    """Persistent error frequency tracker across pipeline runs."""

    def __init__(self, persist_path: str = "./data/error_taxonomy.json"):
        self._path = Path(persist_path)
        self._counts: Counter[str] = Counter()
        self._descriptions: dict[str, list[str]] = {}
        self._load()

    def classify(self, text: str) -> ErrorCategory | None:
        """Classify a weakness text into an error category via keyword matching."""
        text_lower = text.lower()
        best_category: ErrorCategory | None = None
        best_match_count = 0

        for category, keywords in _KEYWORD_MAP.items():
            match_count = sum(1 for kw in keywords if kw in text_lower)
            if match_count > best_match_count:
                best_match_count = match_count
                best_category = category

        return best_category

    def record(self, category: ErrorCategory, description: str) -> None:
        """Record an error observation."""
        key = category.value
        self._counts[key] += 1
        if key not in self._descriptions:
            self._descriptions[key] = []
        # Keep last 10 descriptions per category
        if len(self._descriptions[key]) >= 10:
            self._descriptions[key] = self._descriptions[key][-9:]
        self._descriptions[key].append(description)
        self._save()

    def get_weights(self) -> dict[ErrorCategory, float]:
        """Return normalized weights for each error category."""
        total = sum(self._counts.values())
        if total == 0:
            return {cat: 1.0 / len(ErrorCategory) for cat in ErrorCategory}
        return {cat: self._counts.get(cat.value, 0) / total for cat in ErrorCategory}

    def format_prompt_section(self) -> str:
        """Format error weights as a prompt section for the Critic."""
        weights = self.get_weights()
        if sum(self._counts.values()) == 0:
            return ""

        lines = ["## Historical Error Focus (weight indicates past frequency):"]
        for cat in sorted(weights, key=weights.get, reverse=True):  # type: ignore[arg-type]
            count = self._counts.get(cat.value, 0)
            if count > 0:
                lines.append(
                    f"- **{cat.value}**: {weights[cat]:.0%} of past errors ({count} occurrences)"
                )
        lines.append("Focus more attention on high-frequency error categories.\n")
        return "\n".join(lines)

    def _load(self) -> None:
        if self._path.exists():
            data = json.loads(self._path.read_text())
            self._counts = Counter(data.get("counts", {}))
            self._descriptions = data.get("descriptions", {})

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {
                    "counts": dict(self._counts),
                    "descriptions": self._descriptions,
                },
                indent=2,
            )
        )
