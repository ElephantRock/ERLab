"""SoulLoader: Injects Elephant Rock's research philosophy into LLM prompts.

Reads SOUL.md from the project root and prepends it to system prompts,
ensuring all LLM-generated content aligns with the platform's research values.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SOUL_PATH = Path(__file__).resolve().parents[2] / "SOUL.md"
_SOUL_CACHE: str | None = None


def load_soul() -> str:
    """Load the SOUL.md content. Caches after first read."""
    global _SOUL_CACHE
    if _SOUL_CACHE is not None:
        return _SOUL_CACHE

    if _SOUL_PATH.exists():
        try:
            _SOUL_CACHE = _SOUL_PATH.read_text(encoding="utf-8")
            logger.debug("Loaded SOUL.md (%d chars)", len(_SOUL_CACHE))
            return _SOUL_CACHE
        except Exception as e:
            logger.warning("Failed to read SOUL.md: %s", e)
            return ""

    logger.debug("SOUL.md not found at %s", _SOUL_PATH)
    return ""


def inject_soul(system_prompt: str) -> str:
    """Inject SOUL.md philosophy into a system prompt.

    If SOUL.md exists, prepends it as a "Research Philosophy" section.
    If not found or empty, returns the original prompt unchanged (HB-03).
    """
    soul = load_soul()
    if not soul:
        return system_prompt

    return (
        f"# Research Philosophy\n\n"
        f"{soul}\n\n"
        f"---\n\n"
        f"{system_prompt}"
    )


def clear_cache() -> None:
    """Clear the cached SOUL.md content (for testing)."""
    global _SOUL_CACHE
    _SOUL_CACHE = None
