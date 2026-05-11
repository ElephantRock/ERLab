"""TextGrad-style prompt gradient computation (B165).

Computes a 'gradient' for prompts based on stage outcomes.
The gradient suggests incremental prompt modifications rather than
wholesale rewrites — inspired by TextGrad (Yuksekgonul et al., 2024).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PromptGradient:
    """A single gradient step for a prompt."""
    stage_name: str
    version: int
    current_hash: str
    suggestion: str
    score_delta: float = 0.0
    applied: bool = False


@dataclass
class PromptVersion:
    """Versioned prompt with hash and score."""
    stage_name: str
    version: int
    content: str
    score: float = 0.0
    hash: str = ""

    def compute_hash(self) -> str:
        self.hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]
        return self.hash


class TextGradEngine:
    """Compute and apply prompt gradients from stage outcomes.

    Usage:
        engine = TextGradEngine(persist_dir="./data/textgrad")
        gradient = engine.compute_gradient("gap_analysis", current_prompt, 0.3, 0.5)
        engine.apply_gradient(gradient, new_prompt)
    """

    def __init__(self, persist_dir: str = "./data/textgrad") -> None:
        self._dir = Path(persist_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._history: dict[str, list[PromptVersion]] = {}

    def compute_gradient(
        self,
        stage_name: str,
        current_prompt: str,
        current_score: float,
        target_score: float = 0.8,
    ) -> PromptGradient | None:
        """Compute a gradient suggestion for a prompt.

        Args:
            stage_name: Which pipeline stage.
            current_prompt: The current prompt text.
            current_score: Recent performance score (0-1).
            target_score: Desired performance score.

        Returns:
            PromptGradient if improvement needed, None if already performing well.
        """
        if current_score >= target_score:
            return None  # Already meeting target

        delta = target_score - current_score
        prompt_hash = hashlib.sha256(current_prompt.encode()).hexdigest()[:16]

        # Build suggestion based on gap magnitude
        if delta > 0.4:
            suggestion = (
                "Major rewrite needed. The prompt is producing poor results. "
                "Consider: (1) clearer instructions, (2) explicit output format, "
                "(3) few-shot examples, (4) stricter constraints."
            )
        elif delta > 0.2:
            suggestion = (
                "Moderate improvement needed. Consider: (1) more specific guidance, "
                "(2) better output structure specification, (3) additional context."
            )
        else:
            suggestion = (
                "Minor tuning. Consider: (1) refine ambiguous phrases, "
                "(2) adjust temperature/creativity hints."
            )

        versions = self._history.get(stage_name, [])
        version_num = len(versions) + 1

        return PromptGradient(
            stage_name=stage_name,
            version=version_num,
            current_hash=prompt_hash,
            suggestion=suggestion,
            score_delta=delta,
        )

    def apply_gradient(self, gradient: PromptGradient, new_prompt: str) -> PromptVersion:
        """Record a new prompt version after applying a gradient."""
        version = PromptVersion(
            stage_name=gradient.stage_name,
            version=gradient.version,
            content=new_prompt,
            score=0.0,  # Will be updated on next run
        )
        version.compute_hash()
        gradient.applied = True

        self._history.setdefault(gradient.stage_name, []).append(version)
        self._persist(gradient.stage_name)
        return version

    def get_history(self, stage_name: str) -> list[PromptVersion]:
        """Get prompt version history for a stage."""
        return self._history.get(stage_name, [])

    def _persist(self, stage_name: str) -> None:
        """Save prompt history to disk."""
        versions = self._history.get(stage_name, [])
        data = [
            {"version": v.version, "hash": v.hash, "score": v.score, "content_length": len(v.content)}
            for v in versions
        ]
        path = self._dir / f"{stage_name}_history.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
