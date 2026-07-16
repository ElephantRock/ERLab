"""Shared exact-deduplication and accounting reconciliation for source results.

P0.2.4: Every adapter calls ``reconcile_source_results`` after parsing to
produce source-unique results and a validated ``SourceResultAccounting``.

The identity hierarchy for exact deduplication:
    1. normalized DOI (lowercase, trimmed, prefix-stripped)
    2. canonical source record identifier (paper.id)
    3. normalized title hash (NFKC + casefold + whitespace-collapse + sha256)

No fuzzy matching occurs here. Cross-source and cross-query deduplication
are later pipeline transitions with separate accounting.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from backend.pipeline.literature.contracts import (
    SourceResultAccounting,
    SearchResult,
    validate_accounting,
)

# ── Identity normalization ───────────────────────────────────────────

_DOI_PREFIX = re.compile(r"^https?://doi\.org/", re.IGNORECASE)
_DOI_SCHEME = re.compile(r"^doi:", re.IGNORECASE)
_MULTI_WS = re.compile(r"\s+")


def normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI: lowercase, trim, strip doi: and https://doi.org/ prefixes."""
    if not doi:
        return None
    d = doi.strip()
    d = _DOI_PREFIX.sub("", d)
    d = _DOI_SCHEME.sub("", d)
    d = d.strip().lower()
    return d or None


def normalize_source_id(source_id: str | None) -> str | None:
    """Canonicalize a source record identifier (paper.id).

    Source-aware: no unconditional lowercasing for unknown identifiers,
    but trims surrounding whitespace.
    """
    if not source_id:
        return None
    return source_id.strip() or None


def title_hash(title: str | None) -> str | None:
    """Produce a stable cryptographic hash of a normalized title.

    Normalization: NFKC + casefold + whitespace collapse.
    """
    if not title:
        return None
    normalized = unicodedata.normalize("NFKC", title)
    normalized = normalized.casefold()
    normalized = _MULTI_WS.sub(" ", normalized).strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _result_identity(result: SearchResult) -> str:
    """Determine the canonical exact-identity key for a SearchResult.

    Hierarchy: normalized DOI → canonical source ID → title hash.
    Falls back to a unique synthetic key (object id) if none available.
    """
    paper = result.paper
    # 1. DOI
    doi = normalize_doi(getattr(paper, "doi", None))
    if doi:
        return f"doi:{doi}"
    # 2. Source record ID
    sid = normalize_source_id(getattr(paper, "id", None))
    if sid:
        return f"sid:{sid}"
    # 3. Title hash
    th = title_hash(getattr(paper, "title", None))
    if th:
        return f"th:{th}"
    # No usable identity — treat as unique (won't deduplicate)
    return f"obj:{id(result)}"


# ── Reconciliation ───────────────────────────────────────────────────


def reconcile_source_results(
    *,
    raw_result_count: int,
    normalized_results: list[SearchResult],
    rejected_result_count: int,
) -> tuple[list[SearchResult], SourceResultAccounting]:
    """Exact-deduplicate normalized source results and reconcile counts.

    1. Validates inputs (raw = len(normalized) + rejected).
    2. Deduplicates by exact canonical identity.
    3. Preserves deterministic first-seen order.
    4. Returns source-unique results + validated SourceResultAccounting.

    Raises ``ValueError`` if the input equation is violated.
    """
    # Reject bool
    for name, val in [
        ("raw_result_count", raw_result_count),
        ("rejected_result_count", rejected_result_count),
    ]:
        if isinstance(val, bool) or not isinstance(val, int):
            raise ValueError(f"{name} must be int, not bool or {type(val).__name__}")
        if val < 0:
            raise ValueError(f"{name} must be >= 0, got {val}")

    # Verify input equation
    if raw_result_count != len(normalized_results) + rejected_result_count:
        raise ValueError(
            f"input equation violated: raw ({raw_result_count}) != "
            f"len(normalized) ({len(normalized_results)}) + "
            f"rejected ({rejected_result_count})"
        )

    # Exact deduplication, preserving first-seen order
    seen: dict[str, SearchResult] = {}
    for result in normalized_results:
        key = _result_identity(result)
        if key not in seen:
            seen[key] = result

    source_unique = list(seen.values())
    unique_count = len(source_unique)
    normalized_count = len(normalized_results)

    accounting = SourceResultAccounting(
        schema_version="accounting_v1",
        raw_result_count=raw_result_count,
        normalized_result_count=normalized_count,
        rejected_result_count=rejected_result_count,
        source_unique_count=unique_count,
    )

    # Validate the final accounting (cross-check len(results) == source_unique)
    validate_accounting(accounting, source_unique)

    return source_unique, accounting
