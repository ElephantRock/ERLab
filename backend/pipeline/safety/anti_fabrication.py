"""Anti-fabrication guard: detects hallucinated content in proposals.

Checks for:
- Suspicious DOI patterns (e.g. 10.9999/fake)
- Unverifiable statistics ("99.7% improvement")
- Fabricated author names
- Generic claims with no evidence

Does NOT modify content — only annotates with warnings (HB-02).
Fail-open: never rejects everything (HB-01).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class WarningLevel(str, Enum):
    INFO = "info"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class FabricationWarning:
    """A single fabrication warning."""
    level: WarningLevel
    category: str
    message: str
    context: str = ""  # The text that triggered the warning


@dataclass
class GuardResult:
    """Result of anti-fabrication check."""
    warnings: list[FabricationWarning] = field(default_factory=list)
    confidence_score: float = 1.0  # 1.0 = fully confident, 0.0 = likely fabricated
    passed: bool = True

    @property
    def has_critical(self) -> bool:
        return any(w.level == WarningLevel.CRITICAL for w in self.warnings)


# Patterns that indicate potential fabrication
_SUSPICIOUS_DOI = re.compile(r"10\.\d{4,}/(?:fake|test|example|xxxx|0000)", re.IGNORECASE)
_UNSUPPORTED_STAT = re.compile(
    r"(?:improvement|increase|decrease|reduction|accuracy|performance)"
    r"\s+(?:of|by|to)\s+(\d{2,3}(?:\.\d+)?%)",
    re.IGNORECASE,
)
_GENERIC_CLAIM = re.compile(
    r"(?:our method|we propose|this approach|our framework)"
    r"\s+(?:outperforms|surpasses|exceeds|beats)",
    re.IGNORECASE,
)
_FABRICATED_AUTHOR = re.compile(
    r"(?:Dr\.|Prof\.)\s+(?:Test|Example|Fake|Sample)\s+\w+",
    re.IGNORECASE,
)
_UNVERIFIABLE_NUMBER = re.compile(
    r"(?:p\s*[<>=]\s*0\.\d+|n\s*=\s*\d{1,3}\b)",
    re.IGNORECASE,
)


class AntiFabricationGuard:
    """Checks proposals and ideas for fabricated content.

    This is a heuristic-based guard. It doesn't guarantee catching
    all fabrication, but it catches common patterns.

    Important: fail-open (HB-01), annotate-only (HB-02).
    """

    def __init__(self, known_dois: set[str] | None = None) -> None:
        self._known_dois = known_dois or set()

    def check_proposal(self, text: str) -> GuardResult:
        """Check a proposal text for fabrication patterns.

        Returns a GuardResult with warnings and confidence score.
        Does NOT modify the text (HB-02).
        """
        if not text:
            return GuardResult(confidence_score=1.0, passed=True)

        warnings: list[FabricationWarning] = []

        # Check suspicious DOIs
        warnings.extend(self._check_dois(text))

        # Check unsupported statistics
        warnings.extend(self._check_statistics(text))

        # Check generic claims
        warnings.extend(self._check_generic_claims(text))

        # Check fabricated authors
        warnings.extend(self._check_authors(text))

        # Check unverifiable p-values / sample sizes
        warnings.extend(self._check_unverifiable_numbers(text))

        # Compute confidence score
        confidence = self._compute_confidence(warnings, len(text))

        # Always pass (HB-01) — just warn
        return GuardResult(
            warnings=warnings,
            confidence_score=confidence,
            passed=True,
        )

    def _check_dois(self, text: str) -> list[FabricationWarning]:
        warnings = []
        for match in _SUSPICIOUS_DOI.finditer(text):
            warnings.append(FabricationWarning(
                level=WarningLevel.CRITICAL,
                category="suspicious_doi",
                message="DOI appears to be fabricated",
                context=match.group(0),
            ))
        return warnings

    def _check_statistics(self, text: str) -> list[FabricationWarning]:
        warnings = []
        for match in _UNSUPPORTED_STAT.finditer(text):
            stat = match.group(1)
            value = float(stat.replace("%", ""))
            if value >= 95:
                warnings.append(FabricationWarning(
                    level=WarningLevel.CAUTION,
                    category="unsupported_statistic",
                    message=f"Unusually high statistic claim: {stat}",
                    context=match.group(0),
                ))
        return warnings

    def _check_generic_claims(self, text: str) -> list[FabricationWarning]:
        warnings = []
        for match in _GENERIC_CLAIM.finditer(text):
            warnings.append(FabricationWarning(
                level=WarningLevel.INFO,
                category="generic_claim",
                message="Generic superiority claim without specific evidence",
                context=match.group(0),
            ))
        return warnings

    def _check_authors(self, text: str) -> list[FabricationWarning]:
        warnings = []
        for match in _FABRICATED_AUTHOR.finditer(text):
            warnings.append(FabricationWarning(
                level=WarningLevel.CRITICAL,
                category="fabricated_author",
                message="Author name appears to be fabricated",
                context=match.group(0),
            ))
        return warnings

    def _check_unverifiable_numbers(self, text: str) -> list[FabricationWarning]:
        warnings = []
        for match in _UNVERIFIABLE_NUMBER.finditer(text):
            warnings.append(FabricationWarning(
                level=WarningLevel.INFO,
                category="unverifiable_number",
                message="Statistical claim without context",
                context=match.group(0),
            ))
        return warnings

    @staticmethod
    def _compute_confidence(warnings: list[FabricationWarning], text_len: int) -> float:
        """Compute confidence score based on warnings.

        Starts at 1.0 and deducts for each warning.
        Critical warnings deduct more.
        """
        if not warnings:
            return 1.0

        deduction = 0.0
        for w in warnings:
            if w.level == WarningLevel.CRITICAL:
                deduction += 0.25
            elif w.level == WarningLevel.WARNING:
                deduction += 0.15
            elif w.level == WarningLevel.CAUTION:
                deduction += 0.10
            else:
                deduction += 0.05

        return max(0.1, 1.0 - deduction)
