"""Impasse detection and resolution for the agent loop.

Detects stuck states (duplicate ideas, identical critiques, score plateaus,
low diversity) and proposes resolution strategies. Adopted from Soar's
impasse-driven learning combined with OpenHands' stuck detection.
"""

import logging
import math
from enum import Enum

from pydantic import BaseModel

from backend.pipeline.generation.models import Critique, ResearchIdea

logger = logging.getLogger(__name__)


class ImpasseType(str, Enum):
    DUPLICATE_IDEAS = "duplicate_ideas"
    IDENTICAL_CRITIQUES = "identical_critiques"
    SCORE_PLATEAU = "score_plateau"
    LOW_DIVERSITY = "low_diversity"


class ImpasseDetected(BaseModel):
    impasse_type: ImpasseType
    severity: float  # 0-1
    evidence: str


class Resolution(BaseModel):
    action: (
        str
    )  # "change_perspective", "increase_temperature", "switch_strategy", "inject_constraint"
    params: dict = {}  # Parameters for the resolution action


class ImpasseDetector:
    """Detect stuck states and propose resolutions (Soar + OpenHands pattern)."""

    def detect(
        self,
        current_ideas: list[ResearchIdea],
        previous_ideas: list[ResearchIdea],
        critiques: list[Critique],
        critique_history: list[list[Critique]],
        scores: list[float],
    ) -> ImpasseDetected | None:
        """Check for impasses. Returns the most severe one found, or None."""
        impasses: list[ImpasseDetected] = []

        # Check duplicate ideas
        dup = self._check_duplicate_ideas(current_ideas, previous_ideas)
        if dup:
            impasses.append(dup)

        # Check identical critiques
        ident = self._check_identical_critiques(critiques, critique_history)
        if ident:
            impasses.append(ident)

        # Check score plateau
        plateau = self._check_score_plateau(scores)
        if plateau:
            impasses.append(plateau)

        # Check low diversity
        diversity = self._check_low_diversity(current_ideas, previous_ideas)
        if diversity:
            impasses.append(diversity)

        # Return most severe impasse
        if impasses:
            return max(impasses, key=lambda i: i.severity)
        return None

    def resolve(self, impasse: ImpasseDetected) -> Resolution:
        """Propose a resolution strategy for the detected impasse."""
        strategies = {
            ImpasseType.DUPLICATE_IDEAS: Resolution(
                action="inject_constraint",
                params={"constraint": _random_constraint()},
            ),
            ImpasseType.IDENTICAL_CRITIQUES: Resolution(
                action="switch_strategy",
                params={"strategy": "meta_reflection"},
            ),
            ImpasseType.SCORE_PLATEAU: Resolution(
                action="increase_temperature",
                params={"delta": 0.1},
            ),
            ImpasseType.LOW_DIVERSITY: Resolution(
                action="change_perspective",
                params={"perspective": _random_perspective()},
            ),
        }
        return strategies.get(
            impasse.impasse_type, Resolution(action="increase_temperature", params={"delta": 0.1})
        )

    def _check_duplicate_ideas(
        self,
        current: list[ResearchIdea],
        previous: list[ResearchIdea],
    ) -> ImpasseDetected | None:
        if not current or not previous:
            return None

        # Check title overlap using word sets
        overlap_count = 0
        for curr in current:
            curr_words = set(curr.title.lower().split())
            for prev in previous:
                prev_words = set(prev.title.lower().split())
                if not curr_words or not prev_words:
                    continue
                jaccard = len(curr_words & prev_words) / len(curr_words | prev_words)
                if jaccard > 0.8:
                    overlap_count += 1
                    break

        if overlap_count > len(current) * 0.5:
            return ImpasseDetected(
                impasse_type=ImpasseType.DUPLICATE_IDEAS,
                severity=min(1.0, overlap_count / max(1, len(current))),
                evidence=f"{overlap_count}/{len(current)} ideas overlap with previous round",
            )
        return None

    def _check_identical_critiques(
        self,
        critiques: list[Critique],
        history: list[list[Critique]],
    ) -> ImpasseDetected | None:
        if not critiques or not history:
            return None

        current_weaknesses = set()
        for c in critiques:
            for w in c.weaknesses:
                current_weaknesses.add(w.lower().strip())

        if not current_weaknesses:
            return None

        max_overlap = 0.0
        for past in history[-3:]:  # Check last 3 rounds
            past_weaknesses = set()
            for c in past:
                for w in c.weaknesses:
                    past_weaknesses.add(w.lower().strip())

            if not past_weaknesses:
                continue
            intersection = current_weaknesses & past_weaknesses
            union = current_weaknesses | past_weaknesses
            overlap = len(intersection) / len(union) if union else 0
            max_overlap = max(max_overlap, overlap)

        if max_overlap > 0.7:
            return ImpasseDetected(
                impasse_type=ImpasseType.IDENTICAL_CRITIQUES,
                severity=max_overlap,
                evidence=f" Critique weakness overlap: {max_overlap:.0%}",
            )
        return None

    def _check_score_plateau(self, scores: list[float]) -> ImpasseDetected | None:
        if len(scores) < 3:
            return None

        # Check standard deviation of recent scores
        recent = scores[-3:]
        mean = sum(recent) / len(recent)
        variance = sum((s - mean) ** 2 for s in recent) / len(recent)
        std_dev = math.sqrt(variance)

        if std_dev < 0.02:
            return ImpasseDetected(
                impasse_type=ImpasseType.SCORE_PLATEAU,
                severity=min(1.0, 0.1 / max(0.001, std_dev)),
                evidence=f"Score std_dev: {std_dev:.4f} (recent: {recent})",
            )
        return None

    def _check_low_diversity(
        self,
        current_ideas: list[ResearchIdea],
        previous_ideas: list[ResearchIdea],
    ) -> ImpasseDetected | None:
        if len(current_ideas) < 2:
            return None

        title_words = [set(i.title.lower().split()) for i in current_ideas]
        similarities: list[float] = []
        for i in range(len(title_words)):
            for j in range(i + 1, len(title_words)):
                if not title_words[i] or not title_words[j]:
                    continue
                jaccard = len(title_words[i] & title_words[j]) / len(title_words[i] | title_words[j])
                similarities.append(jaccard)

        if not similarities:
            return None
        avg_similarity = sum(similarities) / len(similarities)
        if avg_similarity > 0.5:
            return ImpasseDetected(
                impasse_type=ImpasseType.LOW_DIVERSITY,
                severity=min(1.0, avg_similarity),
                evidence=f"Average pairwise title similarity: {avg_similarity:.2f}",
            )
        return None


# Resolution helpers

_CONSTRAINTS = [
    "must use a contrastive learning approach",
    "must incorporate multimodal data",
    "must be implementable with less than 10K training samples",
    "must address efficiency alongside accuracy",
    "must leverage existing pretrained models",
    "must include a human evaluation component",
]

_PERSPECTIVES = [
    "Consider this from a cognitive science perspective",
    "Approach this from a systems engineering angle",
    "Think about this from an end-user application perspective",
    "Consider the reproducibility implications",
    "Approach this from a data-centric AI perspective",
]


def _random_constraint() -> str:
    import random

    return random.choice(_CONSTRAINTS)


def _random_perspective() -> str:
    import random

    return random.choice(_PERSPECTIVES)
