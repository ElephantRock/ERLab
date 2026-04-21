"""Constraint validation for evolved artifacts.

Adopted from hermes-agent-self-evolution (DSPy+GEPA). Enforces hard
constraints on evolved parameters before deployment: size limits, growth
limits, non-empty, structural integrity. Failed constraints = immediate
rejection even if fitness improved.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConstraintConfig:
    max_size: int = 5000
    max_growth_pct: float = 0.3  # 30% growth over baseline allowed
    allow_empty: bool = False
    min_sections: int = 1  # Minimum JSON keys or sections expected


@dataclass
class ConstraintResult:
    passed: bool
    constraint_name: str
    message: str


class ConstraintValidator:
    """Validates evolved artifacts against hard constraints."""

    def __init__(self, config: ConstraintConfig | None = None):
        self._config = config or ConstraintConfig()

    def validate(self, text: str, baseline: str) -> list[ConstraintResult]:
        """Run all constraint checks. Returns list of results."""
        results = [
            self._check_non_empty(text),
            self._check_size(text),
            self._check_growth(text, baseline),
            self._check_structure(text),
        ]
        for r in results:
            if not r.passed:
                logger.warning("Constraint failed: %s — %s", r.constraint_name, r.message)
        return results

    def all_passed(self, text: str, baseline: str) -> bool:
        """Convenience: True if all constraints pass."""
        return all(r.passed for r in self.validate(text, baseline))

    def _check_non_empty(self, text: str) -> ConstraintResult:
        if self._config.allow_empty:
            return ConstraintResult(True, "non_empty", "Empty allowed by config")
        if not text or not text.strip():
            return ConstraintResult(False, "non_empty", "Evolved artifact is empty")
        return ConstraintResult(True, "non_empty", "OK")

    def _check_size(self, text: str) -> ConstraintResult:
        size = len(text)
        if size > self._config.max_size:
            return ConstraintResult(
                False,
                "size_limit",
                f"Size {size} exceeds max {self._config.max_size}",
            )
        return ConstraintResult(True, "size_limit", f"Size {size} OK")

    def _check_growth(self, text: str, baseline: str) -> ConstraintResult:
        if not baseline:
            return ConstraintResult(True, "growth_limit", "No baseline provided")
        growth = (len(text) - len(baseline)) / max(1, len(baseline))
        if growth <= self._config.max_growth_pct:
            return ConstraintResult(
                True,
                "growth_limit",
                f"Growth {growth:+.1%} within limit {self._config.max_growth_pct:+.1%}",
            )
        return ConstraintResult(
            False,
            "growth_limit",
            f"Growth {growth:+.1%} exceeds limit {self._config.max_growth_pct:+.1%}",
        )

    def _check_structure(self, text: str) -> ConstraintResult:
        """Structural integrity: check for minimum content sections."""
        # For JSON-like params, check key count
        import json

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                n_keys = len(parsed)
                if n_keys < self._config.min_sections:
                    return ConstraintResult(
                        False,
                        "structure",
                        f"Only {n_keys} keys, minimum {self._config.min_sections}",
                    )
                return ConstraintResult(True, "structure", f"{n_keys} keys OK")
        except (json.JSONDecodeError, TypeError):
            pass
        # For plain text, check line count as proxy
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) < self._config.min_sections:
            return ConstraintResult(
                False,
                "structure",
                f"Only {len(lines)} non-empty lines, minimum {self._config.min_sections}",
            )
        return ConstraintResult(True, "structure", f"{len(lines)} sections OK")
