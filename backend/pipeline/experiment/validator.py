"""Security validator for experiment code (BATCH-49)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Dangerous patterns that should be blocked
_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    ("import os", "Importing 'os' module is not allowed"),
    ("import socket", "Importing 'socket' module is not allowed"),
    ("import subprocess", "Importing 'subprocess' module is not allowed"),
    ("import sys", "Importing 'sys' module is not allowed (except sys.path access)"),
    ("eval(", "Use of eval() is not allowed"),
    ("exec(", "Use of exec() is not allowed"),
    ("__import__", "Use of __import__() is not allowed"),
    ("open(", "Use of open() is restricted (read-only not permitted in sandbox)"),
]


class SecurityValidator:
    """Validates experiment code for dangerous patterns.

    Uses simple string-based checking (no AST needed for MVP).
    """

    def __init__(self, blocked_patterns: list[tuple[str, str]] | None = None) -> None:
        self._patterns = blocked_patterns or _BLOCKED_PATTERNS

    def validate(self, code: str) -> list[str]:
        """Check code for dangerous patterns.

        Returns a list of violation descriptions. Empty list means code is safe.
        """
        violations: list[str] = []
        for pattern, description in self._patterns:
            if pattern in code:
                violations.append(description)
        return violations
