"""Pipeline utility helpers."""

from __future__ import annotations

import re


def safe_filename(name: str, max_length: int = 100) -> str:
    """Sanitize a string for use as a Windows filename component.

    Strips characters that are invalid in Windows file paths
    (colons, quotes, question marks, angle brackets, pipes, asterisks,
    forward/back slashes) and collapses consecutive underscores.

    Args:
        name: Raw string (e.g., a proposal title or domain name).
        max_length: Truncate to this many characters.

    Returns:
        A filesystem-safe string.
    """
    safe = re.sub(r'[<>:"/\\|?*\r\n\t]', '_', name)
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe[:max_length] or "untitled"
