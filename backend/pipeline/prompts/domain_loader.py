"""Domain-specific prompt loader.

Loads domain prompt templates from the prompts/domains/ directory.
Returns the appropriate prompt enhancement for a given domain.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DOMAINS_DIR = Path(__file__).parent / "domains"

# Domain keyword mapping
_DOMAIN_KEYWORDS = {
    "computer_science": ["cs", "nlp", "machine learning", "deep learning", "ai", "computer vision", "neural", "transformer", "llm", "language model"],
    "biology": ["bio", "biomedical", "medicine", "medical", "clinical", "genomics", "proteomics", "drug", "therapy", "disease", "cancer", "neuroscience"],
    "social_science": ["psychology", "sociology", "economics", "political", "social", "education", "anthropology", "demographics", "survey"],
}


def load_domain_prompt(domain: str) -> str:
    """Load a domain-specific prompt enhancement.

    Args:
        domain: Research domain string (e.g. "AI/NLP", "Biology/Genomics").

    Returns:
        Domain-specific prompt text, or empty string if no match.
    """
    domain_lower = domain.lower()

    # Find matching domain
    for domain_name, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in domain_lower for kw in keywords):
            prompt_path = _DOMAINS_DIR / f"{domain_name}.md"
            if prompt_path.exists():
                try:
                    return prompt_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning("Failed to load domain prompt '%s': %s", domain_name, e)
            return ""

    return ""


def list_available_domains() -> list[str]:
    """List available domain prompt files."""
    if not _DOMAINS_DIR.exists():
        return []
    return [p.stem for p in _DOMAINS_DIR.glob("*.md")]
