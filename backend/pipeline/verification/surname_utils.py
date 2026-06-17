"""Shared surname extraction for citation matching.

Used by both the proposal synthesizer sanitizer and the reference
verifier to extract author surnames from heterogeneous name formats.

Handles three common academic author name formats:
  - "Smith, John"        (comma-separated: surname first)
  - "John Smith"         (space-separated: given first)
  - Author Pydantic model (has .name attribute)
"""

from __future__ import annotations

import re
from typing import Any


def extract_surname(author: Any) -> str:
    """Extract a lowercase surname from an author name or object.

    Args:
        author: An Author model object (has ``.name``), a plain string,
            or any object with a ``name`` attribute.

    Returns:
        Lowercase surname, or empty string if unparseable.

    Examples:
        >>> extract_surname("Smith, John")
        'smith'
        >>> extract_surname("John Smith")
        'smith'
        >>> extract_surname("Liu Wei")
        'liu'
    """
    # Resolve to a name string
    name = ""
    if isinstance(author, str):
        name = author
    elif hasattr(author, "name"):
        name = getattr(author, "name", "") or ""
    else:
        name = str(author) if author else ""

    name = name.strip()
    if not name:
        return ""

    # Comma format: "Smith, John" → surname is before comma
    if "," in name:
        return name.split(",")[0].strip().lower()

    # Strip "et al." suffixes before processing
    name = re.sub(r"\s+et\.?\s*al\.?.*$", "", name, flags=re.IGNORECASE).strip()

    # Space format: "John Smith" → surname is last word
    # BUT for Chinese names (2 short words, no space in native form),
    # the first word is the family name.
    # Heuristic: if exactly 2 words and both ≤ 4 chars and no period,
    # treat first word as surname (Chinese/Korean/Vietnamese convention).
    words = name.split()
    if len(words) >= 2:
        # Chinese/Korean name heuristic: "Liu Wei", "Kim Jong"
        # Short given + short family with no middle name or period
        if len(words) == 2 and len(words[0]) <= 4 and len(words[1]) <= 4:
            # Both words are short — ambiguous. Use first as surname
            # because academic DBs (S2, OpenAlex) return Chinese names
            # in native order: "Liu Wei" means family=Liu, given=Wei
            return words[0].lower()
        return words[-1].lower()

    return name.lower()


def build_surname_set(authors_collection: list[Any]) -> set[str]:
    """Build a set of lowercase surnames from a collection of authors.

    Args:
        authors_collection: List of author name strings, Author objects,
            or mixed.

    Returns:
        Set of lowercase surnames.
    """
    surnames: set[str] = set()
    for author in authors_collection:
        surname = extract_surname(author)
        if surname:
            surnames.add(surname)
    return surnames
