"""Context auto-compaction for pipeline stages.

Ported from huggingface/ml-intern context_manager/manager.py compaction logic.
Truncates oversized proposals and compacts stage context to prevent overflow.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maximum tokens for a single proposal before truncation
MAX_PROPOSAL_TOKENS = 50_000  # ~200K chars at 4 chars/token

# Section priority for compaction — preserve these in full
FULL_PRESERVE_SECTIONS = [
    "title", "abstract", "methodology", "evaluation_plan",
    "## methodology", "## evaluation", "## method",
]

# Sections to compress (summarize to key points)
COMPRESS_SECTIONS = [
    "related_work", "literature_review", "background",
    "## related work", "## literature", "## background",
]


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 4 chars per token."""
    return len(text) // 4


def compact_proposal(
    proposal: str | dict,
    max_tokens: int = 40_000,
) -> str | dict:
    """Compact a proposal that exceeds the token budget.

    Strategy:
    1. If under budget, return unchanged
    2. Compress low-priority sections (related work, background)
    3. Truncate any single section that exceeds per-section budget
    4. If still over budget, truncate from the end

    Returns the same type as input (str or dict).
    """
    if isinstance(proposal, dict):
        content = proposal.get("content", proposal.get("methodology", ""))
        was_dict = True
    else:
        content = str(proposal)
        was_dict = False

    tokens = estimate_tokens(content)
    if tokens <= max_tokens:
        return proposal  # Under budget, no compaction needed

    logger.info(
        "Compacting proposal: %d tokens -> budget %d",
        tokens, max_tokens,
    )

    # Try section-aware compaction
    compacted = _compact_sections(content, max_tokens)

    if estimate_tokens(compacted) > max_tokens:
        # Hard truncation from the end
        char_budget = max_tokens * 4
        compacted = compacted[:char_budget] + "\n\n[... truncated for compaction ...]"

    if was_dict and isinstance(proposal, dict):
        proposal["content"] = compacted
        return proposal
    return compacted


def _compact_sections(content: str, max_tokens: int) -> str:
    """Compress low-priority sections while preserving high-priority ones.

    Splits content on ## headers, processes each section, and reassembles.
    """
    sections = _split_sections(content)

    preserved_chars = 0
    compress_sections = []

    for header, body in sections:
        section_text = f"{header}\n{body}" if header else body
        is_preserve = any(p in header.lower() + body[:100].lower() for p in FULL_PRESERVE_SECTIONS)
        is_compress = any(c in header.lower() for c in COMPRESS_SECTIONS)

        if is_preserve or not is_compress:
            preserved_chars += len(section_text)
        else:
            compress_sections.append((header, body, len(section_text)))

    # Calculate how many chars we can afford for compressible sections
    preserved_tokens = preserved_chars // 4
    remaining_budget = max_tokens - preserved_tokens

    if remaining_budget <= 0:
        # Even preserved sections exceed budget — just truncate
        return content[:max_tokens * 4]

    # Reassemble: preserved sections + compressed versions
    result_parts = []
    compress_chars_used = 0

    for header, body in sections:
        section_text = f"{header}\n{body}" if header else body
        is_compress = any(c in header.lower() for c in COMPRESS_SECTIONS)

        if is_compress:
            # Compress to key points (first sentence per paragraph)
            compressed = _compress_to_key_points(body)
            compress_chars_used += len(compressed)
            if compress_chars_used // 4 <= remaining_budget:
                result_parts.append(f"{header}\n{compressed}" if header else compressed)
            else:
                # Budget exhausted — skip this section
                result_parts.append(f"{header}\n[... section compressed ...]")
        else:
            result_parts.append(section_text)

    return "\n\n".join(result_parts)


def _split_sections(content: str) -> list[tuple[str, str]]:
    """Split content into (header, body) tuples on ## markers."""
    sections = []
    current_header = ""
    current_body = []

    for line in content.split("\n"):
        if line.startswith("## ") or line.startswith("# "):
            if current_body or current_header:
                sections.append((current_header, "\n".join(current_body)))
            current_header = line
            current_body = []
        else:
            current_body.append(line)

    if current_body or current_header:
        sections.append((current_header, "\n".join(current_body)))

    return sections


def _compress_to_key_points(text: str) -> str:
    """Compress text to first sentence of each paragraph."""
    paragraphs = text.split("\n\n")
    compressed = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Take first sentence (up to first period + space or end of paragraph)
        sentences = para.split(". ")
        if sentences:
            compressed.append(sentences[0] + ("." if not sentences[0].endswith(".") else ""))
    return "\n\n".join(compressed)


def truncate_oversized(
    items: list[Any],
    max_chars: int = 200_000,
    label: str = "item",
) -> list[Any]:
    """Replace any item exceeding max_chars with a truncated version.

    Ported from ML Intern's _truncate_oversized pattern.
    """
    result = []
    for item in items:
        text = str(item) if not isinstance(item, dict) else json.dumps(item, sort_keys=True)
        if len(text) > max_chars:
            logger.warning(
                "Truncating %s: %d -> %d chars",
                label, len(text), max_chars,
            )
            truncated = text[:max_chars] + "\n[... truncated ...]"
            if isinstance(item, dict):
                item["content"] = truncated
                result.append(item)
            else:
                result.append(truncated)
        else:
            result.append(item)
    return result
